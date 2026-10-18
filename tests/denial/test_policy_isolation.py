"""Real accepted policy + narration controllers; synthetic clock/client/output.

No GPS transport exists in accepted v1. Its unsupported-input boundary is tested
here; actual portable GPS authorization/cache tests run separately in Swift.
"""
import copy
import io
import json
from pathlib import Path
import types
import unittest

from PIL import Image
from jsonschema import ValidationError
from backend.context.consumer import ContextNarration
from backend.freshness import CaptureAgeGate
from edge.context_client import ContextError
from edge.haptics import HapticScheduler, SimulatedOutput
from edge.policy import LocalPolicy
from edge.uploader import Frame, Mapping

ROOT = Path(__file__).resolve().parents[2]


class Sink:
    def __init__(self):
        self.spoken = []
        self.current = None

    def speak(self, text):
        self.current = text
        self.spoken.append(text)

    def stop(self):
        self.current = None


class Handle:
    def __init__(self, request_id, frame):
        self.cancelled = False
        self.value = None
        self.error = None
        self.reply = dict(request_id=request_id, frame=copy.deepcopy(frame.metadata),
                          model='gemini-fixture', capture_age_bounded=False,
                          description={'objects': ['chair'], 'uncertain': True})

    def poll(self):
        if self.error:
            raise self.error
        return self.value

    def cancel(self):
        self.cancelled = True


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.clock = lambda: self.now
        self.gate = CaptureAgeGate('session', 'replay', 'pi', 'pi-boot',
                                   clock_ms=self.clock, relative_drift_ppm=0)
        self.gate.enroll('phone', 'phone-boot', {'heartbeat', 'depth_observation'})
        probe = self.gate.start_probe('phone')
        self.gate.finish_probe(dict(probe, type='clock_reply', t2_ms=self.now, t3_ms=self.now))
        self.seq = 0
        self.gate.receive(dict(self.message('heartbeat'), state='ready'))
        self.scheduler = HapticScheduler(SimulatedOutput(), clock=self.clock)
        self.policy = LocalPolicy(self.gate, 'phone', self.scheduler, clock=self.clock)
        self.policy.arm(True)
        self.addCleanup(self.scheduler.close)
        self.addCleanup(self.policy.close)
        self.now += 500
        self.depth(2)
        self.now += 100
        self.depth(2)
        self.sink = Sink()
        self.handles = []
        self.consent = True
        self.start_error = None
        self.frame = self.make_frame()

        def start(request_id, frame):
            if self.start_error:
                raise self.start_error
            handle = Handle(request_id, frame)
            self.handles.append(handle)
            return handle

        def priority():
            state = self.policy.snapshot()
            return (state['health']['depth'] == 'fresh',
                    'nearby' in state['hazards'].values())

        self.consumer = ContextNarration(lambda: self.frame,
            types.SimpleNamespace(start=start), self.sink, priority=priority,
            consent=lambda: self.consent, clock=self.clock)
        self.addCleanup(self.consumer.close)

    def message(self, kind):
        self.seq += 1
        return dict(schema_version=1, type=kind, session_id='session', mode='replay',
                    source_id='phone', boot_id='phone-boot', seq=self.seq,
                    capture_monotonic_ms=self.now, capture_utc=None)

    def depth(self, distance):
        message = dict(self.message('depth_observation'), tracking='normal',
                       sectors={name: dict(distance_m=distance if name == 'left' else None,
                                           valid_fraction=1)
                                for name in ('left', 'center', 'right')})
        self.gate.receive(message)
        self.policy.tick()
        return message

    def make_frame(self):
        out = io.BytesIO()
        Image.new('RGB', (32, 24), 'gray').save(out, 'JPEG')
        frame = json.loads((ROOT / 'shared/protocol/v1/examples/frame.json').read_text())
        frame.update(capture_monotonic_ms=self.now, jpeg_bytes=len(out.getvalue()),
                     image={'width': 32, 'height': 24})
        return Frame(frame, Mapping(), out.getvalue())

    def policy_state(self):
        return (self.policy.snapshot(), self.scheduler.snapshot()['outputs'], self.scheduler.accepted)

    def begin(self):
        self.assertTrue(self.consumer.request())
        self.assertEqual(len(self.handles), 1)
        return self.handles[0]

    def test_provider_denial_cannot_mutate_fresh_policy(self):
        before = self.policy_state()
        self.start_error = ContextError(fatal=True)
        self.assertFalse(self.consumer.request())
        self.consumer.tick()
        self.assertEqual(self.consumer.snapshot()['button']['failed'], 1)
        self.assertEqual(self.policy_state(), before)
        self.assertEqual(self.sink.spoken, [])
        self.assertEqual(self.handles, [])

    def test_request_factory_failure_isolated_for_each_error(self):
        # Fresh controller per fault so cooldown cannot hide later injections.
        for error in (ContextError(), TimeoutError(), RuntimeError()):
            with self.subTest(error=type(error).__name__):
                calls = []
                def fail(*args):
                    calls.append(True)
                    raise error
                consumer = ContextNarration(lambda: self.frame,
                    types.SimpleNamespace(start=fail), Sink(), priority=lambda: (True, False),
                    consent=lambda: True, clock=self.clock)
                try:
                    before = self.policy_state()
                    self.assertFalse(consumer.request())
                    self.assertEqual(calls, [True])
                    self.assertEqual(self.policy_state(), before)
                finally:
                    consumer.close()

    def test_late_result_after_depth_expiry_cannot_restore_health_or_speak(self):
        handle = self.begin()
        self.now += 501  # Depth has a shorter budget than optional narration.
        self.policy.tick()
        before = self.policy_state()
        handle.value = handle.reply
        self.consumer.tick()
        self.assertTrue(handle.cancelled)
        self.assertEqual(self.policy_state(), before)
        self.assertEqual(before[0]['health']['depth'], 'no-fresh-depth')
        self.assertEqual(set(before[0]['hazards'].values()), {'unknown'})
        self.assertEqual(self.sink.spoken, [])

    def test_hazard_preempts_pending_context_without_cancelling_motor_evidence(self):
        handle = self.begin()
        self.now += 10
        self.depth(.5)
        self.assertTrue(self.scheduler.snapshot()['outputs']['left'])
        deadline = self.scheduler.channels['left'].deadline_ms
        before = self.policy_state()
        handle.value = handle.reply
        self.consumer.tick()
        self.assertTrue(handle.cancelled)
        self.assertEqual(self.policy_state(), before)
        self.assertEqual(self.sink.spoken, [])
        self.now = deadline
        self.policy.tick()
        self.assertFalse(any(self.scheduler.snapshot()['outputs'].values()))

    def test_cancel_and_consent_withdrawal_fence_late_result_even_after_recovery(self):
        for reason in ('cancel', 'withdraw'):
            with self.subTest(reason=reason):
                # Separate consumer, same independent healthy policy.
                handles = []
                def start(rid, frame):
                    h = Handle(rid, frame); handles.append(h); return h
                consumer = ContextNarration(lambda: self.frame,
                    types.SimpleNamespace(start=start), self.sink,
                    priority=lambda: (True, False),
                    consent=lambda: self.consent, clock=self.clock)
                try:
                    self.consent = True
                    self.assertTrue(consumer.request())
                    h = handles[0]
                    before = self.policy_state()
                    if reason == 'cancel':
                        consumer.cancel()
                    else:
                        self.consent = False
                        consumer.tick()
                    h.value = h.reply
                    self.consent = True
                    consumer.tick()
                    self.assertTrue(h.cancelled)
                    self.assertEqual(self.policy_state(), before)
                    self.assertEqual(self.sink.spoken, [])
                finally:
                    consumer.close()

    def test_poll_failure_cannot_revive_or_retrigger_motor_policy(self):
        handle = self.begin()
        before = self.policy_state()
        handle.error = ContextError(fatal=True)
        self.consumer.tick()
        self.assertTrue(handle.cancelled)
        handle.error = None
        handle.value = handle.reply
        self.consumer.tick()
        self.assertEqual(self.policy_state(), before)
        self.assertEqual(self.sink.spoken, [])

    def test_context_success_does_not_extend_depth_deadline(self):
        handle = self.begin()
        depth_deadline = self.gate.current('phone', 'depth_observation').deadline_ms
        before = self.policy_state()
        handle.value = handle.reply
        self.consumer.tick()
        self.assertEqual(self.sink.spoken, ['AI description, uncertain: Possible chair.'])
        self.assertEqual(self.policy_state(), before)
        self.assertEqual(self.gate.current('phone', 'depth_observation').deadline_ms, depth_deadline)
        self.now = depth_deadline + 1
        self.policy.tick()
        self.consumer.tick()
        self.assertIsNone(self.sink.current)
        self.assertEqual(self.policy.snapshot()['guidance'], 'unavailable')

    def test_unreviewed_gps_or_permission_fields_cannot_enter_depth_policy(self):
        baseline = self.policy_state()
        # Proposed location shapes are deliberately rejected, not a GPS wire API.
        for extra in ({'location': {'unavailable': 'unauthorized'}},
                      {'location': {'unavailable': 'staleFix'}},
                      {'description': {'objects': ['chair'], 'uncertain': True}},
                      {'safe_to_cross': True}):
            with self.subTest(field=next(iter(extra))):
                message = dict(self.message('depth_observation'), tracking='normal',
                    sectors={name: dict(distance_m=.5, valid_fraction=1)
                             for name in ('left', 'center', 'right')}, **extra)
                with self.assertRaises(ValidationError):
                    self.gate.receive(message)
                self.policy.tick()
                self.assertEqual(self.policy_state(), baseline)

    def test_context_deadline_rejects_reply_even_with_new_healthy_depth(self):
        handle = self.begin()
        self.now = self.frame.metadata['capture_monotonic_ms'] + 8000
        self.gate.receive(dict(self.message('heartbeat'), state='ready'))
        self.depth(2)
        self.now += 1
        self.depth(2)
        before = self.policy_state()
        handle.value = handle.reply
        self.consumer.tick()
        self.assertTrue(handle.cancelled)
        self.assertEqual(self.policy_state(), before)
        self.assertEqual(self.sink.spoken, [])

    def test_stale_original_frame_cannot_start_provider_or_change_policy(self):
        self.frame.metadata['capture_monotonic_ms'] = self.now - 1501
        before = self.policy_state()
        self.assertFalse(self.consumer.request())
        self.assertEqual(self.handles, [])
        self.assertEqual(self.policy_state(), before)
        self.assertEqual(self.sink.spoken, [])
