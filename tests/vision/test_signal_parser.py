"""Replay/profile rule tests, not real-world recognition accuracy evidence."""
import copy
import json
import unittest

from PIL import Image, ImageDraw

from backend.vision.signal_fixtures import PACK
from backend.vision.signal_parser import ReplaySignalParser, read_digit, segment_template


class ParserTests(unittest.TestCase):
    def setUp(self):
        doc = json.loads((PACK/'manifest.json').read_text(encoding='utf-8'))
        self.cases = {c['id']:c for c in doc['cases']}
        self.parser = ReplaySignalParser()

    def observe(self, case='walk_like', frame=0, seq=1, ms=0, target='target-a', **overrides):
        fixture = self.cases[case]['frames'][frame]
        args = dict(mode='replay',sequence=seq,replay_ms=ms,target_id=target,
                    manual_rois=copy.deepcopy(fixture['manual_rois']))
        args.update(overrides)
        with Image.open(PACK/fixture['file']) as im:
            return self.parser.observe(im,**args)

    def test_single_shape_requires_separate_temporal_confirmation(self):
        first = self.observe()
        self.assertEqual(first.symbol,'unknown')
        self.assertEqual(first.reason,'needs_temporal_confirmation')
        fast = self.observe(seq=2,ms=1)
        self.assertEqual(fast.symbol,'unknown')
        confirmed = self.observe(seq=3,ms=100)
        self.assertEqual(confirmed.symbol,'walk')
        self.assertEqual(confirmed.temporal_state,'consistent_schematic')
        self.assertIsNone(confirmed.confidence)
        self.assertFalse(confirmed.automatic_pedestrian_recognition)

    def test_hand_shape_and_two_observed_digits_not_extrapolated(self):
        self.assertIsNone(self.observe('countdown').countdown_s)
        result = self.observe('countdown',frame=1,seq=2,ms=1000)
        self.assertEqual((result.symbol,result.countdown_s),('dont_walk',11))
        self.assertEqual(self.parser.current(1400).countdown_s,11)
        self.assertEqual(self.parser.current(2501).symbol,'unknown')
        self.assertIsNone(self.parser.current(2502).countdown_s)

    def test_flashing_sequence_stays_uncertain_until_target_reset(self):
        results = [self.observe('flashing',frame=i,seq=i+1,ms=i*500) for i in range(4)]
        self.assertEqual(results[2].temporal_state,'flashing_or_uncertain')
        self.assertTrue(all(r.symbol=='unknown' for r in results))
        self.assertEqual(self.observe('hand_like',seq=5,ms=1600).temporal_state,'flashing_or_uncertain')
        self.assertEqual(self.observe('hand_like',seq=6,ms=1700,target='target-b').symbol,'unknown')
        self.assertEqual(self.observe('hand_like',seq=7,ms=1800,target='target-b').symbol,'dont_walk')

    def test_ambiguous_shapes_and_generic_lights_never_upgrade(self):
        for case in ('no_signal','generic_traffic_light','multiple_heads','occluded','glare','low_resolution'):
            with self.subTest(case=case):
                self.parser = ReplaySignalParser()
                self.observe(case)
                result = self.observe(case,seq=2,ms=1000)
                self.assertEqual(result.symbol,'unknown')
                self.assertIsNone(result.countdown_s)

    def test_ambiguous_digits_do_not_invent_a_value(self):
        self.observe('ambiguous_digits')
        result = self.observe('ambiguous_digits',seq=2,ms=1000)
        self.assertEqual(result.symbol,'dont_walk')
        self.assertIsNone(result.countdown_s)

    def test_target_loss_and_change_clear_previous_state_immediately(self):
        self.observe()
        self.assertEqual(self.observe(seq=2,ms=100).symbol,'walk')
        self.assertEqual(self.observe('no_signal',seq=3,ms=200).symbol,'unknown')
        self.assertEqual(self.observe('hand_like',seq=4,ms=300,target='target-b').symbol,'unknown')
        self.assertEqual(self.observe('hand_like',seq=5,ms=400,target='target-b').symbol,'dont_walk')

    def test_shape_change_requires_new_confirmation(self):
        self.observe()
        self.observe(seq=2,ms=100)
        self.assertEqual(self.observe('hand_like',seq=3,ms=200).symbol,'unknown')
        self.assertEqual(self.observe('hand_like',seq=4,ms=300).symbol,'dont_walk')

    def test_sequence_time_and_mode_errors_remove_evidence(self):
        for overrides in (dict(sequence=2),dict(sequence=3,replay_ms=100),
                          dict(sequence=True),dict(mode='live'),dict(replay_ms=float('nan'))):
            self.parser = ReplaySignalParser()
            self.observe();self.observe(seq=2,ms=100)
            result = self.observe(seq=3,ms=200,**overrides)
            self.assertEqual(result.symbol,'unknown')
            self.assertIsNone(result.countdown_s)

    def test_expiry_polling_does_not_renew_capture_and_clock_reversal_is_sticky(self):
        self.observe();self.observe(seq=2,ms=100)
        self.assertEqual(self.parser.current(1500).symbol,'walk')
        self.assertEqual(self.parser.current(1601).reason,'expired')
        self.assertEqual(self.observe(seq=3,ms=1700).symbol,'unknown')
        self.assertEqual(self.parser.current(1699).reason,'replay_clock_invalid')
        self.assertEqual(self.observe(seq=4,ms=1800).reason,'replay_clock_invalid')

    def test_long_frame_gap_requires_confirmation_again(self):
        self.observe();self.observe(seq=2,ms=100)
        self.assertEqual(self.observe(seq=3,ms=1601).symbol,'unknown')
        self.assertEqual(self.observe(seq=4,ms=1701).symbol,'walk')

    def test_manual_roi_provenance_bounds_and_minimum_size(self):
        fixture = self.cases['walk_like']['frames'][0]['manual_rois']
        for change in (dict(provenance='automatic_detector'),dict(box_xyxy=[0,0,417,416]),
                       dict(box_xyxy=[10,10,20,20]),dict(box_xyxy=[True,0,208,248])):
            rois = copy.deepcopy(fixture);rois[0].update(change)
            self.assertEqual(self.observe(manual_rois=rois).symbol,'unknown')
            self.parser = ReplaySignalParser()

    def test_color_or_brightness_alone_is_not_a_symbol(self):
        rois = self.cases['walk_like']['frames'][0]['manual_rois']
        for color in ('white','#ff9830','green'):
            self.parser = ReplaySignalParser()
            image = Image.new('RGB',(416,416),color)
            for seq in (1,2):
                result = self.parser.observe(image,mode='replay',sequence=seq,replay_ms=seq*100,
                                             target_id='target',manual_rois=rois)
            self.assertEqual(result.symbol,'unknown')

    def test_all_segment_digits_and_broken_or_filled_digits(self):
        for value in '0123456789':
            self.assertEqual(read_digit(segment_template(value).convert('RGB')),value)
        self.assertIsNone(read_digit(Image.new('RGB',(29,49),'white')))
        damaged = segment_template('8').convert('RGB')
        ImageDraw.Draw(damaged).rectangle((0,10,28,32),fill='black')
        self.assertIsNone(read_digit(damaged))

    def test_countdown_increase_jump_and_fast_decrement_are_null(self):
        # Feed image pixels with an independently selected authored numeral;
        # parser never reads manifest drawn_digits or labels.
        from backend.vision.signal_fixtures import render
        rois = self.cases['countdown']['frames'][0]['manual_rois']
        for digits,ms in [('13',1000),('09',1000),('11',100)]:
            self.parser = ReplaySignalParser()
            self.observe('countdown')
            image,_ = render('hand',digits)
            result = self.parser.observe(image,mode='replay',sequence=2,replay_ms=ms,
                                         target_id='target-a',manual_rois=rois)
            self.assertIsNone(result.countdown_s)


if __name__ == '__main__':
    unittest.main()
