"""Independent cases; collection never imports the generated product."""
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class ExpenseAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This guard prevents accidental execution; it does NOT grant approval.
        if os.environ.get('EXPENSE_APPROVED_SNAPSHOT') != '1':
            raise unittest.SkipTest('Requires fresh hash-bound approval and snapshot')
        source = Path(__file__).with_name('main.py')
        expected = '3ee672b721782a0f2bf37dbd713a09db13dbbdce3b7619896ff745eb7fc5f25d'
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Product differs from reviewed Release')
        spec = importlib.util.spec_from_file_location('expense_acceptance_product', source)
        cls.product = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.product)

    def setUp(self):
        self.storage = TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.path = Path(self.storage.name) / 'expenses.json'

    def invoke(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                result = self.product.main(arguments)
                if result is not None:
                    code = result
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_rejected(self, arguments):
        code, stdout, stderr = self.invoke(arguments)
        self.assertIsInstance(code, int)
        self.assertNotEqual(code, 0)
        self.assertTrue(stderr.strip(), 'Useful stderr message required')
        self.assertNotIn('Traceback (most recent call last)', stderr)
        self.assertNotIn('ADDED', stdout)

    def corrupt_storage(self, command):
        for contents in (b'{invalid json', b'', b'[\n'):
            with self.subTest(contents=contents):
                self.path.write_bytes(contents)
                self.assert_rejected(['--file', str(self.path), *command])
                self.assertEqual(self.path.read_bytes(), contents)

    def test_corrupt_json_add_preserves_bytes(self):
        self.corrupt_storage(['add', '100', 'Food'])

    def test_corrupt_json_list_preserves_bytes(self):
        self.corrupt_storage(['list'])

    def test_corrupt_json_total_preserves_bytes(self):
        self.corrupt_storage(['total'])

    def invalid_add(self, amount, category):
        # Error rejection is mandatory; preserving valid storage is advisory
        # and is asserted separately in the advisory test below.
        self.path.write_bytes(b'[{"amount": 7, "category": "Existing"}]')
        self.assert_rejected(['--file', str(self.path), 'add', amount, category])

    def test_zero_amount_rejected(self):
        self.invalid_add('0', 'Food')

    def test_negative_amount_rejected(self):
        self.invalid_add('-1', 'Food')

    def test_noninteger_amount_rejected(self):
        for value in ('1.5', 'abc'):
            with self.subTest(value=value):
                self.invalid_add(value, 'Food')

    def test_blank_category_rejected(self):
        for category in ('', '   ', '\t'):
            with self.subTest(category=category):
                self.invalid_add('100', category)

    def test_file_option_required(self):
        self.assert_rejected(['total'])

    @unittest.skipUnless(os.environ.get('EXPENSE_ADVISORY_CASES') == '1',
                         'Additional robustness contract, not explicitly specified')
    def test_advisory_invalid_schema_preserves_storage(self):
        cases = (b'{}', b'null', b'[{}]',
                 b'[{"amount": "100", "category": "Food"}]',
                 b'[{"amount": -1, "category": "Food"}]',
                 b'[{"amount": 1, "category": null}]')
        for contents in cases:
            for command in (['add', '100', 'Food'], ['list'], ['total']):
                with self.subTest(contents=contents, command=command):
                    self.path.write_bytes(contents)
                    self.assert_rejected(['--file', str(self.path), *command])
                    self.assertEqual(self.path.read_bytes(), contents)

    @unittest.skipUnless(os.environ.get('EXPENSE_ADVISORY_CASES') == '1',
                         'Missing operands and invalid-input preservation are extra contracts')
    def test_advisory_incomplete_add_preserves_storage(self):
        contents = b'[{"amount": 7, "category": "Existing"}]'
        for command in (['add'], ['add', '100'], ['add', '0', 'Food']):
            with self.subTest(command=command):
                self.path.write_bytes(contents)
                self.assert_rejected(['--file', str(self.path), *command])
                self.assertEqual(self.path.read_bytes(), contents)


if __name__ == '__main__':
    unittest.main()
