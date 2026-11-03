import json
from math import ceil
from sqlalchemy import select
from .database import ChatMessage, Project, Task, TaskCheckpoint
from .memory import MemoryService


class ContextBuilder:
    def __init__(self, service):
        self.service = service

    def build(self, task, include_files=True):
        ws = self.service.project_workspace(task.project_id)
        with self.service.sessions() as s:
            task = s.get(Task, task.id) or task
            project = s.get(Project, task.project_id)
            message = s.scalar(select(ChatMessage).where(ChatMessage.project_id == task.project_id,
                ChatMessage.role == 'user').order_by(ChatMessage.created_at.desc()).limit(1))
            previous = list(s.scalars(select(Task).where(Task.project_id == task.project_id,
                Task.created_at <= task.created_at).order_by(Task.created_at.desc()).limit(80)))
            # Walk only this task's dependency ancestry; do not mix another plan's verdicts.
            by_id = {t.id: t for t in previous}
            ancestors, pending, seen = [], list(task.dependencies), set()
            for _ in range(80):
                if not pending:
                    break
                key = pending.pop(0)
                if key in seen:
                    continue
                seen.add(key)
                item = by_id.get(key) or s.get(Task, key)
                if item and item.project_id == task.project_id:
                    ancestors.append(item); pending.extend(item.dependencies)
            qa = next((t for t in ancestors if t.agent == 'qa'), None)
            goal = task if task.agent == 'ceo' else next((t for t in ancestors if t.agent == 'ceo'), None)
            tested = next((t for t in [task, *ancestors] if t.result.get('tests')), None)
            latest = tested.result.get('tests') if tested else None
            report = qa.result.get('qa_report', {}) if qa else {}
            history = [{'task_id': t.id, 'iteration': t.iteration, 'status': t.status,
                        'changed_files': [f.get('path') for f in t.result.get('files', [])],
                        'no_progress': t.result.get('no_progress', False)}
                       for t in ancestors if t.agent == 'developer'][:5]
            memories = MemoryService(s).relevant(task.project_id, task.description)
            rejected = s.get(TaskCheckpoint, (task.id, 'rejected_proposal'))
        hashes = ws.hashes()
        cfg = self.service.settings()
        files = [{'path': path, 'sha256': hashes[path], 'content': ws.read(path)} for path in ws.files()] if include_files else []
        payload = {
            'ProjectGoal': goal.description if goal else message.content if message else project.description,
            'CurrentTask': {'id': task.id, 'title': task.title, 'description': task.description, 'iteration': task.iteration},
            'AcceptanceCriteria': qa.description if qa else task.description,
            'RelevantFiles': files,
            'LatestTestResult': None if not latest else {**latest, 'tested_hashes': tested.result.get('tested_hashes', {}),
                'applies_to_current_files': tested.result.get('tested_hashes') == hashes},
            # A developer needs the preceding review. A new QA review must not treat old
            # complaints (e.g. a formerly missing file) as current observed failures.
            'ErrorSummary': report.get('issues', qa.result.get('review', {}).get('issues', []) if qa else []) if task.agent=='developer' else [],
            'RequiredChanges': task.description,
            'PreviousAttempts': history,
            'RemainingRetries': {'task_attempts': max(0, cfg.max_attempts - task.attempts),
                                 'repair_iterations': max(0, cfg.max_iterations - task.iteration)},
            'RelevantMemory': memories,
            'RejectedProposal': rejected.payload if rejected else None,
        }
        # No silent truncation of errors, requirements or source. Optional memory can be omitted.
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        budget = max(1000, (cfg.context_size - 1800) * 3)
        if len(text.encode('utf-8')) > budget:
            payload['RelevantMemory'] = []
            text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        if len(text.encode('utf-8')) > budget:
            raise ValueError(f'Kontekst wymaga {len(text.encode("utf-8"))} bajtów, limit {budget}. Nie ucięto wymaganych plików/błędów; podziel zadanie.')
        return text, {'bytes': len(text.encode('utf-8')), 'estimated_tokens': ceil(len(text.encode('utf-8')) / 3),
                      'estimate_only': True, 'files': list(hashes), 'source_hashes': hashes,
                      'latest_test_state': 'not_run' if not latest else 'passed' if latest.get('passed') else 'failed'}
