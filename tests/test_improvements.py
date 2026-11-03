import json
import pytest
from sqlalchemy import select
from app.checkpoints import Checkpoints
from app.context import ContextBuilder
from app.database import Task, TaskCheckpoint, Approval, Artifact
from app.evidence import qa_report, test_issues as extract_issues
from app.memory import MemoryService
from app.repairs import materialize, validate_batch
from app.schemas import CodeResult, RepairResult, Review, Decision
from app.orchestrator import Orchestrator
from test_flow import prepare


def test_targeted_edits_are_exact_and_preserve_unrelated_files(system):
    service, worker, *_ = system
    p = service.create_project('Edits'); ws = service.project_workspace(p.id)
    ws.write('main.py', 'value = 1\n'); ws.write('README.md', 'Keep this')
    edit = RepairResult(summary='Fix', edits=[{'path':'main.py','old_text':'value = 1','new_text':'value = 2'}])
    result = materialize(ws, edit)
    assert result.files[0].content == 'value = 2\n'
    assert ws.read('main.py') == 'value = 1\n'  # Preparation never writes.
    assert set(validate_batch(ws, result, repair=True)) == {'main.py'}
    ws.write('main.py', 'value = 1\nvalue = 1\n')
    with pytest.raises(ValueError, match='dokładnie raz'): materialize(ws, edit)
    assert ws.read('README.md') == 'Keep this'
    create = RepairResult(summary='Missing test', edits=[{'path':'test_new.py','old_text':'','new_text':'def test_new():\n    assert True\n'}])
    assert materialize(ws,create).files[0].path == 'test_new.py'
    with pytest.raises(ValueError,match='nie może nadpisać'):
        materialize(ws,RepairResult(summary='Bad',edits=[{'path':'main.py','old_text':'','new_text':'overwrite'}]))


def test_noop_syntax_and_removed_tests_block_entire_batch(system):
    service, *_ = system
    p = service.create_project('Guard'); ws = service.project_workspace(p.id)
    ws.write('test_main.py', 'def test_regression():\n    assert True\n')
    def code(text): return CodeResult(summary='Fix', files=[{'path':'test_main.py','content':text}])
    with pytest.raises(ValueError, match='NO_PROGRESS'):
        validate_batch(ws, code('# cosmetic\ndef test_regression():\n    assert True\n'), True)
    with pytest.raises(ValueError, match='usunięto testy'):
        validate_batch(ws, code('value = 1\n'), True)
    with pytest.raises(SyntaxError): validate_batch(ws, code('def broken('), True)
    assert 'test_regression' in ws.read('test_main.py')


def test_runner_traceback_has_real_file_line_and_not_model_success():
    evidence = {'passed':False,'exit_code':1,'test_count':1,'output':
        'Traceback (most recent call last):\n  File "A:\\x\\workspace\\runs\\abc\\task_manager.py", line 23, in add\n'
        '    tasks.append(task)\nAttributeError: dict has no append\n'}
    issue = extract_issues(evidence)[0]
    assert (issue['file'],issue['line'],issue['kind'],issue['source']) == ('task_manager.py',23,'AttributeError','runner')
    accepted = Review(summary='Looks good', acceptable=True, issues=[])
    assert qa_report(review=accepted, tests=evidence)['outcome'] == 'changes_requested'
    assert qa_report(review=accepted)['test_state'] == 'not_run'


async def test_repair_receives_latest_actual_tests_and_review_is_not_completed(system):
    service, worker, http, runner = system
    project, _, approval = await prepare(system)
    runner.passed = False
    service.decision(approval.id, Decision(approve=True, acknowledge_host_execution=True))
    await worker.tick()
    with service.sessions() as s:
        qa = s.get(Task, approval.task_id)
        assert qa.status == 'REVIEWED'
        dev = s.scalar(select(Task).where(Task.agent=='developer',Task.iteration==1))
    text, meta = ContextBuilder(service).build(dev)
    payload = json.loads(text)
    assert payload['LatestTestResult']['passed'] is False
    assert payload['LatestTestResult']['applies_to_current_files'] is True
    assert payload['ErrorSummary'][0]['source'] == 'runner'
    assert meta['latest_test_state'] == 'failed'
    assert 'AssertionError' in payload['RequiredChanges']
    assert http.get('/api/tasks/'+qa.id+'/checkpoints').json()
    await worker.tick()
    text, _ = ContextBuilder(service).build(dev)
    assert json.loads(text)['LatestTestResult']['applies_to_current_files'] is False
    assert runner.calls == 1  # New version never executes on the old approval.
    with service.sessions() as s:
        next_qa = s.scalar(select(Task).where(Task.agent=='qa',Task.iteration==1))
    qa_context, _ = ContextBuilder(service).build(next_qa)
    assert json.loads(qa_context)['ErrorSummary'] == []
    assert json.loads(qa_context)['LatestTestResult']['passed'] is False


async def test_semantic_noop_fails_without_new_qa_or_execution(system):
    service, worker, http, runner = system
    project, _, approval = await prepare(system)
    runner.passed = False
    service.decision(approval.id, Decision(approve=True, acknowledge_host_execution=True))
    await worker.tick()
    original = worker.client.generate
    async def unchanged(role, system, prompt, schema):
        if schema == RepairResult:
            return RepairResult(summary='No change', edits=[{'path':'main.py','old_text':'return a + b','new_text':'return a + b # fix'}])
        return await original(role, system, prompt, schema)
    worker.client.generate = unchanged
    await worker.tick(); await worker.tick()
    with service.sessions() as s:
        dev = s.scalar(select(Task).where(Task.agent=='developer',Task.iteration==1))
        assert dev.status == 'FAILED' and dev.result['no_progress']
        assert len(list(s.scalars(select(Task).where(Task.agent=='developer')))) == 2
        assert s.scalar(select(Artifact)) is None
    assert runner.calls == 1


