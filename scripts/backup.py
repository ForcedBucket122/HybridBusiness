"""Local restore point: consistent SQLite snapshot plus source and user artifacts."""
import hashlib
import json
import sqlite3
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def backup():
    destination = ROOT / 'data/backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination.mkdir(parents=True, exist_ok=False)
    db = ROOT / 'data/localai.db'
    if db.exists():
        with sqlite3.connect(db) as source, sqlite3.connect(destination / 'localai.db') as target:
            source.backup(target)
            assert target.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    tracked = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'], cwd=ROOT).decode().split('\0')
    with zipfile.ZipFile(destination/'files.zip','x',zipfile.ZIP_DEFLATED) as archive:
        paths = [ROOT / p for p in tracked if p]
        for folder in ['workspace/projects','workspace/runs','workspace/artifacts','logs']:
            paths.extend((ROOT / folder).rglob('*'))
        for path in dict.fromkeys(paths):
            if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT):
                archive.write(path,path.relative_to(ROOT).as_posix())
    manifest = {'created_at':datetime.now(timezone.utc).isoformat(),
                'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
                'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.iterdir()}}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(destination)

if __name__ == '__main__':
    backup()
