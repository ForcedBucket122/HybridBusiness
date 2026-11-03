"""Validate proposed edits without importing generated code."""
import ast
import difflib
from .evidence import semantic_hash, test_names
from .schemas import CodeResult


def materialize(ws, repair):
    contents = {}
    for edit in repair.edits:
        target = ws.path(edit.path)
        exists = ws.contains(edit.path) if hasattr(ws, 'contains') else target.exists()
        if not exists and edit.path not in contents:
            if edit.old_text:
                raise ValueError(f'{edit.path}: nowy plik wymaga pustego old_text.')
            contents[edit.path] = edit.new_text
            continue
        original = contents[edit.path] if edit.path in contents else ws.read(edit.path)
        if not edit.old_text:
            raise ValueError(f'{edit.path}: pusty old_text nie może nadpisać istniejącego pliku.')
        if original.count(edit.old_text) != 1:
            raise ValueError(f'{edit.path}: old_text musi pasować dokładnie raz; plik nie został zmieniony.')
        contents[edit.path] = original.replace(edit.old_text, edit.new_text, 1)
    return CodeResult(summary=repair.summary, files=[{'path': p, 'content': c} for p, c in contents.items()])


def validate_batch(ws, result, repair=False):
    paths = [f.path.replace('\\', '/') for f in result.files]
    if len({p.casefold() for p in paths}) != len(paths):
        raise ValueError('Zduplikowane ścieżki plików.')
    for f in result.files:
        target = ws.path(f.path)
        if target.is_dir() or len(f.content.encode('utf-8')) > 100000:
            raise ValueError('Niepoprawny plik lub przekroczony limit 100 KB.')
    before = {p: ws.read(p) for p in ws.files()}
    after = {**before, **{f.path: f.content for f in result.files}}
    if len(after) > 100 or sum(len(c.encode('utf-8')) for c in after.values()) > 2_000_000:
        raise ValueError('Przekroczono limit rozmiaru projektu.')
    for f in result.files:
        if f.path.endswith('.py'):
            ast.parse(f.content, filename=f.path)
            if f.path in before:
                try:
                    removed = test_names(before[f.path]) - test_names(f.content)
                except SyntaxError:
                    removed = set()
                if removed:
                    raise ValueError(f'{f.path}: usunięto testy regresji: {sorted(removed)}')
    non_python_changed = any(before.get(p) != c for p, c in after.items() if not p.endswith('.py'))
    if repair and semantic_hash(before) == semantic_hash(after) and not non_python_changed:
        raise ValueError('NO_PROGRESS: naprawa nie zmienia kodu ani dokumentacji. Przerwano bez kolejnej iteracji.')
    return {f.path: ''.join(difflib.unified_diff(before.get(f.path, '').splitlines(True),
              f.content.splitlines(True), fromfile=f.path, tofile=f.path)) for f in result.files}
