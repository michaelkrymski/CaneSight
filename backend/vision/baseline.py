"""CS-034: explicitly fetch, verify and inspect one pretrained YOLOv8n artifact.

Importing this module needs only the standard library. Loading never downloads
weights, trains a model, activates a service or produces pedestrian-signal state.
"""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'baseline.json'
DEFAULT_WEIGHTS = ROOT / 'artifacts' / 'yolov8n.pt'


def manifest():
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


def verify_weights(path):
    """Reject missing, truncated, replaced or nonbaseline bytes before loading."""
    path = Path(path)
    spec = manifest()['artifact']
    if path.stat().st_size != spec['bytes']:
        raise ValueError('Baseline weight size mismatch')
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(65536), b''):
            digest.update(chunk)
    if digest.hexdigest() != spec['sha256']:
        raise ValueError('Baseline weight SHA-256 mismatch')
    return path.resolve()


def download_weights(path=DEFAULT_WEIGHTS):
    """Explicit operator action; bounded download, verified before atomic install."""
    path = Path(path)
    if path.exists():
        return verify_weights(path)  # Never silently replace a different model.
    spec = manifest()['artifact']
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.part', delete=False) as target:
            temporary = Path(target.name)
            with urllib.request.urlopen(spec['url'], timeout=30) as response:
                if urllib.parse.urlsplit(response.geturl()).scheme != 'https':
                    raise ValueError('Baseline download requires HTTPS')
                remaining = spec['bytes'] + 1
                while remaining:
                    chunk = response.read(min(65536, remaining))
                    if not chunk:
                        break
                    target.write(chunk)
                    remaining -= len(chunk)
        verify_weights(temporary)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path.resolve()


def runtime_versions():
    """Enforce the selected inference runtime, allowing official +cpu wheels."""
    versions = {}
    for package, expected in manifest()['runtime'].items():
        actual = metadata.version(package)
        allowed = {expected}
        if package in ('torch', 'torchvision'):
            allowed.add(expected + '+cpu')
        if actual not in allowed:
            raise ValueError(f'Baseline requires {package}=={expected}; found {actual}')
        versions[package] = actual
    return versions


def check_classes(names):
    expected = manifest()['classes']
    if (not isinstance(names, dict) or set(names) != set(range(len(expected)))
            or [names[i] for i in range(len(expected))] != expected):
        raise ValueError('Loaded weight class list differs from pinned baseline')
    return expected.copy()


def configure_runtime():
    # Ultralytics checks the parent before creating its own Ultralytics child.
    # A nonexistent parent otherwise causes a fallback to the working directory.
    config = ROOT / 'artifacts' / 'runtime'
    config.mkdir(parents=True, exist_ok=True)
    os.environ['YOLO_OFFLINE'] = 'true'
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    os.environ['YOLO_CONFIG_DIR'] = str(config)


def load_baseline(path=DEFAULT_WEIGHTS):
    """Load only the hash-verified, operator-controlled checkpoint on CPU.

PyTorch .pt checkpoints deserialize Python objects. The publisher URL/hash are
the trust anchor; never substitute a user-uploaded model or relax verification.
The baseline is intentionally separate from the production worker (CS-035).
"""
    path = verify_weights(path)
    runtime_versions()
    # Must precede Ultralytics import. Keep generated settings outside Git and
    # prevent online integrations and dependency/model auto-installation.
    configure_runtime()
    from ultralytics import YOLO, settings
    settings.update({'sync': False})
    model = YOLO(str(path), task='detect')
    if model.task != 'detect':
        raise ValueError('Baseline must be an object detector')
    check_classes(model.names)
    model.to('cpu')
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Explicitly fetch the pinned artifact')
    parser.add_argument('--weights', type=Path, default=DEFAULT_WEIGHTS)
    args = parser.parse_args()
    if args.download:
        download_weights(args.weights)
    model = load_baseline(args.weights)
    print(json.dumps({'model': manifest()['model'], 'sha256': manifest()['artifact']['sha256'],
                      'runtime': runtime_versions(), 'classes': check_classes(model.names),
                      'pedestrian_signal_supported': False}, indent=2))


if __name__ == '__main__':
    main()
