import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    name: Mapped[str]
    description: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(default='IDLE')
    created_at: Mapped[str] = mapped_column(default=now)


class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    agent: Mapped[str]
    priority: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(default='PENDING', index=True)
    created_at: Mapped[str] = mapped_column(default=now)
    started_at: Mapped[str | None]
    finished_at: Mapped[str | None]
    attempts: Mapped[int] = mapped_column(default=0)
    iteration: Mapped[int] = mapped_column(default=0)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    request_id: Mapped[str | None] = mapped_column(String, unique=True)


class TaskRun(Base):
    __tablename__ = 'task_runs'
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'), index=True)
    started_at: Mapped[str] = mapped_column(default=now)
    finished_at: Mapped[str | None]
    status: Mapped[str] = mapped_column(default='RUNNING')
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class Agent(Base):
    __tablename__ = 'agents'
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    role: Mapped[str]
    model: Mapped[str]
    system_prompt: Mapped[str] = mapped_column(Text)
    tools: Mapped[list] = mapped_column(JSON)


class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    role: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=now)


class AgentMessage(Base):
    __tablename__ = 'agent_messages'
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'))
    sender: Mapped[str]
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(default=now)


class MemoryEntry(Base):
    __tablename__ = 'memory_entries'
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=now)


class Approval(Base):
    __tablename__ = 'approvals'
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'))
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default='PENDING')
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(default=now)
    decided_at: Mapped[str | None]


class Artifact(Base):
    __tablename__ = 'artifacts'
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'), unique=True)
    name: Mapped[str]
    path: Mapped[str]
    sha256: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)


class Event(Base):
    __tablename__ = 'events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str | None] = mapped_column(index=True)
    task_id: Mapped[str | None]
    kind: Mapped[str]
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=now)


class SystemSetting(Base):
    __tablename__ = 'system_settings'
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f'sqlite:///{path.as_posix()}', connect_args={'check_same_thread': False, 'timeout': 20})

    @event.listens_for(engine, 'connect')
    def configure(dbapi, _):
        dbapi.execute('PRAGMA foreign_keys=ON')
        dbapi.execute('PRAGMA journal_mode=WAL')
        dbapi.execute('PRAGMA busy_timeout=20000')

    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def record(session, kind, message, project_id=None, task_id=None):
    session.add(Event(kind=kind, message=message, project_id=project_id, task_id=task_id))


def serialize(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}
