from sqlalchemy import select
from .database import MemoryEntry


class MemoryService:
    """Replace search() with a semantic index later; persistence stays independent."""
    def __init__(self, session):
        self.session = session

    def save(self, project_id, content):
        item = MemoryEntry(project_id=project_id, content=content[:16000])
        self.session.add(item)
        self.session.flush()
        return item.id

    def search(self, project_id, query='', limit=12):
        stmt = select(MemoryEntry).where(MemoryEntry.project_id == project_id)
        if query:
            stmt = stmt.where(MemoryEntry.content.contains(query, autoescape=True))
        return list(self.session.scalars(stmt.order_by(MemoryEntry.created_at.desc()).limit(min(limit, 30))))

    def context(self, project_id, budget=16000):
        return '\n\n'.join(m.content for m in self.search(project_id))[:budget]
