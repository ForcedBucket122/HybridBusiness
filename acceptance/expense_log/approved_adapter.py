"""Approval-bound bridge for the existing fixed unittest runner.

The engine, not this adapter, authorizes execution. Include this file in hashes.
"""
import os
import unittest


def load_tests(loader, standard_tests, pattern):
    os.environ['EXPENSE_APPROVED_SNAPSHOT'] = '1'
    os.environ.pop('EXPENSE_ADVISORY_CASES', None)
    import acceptance_cases
    return loader.loadTestsFromTestCase(acceptance_cases.ExpenseAcceptance)
