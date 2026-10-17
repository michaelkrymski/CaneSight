"""Synthetic detector outputs; real decoding and spawned-worker integration.

No model weights, camera scenes or detection-accuracy claims in this suite.
"""
import copy
from dataclasses import dataclass
import io
import json
from pathlib import Path
from types import SimpleNamespace
import time
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from backend.app import AcceptedFrame, SourceGrant, protocol
from backend.inference_worker import InferenceWorker, MAX_RESULT_BYTES
from backend.freshness import CaptureAgeGate
from backend.vision import observations as adapter
from backend.vision.baseline import manifest


class FixtureData:
    def __init__(self, rows):
        self.rows = rows

    def cpu(self):
        return self

    def tolist(self):
        return copy.deepcopy(self.rows)


class FixtureBoxes:
    def __init__(self, rows):
        self.data = FixtureData(rows)

    def __len__(self):
        return len(self.data.rows)


def result(rows=(), width=64, height=32):
    return SimpleNamespace(orig_shape=(height, width),
                           names=dict(enumerate(manifest()['classes'])),
                           boxes=FixtureBoxes(rows))


class FixtureDetector:
    def __init__(self, rows=(), invalid_shape=False):
        self.rows = rows
        self.invalid_shape = invalid_shape
        self.calls = []

    def predict(self, image, **kwargs):
        self.calls.append((image.size, image.mode, kwargs))
        width, height = image.size
        return [result(self.rows, width + int(self.invalid_shape), height)]


@dataclass
class FixtureFactory:
    rows: tuple = ()
    invalid_shape: bool = False

    def __call__(self):
        # Explicit synthetic injection. Production YoloFactory uses the verified
        # baseline loader; the same decoder/mapper executes in the spawned child.
        return adapter._YoloAdapter(FixtureDetector(self.rows, self.invalid_shape))


def frame(mode='replay'):
    buffer = io.BytesIO()
    with Image.new('RGB', (64, 32), 'black') as image:
        image.save(buffer, format='JPEG')
    jpeg = buffer.getvalue()
    root = Path(__file__).resolve().parents[2]
    metadata = json.loads((root / 'shared/protocol/v1/examples/frame.json').read_text(encoding='utf-8'))
    metadata.update(image={'width': 64, 'height': 32}, jpeg_bytes=len(jpeg), mode=mode)
    return AcceptedFrame(metadata, jpeg)


