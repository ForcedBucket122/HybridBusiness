"""Saved context-overflow evidence is data only; never execute its project files."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.context import select_context
from app.database import Task
from app.ollama import OllamaClient


def saved_case():
    return json.loads((Path(__file__).parent / 'fixtures/expense_context_overflow.json').read_text(encoding='utf-8'))


def test_saved_22907_byte_context_fits_without_losing_required_evidence():
    case = saved_case()
    original = deepcopy(case['payload'])
    assert len(json.dumps(original, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) == 22907
    text, selection = select_context(original, case['budget_bytes'])
    packed = json.loads(text)
    assert selection['bytes'] == len(text.encode('utf-8')) <= 19176
    assert len(selection['reductions']) == 2
    assert original == case['payload']  # Persisted tasks/evidence are never rewritten.
    for key in ('ProjectGoal', 'AcceptanceCriteria', 'LatestTestResult', 'ErrorSummary',
                'RelevantFiles', 'RejectedProposal', 'RemainingRetries'):
        assert packed[key] == original[key]
    output = original['LatestTestResult']['output']
    assert output not in packed['CurrentTask']['description']
    assert output not in packed['RequiredChanges']
    assert 'LatestTestResult.output' in packed['RequiredChanges']
    assert output.count('Traceback (most recent call last)') == 4
    assert {i['line'] for i in packed['ErrorSummary']} == {15, 22, 31, 69}
    for f in packed['RelevantFiles']:
        assert hashlib.sha256(f['content'].encode('utf-8')).hexdigest() == f['sha256']


def test_secondary_data_is_summarized_with_explicit_provenance():
    payload = saved_case()['payload']
    payload['RelevantMemory'] = [
        {'id':'preference', 'kind':'preference', 'content':'Keep required validation'},
        {'id':'decision', 'kind':'decision', 'content':'No network calls'},
        {'id':'old-solution', 'kind':'solution', 'content':'Historical detail ' * 600},
    ]
    payload['RelevantFiles'].append({'path':'notes.md', 'sha256':'a'*64, 'content':'Secondary notes\n'*800})
    original = deepcopy(payload)
    text, selection = select_context(payload, 19176)
    packed = json.loads(text)
    assert packed['LatestTestResult'] == original['LatestTestResult']
    assert packed['ProjectGoal'] == original['ProjectGoal']
    assert [m['id'] for m in packed['RelevantMemory']] == ['preference', 'decision']
    notes = next(f for f in packed['RelevantFiles'] if f['path']=='notes.md')
    assert 'content' not in notes and notes['sha256']=='a'*64
    assert notes['context_summary']['body_omitted']
    assert notes['context_summary']['content_bytes'] == len(original['RelevantFiles'][-1]['content'].encode())
    assert any('old-solution' in note for note in selection['reductions'])
    assert any('notes.md' in note for note in packed['ContextSelection']['notes'])
    assert payload == original
    for f in packed['RelevantFiles']:
        if f['path'].endswith('.py'):
            assert f == next(o for o in original['RelevantFiles'] if o['path']==f['path'])


@pytest.mark.parametrize('reference', ['goal', 'error', 'source'])
def test_referenced_documentation_cannot_be_discarded_to_force_a_fit(reference):
    payload = saved_case()['payload']
    payload['RelevantFiles'].append({'path':'contract.md', 'sha256':'b'*64, 'content':'Required specification\n'*1600})
    if reference == 'goal':
        payload['ProjectGoal'] += ' Follow contract.md as the specification.'
    elif reference == 'error':
        payload['ErrorSummary'].append({'file':'contract.md', 'message':'Fix this specification'})
    else:
        payload['RelevantFiles'][1]['content'] += "\nSPECIFICATION = 'contract.md'\n"
    with pytest.raises(ValueError, match='Kontekst wymaga'):
        select_context(payload, 19176)


def test_text_input_is_not_assumed_to_be_optional_documentation():
    payload = saved_case()['payload']
    payload['RelevantFiles'].append({'path':'input.txt', 'sha256':'c'*64, 'content':'Input data\n'*4000})
    with pytest.raises(ValueError, match='Kontekst wymaga'):
        select_context(payload, 19176)


def test_oversized_core_evidence_fails_instead_of_cutting_the_traceback():
    payload = saved_case()['payload']
    payload['LatestTestResult']['output'] = 'Traceback\n' + 'Evidence\n'*6000 + 'Final exception'
    original = deepcopy(payload)
    with pytest.raises(ValueError, match='LatestTestResult'):
        select_context(payload, 19176)
    assert payload == original


def test_short_output_word_does_not_remove_task_instructions():
    payload = saved_case()['payload']
    payload['LatestTestResult']['output'] = 'ERROR'
    payload['CurrentTask']['description'] = payload['RequiredChanges'] = 'Fix ERROR handling without changing the specification.'
    text, _ = select_context(payload, 19176)
    assert json.loads(text)['RequiredChanges'] == payload['RequiredChanges']


def test_legacy_output_tail_is_referenced_but_full_output_is_preserved():
    payload = saved_case()['payload']
    output = 'FIRST FRAME\n' + 'trace line\n'*1300 + 'LAST EXCEPTION'
    payload['LatestTestResult']['output'] = output
    payload['CurrentTask']['description'] = payload['RequiredChanges'] = 'Fix the failure:\n' + output[-10000:]
    text, _ = select_context(payload, 50000)
    packed = json.loads(text)
    assert packed['LatestTestResult']['output'] == output
    assert output[-10000:] not in packed['RequiredChanges']


def test_post_execution_qa_summarizes_test_modules_but_keeps_product_and_runner_evidence():
    payload = saved_case()['payload']
    payload['TaskAgent'] = 'qa'
    payload['ErrorSummary'] = [{'file': 'main.py', 'line': 12, 'message': 'Expected rejection; got exit 0'}]
    product_tests = {'path':'test_main.py', 'sha256':'d'*64,
         'content':'import unittest\nclass TestProduct(unittest.TestCase):\n'
                   + ''.join(f'    def test_product_{i}(self):\n        self.assertTrue(True)\n' for i in range(30))}
    payload['RelevantFiles'] = [product_tests if f['path']=='test_main.py' else f
                                for f in payload['RelevantFiles']]
    payload['RelevantFiles'].extend([
        {'path':'acceptance_cases.py', 'sha256':'e'*64,
         'content':'import unittest\nclass TestAcceptance(unittest.TestCase):\n'
                   + ''.join(f'    def test_acceptance_{i}(self):\n        self.assertTrue(True)\n' for i in range(30))},
        {'path':'test_acceptance.py', 'sha256':'f'*64,
         'content':'import unittest\ndef load_tests(loader, tests, pattern):\n    return tests\n' * 30},
    ])
    original_product = next(f for f in payload['RelevantFiles'] if f['path']=='main.py')
    original_output = payload['LatestTestResult']['output']
    text, selection = select_context(payload, 15000)
    packed = json.loads(text)
    assert selection['bytes'] <= 15000
    assert packed['LatestTestResult']['output'] == original_output
    assert packed['ErrorSummary'] == payload['ErrorSummary']
    assert next(f for f in packed['RelevantFiles'] if f['path']=='main.py') == original_product
    for filename, prefix in [('test_main.py','test_product_'),
                             ('acceptance_cases.py','test_acceptance_'),
                             ('test_acceptance.py',None)]:
        summarized = next(f for f in packed['RelevantFiles'] if f['path']==filename)
        assert 'content' not in summarized
        assert summarized['sha256'] == next(f for f in payload['RelevantFiles'] if f['path']==filename)['sha256']
        assert summarized['context_summary']['body_omitted']
        if prefix:
            assert any(name.startswith(prefix) for name in summarized['context_summary']['test_methods'])
    assert any('test_main.py' in note for note in packed['ContextSelection']['notes'])
    assert payload['RelevantFiles'][-3]['content'].startswith('import unittest')


async def test_saved_failure_reaches_actual_llm_transport_without_product_execution(system):
    service, worker, _, runner = system
    payload = saved_case()['payload']
    project = service.create_project('Saved overflow regression')
    ws = service.project_workspace(project.id)
    for file in payload['RelevantFiles']:
        ws.write(file['path'], file['content'])
    with service.sessions.begin() as s:
        goal = Task(project_id=project.id, agent='ceo', title='Goal', description=payload['ProjectGoal'], status='COMPLETED')
        s.add(goal); s.flush()
        qa = Task(project_id=project.id, agent='qa', title='QA', description=payload['AcceptanceCriteria'],
                  status='REVIEWED', dependencies=[goal.id], result={
                      'tests':payload['LatestTestResult'], 'tested_hashes':ws.hashes(),
                      'qa_report':{'issues':payload['ErrorSummary']}, 'repair_scheduled':True})
        s.add(qa); s.flush()
        repair = Task(project_id=project.id, agent='developer', title='Repair', iteration=1,
                      description=payload['RequiredChanges'], dependencies=[qa.id])
        s.add(repair); s.flush()
    requests = []

    def transport(request):
        if request.url.path.endswith('/tags'):
            return httpx.Response(200, json={'models':[{'name':'qwen2.5-coder:7b'}]})
        if request.url.path.endswith('/show'):
            return httpx.Response(200, json={})
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={'message':{'content':json.dumps({
            'summary':'Transport regression; do not change project files.', 'disposition':'unconfirmed', 'edits':[]})}})

    client = OllamaClient(service.settings, httpx.MockTransport(transport))
    worker.client = client
    before = ws.hashes()
    try:
        await worker.tick()
    finally:
        await client.close()
    assert len(requests)==1 and requests[0]['options']['num_ctx']==8192
    assert requests[0]['options']['num_predict'] >= 256
    sent = json.loads(requests[0]['messages'][1]['content'])
    assert sent['LatestTestResult']['output'] == payload['LatestTestResult']['output']
    assert sent['LatestTestResult']['applies_to_current_files']
    assert sent['RelevantFiles'] == payload['RelevantFiles']
    assert ws.hashes()==before and runner.calls==0
    with service.sessions() as s:
        finished = s.get(Task, repair.id)
        assert finished.status=='FAILED' and 'REPAIR_UNCONFIRMED' in finished.error
