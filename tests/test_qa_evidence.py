"""Regression fixtures are authored system tests; no live model code is executed."""
import json

import pytest
from sqlalchemy import select

from app.context import ContextBuilder
from app.database import Approval, Artifact, Task
from app.evidence import qa_report
from app.orchestrator import Orchestrator
from app.runner import ApprovedHostRunner
from app.schemas import CodeResult, Decision, RepairResult, Review
from test_flow import prepare


def review(**finding):
    return Review(summary='Needs checking', acceptable=False, issues=['Summary of the finding'],
                  findings=[{'file': 'main.py', 'line': 1, 'message': 'Possible bug',
                             'expected': '1', 'actual': '2', **finding}])


@pytest.mark.parametrize('finding,reason', [
    ({'expected': '0: Task 1 [Pending]', 'actual': '0: Task 1 [Pending]'}, 'expected_equals_actual'),
    ({'file': 'missing.py'}, 'unknown_file'),
    ({'file': '../main.py'}, 'unknown_file'),
    ({'line': 999}, 'invalid_line'),
    ({'file': None, 'line': 1}, 'invalid_line'),
    ({'file': None, 'line': None, 'message': 'LatestTestResult: null'}, 'tests_not_run_is_not_failure'),
])
def test_invalid_model_findings_never_schedule_repairs(finding, reason):
    report = qa_report(review=review(**finding), files={'main.py': 'value = 1\n'})
    assert report['outcome'] == 'reviewed_only'
    assert report['issues'] == report['hypotheses'] == []
    assert report['rejected_findings'][0]['reason'] == reason
    assert report['test_state'] == 'not_run'


def test_valid_location_does_not_verify_model_claim_or_forged_source():
    report = qa_report(review=review(source='runner'), files={'main.py': 'value = 1\n'})
    assert report['issues'] == []
    assert report['hypotheses'][0]['source'] == 'model'
    assert report['outcome'] == 'reviewed_only'
    report = qa_report(review=review(), tests={'passed': True}, files={'main.py': 'value = 1\n'})
    assert report['outcome'] == 'review_required'  # Passing tests cannot silently clear plausible concerns.


def test_whitespace_difference_is_not_treated_as_equality():
    report = qa_report(review=review(expected='x ', actual='x'), files={'main.py': 'value = 1\n'})
    assert len(report['hypotheses']) == 1
    assert not report['rejected_findings']


@pytest.mark.parametrize('issues', [[], ['Potential missing coverage']])
def test_bare_negative_verdict_is_only_a_hypothesis(issues):
    report = qa_report(review=Review(summary='Check this', acceptable=False, issues=issues))
    assert report['outcome'] == 'reviewed_only'
    assert report['issues'] == [] and report['hypotheses']


async def test_historical_false_reviews_reach_approval_without_repair(system):
    service, worker, _, runner = system
    # Reproduce the two historical claims without depending on ignored runtime logs.
    reviews = [
        review(file=None, line=None, message='Wynik testów nie został zwrócony (LatestTestResult: null)',
               expected='Obecny wynik testów powinien być zwrócony jako obiekt lub string', actual='null'),
        review(file='test_main.py', line=5, message='mock_print calls are not matching the expected output format',
               expected='0: Task 1 [Pending]\n1: Task 2 [Done]', actual='0: Task 1 [Pending]\n1: Task 2 [Done]'),
    ]
    original = worker.client.generate
    async def replay(role, system, prompt, schema):
        if schema == Review:
            return reviews.pop(0)
        return await original(role, system, prompt, schema)
    worker.client.generate = replay
    project, _, approval = await prepare(system)
    with service.sessions() as s:
        qa = s.get(Task, approval.task_id)
        assert qa.result['qa_report']['test_state'] == 'not_run'
        assert len(list(s.scalars(select(Task).where(Task.agent == 'developer')))) == 1
    payload = json.loads(ContextBuilder(service).build(qa)[0])
    assert payload['LatestTestResult'] is None
    assert payload['TestExecution']['state'] == 'not_run'
    assert payload['TestExecution']['approval_required']
    assert runner.calls == 0
    service.decision(approval.id, Decision(approve=True, acknowledge_host_execution=True))
    await worker.tick(); await worker.tick()
    with service.sessions() as s:
        assert s.scalar(select(Artifact)) is not None
        assert len(list(s.scalars(select(Task).where(Task.agent == 'developer')))) == 1
        assert s.get(Task, qa.id).result['qa_report']['rejected_findings']
    assert runner.calls == 1


async def test_unresolved_hypothesis_blocks_release_and_retries_without_reexecuting(system):
    service, worker, _, runner = system
    original = worker.client.generate
    async def uncertain(role, system, prompt, schema):
        if schema == Review:
            return review()
        return await original(role, system, prompt, schema)
    worker.client.generate = uncertain
    _, _, approval = await prepare(system)
    assert approval.details['qa_report']['hypotheses']
    service.decision(approval.id, Decision(approve=True, acknowledge_host_execution=True))
    await worker.tick()
    for attempt in range(2):
        with service.sessions() as s:
            qa = s.get(Task, approval.task_id)
            assert qa.status == 'FAILED' and 'QA_REVIEW_REQUIRED' in qa.error
            assert qa.result['tests']['passed']
            assert qa.result['qa_report']['hypotheses']
            assert s.scalar(select(Artifact)) is None
            assert len(list(s.scalars(select(Task).where(Task.agent == 'developer')))) == 1
        if attempt == 0:
            service.recover()
            service.action(qa.id, 'retry')
            await Orchestrator(service, worker.client, runner).tick()
    with pytest.raises(ValueError, match='limit'):
        service.action(qa.id, 'retry')
    assert runner.calls == 1


