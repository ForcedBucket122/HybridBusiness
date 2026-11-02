from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from .database import SystemSetting, Task, Project, record, uid
from .service import ACTIVE


class ScheduledWork:
    def __init__(self, service):
        self.service = service

    def tick(self):
        cfg = self.service.settings()
        if not cfg.scheduler_enabled or cfg.mode == 'MANUAL':
            return
        current = datetime.now(timezone.utc)
        day = current.astimezone(ZoneInfo('Europe/Warsaw')).date().isoformat()
        with self.service.sessions.begin() as s:
            s.connection().exec_driver_sql('BEGIN IMMEDIATE')
            row = s.get(SystemSetting, 'scheduler_state')
            state = dict(row.value) if row else {}
            count = state.get('count', 0) if state.get('day') == day else 0
            if count >= cfg.daily_limit:
                return
            if state.get('last') and (current - datetime.fromisoformat(state['last'])).total_seconds() < cfg.schedule_minutes * 60:
                return
            active = s.scalar(select(func.count()).select_from(Task).where(Task.status.in_(ACTIVE)))
            if active >= cfg.max_active_tasks:
                return
            project_id = state.get('project_id')
            if not project_id or not s.get(Project, project_id):
                project_id = uid()
                s.add(Project(id=project_id, name='Pomysły i raporty', description='Zaplanowane propozycje; bez automatycznej implementacji.'))
                s.flush()
                self.service.project_workspace(project_id)
            s.add(Task(project_id=project_id, agent='research', title='Okresowa propozycja produktu',
                       description='Zaproponuj jeden mały produkt cyfrowy, odbiorców, funkcje MVP, ryzyka i następny krok. Oznacz hipotezy.'))
            state = {'day': day, 'count': count + 1, 'last': current.isoformat(), 'project_id': project_id}
            if row:
                row.value = state
            else:
                s.add(SystemSetting(key='scheduler_state', value=state))
            record(s, 'scheduled', 'Dodano propozycję badawczą w granicach limitu dziennego.', project_id)
            self.service.refresh_project(s, project_id)
