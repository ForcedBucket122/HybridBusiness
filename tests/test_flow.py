import asyncio
import json
import zipfile
from sqlalchemy import select
import pytest

from app.database import Approval, Artifact, ChatMessage, Task, TaskRun, SystemSetting, now
from app.memory import MemoryService
from app.schemas import Decision
from app.scheduler import ScheduledWork


async def prepare(system):
    service, worker, http, runner = system
    project = service.create_project('Integration')
    task = service.enqueue(project.id,'Create Python app', 'integration-request')
    for _ in range(3):
        await worker.tick()
    with service.sessions() as s:
        approval = s.scalar(select(Approval).where(Approval.status=='PENDING'))
    assert approval is not None
    return project, task, approval


async def test_complete_flow_with_single_use_approval_and_zip(system):
    service, worker, http, runner = system
    project, task, approval = await prepare(system)
    assert runner.calls == 0
    ws=service.project_workspace(project.id)
    assert {'main.py','test_main.py','README.md'} == set(ws.files())
    with pytest.raises(ValueError,match='sandbox'):
        service.decision(approval.id,Decision(approve=True))
    service.decision(approval.id,Decision(approve=True,acknowledge_host_execution=True))
    with pytest.raises(ValueError):
        service.decision(approval.id,Decision(approve=True,acknowledge_host_execution=True))
    await worker.tick()
    await worker.tick()
    assert runner.calls == 1
    with service.sessions() as s:
        artifact=s.scalar(select(Artifact))
        assert artifact
        assert all(t.status=='COMPLETED' for t in s.scalars(select(Task)))
        assert len(list(s.scalars(select(ChatMessage)))) >= 5
        assert s.get(Approval,approval.id).status=='CONSUMED'
        archive=service.workspace/'artifacts'/artifact.path
        with zipfile.ZipFile(archive) as z:
            assert 'product/main.py' in z.namelist()
            assert json.loads(z.read('VERIFICATION.json'))['test_evidence'][0]['passed']
        assert http.get('/api/artifacts/'+artifact.id+'/download').status_code==200
    assert worker.client.calls == ['ceo','developer','qa','qa','release']


async def test_changed_files_invalidate_approval(system):
    service, worker, http, runner=system
    project, task, approval=await prepare(system)
    service.project_workspace(project.id).write('main.py','print("changed")')
    with pytest.raises(ValueError,match='zmieniły'):
        service.decision(approval.id,Decision(approve=True,acknowledge_host_execution=True))
    assert runner.calls==0


async def test_test_failure_creates_repair_chain(system):
    service, worker, http, runner=system
    project, task, approval=await prepare(system)
    runner.passed=False
    service.decision(approval.id,Decision(approve=True,acknowledge_host_execution=True))
    await worker.tick()
    with service.sessions() as s:
        dev=s.scalar(select(Task).where(Task.agent=='developer',Task.iteration==1))
        qa=s.scalar(select(Task).where(Task.agent=='qa',Task.iteration==1))
        release=s.scalar(select(Task).where(Task.agent=='release'))
        assert 'AssertionError' in dev.description
        assert qa.dependencies==[dev.id] and release.dependencies==[qa.id]
    runner.passed=True
    await worker.tick()
    await worker.tick()
    with service.sessions() as s:
        new=s.scalar(select(Approval).where(Approval.status=='PENDING'))
    assert new.id!=approval.id
    service.decision(new.id,Decision(approve=True,acknowledge_host_execution=True))
    await worker.tick()
    await worker.tick()
    with service.sessions() as s:
        assert s.scalar(select(Artifact)) is not None


async def test_repair_limit(system):
    service,worker,http,runner=system
    cfg=service.settings(); cfg.max_iterations=1; service.save_settings(cfg)
    worker.client.review_failures=10
    p=service.create_project('Repair limit'); service.enqueue(p.id,'Build','repair-limit-request')
    for _ in range(7): await worker.tick()
    with service.sessions() as s:
        assert len(list(s.scalars(select(Task).where(Task.agent=='developer'))))==2
        qa=s.scalar(select(Task).where(Task.agent=='qa',Task.iteration==1))
        assert qa.status=='FAILED'
        assert s.scalar(select(Artifact)) is None