async def test_developer_can_dispute_without_changing_files_or_passing_qa(system):
    service, worker, _, runner = system
    project, _, approval = await prepare(system)
    runner.passed = False
    service.decision(approval.id, Decision(approve=True, acknowledge_host_execution=True))
    await worker.tick()
    before = service.project_workspace(project.id).hashes()
    original = worker.client.generate
    async def disputed(role, system, prompt, schema):
        if schema == RepairResult:
            return RepairResult(summary='The traceback does not identify a reproducible defect.',
                                disposition='unconfirmed', edits=[])
        return await original(role, system, prompt, schema)
    worker.client.generate = disputed
    await worker.tick(); await worker.tick()
    with service.sessions() as s:
        dev = s.scalar(select(Task).where(Task.agent == 'developer', Task.iteration == 1))
        assert dev.status == 'FAILED' and 'REPAIR_UNCONFIRMED' in dev.error
        assert not dev.result['repair_unconfirmed']['written']
        assert s.scalar(select(Artifact)) is None
    assert worker.checkpoints.get(dev.id, 'repair_unconfirmed')['source_hashes'] == before
    assert service.project_workspace(project.id).hashes() == before
    assert runner.calls == 1


async def test_identical_failure_with_documentation_churn_stops_after_restart(system):
    service, worker, _, runner = system
    _, _, approval = await prepare(system)
    runner.passed = False
    service.decision(approval.id, Decision(approve=True, acknowledge_host_execution=True))
    await worker.tick()
    original = worker.client.generate
    async def cosmetic(role, system, prompt, schema):
        if schema == RepairResult:
            return RepairResult(summary='Changed docs only', edits=[
                {'path': 'README.md', 'old_text': '# Run', 'new_text': '# Run the app'}])
        return await original(role, system, prompt, schema)
    worker.client.generate = cosmetic
    await worker.tick(); await worker.tick()
    with service.sessions() as s:
        second = s.scalar(select(Approval).where(Approval.status == 'PENDING'))
        next_qa = s.get(Task, second.task_id)
    context, meta = ContextBuilder(service).build(next_qa)
    assert meta['latest_test_state'] == 'stale'
    assert json.loads(context)['TestExecution']['approval_required']
    service.decision(second.id, Decision(approve=True, acknowledge_host_execution=True))
    resumed = Orchestrator(service, worker.client, runner)
    await resumed.tick()
    with service.sessions() as s:
        qa = s.get(Task, second.task_id)
        assert qa.status == 'FAILED' and 'NO_PROGRESS' in qa.error
        assert qa.result['no_progress'] and qa.result['repair_fingerprint']
        assert len(list(s.scalars(select(Task).where(Task.agent == 'developer')))) == 2
    assert runner.calls == 2


async def test_real_failure_repaired_reapproved_and_released_with_trusted_fixture(system):
    service, worker, _, _ = system
    worker.runner = ApprovedHostRunner()
    original = worker.client.generate
    async def broken_then_fixed(role, system, prompt, schema):
        if schema == RepairResult:
            return RepairResult(summary='Fix actual subtraction error', edits=[
                {'path': 'main.py', 'old_text': 'return a - b', 'new_text': 'return a + b'}])
        result = await original(role, system, prompt, schema)
        if schema == CodeResult:
            result.files[0].content = result.files[0].content.replace('a + b', 'a - b')
        return result
    worker.client.generate = broken_then_fixed
    _, _, approval = await prepare(system)
    service.decision(approval.id, Decision(approve=True, acknowledge_host_execution=True))
    await worker.tick()
    with service.sessions() as s:
        failed = s.get(Task, approval.task_id)
        assert not failed.result['tests']['passed']
        assert failed.result['tests']['test_count'] == 1
        assert failed.result['qa_report']['issues'][0]['source'] == 'runner'
    await worker.tick(); await worker.tick()
    with service.sessions() as s:
        second = s.scalar(select(Approval).where(Approval.status == 'PENDING'))
    assert second.details['hashes'] != approval.details['hashes']
    service.decision(second.id, Decision(approve=True, acknowledge_host_execution=True))
    await worker.tick(); await worker.tick()
    with service.sessions() as s:
        assert s.get(Task, second.task_id).result['tests']['passed']
        assert s.scalar(select(Artifact)) is not None


async def test_file_change_during_post_test_review_blocks_release(system):
    service, worker, _, _ = system
    project, _, approval = await prepare(system)
    original = worker.client.generate
    async def changed(role, system, prompt, schema):
        if schema == Review:
            service.project_workspace(project.id).write('main.py', 'value = 42\n')
        return await original(role, system, prompt, schema)
    worker.client.generate = changed
    service.decision(approval.id, Decision(approve=True, acknowledge_host_execution=True))
    await worker.tick(); await worker.tick()
    with service.sessions() as s:
        qa = s.get(Task, approval.task_id)
        assert qa.status == 'FAILED' and qa.result['phase'] == 'post_tests'
        assert s.scalar(select(Artifact)) is None
