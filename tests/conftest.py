from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas import CodeResult, Plan, Report, Review, RepairResult

CODE = "def add(a, b):\n    return a + b\n"
TEST = "import unittest\nfrom main import add\nclass TestAdd(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n"


class FakeClient:
    def __init__(self, settings):
        self.settings = settings
        self.calls = []
        self.review_failures = 0
        self.error = None

    async def models(self):
        return ['qwen3:4b', 'qwen2.5-coder:7b']

    async def close(self):
        pass

    async def generate(self, role, system, prompt, schema):
        self.calls.append(role)
        if self.error:
            raise self.error
        if schema == Plan:
            return Plan(summary='Plan', steps=[{'agent':'developer', 'title':'Implementacja', 'description':'Build add', 'acceptance':'Works with tests'}])
        if schema == CodeResult:
            return CodeResult(summary='Files', files=[{'path':'main.py','content':CODE}, {'path':'test_main.py','content':TEST}, {'path':'README.md','content':'# Run\npython main.py\n'}])
        if schema == RepairResult:
            return RepairResult(summary='Targeted fixture repair', edits=[{'path':'main.py', 'old_text':'return a + b', 'new_text':'return sum((a, b))'}])
        if schema == Review:
            if self.review_failures:
                self.review_failures -= 1
                return Review(summary='Fix needed', issues=['Concrete bug'], acceptable=False)
            return Review(summary='Review accepted', issues=[], acceptable=True)
        return Report(title='Release notes', body='Actual files and test evidence are attached.', evidence='estimated')


class FakeRunner:
    command = ['python', '-I', '-B', '-m', 'unittest', 'discover', '-s', '.', '-p', 'test*.py', '-v']
    def __init__(self):
        self.calls = 0
        self.passed = True

    async def run(self, directory, cancelled):
        self.calls += 1
        assert Path(directory, 'main.py').is_file()
        return {'exit_code': 0 if self.passed else 1, 'test_count': 1, 'passed': self.passed,
                'output': 'Ran 1 test\nOK' if self.passed else 'AssertionError: bad output', 'isolated': False}


@pytest.fixture
def system(tmp_path):
    runner = FakeRunner()
    app = create_app(tmp_path/'data', tmp_path/'workspace', start_worker=False, client_factory=FakeClient, runner=runner)
    with TestClient(app, headers={'X-LocalAI':'1'}) as http:
        yield app.state.service, app.state.worker, http, runner
