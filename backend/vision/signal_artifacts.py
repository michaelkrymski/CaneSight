"""Inspect trusted local custom-signal artifact records without loading a model.

Integrity/provenance inspection is not evaluation or permission to enable live
inference. No download, deserialization, runtime import or activation exists.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re


@dataclass(frozen=True)
class SignalArtifactRecord:
    sha256: str
    size_bytes: int
    classes: tuple
    source: str
    license: str
    training_scene_split: str
    evaluation_report: str
    supported_conditions: tuple


@dataclass(frozen=True)
class ArtifactInspection:
    sha256: str
    size_bytes: int
    integrity_verified: bool = True
    live_supported: bool = False
    reason: str = 'integrity_only_evaluation_and_loader_review_required'


def inspect_signal_artifact(path, record):
    """Hash bounded operator-owned bytes against a separately trusted record.

    A matching hash proves identity with this record only. Text references are
    required provenance fields, not validated licenses or held-out evidence.
    Runtime class IDs must still be checked by a future reviewed loader.
    """
    if (not isinstance(record, SignalArtifactRecord)
            or not isinstance(record.sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', record.sha256)
            or type(record.size_bytes) is not int or not 1 <= record.size_bytes <= 100_000_000
            or not isinstance(record.classes, tuple) or not 2 <= len(record.classes) <= 64
            or any(not isinstance(c, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', c)
                   for c in record.classes)
            or len(set(record.classes)) != len(record.classes)
            or not {'walk', 'dont_walk'}.issubset(record.classes)
            or any(not isinstance(s, str) or not s.strip() or len(s) > 1024
                   for s in (record.source, record.license, record.training_scene_split,
                             record.evaluation_report))
            or not isinstance(record.supported_conditions, tuple)
            or not 1 <= len(record.supported_conditions) <= 2
            or any(c not in ('day', 'night') for c in record.supported_conditions)
            or len(set(record.supported_conditions)) != len(record.supported_conditions)):
        raise ValueError('Complete bounded custom-signal artifact record required')
    path = Path(path)
    if not path.is_file() or path.stat().st_size != record.size_bytes:
        raise ValueError('Signal artifact size mismatch or missing file')
    digest, count = hashlib.sha256(), 0
    with path.open('rb') as source:
        while chunk := source.read(65536):
            count += len(chunk)
            if count > record.size_bytes:
                raise ValueError('Signal artifact grew during inspection')
            digest.update(chunk)
    if count != record.size_bytes or digest.hexdigest() != record.sha256:
        raise ValueError('Signal artifact SHA-256 or size mismatch')
    return ArtifactInspection(digest.hexdigest(), count)
