"""Deterministic evidence; never imports or executes generated project code."""
import ast
import hashlib
import json
import re

from .schemas import QAIssue


def check_python_source(content, filename):
    """Check parser and compiler constraints without importing or running source."""
    tree = ast.parse(content, filename=filename)
    # ast.parse alone accepts duplicate keywords and return/break outside a scope.
    compile(tree, filename, 'exec', dont_inherit=True)
    return tree


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
                              suggestion='Ustal przyczynę względem wymagań: błąd aplikacji czy testu. '
                                         'Zachowaj sprawdzaną funkcjonalność; uzasadnij zmianę błędnego oczekiwania testu.',
                              source='runner').model_dump())
    if not issues:
        issues.append(QAIssue(kind='test_execution', message=f"exit={evidence.get('exit_code')}, tests={evidence.get('test_count')}, reason={evidence.get('reason')}",
                              actual=output[-4000:] or 'Brak wyjścia runnera.', source='runner').model_dump())
    return deduplicate(issues)


def deduplicate(issues):
    return list({(i.get('file'), i.get('line'), i['message']): i for i in issues}.values())


def review_findings(review, files, tests):
    """Validate references, not model reasoning. Plausible claims remain hypotheses."""
    hypotheses, rejected = [], []
    if not review:
        return hypotheses, rejected
    # issues is the legacy summary of findings, not an independent second vote.
    candidates = [f.model_dump() for f in review.findings]
    if not candidates:
        candidates = [QAIssue(message=e).model_dump() for e in review.issues]
    if not candidates and not review.acceptable:
        candidates = [QAIssue(message=review.summary).model_dump()]
    for issue in deduplicate(candidates):
        issue['source'] = 'model'  # A model cannot promote itself to static/runner evidence.
        reason = None
        path, line = issue.get('file'), issue.get('line')
        if issue['expected'] and issue['expected'] == issue['actual']:
            reason = 'expected_equals_actual'
        elif tests is None and not path and 'latesttestresult' in issue['message'].lower():
            reason = 'tests_not_run_is_not_failure'
        elif files is not None and path and path not in files:
            reason = 'unknown_file'
        elif line is not None and (not path or (files is not None and line > len(files[path].splitlines()))):
            reason = 'invalid_line'
        if reason:
            rejected.append({**issue, 'reason': reason})
        else:
            hypotheses.append({**issue, 'reason': 'requires_verification'})
    return hypotheses, rejected


def repair_fingerprint(files, issues):
    # Documentation/whitespace churn must not restart an identical failing code cycle.
    evidence = sorted({json.dumps({k: i.get(k) for k in ('source', 'file', 'line', 'kind', 'message')},
                                  sort_keys=True) for i in issues})
    return hashlib.sha256(json.dumps([semantic_hash(files), evidence]).encode()).hexdigest()


def qa_report(static=None, review=None, tests=None, hashes=None, files=None):
    issues = []
    if static:
        issues += [QAIssue(kind='static_check', message=str(e), source='static').model_dump() for e in static['errors']]
    issues += test_issues(tests)
    hypotheses, rejected = review_findings(review, files, tests)
    state = 'not_run' if tests is None else 'passed' if tests.get('passed') else 'failed'
    return {'test_state': state, 'structure': static, 'model_review': review.model_dump() if review else None,
            'tests': tests, 'issues': deduplicate(issues), 'hypotheses': hypotheses,
            'rejected_findings': rejected, 'source_hashes': hashes or {},
            'outcome': 'changes_requested' if issues or state == 'failed'
            else 'review_required' if state == 'passed' and hypotheses
            else 'verified' if state == 'passed' else 'reviewed_only'}
