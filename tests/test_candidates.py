import ast
import json
import httpx
import pytest
from app.database import Task
from app.ollama import OllamaClient, OllamaError, parse_json
from app.schemas import CodeResult, RepairResult, SourceFile, SourceLines, Settings, PythonSource


BROKEN = ('import json\nimport os\nfrom collections import defaultdict\nfrom tempfile import TemporaryDirectory\n\n'
          'class Task:\n    def __init__(self, title, completed=False):\n        self.id = Task.generate_id()\n'
          '        self.title = title\n        self.completed = completed\n\n    @staticmethod\ndef generate_id():\n        return os.getpid()\n')
FIXED = BROKEN.replace('\ndef generate_id():','\n    def generate_id():')


def developer(system):
    service, worker, *_ = system
    p = service.create_project('Candidate regression')
    with service.sessions.begin() as s:
        task = Task(project_id=p.id,agent='developer',title='Build',description='Build Python app')
        s.add(task);s.flush()
    return task, service.project_workspace(p.id)


async def test_actual_line_13_error_repaired_without_writing_invalid_code(system):
    service, worker, http, runner = system
    task, ws = developer(system)
    calls=[]
    async def generate(role, system, prompt, schema):
        calls.append(schema)
        assert ws.files()==[]
        if schema == CodeResult:
            return CodeResult(summary='Candidate',files=[{'path':'tasks.py','content':BROKEN},{'path':'README.md','content':'Keep this sibling'}])
        assert schema == RepairResult
        assert '"line": 13' in prompt and 'unexpected unindent' in prompt and BROKEN in prompt
        return RepairResult(summary='Indent method',edits=[{'path':'tasks.py','old_text':'\ndef generate_id():','new_text':'\n    def generate_id():'}])
    worker.client.generate=generate
    await worker.tick()
    assert ws.read('tasks.py')==FIXED
    assert ws.read('README.md')=='Keep this sibling'
    assert len(calls)==2 and runner.calls==0
    with service.sessions() as s: assert s.get(Task,task.id).status=='COMPLETED'


async def test_bad_targeted_edit_falls_back_to_one_file_and_preserves_siblings(system):
    service, worker, *_ = system
    task, ws=developer(system)
    calls=[]
    async def generate(role, system, prompt, schema):
        calls.append(schema)
        assert ws.files()==[]
        if schema==CodeResult:
            return CodeResult(summary='Draft',files=[{'path':'tasks.py','content':BROKEN},{'path':'test_tasks.py','content':'def test_existing():\n    assert True\n'}])
        if schema==RepairResult:
            return RepairResult(summary='Invalid match',edits=[{'path':'tasks.py','old_text':'absent fragment','new_text':'fix'}])
        assert schema==PythonSource and 'dokładnie raz' in prompt
        return PythonSource(content=FIXED)
    worker.client.generate=generate
    await worker.tick()
    assert calls==[CodeResult,RepairResult,PythonSource]
    assert ws.read('tasks.py')==FIXED
    assert 'test_existing' in ws.read('test_tasks.py')


async def test_failed_corrections_are_bounded_across_retry_and_preserve_working_file(system):
    service, worker, http, runner=system
    task, ws=developer(system)
    ws.write('tasks.py',FIXED)
    with service.sessions.begin() as s: worker.own(s,task.project_id,ws.hashes(),ws.files())
    before=ws.hashes(); calls=[]
    async def generate(role, system, prompt, schema):
        calls.append(schema)
        assert ws.hashes()==before
        if schema==CodeResult: return CodeResult(summary='Broken proposal',files=[{'path':'tasks.py','content':BROKEN}])
        if schema==RepairResult: return RepairResult(summary='No change',edits=[{'path':'tasks.py','old_text':'def generate_id():','new_text':'def generate_id():'}])
        return PythonSource(content=BROKEN)
    worker.client.generate=generate
    await worker.tick()
    with service.sessions() as s:
        assert s.get(Task,task.id).status=='FAILED'
        assert 'Limit 3 korekt' in s.get(Task,task.id).error
    assert len(calls)==4
    service.action(task.id,'retry');await worker.tick()
    assert len(calls)==4 and ws.hashes()==before and runner.calls==0
    assert worker.checkpoints.get(task.id,'candidate_state')['corrections_used']==3


