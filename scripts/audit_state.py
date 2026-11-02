"""Read-only SQLite evidence for comparing state across a controlled restart."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('label', choices=['before-restart', 'after-restart'])
args = parser.parse_args()
with sqlite3.connect((ROOT / 'data/localai.db').as_uri() + '?mode=ro', uri=True) as db:
    db.row_factory = sqlite3.Row
    tables = ('projects','tasks','task_runs','task_checkpoints','approvals','artifacts','chat_messages','memory_entries')
    report = {'integrity': db.execute('PRAGMA integrity_check').fetchone()[0], 'tables': {}}
    for table in tables:
        rows = [dict(r) for r in db.execute(f'SELECT * FROM {table}')]
        canonical = '\n'.join(sorted(json.dumps(r,sort_keys=True,ensure_ascii=True) for r in rows))
        report['tables'][table] = {'count':len(rows), 'sha256':hashlib.sha256(canonical.encode()).hexdigest()}
    report['tasks'] = [dict(r) for r in db.execute('SELECT id,project_id,agent,status,attempts,iteration,error FROM tasks ORDER BY created_at')]
target = ROOT / 'logs' / f'runtime-audit-{args.label}.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'path':str(target),'integrity':report['integrity'],'counts':{k:v['count'] for k,v in report['tables'].items()}}))
