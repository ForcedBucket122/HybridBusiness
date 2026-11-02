import hashlib
import os
import re
import stat
from pathlib import Path, PureWindowsPath

MAX_FILE = 100_000
MAX_FILES = 100
MAX_TOTAL = 2_000_000


class Workspace:
    """Path confinement, not an execution sandbox. Reject Windows reparse points."""

    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.absolute()
        self._check_links(self.root)

    @staticmethod
    def _check_links(path):
        for part in [path, *path.parents]:
            if part.exists() or part.is_symlink():
                info = part.lstat()
                if part.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                    raise ValueError('Symlink/junction/reparse point jest zabroniony.')
                if part.is_file() and info.st_nlink > 1:
                    raise ValueError('Hardlink jest zabroniony.')

    def path(self, relative: str):
        win = PureWindowsPath(relative)
        parts = relative.replace('\\', '/').split('/')
        if (not relative or win.is_absolute() or win.drive or relative.startswith(('/', '\\'))
                or any(p in ('', '.', '..') for p in parts)):
            raise ValueError('Niedozwolona ścieżka.')
        for p in parts:
            if (re.search(r'[<>:"|?*\x00-\x1f]', p) or p.endswith((' ', '.'))
                    or p.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}):
                raise ValueError('Niedozwolona nazwa pliku.')
        target = self.root.joinpath(*parts)
        self._check_links(target)
        if not target.resolve().is_relative_to(self.root.resolve()):
            raise ValueError('Ścieżka poza projektem.')
        return target

    def files(self):
        result = []
        total = 0
        for directory, dirs, names in os.walk(self.root, followlinks=False):
            for item in dirs + names:
                self._check_links(Path(directory) / item)
            for name in names:
                p = Path(directory) / name
                if not stat.S_ISREG(p.stat().st_mode):
                    raise ValueError('Tylko zwykłe pliki są dozwolone.')
                total += p.stat().st_size
                result.append(p.relative_to(self.root).as_posix())
                if len(result) > MAX_FILES or total > MAX_TOTAL:
                    raise ValueError('Przekroczono limit plików projektu (100 / 2 MB).')
        return sorted(result)

    def read(self, relative):
        p = self.path(relative)
        if p.stat().st_size > MAX_FILE:
            raise ValueError('Plik przekracza 100 KB.')
        return p.read_text(encoding='utf-8')

    def write(self, relative, content):
        raw = content.encode('utf-8')
        if len(raw) > MAX_FILE:
            raise ValueError('Plik przekracza 100 KB.')
        target = self.path(relative)
        files = self.files()
        total = sum(self.path(f).stat().st_size for f in files if f != relative) + len(raw)
        if total > MAX_TOTAL or (relative not in files and len(files) >= MAX_FILES):
            raise ValueError('Przekroczono limit projektu.')
        target.parent.mkdir(parents=True, exist_ok=True)
        self._check_links(target.parent)
        temp = target.with_name(target.name + '.localai.tmp')
        self._check_links(temp)
        with temp.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
        os.replace(temp, target)
        return {'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    def hashes(self):
        return {name: hashlib.sha256(self.path(name).read_bytes()).hexdigest() for name in self.files()}
