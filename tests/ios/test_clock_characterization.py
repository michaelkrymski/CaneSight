import importlib.util
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from clock_characterization import Exchange, Characterization, rate_interval


def exchange(index, *, beta=1.0002, alpha=300, spacing=1100):
    t1 = 100 + index*spacing
    # Explicitly asymmetric network delays; no midpoint-offset assumption.
    outbound, processing, inbound = 15 + index % 7, 5, 35 + index % 11
    return Exchange(t1, alpha+beta*(t1+outbound), alpha+beta*(t1+outbound+processing),
                    t1+outbound+processing+inbound)


class CharacterizationTests(unittest.TestCase):
    def test_affine_interval_encloses_known_rate_with_asymmetric_delays(self):
        low, high = rate_interval([exchange(i) for i in range(20)])
        self.assertLessEqual(low, 1.0002)
        self.assertGreaterEqual(high, 1.0002)
        self.assertGreater(low, 0)

    def test_twenty_calibration_and_separate_twenty_holdout_keep_original_candidate(self):
        model = Characterization()
        for i in range(20): model.add(exchange(i))
        before = model.frozen
        self.assertIsNotNone(model.candidate_ppm)
        for i in range(20, 40): model.add(exchange(i))
        self.assertEqual(before, model.frozen)
        result = model.summary()
        self.assertTrue(result['holdout_consistent'])
        self.assertFalse(result['hardware_drift_limit_verified'])
        self.assertFalse(result['production_drift_configured'])
        self.assertFalse(result['receiver_guidance_eligible'])

    def test_holdout_clock_jump_latches_failure_without_refitting(self):
        model = Characterization()
        for i in range(20): model.add(exchange(i))
        before = model.frozen
        model.add(exchange(20, alpha=1300))
        self.assertTrue(model.failed)
        self.assertIsNone(model.candidate_ppm)
        for i in range(21, 40): model.add(exchange(i))
        self.assertEqual(before, model.frozen)
        self.assertFalse(model.summary()['holdout_consistent'])

    def test_short_run_cannot_claim_qualified_model(self):
        model = Characterization()
        for i in range(19): model.add(exchange(i))
        self.assertIsNone(model.candidate_ppm)
        self.assertFalse(model.summary()['holdout_consistent'])
        fast = Characterization()
        for i in range(20): fast.add(exchange(i, spacing=10))
        self.assertTrue(fast.failed)

    def test_invalid_or_unbounded_exchange_rejected(self):
        for values in [(0, 1, 2, 1001), (0, 2, 1, 10), (0, float('nan'), 1, 10)]:
            with self.assertRaises(ValueError): Exchange(*values)
        with self.assertRaises(ValueError): rate_interval([Exchange(1, 1, 1, 2)])

class ConditionalReceiverTests(unittest.TestCase):
    def test_measured_model_only_reports_conditional_age_and_never_guidance(self):
        import json
        from pi_clock_characterization import State
        grant = dict(session_id='s', source_id='pi', boot_id='pi-boot')
        state = State(grant, 'phone', 'phone-boot'); state.opened()
        heartbeat = json.loads((Path(__file__).resolve().parents[2]/'shared/protocol/v1/examples/heartbeat.json').read_text())
        heartbeat.update(session_id='s', source_id='phone', boot_id='phone-boot', mode='live', state='ready')
        state.receive(json.dumps(heartbeat), 0)
        for i in range(40):
            row = exchange(i)
            request = json.loads(state.probe(grant, row.t1))
            state.receive(json.dumps(dict(request, type='clock_reply', t2_ms=row.t2, t3_ms=row.t3)), row.t4)
        depth = json.loads((Path(__file__).resolve().parents[2]/'shared/protocol/v1/examples/depth.json').read_text())
        depth.update(session_id='s', source_id='phone', boot_id='phone-boot', mode='live',
                     capture_monotonic_ms=300+1.0002*(row.t4+100))
        state.receive(json.dumps(depth), row.t4+150)
        result = state.summary()
        self.assertTrue(result['clock_characterization']['holdout_consistent'])
        self.assertEqual(result['conditional_age_diagnostics']['packets_within_500ms_and_100ms_halfwidth'], 1)
        self.assertFalse(result['clock_characterization']['receiver_guidance_eligible'])
        self.assertEqual(result['capture_age_eligibility'], 'unknown')