async def test_cancel_cascades_and_no_runner(system):
    service,worker,http,runner=system
    project,task,approval=await prepare(system)
    service.action(approval.task_id,'cancel')
    await worker.tick()
    with service.sessions() as s:
        assert s.scalar(select(Task).where(Task.agent=='release')).status=='CANCELLED'
        assert s.get(Approval,approval.id).status=='REJECTED'
    assert runner.calls==0


async def test_manual_and_deduplication(system):
    service,worker,http,runner=system
    cfg=service.settings();cfg.mode='MANUAL';service.save_settings(cfg)
    p=service.create_project('Manual')
    task=service.enqueue(p.id,'Build','manual-dedup-request')
    assert service.enqueue(p.id,'Build','manual-dedup-request').id==task.id
    await worker.tick();await worker.tick()
    with service.sessions() as s:
        dev=s.scalar(select(Task).where(Task.agent=='developer'))
        assert dev.status=='PENDING'
    service.action(dev.id,'run');await worker.tick()
    with service.sessions() as s: assert s.get(Task,dev.id).status=='COMPLETED'


async def test_retry_limit_and_recovery(system):
    service,worker,http,runner=system
    worker.client.error=RuntimeError('offline')
    p=service.create_project('Retry');task=service.enqueue(p.id,'Build','retry-request')
    await worker.tick()
    service.action(task.id,'retry');await worker.tick()
    with pytest.raises(ValueError,match='limit'):
        service.action(task.id,'retry')
    with service.sessions.begin() as s:
        t=s.get(Task,task.id);t.status='RUNNING'
        s.add(TaskRun(task_id=task.id))
    service.recover()
    with service.sessions() as s:
        assert s.get(Task,task.id).status=='INTERRUPTED'
        assert all(r.status!='RUNNING' for r in s.scalars(select(TaskRun)))


async def test_parallel_ticks_only_claim_once(system):
    service,worker,http,runner=system
    p=service.create_project('Concurrency');service.enqueue(p.id,'Build','concurrent-request')
    await asyncio.gather(worker.tick(),worker.tick())
    assert worker.client.calls.count('ceo')==1


def test_api_security_and_persistence(system):
    service,worker,http,runner=system
    assert http.post('/api/projects',json={'name':'Bad'},headers={'X-LocalAI':'0'}).status_code==403
    assert http.post('/api/projects',json={'name':'Bad'},headers={'Origin':'https://evil.example'}).status_code==403
    assert http.get('/api/projects',headers={'Host':'evil.example'}).status_code==400
    p=http.post('/api/projects',json={'name':'API project'}).json()
    assert http.get('/api/projects/'+p['id']).status_code==200
    assert http.get('/api/projects/missing').status_code==404
    assert http.get('/api/projects/'+p['id']+'/files',params={'path':'../data/localai.db'}).status_code==409
    assert http.post('/api/projects/'+p['id']+'/chat',json={'content':'Build','request_id':'api-request-123'}).status_code==202
    with service.sessions() as s:
        assert s.scalar(select(ChatMessage)).content=='Build'


def test_memory_scoped_and_bounded(system):
    service,worker,http,runner=system
    a=service.create_project('A');b=service.create_project('B')
    with service.sessions.begin() as s:
        memory=MemoryService(s);memory.save(a.id,'alpha '+'a'*2000);memory.save(b.id,'beta')
        assert len(memory.search(a.id,'alpha'))==1
        assert memory.search(a.id,'beta')==[]
        assert len(memory.context(a.id,100))==100


def test_scheduler_default_disabled_and_persistent_limits(system):
    service,worker,http,runner=system
    scheduler=ScheduledWork(service);scheduler.tick()
    with service.sessions() as s: assert s.scalar(select(Task)) is None
    cfg=service.settings();cfg.scheduler_enabled=True;cfg.daily_limit=1;service.save_settings(cfg)
    scheduler.tick();scheduler.tick()
    with service.sessions() as s:
        assert len(list(s.scalars(select(Task))))==1
        assert s.get(SystemSetting,'scheduler_state').value['count']==1