class ObservationTests(unittest.TestCase):
    def test_normalizes_original_rectangular_image_without_swapping_axes(self):
        value = adapter.prediction_from_result(result([[8, 4, 48, 24, .8, 0]]), 64, 32)
        self.assertEqual(value['detections'], [
            {'label': 'person', 'confidence': .8, 'bbox_xyxy': [.125, .125, .75, .75]}])
        self.assertEqual(set(value), {'detections', 'signal'})

    def test_labels_only_map_to_accepted_object_vocabulary(self):
        classes = manifest()['classes']
        names = ['person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck', 'traffic light', 'dog']
        rows = [[0, 0, 64, 32, .9, classes.index(name)] for name in names]
        value = adapter.prediction_from_result(result(rows), 64, 32)
        self.assertEqual([d['label'] for d in value['detections']],
                         names[:6] + ['traffic_light', 'other'])
        # Generic lights are never promoted into pedestrian head candidates.
        self.assertEqual(value['signal'], {'candidate_count': 0, 'symbol': 'unknown',
                                          'confidence': None, 'countdown_s': None})

    def test_empty_detection_keeps_signal_unknown_without_permission_fields(self):
        prediction = adapter.prediction_from_result(result(), 64, 32)
        self.assertEqual(prediction['detections'], [])
        self.assertEqual(prediction['signal']['symbol'], 'unknown')
        self.assertIsNone(prediction['signal']['countdown_s'])
        self.assertEqual(set(prediction), {'detections', 'signal'})

    def test_invalid_geometry_and_confidence_fail_closed(self):
        for row in ([0, 0, 64, 32, float('nan'), 0], [0, 0, 64, 32, 1.1, 0],
                    [-1, 0, 64, 32, .9, 0], [0, 0, 65, 32, .9, 0],
                    [0, 0, 64, 33, .9, 0], [8, 0, 8, 32, .9, 0],
                    [10, 0, 8, 32, .9, 0], [0, 0, 64, float('inf'), .9, 0],
                    [True, 0, 64, 32, .9, 0], [0, 0, 64, 32, .9],
                    [0, 0, 64, 32, 1, .9, 0]):
            with self.subTest(row=row), self.assertRaises(ValueError):
                adapter.prediction_from_result(result([row]), 64, 32)

    def test_bad_class_identity_shape_and_output_count_fail_closed(self):
        for class_id in (-1, .5, 80, float('nan')):
            with self.subTest(class_id=class_id), self.assertRaises(ValueError):
                adapter.prediction_from_result(result([[0, 0, 64, 32, .9, class_id]]), 64, 32)
        for width, height in ((32, 64), (True, 32), (0, 32), (1921, 32), (64, 1081)):
            with self.subTest(width=width, height=height), self.assertRaises(ValueError):
                adapter.prediction_from_result(result(), width, height)
        changed = result()
        changed.names[9] = 'pedestrian signal'
        with self.assertRaises(ValueError):
            adapter.prediction_from_result(changed, 64, 32)
        changed = result()
        changed.boxes = None
        with self.assertRaises(ValueError):
            adapter.prediction_from_result(changed, 64, 32)
        with self.assertRaises(ValueError):
            adapter.prediction_from_result(result([[0, 0, 64, 32, .9, 0]] * 33), 64, 32)

    def test_real_jpeg_decode_preserves_original_metadata_and_bounds(self):
        detector = FixtureDetector([[8, 4, 48, 24, .8, 0]])
        model = adapter._YoloAdapter(detector)
        accepted = frame()
        original = copy.deepcopy(accepted.metadata)
        value = model.predict(accepted)
        self.assertEqual(accepted.metadata, original)
        self.assertEqual(value['detections'][0]['bbox_xyxy'], [.125, .125, .75, .75])
        size, mode, kwargs = detector.calls[0]
        self.assertEqual((size, mode), ((64, 32), 'RGB'))
        self.assertEqual(kwargs['max_det'], 32)
        self.assertFalse(kwargs['save'])
        self.assertFalse(kwargs['verbose'])
        self.assertIn(manifest()['artifact']['sha256'], model.version)
        self.assertLessEqual(len(model.version), 128)

    def test_bad_or_mismatched_image_is_rejected_before_prediction(self):
        accepted = frame()
        detector = FixtureDetector()
        model = adapter._YoloAdapter(detector)
        for image in (b'not an image', accepted.jpeg):
            metadata = copy.deepcopy(accepted.metadata)
            metadata['image']['width'] = 63
            with self.assertRaises((ValueError, OSError)):
                model.predict(AcceptedFrame(metadata, image))
        buffer = io.BytesIO()
        with Image.new('RGB', (64, 32)) as png:
            png.save(buffer, format='PNG')
        with self.assertRaises(ValueError):
            model.predict(AcceptedFrame(accepted.metadata, buffer.getvalue()))
        self.assertEqual(detector.calls, [])

    def test_factory_uses_verified_loader_only_when_called(self):
        with patch.object(adapter, 'load_baseline', return_value=FixtureDetector()) as loader:
            factory = adapter.YoloFactory('operator-controlled-model.pt')
            loader.assert_not_called()
            model = factory()
            loader.assert_called_once_with('operator-controlled-model.pt')
            self.assertEqual(model.predict(frame())['detections'], [])

    def test_spawned_worker_preserves_lineage_and_validates_maximum_result(self):
        rows = tuple([8.125, 4.25, 48.75, 24.5, .8765432101234567, 9] for _ in range(32))
        for mode in ('live', 'replay'):
            with self.subTest(mode=mode):
                worker = InferenceWorker(FixtureFactory(rows), job_timeout=5)
                try:
                    worker.start()
                    self.wait_for(lambda: worker.health()['worker_healthy'])
                    accepted = frame(mode)
                    metadata = accepted.metadata
                    # Explicit synthetic receiver clock: the source captures in
                    # the same boot epoch. Processing must not renew that age.
                    now = [metadata['capture_monotonic_ms'] - 1]
                    gate = CaptureAgeGate(metadata['session_id'], mode,
                        metadata['source_id'], metadata['boot_id'], clock_ms=lambda: now[0])
                    gate.enroll(metadata['source_id'], metadata['boot_id'],
                                {'frame_metadata', 'vision_observation'})
                    gate.set_local_ready(True)
                    now[0] += 1
                    gate.record_frame(metadata)
                    grant = SourceGrant('synthetic-test-credential-not-enrolled', metadata['session_id'],
                        metadata['source_id'], metadata['boot_id'], mode, time.monotonic() + 30)
                    self.assertTrue(worker.submit(grant, metadata, accepted.jpeg))
                    self.wait_for(lambda: worker.metrics()['completed'] == 1)
                    observation = worker.take_result(grant)
                    protocol.validate_message(observation)
                    for key, value in metadata.items():
                        if key not in ('jpeg_bytes', 'type'):
                            self.assertEqual(observation[key], value, key)
                    self.assertEqual(len(observation['detections']), 32)
                    self.assertEqual(observation['type'], 'vision_observation')
                    self.assertGreaterEqual(observation['processing_ms'], 0)
                    self.assertIsNone(observation['signal']['countdown_s'])
                    raw = json.dumps(observation, allow_nan=False, separators=(',', ':')).encode()
                    self.assertLessEqual(len(raw), MAX_RESULT_BYTES)
                    now[0] += 1200
                    eligible = gate.receive(observation)
                    self.assertEqual(eligible.deadline_ms, metadata['capture_monotonic_ms'] + 1500)
                    now[0] = eligible.deadline_ms + .01
                    self.assertIsNone(gate.current(metadata['source_id'], 'vision_observation'))
                    self.assertIsNone(worker.take_result(grant))
                    self.assertEqual(worker.metrics()['model_loads'], 1)
                finally:
                    self.assertTrue(worker.stop())

    def test_invalid_adapter_output_marks_real_worker_unavailable(self):
        worker = InferenceWorker(FixtureFactory(invalid_shape=True), job_timeout=5)
        try:
            worker.start()
            self.wait_for(lambda: worker.health()['worker_healthy'])
            accepted = frame()
            metadata = accepted.metadata
            grant = SourceGrant('synthetic-test-credential-not-enrolled', metadata['session_id'],
                metadata['source_id'], metadata['boot_id'], 'replay', time.monotonic() + 30)
            self.assertTrue(worker.submit(grant, metadata, accepted.jpeg))
            self.wait_for(lambda: worker.metrics()['failed'] == 1)
            self.assertFalse(worker.health()['worker_healthy'])
            self.assertIsNone(worker.take_result(grant))
        finally:
            self.assertTrue(worker.stop())

    def test_missing_pinned_weights_fail_worker_load_without_download(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / 'absent.pt'
            worker = InferenceWorker(adapter.YoloFactory(missing))
            try:
                worker.start()
                self.wait_for(lambda: worker.metrics()['failed'] == 1)
                self.assertFalse(worker.health()['model_available'])
                self.assertFalse(worker.health()['worker_healthy'])
                self.assertFalse(missing.exists())
                self.assertEqual(worker.metrics()['model_loads'], 0)
            finally:
                self.assertTrue(worker.stop())

    def wait_for(self, predicate):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.01)
        self.fail('Bounded worker condition timed out')


if __name__ == '__main__':
    unittest.main()
