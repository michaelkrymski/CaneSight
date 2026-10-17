"""Actual pinned model through the bounded worker; generated replay pixels only."""
import argparse
import io
import json
import math
from pathlib import Path
import platform
import statistics
import time

from .baseline import DEFAULT_WEIGHTS, manifest, runtime_versions
from .observations import YoloFactory


def run(weights=DEFAULT_WEIGHTS, samples=20):
    if type(samples) is not int or not 1 <= samples <= 100:
        raise ValueError('Use 1..100 samples')
    from PIL import Image
    from backend.app import SourceGrant, protocol
    from backend.inference_worker import InferenceWorker
    buffer = io.BytesIO()
    with Image.new('RGB', (416, 416), 'black') as image:
        image.save(buffer, format='JPEG', quality=75)
    jpeg = buffer.getvalue()
    worker = InferenceWorker(YoloFactory(weights))
    started = time.monotonic()
    try:
        worker.start()
        while not worker.health()['worker_healthy']:
            if worker.metrics()['failed'] or time.monotonic() - started > 35:
                raise RuntimeError('Verified model worker did not become available')
            time.sleep(.01)
        load_ms = (time.monotonic() - started) * 1000
        grant = SourceGrant('synthetic-smoke-not-a-device-credential', 'synthetic-worker-session',
                            'generated-camera', 'generated-boot', 'replay', time.monotonic() + 300)
        durations, processing, counts = [], [], []
        for seq in range(samples + 1):
            capture = time.monotonic() * 1000
            metadata = {'schema_version': 1, 'type': 'frame_metadata',
                'session_id': grant.session_id, 'source_id': grant.source_id,
                'boot_id': grant.boot_id, 'mode': 'replay', 'seq': seq,
                'capture_monotonic_ms': capture, 'capture_utc': None,
                'frame_id': 'generated-frame-' + str(seq),
                'image': {'width': 416, 'height': 416}, 'jpeg_bytes': len(jpeg)}
            protocol.validate_message(metadata)
            if not worker.submit(grant, metadata, jpeg):
                raise RuntimeError('Synthetic submission was unavailable')
            deadline = time.monotonic() + 2
            observation = None
            while observation is None:
                observation = worker.take_result(grant)
                if observation is not None:
                    break
                if not worker.health()['worker_healthy'] or time.monotonic() >= deadline:
                    raise RuntimeError('Synthetic result failed or exceeded worker deadline')
                time.sleep(.005)
            protocol.validate_message(observation)
            for key, value in metadata.items():
                if key not in ('type', 'jpeg_bytes') and observation[key] != value:
                    raise RuntimeError('Original frame lineage changed')
            signal = observation['signal']
            if signal != {'candidate_count': 0, 'symbol': 'unknown',
                          'confidence': None, 'countdown_s': None}:
                raise RuntimeError('Unsupported pedestrian-signal interpretation')
            if seq:  # First prediction is warmup; the actual worker deadline applies.
                durations.append(time.monotonic() * 1000 - capture)
                processing.append(observation['processing_ms'])
                counts.append(len(observation['detections']))
        metrics = worker.metrics()
        return {'task': 'CS-035', 'model_version': observation['model_version'],
            'artifact_sha256': manifest()['artifact']['sha256'],
            'runtime': runtime_versions(), 'python': platform.python_version(),
            'platform': platform.system(), 'machine': platform.machine(),
            'input': 'generated black 416x416 JPEG in memory; replay mode',
            'samples': samples, 'warmup_runs': 1, 'worker_load_ms': round(load_ms, 3),
            'local_result_ms': summary(durations), 'worker_processing_ms': summary(processing),
            'detections_per_sample': counts, 'worker_metrics': metrics,
            'lineage_preserved': True, 'signal_unknown': True,
            'limits': ['Generated pixels prove execution only; not detection accuracy or clear space.',
                       'Local JPEG/worker timing excludes camera, network and Pi receipt.',
                       'No public result delivery, deployed readiness or motor evidence.']}
    finally:
        if not worker.stop():
            raise RuntimeError('Worker did not stop within shutdown deadline')


def summary(values):
    return {'median': round(statistics.median(values), 3),
            'p95_nearest_rank': round(sorted(values)[math.ceil(len(values) * .95) - 1], 3),
            'max': round(max(values), 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--weights', type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--report', type=Path, help='New JSON evidence file; never overwrite')
    args = parser.parse_args()
    report = json.dumps(run(args.weights, args.samples), indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open('x', encoding='utf-8') as output:
            output.write(report)
    print(report)


if __name__ == '__main__':
    main()
