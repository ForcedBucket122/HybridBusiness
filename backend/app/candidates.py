"""Bounded syntax repair of in-memory candidates; no generated code execution."""
import json

from .agents import COMMON
from .repairs import materialize, validate_batch
from .schemas import CodeResult, RepairResult, SourceFile, PythonSource


class CandidateFiles:
    """Read-only overlay: targeted edits refer to the rejected candidate, not live files."""
    def __init__(self, ws, code):
        self.ws = ws
        self.contents = {f.path: f.content for f in code.files}

    def path(self, name):
        return self.ws.path(name)

    def read(self, name):
        return self.contents[name] if name in self.contents else self.ws.read(name)

    def contains(self, name):
        return name in self.contents or self.ws.path(name).exists()


def syntax_detail(exc, code):
    file = next((f for f in code.files if f.path == exc.filename), None)
    return {'kind':type(exc).__name__, 'file':exc.filename, 'line':exc.lineno,
            'offset':exc.offset, 'message':exc.msg, 'text':exc.text,
            'content':file.content if file else None}


async def validate_candidate(worker, task, ws, code, source_hashes, context):
    state = worker.checkpoints.get(task.id, 'candidate_state') or {}
    used = state.get('corrections_used', 0)
    limit = min(3, worker.service.settings().max_iterations)
    last_failure = state.get('last_failure', '')
    while True:
        if worker.cancelled(task.id):
            raise ValueError('Anulowano naprawę kandydata.')
        if ws.hashes() != source_hashes:
            raise ValueError('Pliki zmieniły się podczas przygotowania kandydata. Nie zapisano zmian.')
        try:
            validate_batch(ws, code, repair=bool(task.iteration))
            worker.checkpoints.save(task, 'candidate_state', {'code':code.model_dump(),
                'source_hashes':source_hashes, 'corrections_used':used, 'valid':True})
            return code
        except SyntaxError as exc:
            error = syntax_detail(exc, code)
            worker.checkpoints.save(task, 'rejected_proposal', {'code':code.model_dump(), 'written':False,
                'error':error, 'source_hashes':source_hashes})
        if used >= limit:
            raise ValueError(f"Limit {limit} korekt składni kandydata: {error['kind']} w {error['file']}:{error['line']}: {error['message']}")
        target = error['file']
        if error['content'] is None:
            raise ValueError('Brak pliku kandydata dla zgłoszonego błędu.')
        # Reserve the request durably BEFORE inference. Restart/retry never resets this budget.
        used += 1
        mode = 'targeted' if used == 1 else 'single_file'
        state = {'code':code.model_dump(), 'source_hashes':source_hashes, 'corrections_used':used,
                 'valid':False, 'last_failure':last_failure}
        worker.checkpoints.save(task, 'candidate_state', state)
        worker.checkpoints.save(task, f'candidate_attempt_{used}', {'mode':mode, 'error':error, 'status':'requested'})
        task_context = json.loads(context)
        prompt = ('Repair the syntax of ONE candidate file. It has NOT been accepted or written.\n'
            'Project goal: '+str(task_context.get('ProjectGoal',''))+'\n'
            'CURRENT CANDIDATE '+target+':\n'+error['content']+'\nEND OF CANDIDATE.\n'
            'EXACT PYTHON DIAGNOSTIC: '+json.dumps({k:v for k,v in error.items() if k!='content'},ensure_ascii=False)+'\n'
            'Previous failed correction: '+last_failure+'\n'
            'Fix the diagnostic and any other Python syntax errors. Preserve functions, class methods, test names and behavior. '
            'Keep decorators and their methods at the same indentation. Use four spaces, never dedent a class method. '
            'Do not put literal newlines inside single-quoted strings: use separate print calls. '
            'Return a real correction, not the unchanged candidate.')
        try:
            if mode == 'targeted':
                response = await worker.client.generate('developer', COMMON +
                    'Return exact old_text/new_text edits only for '+target+'. Copy old_text including indentation exactly once.', prompt, RepairResult)
                if any(e.path != target for e in response.edits):
                    raise ValueError('Korekta składni może zmienić tylko wskazany plik.')
                replacement = materialize(CandidateFiles(ws, code), response).files[0]
            else:
                response = await worker.client.generate('developer', COMMON +
                    'Return the entire corrected single Python file. No JSON or Markdown fences.', prompt, PythonSource)
                # The engine owns the destination; free-form output cannot choose a path.
                replacement = SourceFile(path=target, content=response.content)
            if replacement.content == error['content']:
                raise ValueError('NO_PROGRESS: model powtórzył identycznego kandydata.')
            # Replace only the faulty file; successful siblings cannot be rewritten by this correction.
            code = CodeResult(summary=code.summary, files=[replacement if f.path==target else f for f in code.files])
            last_failure = ''
            worker.checkpoints.save(task, f'candidate_attempt_{used}', {'mode':mode, 'error':error,
                'status':'returned', 'response':response.model_dump()})
        except ValueError as exc:
            last_failure = str(exc)[:2000]
            worker.checkpoints.save(task, f'candidate_attempt_{used}', {'mode':mode, 'error':error,
                'status':'rejected', 'reason':last_failure})
        worker.checkpoints.save(task, 'candidate_state', {'code':code.model_dump(),
            'source_hashes':source_hashes, 'corrections_used':used, 'valid':False, 'last_failure':last_failure})
