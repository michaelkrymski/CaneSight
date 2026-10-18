import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from qa.measurements.analyze import MAX_BYTES, MeasurementError, analyze, load


def fixture(count=20, endpoint='software_command'):
    return {'format_version': 1, 'origin': 'synthetic', 'build_commit': 'a' * 40,
        'run_id': 'synthetic-test', 'source_id': 'phone-fixture', 'boot_id': 'fixture-boot',
        'clock_evidence_id': 'synthetic-common-clock', 'endpoint': endpoint,
        'latency': [{'capture_sequence': i, 'original_capture_ms': i * 1000,
            'outcome': 'observed', 'stages': {
                'capture': {'lower_ms': i * 1000, 'upper_ms': i * 1000 + 10},
                endpoint: {'lower_ms': i * 1000 + 90 + i, 'upper_ms': i * 1000 + 100 + i}}}
            for i in range(count)],
        'depth': [{'sample_id': 'd1', 'sector': 'left', 'distance_m': 1, 'estimated_m': .8},
                  {'sample_id': 'd2', 'sector': 'left', 'distance_m': 1, 'estimated_m': 1.1},
                  {'sample_id': 'd3', 'sector': 'left', 'distance_m': 1, 'estimated_m': None}]}


class AnalysisTests(unittest.TestCase):
    def test_conservative_bounds_and_nearest_rank_p95(self):
        result = analyze(fixture())
        self.assertEqual(result['latency']['lower_bound_ms'],
                         {'count': 20, 'median': 89.5, 'p95': 98, 'max': 99})
        self.assertEqual(result['latency']['upper_bound_ms'],
                         {'count': 20, 'median': 109.5, 'p95': 118, 'max': 119})
        self.assertEqual(result['latency']['combined_endpoint_interval_width_ms']['max'], 20)
        self.assertEqual(result['latency']['stage_sample_counts']['pi_receive'], 0)
        self.assertTrue(result['latency']['minimum_20_samples_met'])
        self.assertEqual(result['acceptance'], 'synthetic_only')

    def test_command_never_becomes_physical_onset(self):
        sample = fixture()
        sample['latency'][0]['stages']['physical_onset'] = {'lower_ms': 120, 'upper_ms': 121}
        with self.assertRaises(MeasurementError):
            analyze(sample)
        result = analyze(fixture(endpoint='physical_onset'))
        self.assertEqual(result['endpoint'], 'physical_onset')
        self.assertEqual(result['acceptance'], 'synthetic_only')

    def test_depth_unknowns_remain_in_coverage_denominator(self):
        result = analyze(fixture())['depth'][0]
        self.assertEqual((result['total'], result['valid'], result['unavailable']), (3, 2, 1))
        self.assertAlmostEqual(result['coverage'], 2 / 3)
        self.assertAlmostEqual(result['mean_signed_error_m'], -.05)
        self.assertAlmostEqual(result['absolute_error_m']['max'], .2)

    def test_empty_and_all_unavailable_data_never_invent_metrics(self):
        sample = fixture(0)
        sample['depth'][0]['estimated_m'] = None
        sample['depth'][1]['estimated_m'] = None
        result = analyze(sample)
        self.assertIsNone(result['latency']['upper_bound_ms'])
        self.assertFalse(result['latency']['minimum_20_samples_met'])
        self.assertIsNone(result['depth'][0]['absolute_error_m'])
        self.assertEqual(result['depth'][0]['coverage'], 0)

    def test_failed_and_cancelled_trials_are_not_silently_dropped(self):
        sample = fixture()
        for i, outcome in enumerate(('unavailable', 'cancelled', 'measurement_missing')):
            sample['latency'][i]['outcome'] = outcome
            del sample['latency'][i]['stages']['software_command']
        result = analyze(sample)['latency']
        self.assertEqual(result['attempted'], 20)
        self.assertEqual(result['observed'], 17)
        self.assertEqual(result['outcomes']['unavailable'], 1)
        self.assertFalse(result['minimum_20_samples_met'])

    def test_overlapping_clock_bounds_do_not_report_negative_latency(self):
        sample = fixture(1)
        sample['latency'][0]['stages']['software_command'] = {'lower_ms': 5, 'upper_ms': 15}
        result = analyze(sample)['latency']
        self.assertEqual(result['lower_bound_ms']['max'], 0)
        self.assertEqual(result['upper_bound_ms']['max'], 15)

    def test_reversed_nonfinite_boolean_and_huge_numeric_inputs_rejected(self):
        for bad in (True, -1, float('nan'), float('inf'), 10**1000):
            sample = fixture(1)
            sample['latency'][0]['stages']['capture']['lower_ms'] = bad
            with self.subTest(kind=type(bad).__name__), self.assertRaises(MeasurementError):
                analyze(sample)
        sample = fixture(1)
        sample['latency'][0]['stages']['capture'] = {'lower_ms': 11, 'upper_ms': 10}
        with self.assertRaises(MeasurementError):
            analyze(sample)

    def test_causal_pipeline_order_checked_across_overlapping_stages(self):
        sample = fixture(1)
        stages = sample['latency'][0]['stages']
        stages['phone_send'] = {'lower_ms': 60, 'upper_ms': 70}
        stages['backend_receive'] = {'lower_ms': 20, 'upper_ms': 50}
        with self.assertRaises(MeasurementError):
            analyze(sample)
        stages['backend_receive']['upper_ms'] = 65
        self.assertEqual(analyze(sample)['latency']['stage_sample_counts']['backend_receive'], 1)

    def test_replay_sequence_and_original_capture_time_rejected(self):
        for key in ('capture_sequence', 'original_capture_ms'):
            sample = fixture(2)
            sample['latency'][1][key] = sample['latency'][0][key]
            with self.subTest(key=key), self.assertRaises(MeasurementError):
                analyze(sample)
        sample = fixture(2)
        sample['latency'].reverse()
        with self.assertRaises(MeasurementError):
            analyze(sample)

    def test_sensitive_unknown_fields_and_mixed_clock_metadata_rejected(self):
        for key in ('token', 'latitude', 'clock_id', 'boot_id'):
            sample = fixture(1)
            sample['latency'][0][key] = 'PRIVATE_SENTINEL'
            with self.subTest(key=key), self.assertRaises(MeasurementError) as error:
                analyze(sample)
            self.assertNotIn('PRIVATE_SENTINEL', str(error.exception))

    def test_bench_metadata_is_not_an_acceptance_verdict(self):
        sample = fixture()
        sample['origin'] = 'operator_bench'
        result = analyze(sample)
        self.assertEqual(result['acceptance'], 'requires_pm_evidence_review')
        for key, value in (('build_commit', 'main'), ('build_commit', '0' * 40), ('format_version', True),
                           ('origin', 'live'), ('clock_evidence_id', '')):
            bad = copy.deepcopy(sample); bad[key] = value
            with self.subTest(key=key), self.assertRaises(MeasurementError):
                analyze(bad)

    def test_depth_groups_separate_distance_and_sector(self):
        sample = fixture(1)
        sample['depth'] += [{'sample_id': 'd4', 'sector': 'right', 'distance_m': 1, 'estimated_m': 0},
                            {'sample_id': 'd5', 'sector': 'left', 'distance_m': 2, 'estimated_m': 2}]
        result = analyze(sample)['depth']
        self.assertEqual(len(result), 3)
        self.assertEqual(result[-1]['absolute_error_m']['max'], 1)
        self.assertEqual(result[1]['absolute_error_m']['max'], 0)
        sample['depth'].append(sample['depth'][0])
        with self.assertRaises(MeasurementError):
            analyze(sample)

    def test_inconsistent_unobserved_outcome_is_rejected(self):
        sample = fixture(1)
        sample['latency'][0]['outcome'] = 'unavailable'
        with self.assertRaises(MeasurementError):
            analyze(sample)

    def test_loader_rejects_duplicate_keys_nonfinite_oversize_and_malformed_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.json'
            for value in ('{"a":1,"a":2}', '{"a":NaN}', '{', ' ' * (MAX_BYTES + 1)):
                path.write_text(value, encoding='utf-8')
                with self.subTest(size=len(value)), self.assertRaises(MeasurementError):
                    load(path)

    def test_cli_round_trip_and_sanitized_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.json'
            path.write_text(json.dumps(fixture()), encoding='utf-8')
            command = [sys.executable, '-m', 'qa.measurements.analyze', str(path)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['acceptance'], 'synthetic_only')
            path.write_text('{"token":"PRIVATE_SENTINEL"}', encoding='utf-8')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('PRIVATE_SENTINEL', result.stdout + result.stderr)
            self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
