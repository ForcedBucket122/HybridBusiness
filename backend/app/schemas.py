from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROLES = ('ceo', 'developer', 'qa', 'research', 'marketing', 'finance', 'release')


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Settings(StrictModel):
    ollama_url: str = 'http://127.0.0.1:11434'
    models: dict[str, str] = Field(default_factory=lambda: {
        role: 'qwen2.5-coder:7b' if role == 'developer' else 'qwen3:4b' for role in ROLES})
    mode: Literal['MANUAL', 'HYBRID', 'AUTONOMOUS'] = 'HYBRID'
    timeout: int = Field(default=240, ge=10, le=600)
    max_tokens: int = Field(default=6000, ge=256, le=12000)
    context_size: int = Field(default=8192, ge=2048, le=16384)
    temperature: float = Field(default=0.2, ge=0, le=1)
    max_attempts: int = Field(default=2, ge=1, le=3)
    max_iterations: int = Field(default=5, ge=1, le=5)
    llm_concurrency: Literal[1] = 1
    internet_enabled: Literal[False] = False
    scheduler_enabled: bool = False
    schedule_minutes: int = Field(default=60, ge=15, le=1440)
    daily_limit: int = Field(default=3, ge=1, le=10)
    max_active_tasks: int = Field(default=30, ge=10, le=100)

    @field_validator('ollama_url')
    @classmethod
    def local_endpoint(cls, value):
        p = urlparse(value)
        if (p.scheme != 'http' or p.hostname not in ('127.0.0.1', 'localhost', '::1')
                or p.username or p.password or p.path not in ('', '/') or p.query or p.fragment):
            raise ValueError('Ollama musi być lokalnym adresem HTTP (loopback).')
        _ = p.port
        return value.rstrip('/')

    @field_validator('models')
    @classmethod
    def model_roles(cls, value):
        if set(value) != set(ROLES):
            raise ValueError('Wymagane przypisania wszystkich 7 agentów.')
        if any(not m or len(m) > 100 or 'cloud' in m.lower() or '/' in m for m in value.values()):
            raise ValueError('Tylko lokalne modele; modele cloud są zabronione.')
        return value


class ProjectInput(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=4000)


class ChatInput(StrictModel):
    content: str = Field(min_length=1, max_length=12000)
    request_id: str = Field(min_length=8, max_length=80)


class PlanStep(StrictModel):
    agent: Literal['developer', 'research', 'marketing', 'finance']
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=4000)
    acceptance: str = Field(min_length=1, max_length=2000)


class Plan(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    steps: list[PlanStep] = Field(min_length=1, max_length=4)


class SourceFile(StrictModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=100000)


class PythonSource(StrictModel):
    content: str = Field(min_length=1, max_length=100000)


class CodeResult(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    files: list[SourceFile] = Field(min_length=1, max_length=20)


class SourceLines(StrictModel):
    """Wire representation for the local coder; indentation is data, never normalized."""
    path: str = Field(min_length=1, max_length=200)
    lines: list[str] = Field(min_length=1, max_length=2000)

    @field_validator('lines')
    @classmethod
    def physical_lines(cls, value):
        if any('\n' in line or '\r' in line for line in value):
            raise ValueError('Each array item must contain exactly one physical source line.')
        if len(('\n'.join(value)+'\n').encode('utf-8')) > 100000:
            raise ValueError('File exceeds 100 KB.')
        return value

    def source(self):
        return SourceFile(path=self.path, content='\n'.join(self.lines)+'\n')


class CodeLinesResult(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    files: list[SourceLines] = Field(min_length=1, max_length=20)


class FileEdit(StrictModel):
    path: str = Field(min_length=1, max_length=200)
    old_text: str = Field(max_length=100000)
    new_text: str = Field(max_length=100000)


class RepairResult(StrictModel):
    summary: str = Field(min_length=1, max_length=2000)
    disposition: Literal['repaired', 'unconfirmed'] = 'repaired'
    edits: list[FileEdit] = Field(max_length=20)

    @model_validator(mode='after')
    def consistent_disposition(self):
        if (self.disposition == 'repaired') != bool(self.edits):
            raise ValueError('repaired requires edits; unconfirmed requires empty edits and an explanation in summary.')
        return self


class QAIssue(StrictModel):
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    kind: str = Field(default='review', max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    expected: str = Field(default='', max_length=2000)
    actual: str = Field(default='', max_length=4000)
    suggestion: str = Field(default='', max_length=2000)
    source: Literal['static', 'runner', 'model'] = 'model'


class Review(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    issues: list[str] = Field(max_length=30)
    acceptable: bool
    findings: list[QAIssue] = Field(default_factory=list, max_length=30)


class MemoryInput(StrictModel):
    content: str = Field(min_length=1, max_length=4000)
    kind: Literal['preference', 'decision'] = 'preference'


class Report(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=16000)
    evidence: Literal['hypothetical', 'estimated'] = 'hypothetical'


class Decision(StrictModel):
    approve: bool
    acknowledge_host_execution: bool = False


class FileArgs(StrictModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(default='', max_length=100000)


class QueryArgs(StrictModel):
    query: str = Field(default='', max_length=1000)
