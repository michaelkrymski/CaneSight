"""Analyze explicitly sourced bench or synthetic timing/depth measurements."""
import argparse
import json
import math
import re
import statistics
from pathlib import Path

MAX_BYTES = 1_048_576
MAX_SAMPLES = 10_000
STAGES = ('capture', 'phone_send', 'backend_receive', 'pi_receive',
          'software_command', 'physical_onset')


class MeasurementError(ValueError):
    """Messages contain fixed field names only, never rejected input values."""


def shape(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise MeasurementError('Unexpected or missing fields')


def number(value, maximum=1e12):
    if type(value) not in (int, float) or not 0 <= value <= maximum or not math.isfinite(value):
        raise MeasurementError('Invalid numeric measurement')
    return float(value)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise MeasurementError('Invalid evidence identifier')
    return value


def rows(value):
    if not isinstance(value, list) or len(value) > MAX_SAMPLES:
        raise MeasurementError('Invalid sample collection')
    return value


def stats(values):
    """p95 uses nearest rank, so small cohorts never hide their worst sample."""
    if not values:
        return None
    ordered = sorted(values)
    return {'count': len(ordered), 'median': statistics.median(ordered),
            'p95': ordered[math.ceil(.95 * len(ordered)) - 1], 'max': ordered[-1]}


def interval(value):
    shape(value, ('lower_ms', 'upper_ms'))
    lower, upper = number(value['lower_ms']), number(value['upper_ms'])
    if lower > upper:
        raise MeasurementError('Reversed timing interval')
    return lower, upper


def analyze(document):
    shape(document, ('format_version', 'origin', 'build_commit', 'run_id',
                     'source_id', 'boot_id', 'clock_evidence_id', 'endpoint', 'latency', 'depth'))
    if type(document['format_version']) is not int or document['format_version'] != 1:
        raise MeasurementError('Unsupported measurement format')
    if document['origin'] not in ('synthetic', 'operator_bench'):
        raise MeasurementError('Invalid evidence origin')
    commit = document['build_commit']
    if not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}', commit):
        raise MeasurementError('Exact tested commit required')
    if document['origin'] == 'operator_bench' and commit == '0' * 40:
        raise MeasurementError('Bench input cannot use a placeholder commit')
    run_id = identifier(document['run_id'])
    source_id = identifier(document['source_id'])
    boot_id = identifier(document['boot_id'])
    clock_id = identifier(document['clock_evidence_id'])
    endpoint = document['endpoint']
    if endpoint not in ('software_command', 'physical_onset'):
        raise MeasurementError('Invalid measurement endpoint')

    lower_latencies, upper_latencies, widths = [], [], []
    seen = set()
    last_sequence = -1
    last_capture = -1.0
    outcomes = dict.fromkeys(('observed', 'unavailable', 'cancelled', 'measurement_missing'), 0)
    stage_counts = dict.fromkeys(STAGES, 0)
    for sample in rows(document['latency']):
        shape(sample, ('capture_sequence', 'original_capture_ms', 'outcome', 'stages'))
        sequence = sample['capture_sequence']
        if type(sequence) is not int or not 0 <= sequence <= 2**53 - 1 or sequence <= last_sequence:
            raise MeasurementError('Duplicate or invalid capture sequence')
        original_capture = number(sample['original_capture_ms'])
        if original_capture <= last_capture:
            raise MeasurementError('Replayed or reordered capture time')
        last_sequence, last_capture = sequence, original_capture
        seen.add(sequence)
        outcome = sample['outcome']
        if not isinstance(outcome, str) or outcome not in outcomes:
            raise MeasurementError('Invalid latency outcome')
        outcomes[outcome] += 1
        stages = sample['stages']
        shape(stages, ('capture', endpoint) if outcome == 'observed' else ('capture',), STAGES)
        if outcome != 'observed' and endpoint in stages:
            raise MeasurementError('Unobserved outcome has an endpoint')
        # A command-only run must not silently include physical timing or mix
        # endpoints. Distinct runs are required for distinct endpoint cohorts.
        if endpoint == 'software_command' and 'physical_onset' in stages:
            raise MeasurementError('Mixed measurement endpoints')
        bounds = {key: interval(value) for key, value in stages.items()}
        causal_floor = 0.0
        for name in STAGES:
            if name not in bounds:
                continue
            lower, upper = bounds[name]
            if upper < causal_floor:
                raise MeasurementError('Impossible pipeline stage order')
            causal_floor = max(causal_floor, lower)
            stage_counts[name] += 1
        if outcome != 'observed':
            continue
        capture, end = bounds['capture'], bounds[endpoint]
        # All input intervals must already share the documented reference clock.
        # Include both endpoints' mapping/measurement uncertainty, not just RTT.
        lower_latencies.append(max(0.0, end[0] - capture[1]))
        upper_latencies.append(end[1] - capture[0])
        widths.append((end[1] - end[0]) + (capture[1] - capture[0]))

    groups = {}
    depth_ids = set()
    for sample in rows(document['depth']):
        shape(sample, ('sample_id', 'sector', 'distance_m', 'estimated_m'))
        sample_id = identifier(sample['sample_id'])
        if sample_id in depth_ids:
            raise MeasurementError('Duplicate depth sample')
        depth_ids.add(sample_id)
        sector = sample['sector']
        if sector not in ('left', 'center', 'right'):
            raise MeasurementError('Invalid depth sector')
        distance = number(sample['distance_m'], maximum=1000)
        if distance == 0:
            raise MeasurementError('Positive measured distance required')
        group = groups.setdefault((sector, distance), {'total': 0, 'errors': []})
        group['total'] += 1
        if sample['estimated_m'] is not None:
            estimate = number(sample['estimated_m'], maximum=1000)
            group['errors'].append(estimate - distance)

    depth_report = []
    for (sector, distance), group in sorted(groups.items()):
        errors = group['errors']
        depth_report.append({'sector': sector, 'distance_m': distance,
            'total': group['total'], 'valid': len(errors),
            'unavailable': group['total'] - len(errors),
            'coverage': len(errors) / group['total'],
            'mean_signed_error_m': statistics.mean(errors) if errors else None,
            'absolute_error_m': stats([abs(error) for error in errors])})

    return {'format_version': 1, 'task': 'CS-045', 'origin': document['origin'],
        'build_commit': commit, 'run_id': run_id, 'source_id': source_id, 'boot_id': boot_id,
        'clock_evidence_id': clock_id,
        'endpoint': endpoint,
        'latency': {'attempted': len(seen), 'observed': len(lower_latencies),
            'outcomes': outcomes, 'minimum_20_samples_met': len(lower_latencies) >= 20,
            'lower_bound_ms': stats(lower_latencies), 'upper_bound_ms': stats(upper_latencies),
            'combined_endpoint_interval_width_ms': stats(widths),
            'stage_sample_counts': stage_counts},
        'depth': depth_report,
        'acceptance': 'synthetic_only' if document['origin'] == 'synthetic' else 'requires_pm_evidence_review',
        'limits': ['Clock evidence and measurement provenance require independent review.',
                   'Software command time is not physical motor onset.',
                   'No accuracy threshold or physical readiness verdict is inferred.',
                   'Unavailable depth remains in the denominator; no all-clear inference.']}


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise MeasurementError('Duplicate JSON key')
            result[key] = value
        return result

    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise MeasurementError('Measurement input exceeds size bound')
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(MeasurementError('Nonfinite JSON number')))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        if isinstance(error, MeasurementError):
            raise
        raise MeasurementError('Cannot read measurement JSON') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='private, normalized measurement JSON')
    args = parser.parse_args()
    try:
        print(json.dumps(analyze(load(args.input)), indent=2, allow_nan=False))
    except MeasurementError as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
