"""Run actual CPU inference on generated pixels, without training or image files."""
import argparse
import json
import math
from pathlib import Path
import platform
import statistics
import time

from .baseline import DEFAULT_WEIGHTS, check_classes, load_baseline, manifest, runtime_versions


def run(weights=DEFAULT_WEIGHTS, samples=20):
    if type(samples) is not int or not 1 <= samples <= 100:
        raise ValueError('Use 1..100 samples')
    started = time.perf_counter()
    model = load_baseline(weights)
    load_ms = (time.perf_counter() - started) * 1000
    from PIL import Image
    # This image tests execution only. No real scene or recognition accuracy is
    # inferred from synthetic pixels or the absence of detections.
    image = Image.new('RGB', (416, 416), 'black')
    durations, counts = [], []
    for i in range(samples + 1):
        started = time.perf_counter()
        result = model.predict(image, device='cpu', imgsz=416, rect=False,
                               conf=0.25, iou=0.7, max_det=32, half=False,
                               augment=False, save=False, save_txt=False,
                               save_crop=False, show=False, verbose=False)
        elapsed = (time.perf_counter() - started) * 1000
        if len(result) != 1 or result[0].orig_shape != (416, 416):
            raise ValueError('Unexpected inference output shape')
        check_classes(result[0].names)
        boxes = result[0].boxes
        if boxes is None or len(boxes) > 32 or not bool(boxes.data.isfinite().all()):
            raise ValueError('Invalid or unbounded detector output')
        if i:  # Discard the one warmup run.
            durations.append(elapsed)
            counts.append(len(boxes))
    return {
        'task': 'CS-034', 'model': manifest()['model'],
        'artifact_sha256': manifest()['artifact']['sha256'],
        'artifact_bytes': manifest()['artifact']['bytes'],
        'license': manifest()['license']['publisher_identifier'],
        'runtime': runtime_versions(), 'python': platform.python_version(),
        'platform': platform.system(), 'machine': platform.machine(),
        'device': 'cpu', 'input': 'generated all-black RGB; 416x416; no image file',
        'parameters': {'imgsz': 416, 'conf': 0.25, 'iou': 0.7, 'max_det': 32},
        'warmup_runs': 1, 'samples': samples,
        'load_ms': round(load_ms, 3),
        'wall_prediction_ms': {
            'median': round(statistics.median(durations), 3),
            'p95_nearest_rank': round(sorted(durations)[math.ceil(samples * .95) - 1], 3),
            'max': round(max(durations), 3),
        },
        'detections_per_sample': counts,
        'loaded_classes': check_classes(model.names),
        'pedestrian_signal_supported': False,
        'limits': [
            'Execution smoke only; not detection accuracy or absence-of-hazard evidence.',
            'Local laptop CPU timings; not Pi, deployed backend or end-to-end latency.',
            'Generic traffic light is not pedestrian WALK/hand/countdown recognition.',
            'No training, service activation, readiness or crossing permission.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--weights', type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--report', type=Path, help='Optional new JSON evidence file; never overwrite')
    args = parser.parse_args()
    report = json.dumps(run(args.weights, args.samples), indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open('x', encoding='utf-8') as output:
            output.write(report)
    print(report)


if __name__ == '__main__':
    main()
