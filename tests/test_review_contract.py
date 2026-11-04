"""Static inspection and repair instructions; no live model/product execution."""
import json

import pytest
from sqlalchemy import select

from app.database import Approval, Task
from app.schemas import CodeResult, Decision, Plan, RepairResult
from app.tools import ToolRegistry


@pytest.mark.parametrize('source, broken_test, expected', [
    ("if __name__ == '__main__':\n    print('x', file=None, file=None)\n", False, 'unknown'),
    ("if __name__ == '__main__':\n    print(\n", False, 'unknown'),
    ('value = 1\n', False, 'missing'),
    ('value = 1\n', True, 'missing'),
    ("if __name__ == '__main__':\n    print('x')\n", False, 'present'),
])
def test_cli_absence_requires_complete_implementation_inspection(system, source, broken_test, expected):
    service, _, _, runner = system
    project = service.create_project('CLI inspection')
    task = service.enqueue(project.id, 'Build a console app', 'cli-inspection-regression')
    ws = service.project_workspace(project.id)
    ws.write('main.py', source)
    ws.write('test_main.py', 'def test_existing():\n    pass\n' +
             ("print('x', end='', end='')\n" if broken_test else
              "if __name__ == '__main__':\n    pass\n"))
    ws.write('README.md', '# Run the application')
    with service.sessions() as s:
        report = ToolRegistry(ws, s, task, {}).inspect()
    assert report['cli_entrypoint'] == expected
    assert any('brak punktu wejścia' in error for error in report['errors']) == (expected == 'missing')
    if expected == 'unknown' or broken_test:
        assert any('main.py:' in error for error in report['errors'])
    if expected == 'present':
        assert report['errors'] == []
    assert ws.read('main.py') == source and runner.calls == 0


async def test_generation_and_repair_prioritize_user_over_generated_test_expectations(system):
    service, worker, _, runner = system
    goal = 'Build an app. Invalid input must produce a nonzero exit code; no exact code is required.'
    invented = 'Invalid input must return exactly exit code 1.'
    captured = {}
    original = worker.client.generate

    async def generate(role, system_prompt, prompt, schema):
        if schema == Plan:
            return Plan(summary='Plan', steps=[{'agent':'developer', 'title':'Build',
                                               'description':'Build add', 'acceptance':invented}])
        if schema in (CodeResult, RepairResult):
            captured[schema] = (system_prompt, json.loads(prompt))
        return await original(role, system_prompt, prompt, schema)

    worker.client.generate = generate
    project = service.create_project('Requirement precedence')
    service.enqueue(project.id, goal, 'requirements-priority-regression')
    for _ in range(3):
        await worker.tick()
    with service.sessions() as s:
        approval = s.scalar(select(Approval).where(Approval.project_id == project.id))
    assert approval is not None and runner.calls == 0
    runner.passed = False
    service.decision(approval.id, Decision(approve=True, acknowledge_host_execution=True))
    await worker.tick()
    await worker.tick()
    assert set(captured) == {CodeResult, RepairResult}
    for system_prompt, context in captured.values():
        assert context['ProjectGoal'] == goal
        assert invented in context['AcceptanceCriteria']
        assert ('ProjectGoal contains the original user requirements and takes precedence over conflicting '
                'agent-generated AcceptanceCriteria and generated test expectations.') in system_prompt
        assert 'justify the change against ProjectGoal' in system_prompt
        assert 'preserve coverage, test names and meaningful assertions' in system_prompt
    assert captured[RepairResult][1]['LatestTestResult']['passed'] is False
    assert captured[RepairResult][1]['ErrorSummary'][0]['source'] == 'runner'
    with service.sessions() as s:
        dev = s.scalar(select(Task).where(Task.project_id == project.id, Task.agent == 'developer', Task.iteration == 1))
        assert dev.status == 'COMPLETED'
    assert runner.calls == 1
