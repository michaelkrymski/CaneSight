"""Private allowlisted Pi context run evidence; no credentials, scenes or device IDs."""
import json
import os
from pathlib import Path
import stat
import subprocess


def revision():
    try:
        value = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parents[1],
                               capture_output=True, text=True, timeout=2, check=True).stdout.strip()
        return value if len(value) == 40 and all(c in '0123456789abcdef' for c in value) else None
    except Exception:
        return None


def bounded_status(snapshot):
    """Closed metadata only, even if a future adapter adds sensitive fields."""
    result = {}
    for key in ('audio_enabled', 'audio_delivery_verified', 'consent', 'input_closed', 'closed'):
        result[key] = snapshot.get(key) if type(snapshot.get(key)) is bool else None
    result['fault_present'] = snapshot.get('fault') is not None
    result['shown'] = snapshot.get('shown') if type(snapshot.get('shown')) is int and 0 <= snapshot['shown'] <= 2**53-1 else None
    button = snapshot.get('button')
    result['button'] = None
    if type(button) is dict:
        fields = {}
        for key in ('requesting', 'result_available', 'enabled', 'closed'):
            fields[key] = button.get(key) if type(button.get(key)) is bool else None
        for key in ('requests', 'cancelled', 'failed'):
            value = button.get(key)
            fields[key] = value if type(value) is int and 0 <= value <= 2**53-1 else None
        fields['fault_present'] = button.get('fault') is not None
        result['button'] = fields
    return result


class ContextRunReport:
    def __init__(self):
        self.file = None
        self.data = {'mode': 'manual-context-run', 'complete': False,
                     'physical_audio_accepted': False, 'phone_backend_verified': False,
                     'gpio_used': False, 'build_commit': revision(), 'outcome': 'unavailable'}

    def open(self, path, *, audio):
        if path is None:
            return
        # Do not follow a report symlink or overwrite an earlier run.
        path = Path(path).expanduser().absolute()
        parent = path.parent.resolve()
        repository = Path(__file__).resolve().parents[1]
        if parent.is_relative_to(repository) or stat.S_IMODE(parent.stat().st_mode) & 0o077:
            raise ValueError('Choose a private report directory outside the checkout')
        fd = os.open(parent/path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.file = os.fdopen(fd, 'w', encoding='utf-8')
        self.data['audio_enabled'] = audio is True

    def capture(self, runtime):
        if self.file is not None and runtime is not None:
            try:
                self.data['context'] = bounded_status(runtime.snapshot())
            except Exception:
                self.data['snapshot_unavailable'] = True

    def finish(self):
        if self.file is not None:
            with self.file:
                self.file.write(json.dumps(self.data, indent=2, allow_nan=False)+'\n')
            self.file = None
