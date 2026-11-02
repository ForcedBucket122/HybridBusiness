import asyncio
import hashlib
import json
import shutil
import threading
import zipfile

from sqlalchemy import func, select

from .agents import AGENTS, COMMON
from .checkpoints import Checkpoints
from .context import ContextBuilder
from .evidence import qa_report
from .repairs import materialize, validate_batch
from .database import (AgentMessage, Approval, Artifact, ChatMessage, MemoryEntry, Project,
                       SystemSetting, Task, TaskRun, now, record, uid)
from .memory import MemoryService
from .runner import ApprovedHostRunner
from .schemas import CodeResult, RepairResult
from .security import Workspace
from .service import TERMINAL
from .service import ACTIVE
from .tools import ToolRegistry


class Orchestrator:
    def __init__(self, service, client, runner=None):
        self.service, self.client = service, client
        self.sessions = service.sessions
        self.runner = runner or ApprovedHostRunner()
        self.lock = asyncio.Lock()
        self.stopping = False
        self.cancel_event = threading.Event()
        self.active_id = None
        self.checkpoints = Checkpoints(self.sessions)

    def cancelled(self, task_id):
        if self.stopping or self.cancel_event.is_set():
            return True
        with self.sessions() as s:
            task = s.get(Task, task_id)
            return task is None or task.cancel_requested

    def claim(self):
        cfg = self.service.settings()
        with self.sessions.begin() as s:
            s.connection().exec_driver_sql('BEGIN IMMEDIATE')
            if s.scalar(select(Task).where(Task.status == 'RUNNING')):
                return None
            pending = list(s.scalars(select(Task).where(Task.status == 'PENDING').order_by(Task.priority.desc(), Task.created_at, Task.id)))
            for task in pending:
                dependencies = [s.get(Task, dep) for dep in task.dependencies]
                if any(dep is None or dep.status == 'CANCELLED' for dep in dependencies):
                    task.status, task.error, task.finished_at = 'CANCELLED', 'Zależność została anulowana.', now()
                    self.service.refresh_project(s, task.project_id)
                    record(s, 'dependency_cancelled', task.error, task.project_id, task.id)
                    continue
                # FAILED/INTERRUPTED dependencies remain blocked so an explicit retry can resume the plan.
                if any(dep.status != 'COMPLETED' and not (dep.status == 'REVIEWED' and task.agent == 'developer'
                       and task.iteration > 0 and dep.result.get('repair_scheduled')) for dep in dependencies):
                    continue
                if cfg.mode == 'MANUAL' and not task.manual_ready:
                    continue
                continuing = task.result.get('phase') in ('execute', 'write')
                if not continuing and task.attempts >= cfg.max_attempts:
                    task.status, task.error = 'FAILED', 'Wyczerpano limit prób.'
                    continue
                task.status, task.started_at, task.error = 'RUNNING', now(), None
                if not continuing:
                    task.attempts += 1
                run = TaskRun(task_id=task.id)
                s.add(run)
                record(s, 'task_started', f'{task.agent}: {task.title}', task.project_id, task.id)
                s.flush()
                return task.id, run.id
        return None

    async def tick(self):
        if self.stopping or self.lock.locked():
            return
        async with self.lock:
            claimed = self.claim()
            if claimed is None:
                return
            task_id, run_id = claimed
            self.active_id = task_id
            self.cancel_event.clear()
            if hasattr(self.client, 'metrics'):
                self.client.metrics = []
            try:
                cfg = self.service.settings()
                result = await asyncio.wait_for(self.execute(task_id), timeout=cfg.timeout * cfg.max_attempts + 150)
                with self.sessions.begin() as s:
                    task, run = s.get(Task, task_id), s.get(TaskRun, run_id)
                    if self.cancelled(task_id):
                        task.status = 'INTERRUPTED' if self.stopping else 'CANCELLED'
                    elif task.status == 'RUNNING':
                        task.status = 'REVIEWED' if result.get('repair_scheduled') else 'COMPLETED'
                        task.result = result
                        s.add(AgentMessage(project_id=task.project_id, task_id=task.id, sender=task.agent, content=result))
                        MemoryService(s).save(task.project_id, f'{task.agent}: ' + json.dumps(result, ensure_ascii=False)[:12000])
                        s.add(ChatMessage(project_id=task.project_id, role=task.agent,
                                          content=str(result.get('summary', result.get('body', 'Zakończono etap.')))[:6000]))
                    if task.status in TERMINAL:
                        task.finished_at = now()
                    run.status, run.finished_at, run.result = task.status, now(), result
                    record(s, 'task_status', f'{task.agent}: {task.status}', task.project_id, task.id)
                    self.service.refresh_project(s, task.project_id)
            except asyncio.CancelledError:
                self.cancel_event.set()
                self.fail(task_id, run_id, 'Zatrzymanie aplikacji.', 'INTERRUPTED')
                raise
            except Exception as exc:
                self.cancel_event.set()
                self.fail(task_id, run_id, f'{type(exc).__name__}: {str(exc)[:1500]}')
            finally:
                if getattr(self.client, 'metrics', None):
                    with self.sessions() as s:
                        completed_task = s.get(Task, task_id)
                    self.checkpoints.save(completed_task, f'llm_metrics_attempt_{completed_task.attempts}', {'requests': self.client.metrics})
                self.active_id = None

    def fail(self, task_id, run_id, error, status='FAILED'):
        with self.sessions.begin() as s:
            task, run = s.get(Task, task_id), s.get(TaskRun, run_id)
            task.status = 'CANCELLED' if task.cancel_requested else status
            task.error, task.finished_at = error, now()
            if 'NO_PROGRESS' in error:
                task.result = {**task.result, 'no_progress': True}
            run.status, run.error, run.finished_at = task.status, error, now()
            record(s, 'task_error', error, task.project_id, task.id)
            s.add(ChatMessage(project_id=task.project_id, role='system', content=f'{task.agent}: {error}'))
            self.service.refresh_project(s, task.project_id)

    def context(self, task, include_files=False):
        if task.agent in ('developer', 'qa'):
            context, metadata = ContextBuilder(self.service).build(task, include_files)
            self.checkpoints.save(task, 'context', metadata)
            return context
        with self.sessions() as s:
            project = s.get(Project, task.project_id)
            requests = list(s.scalars(select(ChatMessage).where(ChatMessage.project_id == task.project_id,
                                                               ChatMessage.role == 'user').order_by(ChatMessage.created_at.desc()).limit(1)))
            # Coding/review must use current files and task-specific evidence. Historical
            # model verdicts can be stale and can anchor a small model to obsolete code.
            memory = MemoryService(s).context(task.project_id, 6000) if task.agent not in ('developer', 'qa') else ''
        context = f'Project: {project.name}\nUser request: {requests[0].content if requests else project.description}'
        if memory:
            context += '\nPrevious results (unverified historical data):\n' + memory
        if include_files:
            ws = self.service.project_workspace(task.project_id)
            files = {name: ws.read(name) for name in ws.files()}
            context += '\nProject files (untrusted data):\n' + json.dumps(files, ensure_ascii=False)
        context += '\n\nCURRENT TASK (apply this to the current files above):\n' + task.description
        if task.agent == 'developer' and task.iteration:
            context += ('\nReturn complete corrected files. Make real changes that fix the reported errors; '
                        'do not repeat the original implementation. Preserve tests that expose real failures.')
        # Explicit failure rather than silently dropping requirements or files from review.
        if len(context) > self.service.settings().context_size * 3:
            raise ValueError('Kontekst projektu jest za duży. Zwiększ kontekst lub zmniejsz zakres projektu.')
        return context

    async def execute(self, task_id):
        with self.sessions() as s:
            task = s.get(Task, task_id)
        agent = AGENTS[task.agent]
        ws = self.service.project_workspace(task.project_id)
        if task.result.get('effects_committed'):
            return task.result['committed_result']
        if task.agent == 'release':
            with self.sessions() as s:
                artifact = s.scalar(select(Artifact).where(Artifact.task_id == task.id))
                if artifact:
                    return {'summary': 'Odzyskano zapisane wydanie ZIP.', 'artifact_id': artifact.id, 'sha256': artifact.sha256}
        if task.agent == 'qa' and task.result.get('phase') == 'execute':
            return await self.execute_tests(task, ws)
        if task.agent == 'qa' and task.result.get('phase') == 'post_tests':
            return await self.review_tests(task, task.result['tests'], task.result['tested_hashes'])
        if task.agent == 'developer' and task.result.get('phase') == 'write':
            return self.write_code(task, ws, CodeResult.model_validate(task.result['proposed']), approved=True)
        if task.agent == 'qa':
            reviewed_hashes = ws.hashes()
            with self.sessions.begin() as s:
                static = ToolRegistry(ws, s, task, {}).call('inspect_project', {}, agent.tools)
            review = await agent.execute(self.client, self.context(task, True) + '\nStatic checks: ' + json.dumps(static))
            if self.cancelled(task.id):
                return {'summary': 'Anulowano.'}
            if reviewed_hashes != ws.hashes():
                raise ValueError('Pliki zmieniły się podczas przeglądu QA. Nie utworzono zgody.')
            report = qa_report(static=static, review=review, hashes=ws.hashes())
            result = {'summary': review.summary, 'review': review.model_dump(), 'static': static, 'qa_report': report}
            self.checkpoints.save(task, 'qa_review', result)
            if report['outcome'] == 'changes_requested':
                return self.repair(task, result, [i['message'] for i in report['issues']] or [review.summary])
            with self.sessions.begin() as s:
                approval = Approval(project_id=task.project_id, task_id=task.id, kind='host_tests', details={
                    'hashes': ws.hashes(), 'command': self.runner.command, 'source_directory': str(ws.root),
                    'execution_directory': str(self.service.workspace / 'runs' / '<approval-id>'),
                    'warning': 'Testy wykonają niezaufany kod z pełnymi uprawnieniami użytkownika. To NIE jest sandbox. Zatwierdź tylko po przeglądzie plików.',
                    'timeout_seconds': 120,
                })
                s.add(approval)
                current = s.get(Task, task.id)
                current.status, current.result = 'WAITING_APPROVAL', result
                record(s, 'approval_required', 'QA zakończył analizę. Wymagana zgoda na wykonanie testów.', task.project_id, task.id)
            return result
        if task.agent == 'developer':
            proposal = self.checkpoints.get(task.id, 'proposal')
            if proposal:
                current = ws.hashes()
                # Recovery permits already-written proposed files, but never unrelated edits.
                target = {f['path']: hashlib.sha256(f['content'].encode()).hexdigest() for f in proposal['code']['files']}
                if any(current.get(p) not in ([proposal['source_hashes'].get(p)] + ([target[p]] if p in target else []))
                       for p in set(current) | set(proposal['source_hashes']) | set(target)):
                    raise ValueError('Pliki zmieniły się od checkpointu. Wymagany nowy przegląd zadania.')
                return self.write_code(task, ws, CodeResult.model_validate(proposal['code']), recovering=True)
            before = ws.hashes()
            context = self.context(task, True)
            if task.iteration:
                edits = await self.client.generate('developer', COMMON +
                    'Repair the current files using exact old_text/new_text replacements. old_text must occur exactly once. '
                    'To create a missing file only, use empty old_text and the full content as new_text. '
                    'Fix ErrorSummary and RequiredChanges. Preserve regression tests and working features. '
                    'Do not rewrite unrelated code. Never claim tests ran.', context, RepairResult)
                if before != ws.hashes():
                    raise ValueError('Pliki zmieniły się podczas generowania; nie zapisano poprawek.')
                result = materialize(ws, edits)
            else:
                result = await agent.execute(self.client, context)
            if self.cancelled(task.id):
                return {'summary': 'Anulowano.'}
            if before != ws.hashes():
                raise ValueError('Pliki zmieniły się podczas generowania; nie zapisano odpowiedzi.')
            try:
                validate_batch(ws, result, repair=bool(task.iteration))
            except (ValueError, SyntaxError) as exc:
                self.checkpoints.save(task, 'rejected_proposal', {'code': result.model_dump(), 'written': False,
                    'error': {'kind': type(exc).__name__, 'file': getattr(exc, 'filename', None),
                              'line': getattr(exc, 'lineno', None), 'message': str(exc)}, 'source_hashes': before})
                raise
            self.checkpoints.save(task, 'proposal', {'code': result.model_dump(), 'source_hashes': before})
            return self.write_code(task, ws, result)
        result = await agent.execute(self.client, self.context(task, task.agent in ('developer', 'release')))
        if self.cancelled(task.id):
            return {'summary': 'Anulowano.'}
        if task.agent == 'ceo':
            with self.sessions.begin() as s:
                active = s.scalar(select(func.count()).select_from(Task).where(Task.status.in_(ACTIVE)))
                added = len(result.steps) + sum(step.agent == 'developer' for step in result.steps) + 1
                if active + added - 1 > self.service.settings().max_active_tasks:
                    raise ValueError('Plan przekracza limit aktywnych zadań. Ponów po zakończeniu innych projektów.')
                previous = task.id
                # Coalesce consecutive development steps so code, tests and docs reach QA together.
                steps = []
                for step in result.steps:
                    item = step.model_dump()
                    if steps and item['agent'] == steps[-1]['agent'] == 'developer':
                        steps[-1]['description'] += '\n\n' + item['title'] + ': ' + item['description']
                        steps[-1]['acceptance'] += '\n' + item['acceptance']
                    else:
                        steps.append(item)
                for step in steps:
                    child = Task(id=uid(), project_id=task.project_id, agent=step['agent'], title=step['title'],
                                 description=step['description'] + '\nKryteria ukończenia: ' + step['acceptance'], dependencies=[previous])
                    s.add(child)
                    previous = child.id
                    if step['agent'] == 'developer':
                        qa = Task(id=uid(), project_id=task.project_id, agent='qa', title='Przegląd i testy',
                                  description=step['acceptance'], dependencies=[previous])
                        s.add(qa)
                        previous = qa.id
                s.add(Task(project_id=task.project_id, agent='release', title='Przygotuj wydanie ZIP',
                           description='Spakuj pliki i udokumentuj rzeczywiste wyniki weryfikacji.', dependencies=[previous]))
                record(s, 'plan', result.summary, task.project_id, task.id)
                s.get(Task, task.id).result = {'effects_committed': True, 'committed_result': result.model_dump()}
            return result.model_dump()
        if task.agent == 'developer':
            return self.write_code(task, ws, result)
        if task.agent == 'release':
            return self.release(task, ws, result)
        with self.sessions.begin() as s:
            # Reports are task-owned paths, separate from user source files.
            path = f'reports/{task.agent}-{task.id}.md'
            ws.write(path, f'# {result.title}\n\nStatus informacji: {result.evidence}. Brak researchu internetowego.\n\n{result.body}')
            self.own(s, task.project_id, ws.hashes(), [path])
            record(s, 'report', f'Zapisano {path}', task.project_id, task.id)
        return {**result.model_dump(), 'summary': result.title, 'file': path}

    def owned(self, s, project_id):
        item = s.get(SystemSetting, 'owned:' + project_id)
        return dict(item.value) if item else {}

    def own(self, s, project_id, hashes, paths):
        key = 'owned:' + project_id
        item = s.get(SystemSetting, key)
        value = dict(item.value) if item else {}
        value.update({p: hashes[p] for p in paths})
        if item:
            item.value = value
        else:
            s.add(SystemSetting(key=key, value=value))

    def write_code(self, task, ws, result, approved=False, recovering=False):
        # Validate the whole batch before any write. Reject case-insensitive collisions on Windows.
        paths = [f.path for f in result.files]
        if len({p.replace('\\', '/').casefold() for p in paths}) != len(paths):
            raise ValueError('Zduplikowane ścieżki plików.')
        for f in result.files:
            ws.path(f.path)
            if len(f.content.encode('utf-8')) > 100000:
                raise ValueError('Plik jest za duży.')
        diffs_all = validate_batch(ws, result, repair=bool(task.iteration) and not recovering and not approved)
        before = ws.hashes()
        with self.sessions.begin() as s:
            owned = self.owned(s, task.project_id)
            hashes = ws.hashes()
            if recovering:
                # Only content exactly matching the durable proposal is recoverable as our write.
                for f in result.files:
                    if hashes.get(f.path) == hashlib.sha256(f.content.encode()).hexdigest():
                        owned[f.path] = hashes[f.path]
            changes = [p for p in paths if p in hashes and hashes[p] != owned.get(p)]
            if changes and not approved:
                registry = ToolRegistry(ws, s, task, owned)
                diffs = {f.path: registry.call('compare_changes', f.model_dump(), AGENTS['developer'].tools)
                         for f in result.files if f.path in changes}
                s.add(Approval(project_id=task.project_id, task_id=task.id, kind='overwrite', details={
                    'hashes': hashes, 'files': changes, 'diffs': diffs,
                    'warning': 'Nadpisanie plików zmienionych przez użytkownika. Sprawdź proponowane różnice.'}))
                current = s.get(Task, task.id)
                current.status, current.result = 'WAITING_APPROVAL', {'proposed': result.model_dump()}
                return {'summary': 'Wymagana zgoda na nadpisanie plików użytkownika.'}
            if approved:
                approval = s.get(Approval, task.result['approval_id'])
                if approval.status != 'APPROVED' or approval.details['hashes'] != hashes:
                    raise ValueError('Zgoda na zapis wygasła.')
                approval.status = 'CONSUMED'
                owned.update(hashes)
            registry = ToolRegistry(ws, s, task, owned)
            written = [registry.call('write_file', f.model_dump(), AGENTS['developer'].tools) for f in result.files]
            self.own(s, task.project_id, ws.hashes(), paths)
            committed = {'summary': result.summary, 'files': written, 'changed_files': [p for p in paths if before.get(p) != ws.hashes().get(p)],
                         'diffs': diffs_all, 'source_hashes': ws.hashes(), 'verification': 'files_written_and_syntax_checked; tests_not_run'}
            s.get(Task, task.id).result = {'effects_committed': True, 'committed_result': committed}
        self.checkpoints.save(task, 'files_written', committed)
        return committed

    def repair(self, task, result, errors):
        self.checkpoints.save(task, 'qa_result', result)
        if task.iteration >= self.service.settings().max_iterations:
            with self.sessions.begin() as s:
                s.get(Task, task.id).result = result
            raise ValueError('Wyczerpano limit poprawek: ' + '\n'.join(errors)[:3000])
        with self.sessions.begin() as s:
            dev = Task(id=uid(), project_id=task.project_id, agent='developer', title=f'Poprawki {task.iteration + 1}',
                       description='Napraw konkretne problemy bez usuwania testów wykrywających błędy:\n' + '\n'.join(errors)[:12000],
                       dependencies=[task.id], iteration=task.iteration + 1)
            qa = Task(id=uid(), project_id=task.project_id, agent='qa', title=f'Weryfikacja poprawek {task.iteration + 1}',
                      description=task.description, dependencies=[dev.id], iteration=task.iteration + 1)
            for downstream in s.scalars(select(Task).where(Task.project_id == task.project_id, Task.status == 'PENDING')):
                if task.id in downstream.dependencies:
                    downstream.dependencies = [qa.id if dep == task.id else dep for dep in downstream.dependencies]
            s.add_all([dev, qa])
            record(s, 'repair', f'Przekazano błędy Developerowi, iteracja {task.iteration + 1}.', task.project_id, task.id)
            committed = {**result, 'summary': 'Wykryto problemy; utworzono zadanie poprawek.', 'repair_scheduled': True}
            s.get(Task, task.id).result = {'effects_committed': True, 'committed_result': committed}
        return committed

    async def execute_tests(self, task, ws):
        with self.sessions.begin() as s:
            approval = s.get(Approval, task.result['approval_id'])
            if approval is None or approval.status != 'APPROVED' or approval.kind != 'host_tests':
                raise ValueError('Brak jednorazowej zgody na wykonanie testów.')
            if ws.hashes() != approval.details['hashes']:
                approval.status = 'EXPIRED'
                raise ValueError('Pliki zmieniły się po zatwierdzeniu.')
            approved_hashes = approval.details['hashes']
            destination = self.service.workspace / 'runs' / approval.id
            destination.mkdir(exist_ok=False)
            snapshot = Workspace(destination)
            for name in ws.files():
                snapshot.write(name, ws.read(name))
            if snapshot.hashes() != approval.details['hashes']:
                raise ValueError('Migawka nie odpowiada zatwierdzonym plikom.')
            approval.status = 'EXECUTING'
            record(s, 'tests_started', 'Uruchomiono zatwierdzone testy na migawce, bez izolacji systemowej.', task.project_id, task.id)
        evidence = await self.runner.run(destination, lambda: self.cancelled(task.id))
        with self.sessions.begin() as s:
            s.get(Approval, task.result['approval_id']).status = 'CONSUMED'
            s.get(Task, task.id).result = {'phase': 'post_tests', 'tests': evidence, 'tested_hashes': approved_hashes}
            record(s, 'tests_finished', f"exit={evidence['exit_code']}, tests={evidence['test_count']}", task.project_id, task.id)
            MemoryService(s).remember(task.project_id, 'test_result', {'passed': evidence['passed'],
                'test_count': evidence['test_count'], 'hashes': approved_hashes}, task.id, verified=True)
        self.checkpoints.save(task, 'tests_executed', {'tests': evidence, 'tested_hashes': approved_hashes})
        if self.cancelled(task.id):
            return {'summary': 'Testy anulowane.', 'tests': evidence}
        return await self.review_tests(task, evidence, approved_hashes)

    async def review_tests(self, task, evidence, approved_hashes):
        if self.service.project_workspace(task.project_id).hashes() != approved_hashes:
            raise ValueError('Bieżące pliki nie odpowiadają wykonanym testom. Wynik testów zachowano; potrzebny nowy przegląd.')
        review = await AGENTS['qa'].execute(self.client, self.context(task, True))
        report = qa_report(review=review, tests=evidence, hashes=approved_hashes)
        result = {'summary': review.summary, 'tests': evidence, 'review': review.model_dump(),
                  'tested_hashes': approved_hashes, 'qa_report': report}
        if report['outcome'] == 'changes_requested':
            return self.repair(task, result, [evidence['output'][-10000:]] + [i['message'] for i in report['issues']])
        self.checkpoints.save(task, 'qa_result', result)
        with self.sessions.begin() as s:
            MemoryService(s).remember(task.project_id, 'solution', {'summary': review.summary,
                'tested_hashes': approved_hashes, 'test_count': evidence['test_count']}, task.id, verified=True)
        return result

    def release(self, task, ws, report):
        with self.sessions.begin() as s:
            # Every code release must be backed by a passing executed QA of exactly these files.
            tasks = list(s.scalars(select(Task).where(Task.project_id == task.project_id)))
            code = any(t.agent == 'developer' for t in tasks)
            qa = [t for t in tasks if t.agent == 'qa' and t.status == 'COMPLETED' and t.result.get('tests', {}).get('passed')]
            hashes = ws.hashes()
            # Reports written by non-coding agents do not change executable source.
            source_hashes = {k: v for k, v in hashes.items() if not k.startswith('reports/')}
            if code and not any({k: v for k, v in t.result.get('tested_hashes', {}).items() if not k.startswith('reports/')} == source_hashes for t in qa):
                raise ValueError('Brak zaliczonych testów odpowiadających bieżącym plikom. Wydanie zablokowane.')
            artifact_id = uid()
            target = self.service.workspace / 'artifacts' / (artifact_id + '.zip')
            manifest = {'project_id': task.project_id, 'hashes': hashes,
                        'test_evidence': [t.result['tests'] for t in qa], 'generated_at': now()}
            with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
                for name in ws.files():
                    archive.write(ws.path(name), 'product/' + name)
                archive.writestr('VERIFICATION.json', json.dumps(manifest, ensure_ascii=False, indent=2))
                archive.writestr('RELEASE.md', '# ' + report.title + '\n\n' + report.body)
                archive.writestr('CHANGELOG.md', '# Changelog\n\nPierwsze lokalne wydanie. Szczegóły i wyniki testów: VERIFICATION.json.\n')
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            artifact = Artifact(id=artifact_id, project_id=task.project_id, task_id=task.id,
                                name=f'LocalAICompany-{task.project_id[:8]}.zip', path=target.name, sha256=digest)
            s.add(artifact)
            record(s, 'artifact', f'ZIP zapisany: {artifact.name}', task.project_id, task.id)
        return {'summary': report.body, 'artifact_id': artifact_id, 'sha256': digest, 'files': list(hashes)}
