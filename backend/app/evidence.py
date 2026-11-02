"""Deterministic evidence; never imports or executes generated project code."""
import ast
import hashlib
import json
import re

from .schemas import QAIssue


def semantic_hash(files):
    normalized = {}
    for name, content in sorted(files.items()):
        if not name.endswith('.py'):
            continue
        try:
            normalized[name] = ast.dump(ast.parse(content), include_attributes=False)
        except (SyntaxError, ValueError):
            normalized[name] = content
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


def test_names(content):
    tree = ast.parse(content)
    return {node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test')}


def test_issues(evidence):
    """Extract final traceback location and exact exception text; deduplicate repeated errors."""
    if not evidence or evidence.get('passed'):
        return []
    output = evidence.get('output', '')
    issues = []
    for block in re.split(r'\n={10,}\s*\n', output):
        frames = re.findall(r'File "([^"]+)", line (\d+)', block)
        exceptions = re.findall(r'^([A-Za-z_][\w.]*(?:Error|Exception|Interrupt)(?::[^\r\n]*)?)\r?$', block, re.M)
        if not frames or not exceptions:
            continue
        path, line = frames[-1]
        # Runner paths include workspace/runs/<approval-id>; retain relative nested path.
        portable = path.replace('\\', '/')
        match = re.search(r'/runs/[^/]+/(.+)$', portable)
        path = match.group(1) if match else portable.split('/')[-1]
        message = exceptions[-1]
        issues.append(QAIssue(file=path, line=int(line), kind=message.split(':')[0],
                              message=message, expected='Test zakończony bez błędu.', actual=message,
                              suggestion='Popraw wskazaną implementację i zachowaj test regresji.', source='runner').model_dump())
    if not issues:
        issues.append(QAIssue(kind='test_execution', message=f"exit={evidence.get('exit_code')}, tests={evidence.get('test_count')}, reason={evidence.get('reason')}",
                              actual=output[-4000:] or 'Brak wyjścia runnera.', source='runner').model_dump())
    return deduplicate(issues)


def deduplicate(issues):
    return list({(i.get('file'), i.get('line'), i['message']): i for i in issues}.values())


def qa_report(static=None, review=None, tests=None, hashes=None):
    issues = []
    if static:
        issues += [QAIssue(kind='static_check', message=str(e), source='static').model_dump() for e in static['errors']]
    issues += test_issues(tests)
    if review:
        issues += [{**f.model_dump(), 'source': 'model'} for f in review.findings]
        issues += [QAIssue(message=e, source='model').model_dump() for e in review.issues]
    state = 'not_run' if tests is None else 'passed' if tests.get('passed') else 'failed'
    return {'test_state': state, 'structure': static, 'model_review': review.model_dump() if review else None,
            'tests': tests, 'issues': deduplicate(issues), 'source_hashes': hashes or {},
            'outcome': 'changes_requested' if issues or (review and not review.acceptable) or state == 'failed'
            else 'verified' if state == 'passed' else 'reviewed_only'}
