import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select

from .database import (Agent, AgentMessage, Approval, Artifact, ChatMessage, Event, Project, Task,
                       TaskRun, TaskCheckpoint, connect, serialize)
from .memory import MemoryService
from .ollama import OllamaClient, OllamaError
from .orchestrator import Orchestrator
from .scheduler import ScheduledWork
from .schemas import ChatInput, Decision, ProjectInput, Settings, MemoryInput
from .security import Workspace
from .service import Service

ROOT = Path(__file__).resolve().parents[2]


class InstanceLock:
    def __init__(self, path):
        self.path, self.file = path, None

    def acquire(self):
        self.file = self.path.open('a+b')
        self.file.seek(0)
        self.file.write(b'0')
        self.file.flush()
        self.file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError('Inny worker LocalAICompany używa tej bazy. Uruchom tylko jeden proces.')

    def release(self):
        if self.file:
            self.file.close()


def create_app(data_dir=None, workspace=None, start_worker=True, client_factory=None, runner=None):
    data_dir = Path(data_dir or os.getenv('LOCALAI_DATA_DIR', ROOT / 'data'))
    workspace = Path(workspace or os.getenv('LOCALAI_WORKSPACE', ROOT / 'workspace'))
    engine, sessions = connect(data_dir / 'localai.db')
    service = Service(sessions, workspace)
    client = client_factory(service.settings) if client_factory else OllamaClient(service.settings)
    worker = Orchestrator(service, client, runner)
    lock = InstanceLock(data_dir / 'worker.lock')

    @asynccontextmanager
    async def lifespan(app):
        scheduler = None
        if start_worker:
            lock.acquire()
            service.recover()
            scheduler = AsyncIOScheduler(timezone='Europe/Warsaw')
            scheduler.add_job(worker.tick, 'interval', seconds=1, max_instances=1, coalesce=True, id='queue')
            scheduler.add_job(ScheduledWork(service).tick, 'interval', seconds=60, max_instances=1, coalesce=True, id='proposals')
            scheduler.start()
        try:
            yield
        finally:
            worker.stopping = True
            worker.cancel_event.set()
            if scheduler:
                scheduler.shutdown(wait=False)
                await asyncio.sleep(0.1)
            await client.close()
            lock.release()
            engine.dispose()

    app = FastAPI(title='LocalAICompany', version='0.1.0', lifespan=lifespan)
    app.state.service, app.state.worker = service, worker
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]', 'testserver'])

    @app.middleware('http')
    async def local_security(request: Request, call_next):
        origin = request.headers.get('origin')
        allowed = {'http://127.0.0.1:8000', 'http://localhost:8000', 'http://127.0.0.1:5173', 'http://localhost:5173'}
        if origin and origin not in allowed:
            return JSONResponse({'detail': 'Niedozwolone źródło żądania.'}, status_code=403)
        if request.url.path.startswith('/api') and request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if request.headers.get('x-localai') != '1':
                return JSONResponse({'detail': 'Wymagany nagłówek X-LocalAI: 1.'}, status_code=403)
            try:
                if int(request.headers.get('content-length', '0')) > 100000:
                    return JSONResponse({'detail': 'Zbyt duże żądanie.'}, status_code=413)
            except ValueError:
                return JSONResponse({'detail': 'Niepoprawny rozmiar żądania.'}, status_code=400)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.exception_handler(PermissionError)
    async def permission_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=403)

    @app.exception_handler(LookupError)
    async def not_found(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=404)

    def require_project(s, project_id):
        project = s.get(Project, project_id)
        if project is None:
            raise HTTPException(404, 'Nie znaleziono projektu.')
        return project

    @app.get('/api/ready')
    def ready():
        return {'status': 'ok'}

    @app.get('/api/health')
    async def health():
        try:
            models = await client.models()
            missing = sorted(set(service.settings().models.values()) - set(models))
            ollama = {'online': True, 'models': models, 'missing': missing}
        except OllamaError as exc:
            ollama = {'online': False, 'models': [], 'missing': [], 'error': str(exc)}
        return {'status': 'ok', 'ollama': ollama, 'active_task': worker.active_id, 'worker_enabled': start_worker,
                'mode': service.settings().mode, 'execution_isolated': False}

    @app.get('/api/projects')
    def projects():
        with sessions() as s:
            return [serialize(p) for p in s.scalars(select(Project).order_by(Project.created_at.desc()))]

    @app.post('/api/projects', status_code=201)
    def create_project(body: ProjectInput):
        return serialize(service.create_project(body.name, body.description))

    @app.get('/api/projects/{project_id}')
    def project_detail(project_id: str):
        with sessions() as s:
            project = require_project(s, project_id)
            return {**serialize(project), 'files': service.project_workspace(project_id).files(),
                    'artifacts': [serialize(a) for a in s.scalars(select(Artifact).where(Artifact.project_id == project_id))]}

    @app.get('/api/projects/{project_id}/files')
    def read_file(project_id: str, path: str):
        with sessions() as s:
            require_project(s, project_id)
        ws = service.project_workspace(project_id)
        if not ws.path(path).is_file():
            raise HTTPException(404, 'Brak pliku.')
        return {'path': path, 'content': ws.read(path)}

    @app.get('/api/projects/{project_id}/chat')
    def chat(project_id: str):
        with sessions() as s:
            require_project(s, project_id)
            return [serialize(m) for m in s.scalars(select(ChatMessage).where(ChatMessage.project_id == project_id).order_by(ChatMessage.created_at))]

    @app.post('/api/projects/{project_id}/chat', status_code=202)
    def send_chat(project_id: str, body: ChatInput):
        return serialize(service.enqueue(project_id, body.content, body.request_id))

    @app.get('/api/tasks')
    def tasks(project_id: str | None = None):
        with sessions() as s:
            stmt = select(Task).order_by(Task.created_at.desc(), Task.id)
            if project_id:
                stmt = stmt.where(Task.project_id == project_id)
            return [serialize(t) for t in s.scalars(stmt.limit(500))]

    @app.get('/api/tasks/{task_id}/runs')
    def task_runs(task_id: str):
        with sessions() as s:
            return [serialize(r) for r in s.scalars(select(TaskRun).where(TaskRun.task_id == task_id).order_by(TaskRun.started_at))]

    @app.get('/api/tasks/{task_id}/checkpoints')
    def checkpoints(task_id: str):
        with sessions() as s:
            if not s.get(Task, task_id):
                raise HTTPException(404, 'Nie znaleziono zadania.')
            return [serialize(r) for r in s.scalars(select(TaskCheckpoint).where(
                TaskCheckpoint.task_id == task_id).order_by(TaskCheckpoint.updated_at))]

    @app.post('/api/tasks/{task_id}/{action}')
    def task_action(task_id: str, action: str):
        result = service.action(task_id, action)
        if action == 'cancel' and worker.active_id == task_id:
            worker.cancel_event.set()
        return serialize(result)

    @app.get('/api/agents')
    def agents():
        with sessions() as s:
            return [serialize(a) for a in s.scalars(select(Agent))]

    @app.get('/api/approvals')
    def approvals():
        with sessions() as s:
            return [serialize(a) for a in s.scalars(select(Approval).order_by(Approval.created_at.desc()).limit(100))]

    @app.post('/api/approvals/{approval_id}')
    def decide(approval_id: str, body: Decision):
        return serialize(service.decision(approval_id, body))

    @app.get('/api/settings')
    def settings():
        return service.settings()

    @app.put('/api/settings')
    def set_settings(body: Settings):
        service.save_settings(body)
        return body

    @app.get('/api/events')
    def events(project_id: str | None = None):
        with sessions() as s:
            stmt = select(Event).order_by(Event.id.desc())
            if project_id:
                stmt = stmt.where(Event.project_id == project_id)
            return [serialize(e) for e in s.scalars(stmt.limit(100))]

    @app.get('/api/events/stream')
    async def stream(request: Request):
        try:
            cursor = max(0, int(request.headers.get('last-event-id', '0')))
        except ValueError:
            cursor = 0

        async def generate():
            nonlocal cursor
            # Bounded connection; native EventSource reconnects with Last-Event-ID.
            for _ in range(1800):
                if await request.is_disconnected():
                    break
                with sessions() as s:
                    rows = list(s.scalars(select(Event).where(Event.id > cursor).order_by(Event.id).limit(100)))
                for row in rows:
                    cursor = row.id
                    yield f'id: {row.id}\ndata: {json.dumps(serialize(row), ensure_ascii=False)}\n\n'
                if not rows:
                    yield ': heartbeat\n\n'
                await asyncio.sleep(2)
        return StreamingResponse(generate(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @app.get('/api/projects/{project_id}/memory')
    def memory(project_id: str, query: str = ''):
        with sessions() as s:
            require_project(s, project_id)
            return [serialize(m) for m in MemoryService(s).search(project_id, query)]

    @app.post('/api/projects/{project_id}/memory', status_code=201)
    def remember(project_id: str, body: MemoryInput):
        with sessions.begin() as s:
            require_project(s, project_id)
            return {'id': MemoryService(s).remember(project_id, body.kind, body.content)}

    @app.get('/api/artifacts/{artifact_id}/download')
    def download(artifact_id: str):
        with sessions() as s:
            artifact = s.get(Artifact, artifact_id)
            if not artifact:
                raise HTTPException(404, 'Brak artefaktu.')
            path = Workspace(workspace / 'artifacts').path(artifact.path)
            if not path.is_file():
                raise HTTPException(404, 'Plik artefaktu nie istnieje.')
            return FileResponse(path, filename=artifact.name, media_type='application/zip')

    dist = ROOT / 'frontend' / 'dist'
    if dist.exists():
        app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
    return app


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logging.getLogger('apscheduler').setLevel(logging.ERROR)