async def test_candidate_correction_cannot_override_concurrent_user_change(system):
    service, worker, *_=system
    task, ws=developer(system)
    async def generate(role, system, prompt, schema):
        if schema==CodeResult: return CodeResult(summary='Broken',files=[{'path':'tasks.py','content':BROKEN}])
        ws.write('user.txt','Keep user work')
        return RepairResult(summary='Fix',edits=[{'path':'tasks.py','old_text':'\ndef generate_id():','new_text':'\n    def generate_id():'}])
    worker.client.generate=generate
    await worker.tick()
    assert ws.files()==['user.txt']
    with service.sessions() as s: assert s.get(Task,task.id).status=='FAILED'


@pytest.mark.parametrize('source', [' x = 1\n', BROKEN, 'print("unterminated\n)', 'def x():\n\treturn 1\n    return 2\n',
    "print(f'{i + 1}: {task[\n", "print(f'{i + 1}: {task['task']})\n", "print(f'{i + 1}: {task['task']}'\n"])
def test_invalid_indentation_and_strings_never_become_valid_by_serialization(source):
    decoded=parse_json('```json\n'+json.dumps({'content':source})+'\n```')['content']
    assert decoded==source
    with pytest.raises(SyntaxError): ast.parse(decoded)


def test_parser_does_not_remove_markdown_or_thinking_tags_inside_code():
    content='text = "<think>keep this</think>"\nblock = "```python"\n'
    assert parse_json(json.dumps({'content':content}))['content']==content
    assert parse_json('<think>outer only</think>'+json.dumps({'content':content}))['content']==content


async def test_coder_line_transport_preserves_indentation_and_escapes():
    requests=[]
    lines=['class Example:', '    @staticmethod', '    def method():', '        return "a\\nb"']
    def handler(request):
        if request.url.path.endswith('tags'): return httpx.Response(200,json={'models':[{'name':'qwen2.5-coder:7b'}]})
        if request.url.path.endswith('show'): return httpx.Response(200,json={})
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'message':{'content':json.dumps({'path':'main.py','lines':lines})},'done_reason':'stop'})
    client=OllamaClient(Settings,httpx.MockTransport(handler))
    result=await client.generate('developer','system','repair',SourceFile)
    assert result.content=='\n'.join(lines)+'\n'
    ast.parse(result.content)
    assert 'lines' in requests[0]['format']['properties']
    await client.close()


async def test_single_file_fallback_has_no_json_constraint_and_preserves_code():
    requests=[]
    source='class Example:\n    def method(self):\n        return "``` <think>literal</think>"\n'
    def handler(request):
        if request.url.path.endswith('tags'): return httpx.Response(200,json={'models':[{'name':'qwen2.5-coder:7b'}]})
        if request.url.path.endswith('show'): return httpx.Response(200,json={})
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'message':{'content':'```python\n'+source+'```\n'},'done_reason':'stop'})
    client=OllamaClient(Settings,httpx.MockTransport(handler))
    result=await client.generate('developer','Repair one file','Fix syntax',PythonSource)
    assert result.content==source
    ast.parse(result.content)
    assert 'format' not in requests[0] and requests[0]['options']['temperature']==0
    assert 'Return only JSON' not in requests[0]['messages'][0]['content']
    await client.close()


@pytest.mark.parametrize('response', ['{"path":"x.py",', '{"path":"x.py","lines":["def f():\\n return 1"]}'])
async def test_corrupted_or_embedded_newline_response_is_rejected_with_bounded_retry(response):
    calls=[]
    def handler(request):
        if request.url.path.endswith('tags'): return httpx.Response(200,json={'models':[{'name':'qwen2.5-coder:7b'}]})
        if request.url.path.endswith('show'): return httpx.Response(200,json={})
        calls.append(request)
        return httpx.Response(200,json={'message':{'content':response},'done_reason':'stop'})
    client=OllamaClient(Settings,httpx.MockTransport(handler))
    with pytest.raises(OllamaError): await client.generate('developer','','',SourceFile)
    assert len(calls)==Settings().max_attempts
    await client.close()
