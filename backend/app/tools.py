import ast
import difflib
from dataclasses import dataclass

from .database import record
from .evidence import check_python_source
from .schemas import FileArgs, QueryArgs


@dataclass
class Tool:
    name: str
    description: str
    schema: type
    permission: str
    implementation: object


class ToolRegistry:
    def __init__(self, workspace, session, task, owned, requirements=None):
        self.workspace, self.session, self.task, self.owned = workspace, session, task, owned
        self.calls = 0
        self.requirements = task.description if requirements is None else requirements
        self.registry = {
            'list_files': Tool('list_files', 'List project files', QueryArgs, 'read', lambda a: workspace.files()),
            'read_file': Tool('read_file', 'Read UTF-8 file', FileArgs, 'read', lambda a: workspace.read(a.path)),
            'write_file': Tool('write_file', 'Write generated file', FileArgs, 'write', self.write),
            'create_directory': Tool('create_directory', 'Create project directory', FileArgs, 'write', self.mkdir),
            'inspect_project': Tool('inspect_project', 'Parse Python syntax without executing code', QueryArgs, 'read', lambda a: self.inspect()),
            'search_in_files': Tool('search_in_files', 'Search literal text', QueryArgs, 'read', self.search),
            'compare_changes': Tool('compare_changes', 'Preview file differences', FileArgs, 'read', self.diff),
        }

    def call(self, name, params, allowed):
        self.calls += 1
        try:
            if self.calls > 60:
                raise ValueError('Limit 60 operacji narzędzi na etap.')
            if name not in allowed or name not in self.registry:
                raise PermissionError('Narzędzie niedozwolone dla agenta.')
            tool = self.registry[name]
            result = tool.implementation(tool.schema.model_validate(params))
            record(self.session, 'tool', f'{name}: OK', self.task.project_id, self.task.id)
            return result
        except Exception as exc:
            record(self.session, 'tool_error', f'{name}: {type(exc).__name__}', self.task.project_id, self.task.id)
            raise

    def write(self, args):
        target = self.workspace.path(args.path)
        if target.exists() and self.workspace.hashes().get(args.path) != self.owned.get(args.path):
            raise PermissionError('Plik zmieniony przez użytkownika wymaga osobnego zatwierdzenia.')
        return self.workspace.write(args.path, args.content)

    def mkdir(self, args):
        self.workspace.path(args.path).mkdir(parents=True, exist_ok=True)
        return {'path': args.path}

    def search(self, args):
        matches = []
        for path in self.workspace.files():
            try:
                if args.query in self.workspace.read(path):
                    matches.append(path)
            except (UnicodeError, ValueError):
                continue
        return matches

    def diff(self, args):
        original = self.workspace.read(args.path) if self.workspace.path(args.path).exists() else ''
        return '\n'.join(difflib.unified_diff(original.splitlines(), args.content.splitlines(), fromfile=args.path, tofile=args.path))[:16000]

    def inspect(self):
        errors, files, tests, entrypoint = [], self.workspace.files(), [], False
        for path in files:
            if path.endswith('.py'):
                try:
                    tree = check_python_source(self.workspace.read(path), path)
                    if not path.split('/')[-1].startswith('test'):
                        entrypoint |= any(isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
                                          and node.left.id == '__name__' and any(isinstance(c, ast.Constant) and c.value == '__main__' for c in node.comparators)
                                          for node in ast.walk(tree))
                    if path.split('/')[-1].startswith('test'):
                        tests.extend(f'{path}:{node.name}' for node in ast.walk(tree)
                                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test'))
                except (SyntaxError, ValueError) as exc:
                    errors.append(f'{path}: {exc}')
        if not any(f.endswith('.py') and not f.split('/')[-1].startswith('test') for f in files):
            errors.append('Brak implementacji Python. MVP runner obsługuje Python unittest.')
        if not tests:
            errors.append('Brak testów unittest test_*.py.')
        if not any(f.lower() == 'readme.md' for f in files):
            errors.append('Brak README.md.')
        if any(word in self.requirements.lower() for word in ('konsol', 'console', 'command-line')) and not entrypoint:
            errors.append('Zlecono aplikację konsolową, ale brak punktu wejścia if __name__ == "__main__" w kodzie aplikacji.')
        return {'kind': 'static_only', 'errors': errors, 'test_functions': tests, 'files': files}
