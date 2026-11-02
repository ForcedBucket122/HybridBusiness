import asyncio
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from .process_job import ProcessJob


class ExecutionRunner:
    isolated = False

    async def run(self, directory: Path, cancelled):
        raise NotImplementedError


class ApprovedHostRunner(ExecutionRunner):
    """Full host permissions. Explicit single-use approval is mandatory in the engine."""
    command = [sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', '.', '-p', 'test*.py', '-v']

    async def run(self, directory, cancelled):
        return await asyncio.to_thread(self._run, directory, cancelled)

    def _run(self, directory, cancelled):
        output_path = directory.parent / f'{directory.name}-test-output.log'
        env = {k: v for k, v in os.environ.items() if k.upper() in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH')}
        env['PYTHONIOENCODING'] = 'utf-8'
        reason = None
        started = time.monotonic()
        with output_path.open('wb') as output:
            job = ProcessJob() if os.name == 'nt' else None
            process = subprocess.Popen(self.command, cwd=directory, env=env, stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            try:
                if job:
                    job.assign(process)
                for _ in range(1200):
                    if process.poll() is not None:
                        break
                    if cancelled() or time.monotonic() - started > 120 or output_path.stat().st_size > 1_000_000:
                        reason = 'cancelled' if cancelled() else 'timeout_or_output_limit'
                        break
                    time.sleep(0.1)
            finally:
                if job:
                    job.close()
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
        with output_path.open('rb') as stream:
            text = stream.read(100000).decode('utf-8', errors='replace')
        match = re.search(r'Ran (\d+) tests?', text)
        count = int(match.group(1)) if match else 0
        return {'exit_code': process.returncode, 'output': text, 'test_count': count,
                'passed': process.returncode == 0 and count > 0 and not reason,
                'reason': reason, 'seconds': round(time.monotonic() - started, 2),
                'isolated': False, 'command': self.command}
