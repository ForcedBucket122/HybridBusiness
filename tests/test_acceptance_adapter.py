"""Infrastructure tests: trusted stubs only; never load generated main.py."""
import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from app.runner import ApprovedHostRunner

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / 'acceptance/expense_log/approved_adapter.py'
CASES = ROOT / 'acceptance/expense_log/test_acceptance.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unapproved_cases_do_not_import_product():
    with patch.dict(os.environ, {}, clear=True):
        cases = load(CASES, 'unapproved_acceptance')
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(cases.ExpenseAcceptance)
        result = unittest.TestResult()
        suite.run(result)
        assert result.testsRun == 0
        assert len(result.skipped) == 1
        assert not result.errors


def test_adapter_enables_guard_but_disables_advisory():
    module = types.ModuleType('acceptance_cases')
    class TrustedCase(unittest.TestCase):
        def test_trusted(self):
            pass
    module.ExpenseAcceptance = TrustedCase
    with patch.dict(sys.modules, {'acceptance_cases': module}):
        with patch.dict(os.environ, {'EXPENSE_ADVISORY_CASES': '1'}):
            adapter = load(ADAPTER, 'adapter_under_test')
            suite = adapter.load_tests(unittest.TestLoader(), None, None)
            assert suite.countTestCases() == 1
            assert os.environ['EXPENSE_APPROVED_SNAPSHOT'] == '1'
            assert 'EXPENSE_ADVISORY_CASES' not in os.environ


def test_real_runner_with_trusted_external_stub(tmp_path):
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    (snapshot / 'test_acceptance.py').write_bytes(ADAPTER.read_bytes())
    stub = "import os, unittest\nclass ExpenseAcceptance(unittest.TestCase):\n"
    for index in range(8):
        stub += (f"    def test_required_{index}(self):\n"
                 "        self.assertEqual(os.environ.get('EXPENSE_APPROVED_SNAPSHOT'), '1')\n"
                 "        self.assertNotIn('EXPENSE_ADVISORY_CASES', os.environ)\n")
    for index in range(2):
        stub += ("    @unittest.skip('advisory disabled')\n"
                 f"    def test_optional_{index}(self):\n        self.fail('must not run')\n")
    (snapshot / 'acceptance_cases.py').write_text(stub, encoding='utf-8')
    evidence = asyncio.run(ApprovedHostRunner().run(snapshot, lambda: False))
    assert evidence['passed'], evidence
    assert evidence['test_count'] == 10
    assert 'skipped=2' in evidence['output']
    assert evidence['isolated'] is False
    assert evidence['command'][1:] == ['-I', '-B', '-m', 'unittest', 'discover', '-s', '.', '-p', 'test*.py', '-v']
