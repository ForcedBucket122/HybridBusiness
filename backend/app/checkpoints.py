from .database import TaskCheckpoint, now, record


class Checkpoints:
    def __init__(self, sessions):
        self.sessions = sessions

    def get(self, task_id, stage):
        with self.sessions() as s:
            row = s.get(TaskCheckpoint, (task_id, stage))
            return row.payload if row else None

    def save(self, task, stage, payload):
        with self.sessions.begin() as s:
            row = s.get(TaskCheckpoint, (task.id, stage))
            if row:
                row.payload, row.updated_at = payload, now()
            else:
                s.add(TaskCheckpoint(task_id=task.id, stage=stage, payload=payload))
            record(s, 'checkpoint', stage, task.project_id, task.id)
