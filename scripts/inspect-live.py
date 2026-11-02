"""Read-only verification evidence for the practical live project. Never executes its code."""
import hashlib
import json
import sys
from pathlib import Path
import httpx

root = Path(__file__).resolve().parents[1]
state = json.loads((root / 'data/live-e2e.json').read_text(encoding='utf-8'))
project_id = state['project_id']
with httpx.Client(base_url='http://127.0.0.1:8000', trust_env=False) as client:
    project = client.get(f'/api/projects/{project_id}').raise_for_status().json()
    tasks = client.get('/api/tasks', params={'project_id':project_id}).raise_for_status().json()
    approvals = [a for a in client.get('/api/approvals').raise_for_status().json() if a['project_id'] == project_id]
    evidence = {'project': project, 'tasks': tasks, 'approvals': approvals,
                'files': {name: hashlib.sha256((root / 'workspace/projects' / project_id / name).read_bytes()).hexdigest()
                          for name in project['files']}}
    (root / 'logs/live-e2e-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'project_id': project_id, 'status': project['status'],
                      'tasks': [{'agent':t['agent'], 'status':t['status']} for t in tasks],
                      'files': list(evidence['files']), 'artifacts': project['artifacts']}, ensure_ascii=True, indent=2))