async def test_checkpoint_recovers_partial_write_without_repeating_llm(system):
    service, worker, http, runner = system
    p = service.create_project('Restart'); ws = service.project_workspace(p.id)
    ws.write('main.py', 'value = 1\n')
    with service.sessions.begin() as s:
        task = Task(project_id=p.id, agent='developer', title='Build', description='Build', status='RUNNING', attempts=1)
        s.add(task); s.flush()
        worker.own(s, p.id, ws.hashes(), ['main.py'])
    proposed = CodeResult(summary='Recovered', files=[{'path':'main.py','content':'value = 2\n'}, {'path':'README.md','content':'Documentation'}])
    worker.checkpoints.save(task, 'proposal', {'code':proposed.model_dump(), 'source_hashes':ws.hashes()})
    ws.write('main.py','value = 2\n')  # Process died between two files and before DB commit.
    service.recover(); service.action(task.id,'retry')
    resumed = Orchestrator(service, worker.client, runner)
    await resumed.tick()
    assert worker.client.calls == []
    assert ws.read('README.md') == 'Documentation'
    with service.sessions() as s: assert s.get(Task,task.id).status == 'COMPLETED'
    assert Checkpoints(service.sessions).get(task.id,'files_written')['source_hashes'] == ws.hashes()


async def test_checkpoint_rejects_user_change(system):
    service, worker, http, runner = system
    p = service.create_project('Changed'); ws = service.project_workspace(p.id)
    ws.write('main.py','value = 1\n'); ws.write('README.md','Keep')
    with service.sessions.begin() as s:
        task = Task(project_id=p.id,agent='developer',title='Build',description='Build');s.add(task);s.flush()
    result = CodeResult(summary='Fix',files=[{'path':'main.py','content':'value = 2\n'}])
    worker.checkpoints.save(task,'proposal',{'code':result.model_dump(),'source_hashes':ws.hashes()})
    ws.write('README.md','User edit')
    await worker.tick()
    with service.sessions() as s: assert s.get(Task,task.id).status == 'FAILED'
    assert ws.read('main.py') == 'value = 1\n'
    assert not worker.client.calls


def test_memory_preferences_are_scoped_and_unverified_solutions_excluded(system):
    service, worker, http, runner = system
    p = service.create_project('Memory'); other = service.create_project('Other')
    assert http.post('/api/projects/'+p.id+'/memory',json={'kind':'preference','content':'Use unittest'}).status_code == 201
    with service.sessions.begin() as s:
        memory = MemoryService(s)
        memory.remember(p.id,'solution','Broken unittest solution',verified=False)
        memory.remember(other.id,'preference','Not this project')
        entries = memory.relevant(p.id,'unittest')
        assert len(entries)==1 and entries[0]['content']=='Use unittest'
    assert http.get('/api/ready').json() == {'status':'ok'}


def test_context_never_silently_truncates_required_files(system):
    service, worker, *_ = system
    p = service.create_project('Budget')
    ws = service.project_workspace(p.id); ws.write('large.py','#' + 'a'*30000)
    with service.sessions.begin() as s:
        t = Task(project_id=p.id,agent='developer',title='Build',description='Build');s.add(t);s.flush()
    with pytest.raises(ValueError,match='Kontekst wymaga'): worker.context(t,True)


async def test_invalid_proposal_is_preserved_and_available_on_retry(system):
    service, worker, http, runner = system
    p = service.create_project('Syntax')
    with service.sessions.begin() as s:
        task = Task(project_id=p.id,agent='developer',title='Build',description='Build');s.add(task);s.flush()
    original = worker.client.generate
    async def broken(role, system, prompt, schema):
        if schema != CodeResult:
            raise RuntimeError('offline during candidate correction')
        return CodeResult(summary='Broken',files=[{'path':'main.py','content':'def broken('}])
    worker.client.generate = broken
    await worker.tick()
    assert service.project_workspace(p.id).files() == []
    rejected = worker.checkpoints.get(task.id,'rejected_proposal')
    assert rejected['written'] is False and rejected['error']['line']==1
    service.action(task.id,'retry')
    async def corrected(role, system, prompt, schema):
        from app.schemas import PythonSource
        assert schema == PythonSource and 'SyntaxError' in prompt and 'def broken(' in prompt
        return PythonSource(content='def broken():\n    return 1\n')
    worker.client.generate = corrected
    await worker.tick()
    with service.sessions() as s: assert s.get(Task,task.id).status=='COMPLETED'
    assert runner.calls==0


async def test_file_change_during_qa_cannot_receive_approval(system):
    service, worker, http, runner = system
    p = service.create_project('Concurrent QA');service.enqueue(p.id,'Build app','qa-concurrent-request')
    await worker.tick();await worker.tick()
    original = worker.client.generate
    async def changed(role, system, prompt, schema):
        if schema == Review: service.project_workspace(p.id).write('main.py','value = 99\n')
        return await original(role,system,prompt,schema)
    worker.client.generate = changed
    await worker.tick()
    with service.sessions() as s:
        assert s.scalar(select(Approval)) is None
        assert s.scalar(select(Task).where(Task.agent=='qa')).status=='FAILED'
