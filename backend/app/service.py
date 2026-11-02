import json
from pathlib import Path

from sqlalchemy import func, select

from .agents import AGENTS
from .database import (Agent, Approval, ChatMessage, Project, SystemSetting, Task, TaskRun, now, record, uid)
from .schemas import Settings
from .security import Workspace

ACTIVE = ('PENDING', 'RUNNING', 'WAITING_APPROVAL', 'INTERRUPTED')
TERMINAL = ('COMPLETED', 'FAILED', 'CANCELLED')


class Service:
    def __init__(self, sessions, workspace: Path):
        self.sessions, self.workspace = sessions, workspace
        Workspace(workspace)
        (workspace / 'projects').mkdir(exist_ok=True)
        (workspace / 'artifacts').mkdir(exist_ok=True)
        (workspace / 'runs').mkdir(exist_ok=True)
        with sessions.begin() as s:
            cfg = s.get(SystemSetting, 'config')
            if cfg is None:
                s.add(SystemSetting(key='config', value=Settings().model_dump()))
            settings = Settings.model_validate(cfg.value) if cfg else Settings()
            for key, definition in AGENTS.items():
                existing = s.get(Agent, key)
                if existing is None:
                    s.add(Agent(id=key, name=definition.name, role=definition.role, model=settings.models[key],
                                system_prompt=definition.prompt, tools=list(definition.tools)))
                else:
                    existing.system_prompt, existing.tools = definition.prompt, list(definition.tools)
                    existing.model = settings.models[key]

    def settings(self):
        with self.sessions() as s:
            return Settings.model_validate(s.get(SystemSetting, 'config').value)

    def save_settings(self, cfg):
        with self.sessions.begin() as s:
            s.get(SystemSetting, 'config').value = cfg.model_dump()
            for role, model in cfg.models.items():
                s.get(Agent, role).model = model
            record(s, 'settings', 'Zaktualizowano konfigurację.')

    def project_workspace(self, project_id):
        if len(project_id) != 32 or any(c not in '0123456789abcdef' for c in project_id):
            raise ValueError('Niepoprawny identyfikator projektu.')
        return Workspace(self.workspace / 'projects' / project_id)

    def create_project(self, name, description=''):
        with self.sessions.begin() as s:
            project = Project(name=name, description=description)
            s.add(project)
            s.flush()
            self.project_workspace(project.id)
            record(s, 'project_created', f'Utworzono projekt: {name}', project.id)
            return project

    def enqueue(self, project_id, content, request_id):
        with self.sessions.begin() as s:
            s.connection().exec_driver_sql('BEGIN IMMEDIATE')
            previous = s.scalar(select(Task).where(Task.request_id == request_id))
            if previous:
                if previous.project_id != project_id or previous.description != content:
                    raise ValueError('request_id został użyty dla innego polecenia.')
                return previous
            project = s.get(Project, project_id)
            if not project:
                raise LookupError('Nie znaleziono projektu.')
            if s.scalar(select(func.count()).select_from(Task).where(Task.project_id == project_id, Task.status.in_(ACTIVE))):
                raise ValueError('Projekt ma aktywny plan. Zakończ lub anuluj jego zadania przed nowym poleceniem.')
            if s.scalar(select(func.count()).select_from(Task).where(Task.status.in_(ACTIVE))) >= self.settings().max_active_tasks:
                raise ValueError('Limit aktywnych zadań.')
            task = Task(project_id=project_id, agent='ceo', title='Zaplanuj: ' + content[:80],
                        description=content, request_id=request_id, manual_ready=True)
            s.add(task)
            s.add(ChatMessage(project_id=project_id, role='user', content=content))
            project.status = 'ACTIVE'
            record(s, 'queued', 'Polecenie zapisane w trwałej kolejce.', project_id)
            s.flush()
            return task

    def recover(self):
        with self.sessions.begin() as s:
            for task in s.scalars(select(Task).where(Task.status == 'RUNNING')):
                task.status = 'INTERRUPTED'
                task.error = 'Proces zakończył się podczas pracy. Wznów jawnie; testy wymagają nowej zgody.'
                if task.result.get('phase') == 'execute':
                    task.result = {}
                record(s, 'recovery', task.error, task.project_id, task.id)
                for a in s.scalars(select(Approval).where(Approval.task_id == task.id, Approval.status.in_(['APPROVED', 'EXECUTING']))):
                    a.status = 'EXPIRED'
            for run in s.scalars(select(TaskRun).where(TaskRun.status == 'RUNNING')):
                run.status, run.finished_at = 'INTERRUPTED', now()
            for project in s.scalars(select(Project)):
                self.refresh_project(s, project.id)

    def action(self, task_id, action):
        with self.sessions.begin() as s:
            task = s.get(Task, task_id)
            if not task:
                raise LookupError('Nie znaleziono zadania.')
            if action == 'cancel':
                if task.status in TERMINAL:
                    raise ValueError('Zadanie jest zakończone.')
                task.cancel_requested = True
                if task.status != 'RUNNING':
                    task.status, task.finished_at = 'CANCELLED', now()
                for a in s.scalars(select(Approval).where(Approval.task_id == task.id, Approval.status == 'PENDING')):
                    a.status, a.decided_at = 'REJECTED', now()
            elif action == 'retry':
                if task.status not in ('FAILED', 'INTERRUPTED'):
                    raise ValueError('Można ponawiać tylko błędy lub przerwane zadania.')
                if task.attempts >= self.settings().max_attempts:
                    raise ValueError('Wyczerpano limit prób zadania.')
                task.status, task.error, task.finished_at = 'PENDING', None, None
                task.cancel_requested, task.manual_ready = False, True
                if task.agent == 'qa' and task.result.get('phase') != 'post_tests' and not task.result.get('effects_committed'):
                    task.result = {}
            elif action == 'run':
                if task.status != 'PENDING':
                    raise ValueError('Zadanie nie oczekuje w kolejce.')
                task.manual_ready = True
            else:
                raise ValueError('Nieznana operacja.')
            record(s, action, f'{action}: {task.title}', task.project_id, task.id)
            self.refresh_project(s, task.project_id)
            return task

    def decision(self, approval_id, decision):
        with self.sessions.begin() as s:
            s.connection().exec_driver_sql('BEGIN IMMEDIATE')
            approval = s.get(Approval, approval_id)
            if not approval:
                raise LookupError('Nie znaleziono zgody.')
            task = s.get(Task, approval.task_id)
            if approval.status != 'PENDING' or task.status != 'WAITING_APPROVAL':
                raise ValueError('Zgoda została już wykorzystana lub zadanie zmieniło stan.')
            if decision.approve and approval.kind == 'host_tests' and not decision.acknowledge_host_execution:
                raise ValueError('Potwierdź pełne uprawnienia procesu na komputerze; to nie jest sandbox.')
            if decision.approve:
                ws = self.project_workspace(task.project_id)
                if ws.hashes() != approval.details['hashes']:
                    raise ValueError('Pliki zmieniły się od przygotowania zgody. Odrzuć zgodę i przygotuj nowe zadanie.')
                approval.status = 'APPROVED'
                task.result = {**task.result, 'phase': 'execute' if approval.kind == 'host_tests' else 'write', 'approval_id': approval.id}
                task.status, task.manual_ready = 'PENDING', True
            else:
                approval.status = 'REJECTED'
                task.status, task.finished_at = 'CANCELLED', now()
            approval.decided_at = now()
            record(s, 'approval_decision', f'{approval.kind}: {approval.status}', task.project_id, task.id)
            self.refresh_project(s, task.project_id)
            return approval

    @staticmethod
    def refresh_project(s, project_id):
        s.flush()
        tasks = list(s.scalars(select(Task).where(Task.project_id == project_id)))
        states = {t.status for t in tasks}
        project = s.get(Project, project_id)
        if 'RUNNING' in states:
            project.status = 'ACTIVE'
        elif 'WAITING_APPROVAL' in states:
            project.status = 'WAITING_APPROVAL'
        elif 'INTERRUPTED' in states:
            project.status = 'INTERRUPTED'
        elif 'FAILED' in states:
            project.status = 'FAILED'
        elif 'PENDING' in states:
            project.status = 'ACTIVE'
        elif 'CANCELLED' in states:
            project.status = 'CANCELLED'
        else:
            project.status = 'COMPLETED' if tasks else 'IDLE'
