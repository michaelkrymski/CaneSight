"""CS-035: pinned YOLO detections for the accepted bounded inference worker.

This adapter returns evidence only. The worker owns original frame provenance,
processing duration and schema validation; receiving devices own capture age.
Importing this module loads no model or optional inference dependencies.
"""
from dataclasses import dataclass
import io
import math
from pathlib import Path

from .baseline import DEFAULT_WEIGHTS, check_classes, load_baseline, manifest

MAX_DETECTIONS = 32
LABELS = frozenset(('person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck'))


def prediction_from_result(result, width, height):
    """Map original-image pixel boxes into the existing normalized wire schema.

    Reject malformed output rather than clamp, retime, or invent observations.
    A generic traffic light is an object, not an identified pedestrian head.
    """
    if (type(width) is not int or type(height) is not int
            or not 1 <= width <= 1920 or not 1 <= height <= 1080
            or tuple(result.orig_shape) != (height, width)):
        raise ValueError('Detector image dimensions do not match original frame')
    classes = check_classes(result.names)
    boxes = result.boxes
    if boxes is None or len(boxes) > MAX_DETECTIONS:
        raise ValueError('Missing or unbounded detector boxes')
    rows = boxes.data.cpu().tolist()
    if len(rows) != len(boxes):
        raise ValueError('Inconsistent detector boxes')
    detections = []
    for row in rows:
        if (len(row) != 6 or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                or not math.isfinite(v) for v in row)):
            raise ValueError('Expected finite untracked detector boxes')
        x1, y1, x2, y2, confidence, class_id = row
        if (not 0 <= x1 < x2 <= width or not 0 <= y1 < y2 <= height
                or not 0 <= confidence <= 1 or class_id != int(class_id)
                or not 0 <= class_id < len(classes)):
            raise ValueError('Invalid box, confidence or class ID')
        name = classes[int(class_id)]
        label = 'traffic_light' if name == 'traffic light' else name if name in LABELS else 'other'
        detections.append({'label': label, 'confidence': confidence,
                           'bbox_xyxy': [x1 / width, y1 / height, x2 / width, y2 / height]})
    return {'detections': detections,
            'signal': {'candidate_count': 0, 'symbol': 'unknown',
                       'confidence': None, 'countdown_s': None}}


class _YoloAdapter:
    def __init__(self, model):
        self.model = model
        spec = manifest()
        self.version = spec['model'] + '-sha256-' + spec['artifact']['sha256']

    def predict(self, frame):
        from PIL import Image
        dimensions = frame.metadata['image']
        width, height = dimensions['width'], dimensions['height']
        if (type(width) is not int or type(height) is not int
                or not 1 <= width <= 1920 or not 1 <= height <= 1080
                or not isinstance(frame.jpeg, bytes) or not 0 < len(frame.jpeg) <= 1_000_000):
            raise ValueError('Bounded validated JPEG required')
        # Decode only after verifying dimensions. Preserve uploaded image axes;
        # EXIF orientation is not applied and no camera calibration is inferred.
        with Image.open(io.BytesIO(frame.jpeg)) as encoded:
            if encoded.format != 'JPEG' or encoded.size != (width, height):
                raise ValueError('JPEG dimensions differ from original metadata')
            image = encoded.convert('RGB')
        try:
            results = self.model.predict(image, device='cpu', imgsz=416, rect=False,
                conf=0.25, iou=0.7, max_det=MAX_DETECTIONS, half=False,
                augment=False, save=False, save_txt=False, save_crop=False,
                show=False, verbose=False)
            if len(results) != 1:
                raise ValueError('Expected one original-image detector result')
            return prediction_from_result(results[0], width, height)
        finally:
            image.close()


@dataclass(frozen=True)
class YoloFactory:
    """Picklable trusted factory; verifies local weights/runtime in the child.

    No implicit download, retraining, service activation or credential access.
    Pass this factory to backend.inference_worker.InferenceWorker.
    """
    weights: str | Path = DEFAULT_WEIGHTS

    def __call__(self):
        return _YoloAdapter(load_baseline(self.weights))
