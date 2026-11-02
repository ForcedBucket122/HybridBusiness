import json
import re
from sqlalchemy import or_, select
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

    def remember(self, project_id, kind, content, task_id=None, verified=False):
        """Typed envelope preserves compatibility with existing plain-text memories."""
        value = json.dumps({'version': 1, 'kind': kind, 'content': content,
                            'task_id': task_id, 'verified': verified}, ensure_ascii=False, sort_keys=True)
        existing = self.session.scalar(select(MemoryEntry).where(
            MemoryEntry.project_id == project_id, MemoryEntry.content == value))
        return existing.id if existing else self.save(project_id, value)

    def relevant(self, project_id, query='', kinds=('preference', 'decision', 'solution'), limit=5, budget=2000):
        words = list(dict.fromkeys(re.findall(r'[\w.]{3,}', query.lower())))[:12]
        stmt = select(MemoryEntry).where(MemoryEntry.project_id == project_id)
        if words:
            stmt = stmt.where(or_(*(MemoryEntry.content.contains(w, autoescape=True) for w in words),
                                  MemoryEntry.content.contains('"kind": "preference"')))
        rows = self.session.scalars(stmt.order_by(MemoryEntry.created_at.desc()).limit(100))
        candidates = []
        for row in rows:
            try:
                entry = json.loads(row.content)
            except ValueError:
                continue
            if not isinstance(entry, dict) or entry.get('kind') not in kinds:
                continue
            if entry['kind'] == 'solution' and not entry.get('verified'):
                continue
            content = str(entry.get('content', ''))
            score = sum(w in content.lower() for w in words) + (10 if entry['kind'] == 'preference' else 0)
            if score or not words:
                candidates.append((score, {'id': row.id, **entry}))
        result, used = [], 0
        for _, entry in sorted(candidates, key=lambda pair: pair[0], reverse=True):
            size = len(json.dumps(entry, ensure_ascii=False))
            if used + size <= budget and len(result) < limit:
                result.append(entry); used += size
        return result
