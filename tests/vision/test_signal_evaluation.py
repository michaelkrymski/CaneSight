"""CS-038 evaluation accounting and failure evidence, not live accuracy tests."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.vision import signal_evaluation as evaluation
from backend.vision.signal_parser import ReplayResult


def row(reference, predicted, drawn, emitted, expected_countdown=None, mismatch=False):
    return {'input': {'operation': 'frame', 'reference_symbol': reference,
                      'drawn_countdown': drawn,
                      'required': {'symbol': reference, 'countdown_s': expected_countdown}},
            'result': {'symbol': predicted, 'countdown_s': emitted},
            'mismatches': {'symbol': 'wrong'} if mismatch else {}}


class EvaluationTests(unittest.TestCase):
    def test_accounting_keeps_zero_abstentions_and_wrong_emitted_values(self):
        rows = [row('dont_walk', 'dont_walk', 0, 0, 0),
                row('dont_walk', 'unknown', 12, None),
                row('dont_walk', 'dont_walk', 11, 9, 11, mismatch=True),
                row('unknown', 'walk', None, 5, mismatch=True)]
        result = evaluation.metrics(rows)
        self.assertEqual(result['ocr_numeric_exact_match_all_readable_frames'],
                         {'numerator': 1, 'denominator': 3, 'fraction': 1 / 3})
        self.assertEqual(result['ocr_numeric_exact_match_when_emitted']['fraction'], .5)
        self.assertEqual(result['ocr_readable_frame_coverage']['fraction'], 2 / 3)
        self.assertEqual(result['ocr_abstentions_on_readable_frames'], 1)
        self.assertEqual(result['ocr_wrong_values_on_readable_frames'], 1)
        self.assertEqual(result['required_null_countdown_violations']['numerator'], 1)
        self.assertEqual(result['reference_symbol_confusion']['unknown']['walk'], 1)
        self.assertEqual(result['checks_matching_required_output']['fraction'], .5)

    def test_no_samples_reports_unavailable_instead_of_perfect_accuracy(self):
        result = evaluation.metrics([])
        for name in ('ocr_numeric_exact_match_all_readable_frames',
                     'ocr_numeric_exact_match_when_emitted', 'checks_matching_required_output'):
            self.assertIsNone(result[name]['fraction'])
            self.assertEqual(result[name]['denominator'], 0)

    def test_scoring_annotations_do_not_change_pixels_or_parser_inputs(self):
        original = evaluation.frame('digits:12', 0, drawn_countdown=12)
        relabeled = copy.deepcopy(original)
        relabeled['required'] = {'symbol': 'walk', 'countdown_s': 99}
        relabeled['reference_symbol'] = 'walk'
        relabeled['drawn_countdown'] = 99
        image_a, rois_a = evaluation.load_input(original, {})
        image_b, rois_b = evaluation.load_input(relabeled, {})
        self.assertEqual(image_a.tobytes(), image_b.tobytes())
        self.assertEqual(rois_a, rois_b)

    def test_suite_scores_cold_and_warm_ambiguity_and_all_two_slot_values(self):
        cases = {case['id']: case for case in evaluation.suite()}
        for condition in ('multiple_heads', 'glare', 'occluded', 'low_resolution',
                          'no_signal', 'generic_traffic_light'):
            cold = cases['cold_' + condition]['steps']
            warm = cases['after_walk_' + condition]['steps']
            self.assertTrue(all(step['required']['symbol'] == 'unknown' for step in cold))
            self.assertEqual(warm[1]['required']['symbol'], 'walk')
            self.assertEqual(warm[2]['required']['symbol'], 'unknown')
            self.assertEqual(warm[3]['required']['symbol'], 'unknown')
        for value in range(100):
            steps = cases[f'two_slot_{value:02}']['steps']
            self.assertIsNone(steps[0]['required']['countdown_s'])
            self.assertEqual(steps[1]['required']['countdown_s'], value)

    def test_actual_evaluation_includes_every_step_and_no_hidden_failures(self):
        result = evaluation.run()
        rows = result['observations']
        self.assertEqual(result['observation_count'], sum(len(c['steps']) for c in evaluation.suite()))
        self.assertEqual(result['mismatch_count'], 0)
        self.assertTrue(all(not r['mismatches'] for r in rows))
        self.assertTrue(result['dataset']['prototype_overlap'])
        self.assertEqual(result['dataset']['held_out_scenes'], 0)
        counts = result['metrics']['reference_symbol_confusion']
        self.assertEqual(sum(sum(predictions.values()) for predictions in counts.values()),
                         result['metrics']['frame_observations'])
        self.assertGreater(counts['walk']['unknown'], 0)
        self.assertGreater(counts['dont_walk']['unknown'], 0)
        self.assertGreater(result['metrics']['ocr_abstentions_on_readable_frames'], 0)
        by_condition = result['by_condition']
        self.assertEqual(sum(m['frame_observations'] for m in by_condition.values()),
                         result['metrics']['frame_observations'])

    def test_wrong_parser_is_reported_without_short_circuiting_the_suite(self):
        class AlwaysWalk:
            def current(self, replay_ms):
                return ReplayResult(symbol='walk', countdown_s=99)

            def observe(self, image, **kwargs):
                # Scoring references must not be visible to the parser.
                self_keys = {'mode', 'sequence', 'replay_ms', 'target_id', 'manual_rois'}
                if set(kwargs) != self_keys:
                    raise AssertionError('Scoring label leaked into inference')
                return self.current(kwargs['replay_ms'])

        result = evaluation.run(parser_factory=AlwaysWalk)
        self.assertEqual(result['observation_count'], sum(len(c['steps']) for c in evaluation.suite()))
        self.assertGreater(result['mismatch_count'], 0)
        self.assertGreater(result['metrics']['required_null_countdown_violations']['numerator'], 0)
        self.assertGreater(result['metrics']['reference_symbol_confusion']['unknown']['walk'], 0)

    def test_cli_writes_failure_evidence_before_nonzero_exit_and_preserves_it(self):
        failed = {'task': 'CS-038', 'case_count': 1, 'observation_count': 1,
                  'mismatch_count': 1, 'metrics': {}, 'observations': ['failure remains visible']}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'failed.json'
            with patch.object(evaluation, 'run', return_value=failed), \
                    patch('sys.argv', ['evaluation', '--report', str(output)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    evaluation.main()
                self.assertEqual(error.exception.code, 1)
                self.assertEqual(json.loads(output.read_text(encoding='utf-8')), failed)
                before = output.read_bytes()
                with self.assertRaises(FileExistsError):
                    evaluation.main()
                self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
