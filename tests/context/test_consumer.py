"""Original-frame button/client/narration composition with a synthetic sink."""
import copy
import io
import json
from pathlib import Path
import threading
import types
import unittest

from PIL import Image

from backend.context.consumer import ContextNarration
from edge.uploader import Frame, Mapping


class Sink:
    def __init__(self):
        self.current = None
        self.spoken = []
        self.stopped = threading.Event()
    def speak(self, text):
        self.current = text
        self.spoken.append(text)
    def stop(self):
        self.current = None
        self.stopped.set()


def generated_frame(now):
    output = io.BytesIO()
    Image.new('RGB', (32, 24), 'gray').save(output, 'JPEG')
    metadata = json.loads((Path(__file__).resolve().parents[2]/'shared/protocol/v1/examples/frame.json').read_text())
    metadata.update(capture_monotonic_ms=now, jpeg_bytes=len(output.getvalue()),
                    image={'width': 32, 'height': 24})
    return Frame(metadata, Mapping(), output.getvalue())


class Handle:
    def __init__(self, request_id, frame):
        self.value = None
        self.cancelled = False
        self.reply = dict(request_id=request_id, frame=copy.deepcopy(frame.metadata),
            model='gemini-fixture', capture_age_bounded=False,
            description={'objects': ['chair'], 'uncertain': True})
    def poll(self): return self.value
    def cancel(self): self.cancelled = True


class ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.ready, self.hazard, self.consent = True, False, True
        self.frame = generated_frame(self.now)
        self.sink, self.handles = Sink(), []
        def start(request_id, frame):
            handle = Handle(request_id, frame)
            self.handles.append(handle)
            return handle
        self.consumer = ContextNarration(lambda: self.frame,
            types.SimpleNamespace(start=start), self.sink,
            priority=lambda: (self.ready, self.hazard), consent=lambda: self.consent,
            clock=lambda: self.now)
        self.addCleanup(self.consumer.close)

    def press(self):
        self.consumer.sample(False)
        self.now += 30
        self.consumer.tick()
        self.consumer.sample(True)
        self.now += 30
        self.consumer.tick()

    def deliver(self):
        self.handles[-1].value = self.handles[-1].reply
        self.consumer.tick()

    def test_snapshot_exposes_request_counts_without_frame_or_audio_acceptance(self):
        self.press()
        status = self.consumer.snapshot()
        self.assertEqual(status['button']['requests'], 1)
        self.assertTrue(status['button']['requesting'])
        self.assertFalse(status['audio_delivery_verified'])
        self.assertNotIn('frame', json.dumps(status))
        self.deliver()
        self.assertTrue(self.consumer.snapshot()['result_delivered'])
        self.consumer.cancel()
        self.assertFalse(self.consumer.snapshot()['result_delivered'])

    def test_original_capture_bounds_audio_through_network_time(self):
        self.press()
        self.now = 5000
        self.deliver()
        self.assertEqual(self.sink.current, 'AI description, uncertain: Possible chair.')
        self.consumer.sample(True)  # A held level is not a new cancel press.
        self.assertIsNotNone(self.sink.current)
        self.now = 8999
        self.consumer.tick()
        self.assertIsNotNone(self.sink.current)
        self.now = 9000
        self.consumer.tick()
        self.assertIsNone(self.sink.current)
        self.assertEqual(len(self.sink.spoken), 1)

    def test_manual_cancel_and_second_press_preempt_pending_result(self):
        for method in ('cancel', 'second-press'):
            with self.subTest(method=method):
                self.setUp()
                self.press()
                if method == 'cancel': self.consumer.cancel()
                else: self.press()
                self.assertTrue(self.handles[0].cancelled)
                self.deliver()
                self.assertEqual(self.sink.spoken, [])

    def test_hazard_unavailable_and_consent_loss_stop_audio_and_never_resume(self):
        for field, value in (('hazard', True), ('ready', False), ('hazard', None), ('consent', False)):
            with self.subTest(field=field):
                self.setUp()
                self.press()
                self.deliver()
                setattr(self, field, value)
                self.consumer.tick()
                self.assertIsNone(self.sink.current)
                self.ready, self.hazard, self.consent = True, False, True
                self.consumer.tick()
                self.assertEqual(len(self.sink.spoken), 1)

    def test_new_press_interrupts_playing_audio_without_bypassing_cooldown(self):
        self.press()
        self.deliver()
        self.press()
        self.assertIsNone(self.sink.current)
        self.assertEqual(len(self.handles), 1)
        self.deliver()
        self.assertEqual(len(self.sink.spoken), 1)

    def test_retimed_or_injected_reply_never_reaches_speech(self):
        for mutate in (lambda v: v['frame'].update(capture_monotonic_ms=1050),
                       lambda v: v['description'].update(objects=['go forward']),
                       lambda v: v.update(request_id='foreign-request')):
            with self.subTest(mutation=mutate):
                self.setUp()
                self.press()
                mutate(self.handles[0].reply)
                self.deliver()
                self.assertEqual(self.sink.spoken, [])
                self.assertTrue(self.handles[0].cancelled)

    def test_clock_reversal_stops_audio_and_latches_button_fault(self):
        self.press()
        self.deliver()
        self.now -= 1
        self.consumer.tick()
        self.assertIsNone(self.sink.current)
        self.now = 12000
        self.frame = generated_frame(self.now)
        self.press()
        self.assertEqual(len(self.handles), 1)
        self.assertEqual(len(self.sink.spoken), 1)

    def test_independent_worker_preempts_without_new_input_or_network_poll(self):
        self.press()
        self.deliver()
        self.sink.stopped.clear()
        self.consumer.start()
        self.hazard = True
        self.assertTrue(self.sink.stopped.wait(.5))
        self.assertIsNone(self.sink.current)

    def test_invalid_input_and_close_stop_audio(self):
        self.press()
        self.deliver()
        self.consumer.sample('press')
        self.assertIsNone(self.sink.current)
        self.consumer.close()
        self.assertFalse(self.consumer.sample(True))
        with self.assertRaises(ValueError): self.consumer.start()

    def test_speech_engine_health_blocks_requests_and_preempts_audio(self):
        self.sink.healthy = lambda: False
        self.press()
        self.assertEqual(self.handles, [])
        self.sink.healthy = lambda: True
        self.press()
        self.deliver()
        self.assertIsNotNone(self.sink.current)
        self.sink.healthy = lambda: False
        self.consumer.tick()
        self.assertIsNone(self.sink.current)
