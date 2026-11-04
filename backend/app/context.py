import json
import ast
from copy import deepcopy
from math import ceil
from sqlalchemy import select
from .database import ChatMessage, Project, Task, TaskCheckpoint
from .memory import MemoryService


def select_context(payload, budget):
    """Fit whole evidence/source units; never slice requirements, code or tracebacks."""
    data = deepcopy(payload)
    notes = []
    compact = False
    original_bytes = len(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))

    def render():
        if notes:
            data['ContextSelection'] = {'notes': notes}
        return json.dumps(data, ensure_ascii=False, **(
            {'separators': (',', ':')} if compact else {'indent': 2}))

    # Legacy repair descriptions embed the same runner output already stored below.
    # Only replace an exact, substantial evidence block, including its old tail form.
    output = (data.get('LatestTestResult') or {}).get('output', '')
    duplicate = output[-10000:]
    if len(duplicate) >= 128:
        reference = '[Full runner output and tracebacks: LatestTestResult.output]'
        for owner, key, label in [(data.get('CurrentTask', {}), 'description', 'CurrentTask.description'),
                                  (data, 'RequiredChanges', 'RequiredChanges')]:
            if duplicate in owner.get(key, ''):
                owner[key] = owner[key].replace(duplicate, reference)
                notes.append(label + ': deduplicated exact runner output; retained in LatestTestResult.output')

    text = render()
    if len(text.encode('utf-8')) > budget:
        compact = True
        text = render()
    if len(text.encode('utf-8')) > budget:
        # User preferences/decisions remain protected; historical solutions are optional.
        memories = data.get('RelevantMemory', [])
        optional = [m for m in memories if m.get('kind') == 'solution']
        if optional:
            data['RelevantMemory'] = [m for m in memories if m.get('kind') != 'solution']
            notes.append('RelevantMemory: omitted historical solutions ' +
                         json.dumps([m.get('id') for m in optional]))
            text = render()
    if len(text.encode('utf-8')) > budget and data.get('PreviousAttempts'):
        # Keep IDs, status, iteration and no-progress signals; file names are secondary.
        for attempt in data['PreviousAttempts']:
            if 'changed_files' in attempt:
                attempt['changed_file_count'] = len(attempt.pop('changed_files'))
        notes.append('PreviousAttempts: retained outcomes; summarized changed-file lists as counts')
        text = render()
    if len(text.encode('utf-8')) > budget:
        # Full Python sources remain mandatory. Only unreferenced prose can be reduced.
        evidence = json.dumps([data.get('ProjectGoal'), data.get('ErrorSummary'), data.get('RejectedProposal'),
                               data.get('CurrentTask'), data.get('RequiredChanges'),
                               data.get('LatestTestResult'),
                               [f.get('content', '') for f in data.get('RelevantFiles', [])
                                if f['path'].endswith('.py')]], ensure_ascii=False).casefold()
        documents = sorted((f for f in data.get('RelevantFiles', [])
                            if f['path'].lower().endswith(('.md', '.rst'))
                            and f['path'].casefold() not in evidence),
                           key=lambda f: len(f.get('content', '').encode('utf-8')), reverse=True)
        for document in documents:
            content = document.pop('content', '')
            document['context_summary'] = {'kind': 'documentation', 'content_bytes': len(content.encode('utf-8')),
                                           'line_count': len(content.splitlines()), 'body_omitted': True}
            notes.append('RelevantFiles: documentation body omitted for ' + document['path'] + '; path/hash retained')
            text = render()
            if len(text.encode('utf-8')) <= budget:
                break
    if (len(text.encode('utf-8')) > budget and data.get('TaskAgent') == 'qa'
            and data.get('LatestTestResult')):
        # Once tests have run, the immutable source hashes and complete runner
        # output are stronger evidence than repeating entire test modules to QA.
        # Keep product Python and represent test modules by explicit method names.
        for source in data.get('RelevantFiles', []):
            name = source.get('path', '').rsplit('/', 1)[-1].lower()
            if not (name.startswith('test') and name.endswith('.py') or name == 'acceptance_cases.py'):
                continue
            content = source.get('content')
            if content is None:
                continue
            try:
                tree = ast.parse(content, filename=source['path'])
                methods = sorted({node.name for node in ast.walk(tree)
                                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                  and node.name.startswith('test_')})
            except (SyntaxError, ValueError):
                methods = []
            source.pop('content')
            source['context_summary'] = {
                'kind': 'executed_test_source',
                'content_bytes': len(content.encode('utf-8')),
                'test_methods': methods,
                'body_omitted': True,
            }
            notes.append('RelevantFiles: executed test source summarized; complete runner evidence and source hash retained for ' + source['path'])
            text = render()
            if len(text.encode('utf-8')) <= budget:
                break
    size = len(text.encode('utf-8'))
    if size > budget:
        sizes = {key: len(json.dumps(value, ensure_ascii=False).encode('utf-8')) for key, value in data.items()}
        raise ValueError(f'Kontekst wymaga {size} bajtów, limit {budget}. Zachowano wymagania, kod i dowody; '
                         'podziel zadanie. Rozmiary pól: ' + json.dumps(sizes, ensure_ascii=False))
    return text, {'original_bytes': original_bytes, 'bytes': size, 'budget_bytes': budget, 'reductions': notes}


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
        current_tests = latest is not None and tested.result.get('tested_hashes') == hashes
        test_state = ('not_run' if latest is None else 'stale' if not current_tests
                      else 'passed' if latest.get('passed') else 'failed')
        cfg = self.service.settings()
        files = [{'path': path, 'sha256': hashes[path], 'content': ws.read(path)} for path in ws.files()] if include_files else []
        payload = {
            'ProjectGoal': goal.description if goal else message.content if message else project.description,
            'CurrentTask': {'id': task.id, 'title': task.title, 'description': task.description, 'iteration': task.iteration},
            'TaskAgent': task.agent,
            'AcceptanceCriteria': qa.description if qa else task.description,
            'RelevantFiles': files,
            'TestExecution': {'state': test_state,
                'approval_required': not current_tests,
                'explanation': 'Only passed/failed applies to current files. not_run/stale is not a failure; '
                               'execution requires a separate user approval bound to current file hashes.'},
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
        budget = max(1000, (cfg.context_size - 1800) * 3)
        text, selection = select_context(payload, budget)
        return text, {'bytes': len(text.encode('utf-8')), 'estimated_tokens': ceil(len(text.encode('utf-8')) / 3),
                      'estimate_only': True, 'files': list(hashes), 'source_hashes': hashes,
                      'latest_test_state': test_state, 'selection': selection}
