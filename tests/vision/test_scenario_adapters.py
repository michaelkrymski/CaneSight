"""Synthetic replay failure/transition tests; no real scene accuracy claim."""
from dataclasses import replace
import json
import unittest

from PIL import Image

from backend.vision.scenario_adapters import (
    BeaconSample, ReplayFrame, ScenarioReplay, VehicleSample, live_capabilities,
)
from backend.vision.signal_fixtures import PACK


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.adapter = ScenarioReplay()
        self.token = self.select()

    def select(self, scenario='pedestrian_yellow_beacon', **kw):
        return self.adapter.select(scenario, **(dict(source_id='camera', session_id='session', boot_id='boot') | kw))

    def frame(self, ms, **kw):
        return replace(ReplayFrame('camera', 'session', 'boot', ms+1, ms), **kw)

    def sample(self, on=True, **kw):
        return replace(BeaconSample('beacon-a', (.1, .1, .2, .3), on), **kw)

    def observe(self, ms, **kw):
        return self.adapter.observe(self.token, self.frame(ms), replay_ms=ms, **kw)

    def alternating(self, **kw):
        result = None
        for ms in range(0, 901, 100):
            result = self.observe(ms, beacon=self.sample((ms//200) % 2 == 0, **kw))
        return result

    def vehicle(self, track='car-a', x=.1, **kw):
        return replace(VehicleSample(track, (x, .2, x+.1, .4)), **kw)

    def test_requires_explicit_selection_and_never_enables_live(self):
        a = ScenarioReplay()
        self.assertEqual(a.observe(None, self.frame(0), replay_ms=0).reason, 'selection_required')
        for scenario in (None, '', 'automatic', 'traffic_light'):
            with self.assertRaises(ValueError):
                a.select(scenario, source_id='camera', session_id='session', boot_id='boot')
        self.assertEqual(set(live_capabilities().values()), {False})
        self.assertFalse(self.alternating().live_supported)

    def test_live_or_non_synthetic_inputs_cancel_without_observations(self):
        for fields in ({'mode':'live'}, {'provenance':'gemini'}, {'provenance':'coco_traffic_light'}):
            self.token = self.select()
            result = self.adapter.observe(self.token, self.frame(0, **fields), replay_ms=0,
                                          beacon=self.sample())
            self.assertEqual(result.reason, 'synthetic_replay_only')
            self.assertEqual((result.symbol, result.beacon_state, result.vehicles), ('unknown', 'unknown', ()))
            self.assertIsNone(self.adapter.selection)

    def test_single_yellow_frame_and_vehicle_light_do_not_establish_beacon(self):
        self.assertEqual(self.observe(0, beacon=self.sample()).beacon_state, 'unknown')
        self.token = self.select()
        self.assertEqual(self.alternating(kind='vehicle_yellow_light').beacon_state, 'unknown')

    def test_dense_annotated_two_cycles_are_replay_only(self):
        result = self.alternating()
        self.assertEqual(result.beacon_state, 'alternating_replay_evidence')
        self.assertEqual(result.symbol, 'unknown')
        self.assertIsNone(result.countdown_s)
        self.assertEqual(result.captured_ms, 900)
        self.assertEqual(result.mode, 'replay')

    def test_sparse_one_hz_samples_and_fast_flicker_remain_unknown(self):
        for step in (1000, 50):
            self.adapter = ScenarioReplay(); self.token = self.select()
            for i in range(6):
                result = self.observe(i*step, beacon=self.sample(i % 2 == 0))
            self.assertEqual(result.beacon_state, 'unknown')

    def test_target_or_region_change_cannot_reuse_alternation(self):
        for change in ({'target_id':'beacon-b'}, {'box_xyxy':(.2, .1, .3, .3)}):
            self.adapter = ScenarioReplay(); self.token = self.select()
            self.assertNotEqual(self.alternating().beacon_state, 'unknown')
            self.assertEqual(self.observe(1000, beacon=self.sample(**change)).beacon_state, 'unknown')

    def test_missing_malformed_or_occluded_beacon_resets_history(self):
        for bad in (None, self.sample(illuminated=1), self.sample(box_xyxy=(.2,.2,.1,.1))):
            self.adapter = ScenarioReplay(); self.token = self.select()
            self.alternating()
            self.assertEqual(self.observe(1000, beacon=bad).beacon_state, 'unknown')
            self.assertEqual(self.observe(1100, beacon=self.sample()).beacon_state, 'unknown')

    def test_motion_night_or_visibility_loss_cancel_and_require_new_selection(self):
        for fields, reason in [({'camera_motion':'moving'}, 'camera_motion_or_visibility_unknown'),
                               ({'camera_motion':'unknown'}, 'camera_motion_or_visibility_unknown'),
                               ({'visibility':'occluded'}, 'camera_motion_or_visibility_unknown'),
                               ({'lighting':'night'}, 'unsupported_lighting')]:
            self.adapter = ScenarioReplay(); self.token = self.select(); self.alternating()
            result = self.adapter.observe(self.token, self.frame(1000, **fields), replay_ms=1000)
            self.assertEqual(result.reason, reason)
            self.assertIsNone(self.adapter.selection)
            self.assertEqual(self.observe(1100, beacon=self.sample()).beacon_state, 'unknown')

    def test_expiry_poll_does_not_renew_original_capture_or_resume(self):
        self.alternating()
        self.assertEqual(self.adapter.current(2400).captured_ms, 900)
        self.assertEqual(self.adapter.current(2401).reason, 'expired')
        self.assertIsNone(self.adapter.selection)
        self.assertIsNone(self.observe(2500, beacon=self.sample()).captured_ms)

    def test_delayed_future_and_nonfinite_or_boolean_time_cancel(self):
        for capture, now in [(0,1501), (100,99), (True,100), (float('nan'),100), (-1,100)]:
            self.adapter = ScenarioReplay(); self.token = self.select()
            r = self.adapter.observe(self.token, self.frame(0,captured_ms=capture), replay_ms=now)
            self.assertEqual(r.reason, 'invalid_or_expired_frame')

    def test_wrong_epoch_cancels_and_new_epoch_needs_new_controller(self):
        self.observe(0, beacon=self.sample())
        r = self.adapter.observe(self.token, self.frame(100,boot_id='new'), replay_ms=100)
        self.assertEqual(r.reason, 'source_epoch_changed')
        with self.assertRaises(ValueError):
            self.select(boot_id='new')

    def test_switch_and_old_completion_cannot_contaminate_new_scenario_or_clock(self):
        old = self.token; self.alternating()
        self.token = self.select('unsignalized_street')
        r = self.observe(1000, vehicles=(self.vehicle(),))
        self.assertEqual(r.beacon_state, 'unknown')
        self.assertEqual(r.vehicles[0].state, 'unknown')
        late = self.adapter.observe(old, self.frame(1200), replay_ms=100000, beacon=self.sample())
        self.assertEqual(late.reason, 'superseded_selection')
        self.assertEqual(late.vehicles, ())
        self.assertEqual(self.adapter.result, r)
        self.assertEqual(self.adapter.clock, 1000)

    def test_switch_does_not_reset_capture_or_sequence_high_water(self):
        self.observe(100, beacon=self.sample())
        self.token = self.select('unsignalized_street')
        self.assertEqual(self.observe(100).reason, 'replayed_or_reordered_frame')

    def test_backward_clock_latches_even_after_selection(self):
        self.observe(100, beacon=self.sample())
        self.assertEqual(self.adapter.current(99).reason, 'replay_clock_invalid')
        with self.assertRaises(ValueError):
            self.select()

    def test_payload_isolation_and_no_gemini_traffic_verdict_input(self):
        self.token = self.select('unsignalized_street')
        self.assertEqual(self.observe(0, beacon=self.sample()).reason, 'scenario_payload_mismatch')
        self.token = self.select('pedestrian_signal')
        self.assertEqual(self.observe(100, vehicles=(self.vehicle(),)).reason, 'scenario_payload_mismatch')
        with self.assertRaises(TypeError):
            self.observe(200, gemini_verdict='stopped')

    def test_vehicle_displacement_is_image_evidence_not_speed_stop_or_yield(self):
        self.token = self.select('unsignalized_street')
        self.assertEqual(self.observe(0,vehicles=(self.vehicle(),)).vehicles[0].state, 'unknown')
        result = self.observe(100, vehicles=(self.vehicle(x=.13),))
        self.assertEqual(result.vehicles[0].state, 'image_displacement_observed')
        self.assertAlmostEqual(result.vehicles[0].displacement_xy[0], .03)
        self.assertEqual(result.symbol, 'unknown')
        same = self.observe(200, vehicles=(self.vehicle(x=.13),))
        self.assertEqual(same.vehicles[0].state, 'unknown')
        self.assertIsNone(same.vehicles[0].displacement_xy)

    def test_hidden_missing_track_and_large_jump_need_new_continuity(self):
        for second in ((), (self.vehicle(visible=False),), (self.vehicle(x=.7),)):
            self.adapter = ScenarioReplay();self.token = self.select('unsignalized_street')
            self.observe(0, vehicles=(self.vehicle(),))
            self.observe(100, vehicles=second)
            r = self.observe(200,vehicles=(self.vehicle(x=.13),))
            self.assertEqual(r.vehicles[0].state, 'unknown')

    def test_tracks_are_independent_and_empty_frame_does_not_mean_clear(self):
        self.token = self.select('unsignalized_street')
        self.observe(0, vehicles=(self.vehicle(), self.vehicle('car-b', .5)))
        r = self.observe(100, vehicles=(self.vehicle(x=.13), self.vehicle('car-b', .5)))
        self.assertEqual([v.state for v in r.vehicles], ['image_displacement_observed','unknown'])
        empty = self.observe(200)
        self.assertEqual((empty.reason,empty.symbol,empty.vehicles), ('needs_temporal_evidence','unknown',()))

    def test_sparse_vehicle_samples_do_not_establish_motion(self):
        self.token = self.select('unsignalized_street')
        self.observe(0, vehicles=(self.vehicle(),))
        self.assertEqual(self.observe(1000,vehicles=(self.vehicle(x=.15),)).vehicles[0].state, 'unknown')

    def test_invalid_unbounded_duplicate_and_nonfinite_tracks_cancel(self):
        for samples in [(self.vehicle(),)*2, tuple(self.vehicle('car'+str(i)) for i in range(17)),
                        (self.vehicle(box_xyxy=(0,0,float('nan'),1)),), [],
                        (self.vehicle(box_xyxy=(0,0,10**1000,1)),),
                        (self.vehicle(visible=1),), (self.vehicle(track='bad space'),)]:
            self.adapter = ScenarioReplay();self.token = self.select('unsignalized_street')
            self.assertEqual(self.observe(0,vehicles=samples).reason, 'invalid_vehicle_annotations')

    def test_long_replay_keeps_bounded_state(self):
        for ms in range(0,100000,100):
            self.observe(ms,beacon=self.sample((ms//200)%2 == 0),vehicles=(self.vehicle(),))
        self.assertLessEqual(len(self.adapter.beacon.samples),16)
        self.assertLessEqual(len(self.adapter.vehicle.previous),16)

    def test_original_pixel_parser_confirmation_countdown_and_switch_reset(self):
        self.token = self.select('pedestrian_signal')
        doc = json.loads((PACK/'manifest.json').read_text(encoding='utf-8'))
        case = next(c for c in doc['cases'] if c['id']=='countdown')
        for i in range(2):
            fixture = case['frames'][i]
            with Image.open(PACK/fixture['file']) as image:
                result = self.observe(i*1000,image=image,target_id='panel',manual_rois=fixture['manual_rois'])
        self.assertEqual((result.symbol,result.countdown_s), ('dont_walk',11))
        self.token = self.select('pedestrian_signal')
        with Image.open(PACK/case['frames'][1]['file']) as image:
            result = self.observe(1100,image=image,target_id='panel',manual_rois=case['frames'][1]['manual_rois'])
        self.assertEqual(result.symbol,'unknown')
        self.assertIsNone(result.countdown_s)


if __name__ == '__main__':
    unittest.main()
