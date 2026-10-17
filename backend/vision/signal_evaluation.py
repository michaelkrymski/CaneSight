"""CS-038: deterministic evaluation of the manual schematic replay profile.

Annotations score outputs only; they are never passed to the parser. This is a
fixture regression evaluation with prototype overlap, not held-out accuracy.
"""
import argparse
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform

import PIL
from PIL import Image

from .signal_fixtures import PACK, PANEL, render, verify
from .signal_parser import PROFILE, ReplaySignalParser

ROOT = Path(__file__).resolve().parents[2]
LABELS = ('unknown', 'walk', 'dont_walk')


def frame(source, ms, *, required='unknown', reference='unknown', countdown=None,
          drawn_countdown=None, target='target-a', transform=None, temporal=None):
    """Hand-authored references, independent of any observed parser output."""
    return {
        'operation': 'frame', 'source': source, 'replay_ms': ms,
        'target_id': target, 'transform': transform,
        'reference_symbol': reference, 'drawn_countdown': drawn_countdown,
        'required': {'symbol': required, 'countdown_s': countdown,
                     **({'temporal_state': temporal} if temporal else {})},
    }


def poll(ms, *, symbol='unknown', countdown=None):
    return {'operation': 'poll', 'replay_ms': ms,
            'required': {'symbol': symbol, 'countdown_s': countdown}}


def suite():
    """Fixed inputs/labels, not selected or relabeled in response to results."""
    cases = []

    def add(name, condition, steps):
        cases.append({'id': name, 'condition': condition, 'steps': steps})

    def confirmed(source='walk_like', symbol='walk'):
        return [frame(source, 0, reference=symbol),
                frame(source, 100, reference=symbol, required=symbol)]

    for source, symbol in [('walk_like', 'walk'), ('hand_like', 'dont_walk')]:
        add('steady_' + source, 'positive_control', confirmed(source, symbol))
    for source in ('no_signal', 'generic_traffic_light', 'multiple_heads',
                   'occluded', 'glare', 'low_resolution'):
        add('cold_' + source, source,
            [frame(source, 0), frame(source, 100), frame(source, 1000)])
        add('after_walk_' + source, source,
            confirmed() + [frame(source, 200), frame(source, 300),
                           frame('walk_like', 400, reference='walk'),
                           frame('walk_like', 500, reference='walk', required='walk')])

    add('target_id_change_same_symbol', 'track_change', confirmed() + [
        frame('walk_like', 200, reference='walk', target='target-b'),
        frame('walk_like', 300, reference='walk', required='walk', target='target-b')])
    add('target_id_and_symbol_change', 'track_change', confirmed() + [
        frame('hand_like', 200, reference='dont_walk', target='target-b'),
        frame('hand_like', 300, reference='dont_walk', required='dont_walk', target='target-b')])
    add('roi_geometry_change_reused_id', 'track_change', confirmed() + [
        frame('walk_like', 200, reference='walk', transform='translate_panel'),
        frame('walk_like', 300, reference='walk', required='walk', transform='translate_panel')])
    add('same_target_symbol_change', 'symbol_change', confirmed() + [
        frame('hand_like', 200, reference='dont_walk'),
        frame('hand_like', 300, reference='dont_walk', required='dont_walk')])
    add('flashing_after_confirmed_hand', 'flashing', confirmed('hand_like', 'dont_walk') + [
        frame('flashing/1', 500),
        frame('flashing/2', 1000, temporal='flashing_or_uncertain'),
        frame('hand_like', 1100, temporal='flashing_or_uncertain'),
        frame('hand_like', 1200, temporal='flashing_or_uncertain')])
    add('paused_replay_expiry', 'expiry', confirmed() + [
        poll(1599, symbol='walk'), poll(1600, symbol='walk'), poll(1601), poll(2000),
        frame('walk_like', 2100, reference='walk'),
        frame('walk_like', 2200, reference='walk', required='walk')])
    add('frame_gap_requires_reconfirmation', 'expiry', confirmed() + [
        frame('walk_like', 1601, reference='walk'),
        frame('walk_like', 1701, reference='walk', required='walk')])
    add('broken_digits', 'ambiguous_digits', [
        frame('ambiguous_digits', 0, reference='dont_walk'),
        frame('ambiguous_digits', 1000, reference='dont_walk', required='dont_walk')])
    add('valid_then_broken_digits', 'ambiguous_digits', [
        frame('digits:12', 0, reference='dont_walk', drawn_countdown=12),
        frame('digits:11', 1000, reference='dont_walk', drawn_countdown=11,
              required='dont_walk', countdown=11),
        frame('ambiguous_digits', 1100, reference='dont_walk', required='dont_walk'),
        frame('digits:10', 1200, reference='dont_walk', drawn_countdown=10, required='dont_walk'),
        frame('digits:10', 1300, reference='dont_walk', drawn_countdown=10,
              required='dont_walk', countdown=10)])
    add('countdown_does_not_extrapolate', 'countdown', [
        frame('digits:12', 0, reference='dont_walk', drawn_countdown=12),
        frame('digits:11', 1000, reference='dont_walk', drawn_countdown=11,
              required='dont_walk', countdown=11),
        poll(2000, symbol='dont_walk', countdown=11), poll(2501)])
    for name, values, times in [('increase', (11, 12), (0, 1000)),
                                ('large_jump', (12, 9), (0, 1000)),
                                ('fast_decrement', (12, 11), (0, 100))]:
        add('implausible_countdown_' + name, 'countdown_plausibility', [
            frame('digits:' + str(values[0]), times[0], reference='dont_walk', drawn_countdown=values[0]),
            frame('digits:' + str(values[1]), times[1], reference='dont_walk',
                  required='dont_walk', drawn_countdown=values[1])])
    # Exhaustive two-slot layout diagnostic, not 100 independent scenes. Leading
    # zero is an authored display convention; score the numeric result 0..99.
    for value in range(100):
        add(f'two_slot_{value:02}', 'digit_layout_control', [
            frame(f'digits:{value}', 0, reference='dont_walk', drawn_countdown=value),
            frame(f'digits:{value}', 1000, reference='dont_walk', drawn_countdown=value,
                  required='dont_walk', countdown=value)])
    return cases


def load_input(step, sources):
    """Resolve only pixels/selection metadata. No output labels enter inference."""
    source = step['source']
    if source.startswith('digits:'):
        image, rois = render('hand', f'{int(source.split(":")[1]):02}')
        for roi in rois:
            roi['provenance'] = 'manual_fixture_annotation'
    else:
        entry = sources[source]
        with Image.open(PACK / entry['file']) as original:
            image = original.copy()
        rois = copy.deepcopy(entry['manual_rois'])
    if step['transform'] == 'translate_panel':
        # Move only the panel; retain visible replay/manual labels.
        panel = image.crop(PANEL)
        image.paste('#202830', PANEL)
        image.paste(panel, (120, 96))
        rois[0]['box_xyxy'] = [120, 96, 328, 344]
    elif step['transform'] is not None:
        raise ValueError('Unknown evaluation transform')
    return image, rois


def fraction(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'fraction': numerator / denominator if denominator else None}


def metrics(rows):
    """Include all frame observations; never omit abstentions or mismatches."""
    frames = [r for r in rows if r['input']['operation'] == 'frame']
    confusion = {truth: {prediction: 0 for prediction in LABELS} for truth in LABELS}
    contract_confusion = copy.deepcopy(confusion)
    for row in frames:
        confusion[row['input']['reference_symbol']][row['result']['symbol']] += 1
        contract_confusion[row['input']['required']['symbol']][row['result']['symbol']] += 1
    eligible = [r for r in frames if r['input']['drawn_countdown'] is not None]
    emitted = [r for r in eligible if r['result']['countdown_s'] is not None]
    correct = sum(r['result']['countdown_s'] == r['input']['drawn_countdown'] for r in eligible)
    must_null = [r for r in rows if r['input']['required']['countdown_s'] is None]
    return {
        'frame_observations': len(frames), 'poll_observations': len(rows) - len(frames),
        'reference_symbol_confusion': confusion,
        'required_output_confusion': contract_confusion,
        'symbol_abstentions': sum(r['result']['symbol'] == 'unknown' for r in frames),
        'checks_matching_required_output': fraction(sum(not r['mismatches'] for r in rows), len(rows)),
        'ocr_numeric_exact_match_all_readable_frames': fraction(correct, len(eligible)),
        'ocr_readable_frame_coverage': fraction(len(emitted), len(eligible)),
        'ocr_numeric_exact_match_when_emitted': fraction(correct, len(emitted)),
        'ocr_abstentions_on_readable_frames': len(eligible) - len(emitted),
        'ocr_wrong_values_on_readable_frames': len(emitted) - correct,
        'required_null_countdown_violations': fraction(
            sum(r['result']['countdown_s'] is not None for r in must_null), len(must_null)),
    }


def run(parser_factory=ReplaySignalParser):
    verify()
    manifest = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    sources = {}
    for case in manifest['cases']:
        for index, item in enumerate(case['frames']):
            sources[f'{case["id"]}/{index}'] = item
        sources[case['id']] = case['frames'][0]
    cases = suite()
    rows = []
    for case in cases:
        parser = parser_factory()
        sequence = 0
        for index, step in enumerate(case['steps']):
            if step['operation'] == 'poll':
                result = parser.current(step['replay_ms'])
                evidence_input = copy.deepcopy(step)
            else:
                image, rois = load_input(step, sources)
                sequence += 1
                result = parser.observe(image, mode='replay', sequence=sequence,
                                        replay_ms=step['replay_ms'], target_id=step['target_id'],
                                        manual_rois=rois)
                evidence_input = {**copy.deepcopy(step), 'sequence': sequence,
                                  'manual_rois': rois,
                                  'rgb_sha256': hashlib.sha256(image.tobytes()).hexdigest()}
            actual = asdict(result)
            expected = {**step['required'], 'mode': 'replay', 'profile': PROFILE,
                        'automatic_pedestrian_recognition': False, 'confidence': None}
            mismatches = {key: {'expected': value, 'actual': actual.get(key)}
                          for key, value in expected.items() if actual.get(key) != value}
            rows.append({'case': case['id'], 'condition': case['condition'], 'step': index,
                         'input': evidence_input, 'result': actual, 'mismatches': mismatches})
    source_files = ['backend/vision/signal_parser.py', 'backend/vision/signal_evaluation.py',
                    'backend/vision/signal_fixtures.py', 'qa/vision/signal-fixtures/manifest.json']
    conditions = sorted({row['condition'] for row in rows})
    return {
        'task': 'CS-038', 'mode': 'replay', 'profile': PROFILE,
        'python': platform.python_version(), 'pillow': PIL.__version__,
        'training_performed': False, 'automatic_pedestrian_recognition': False,
        'dataset': {'origin': 'CS-036 original CC0 schematic fixtures and deterministic derivatives',
                    'license': 'CC0-1.0', 'independent_scenes': 0, 'held_out_scenes': 0,
                    'prototype_overlap': True, 'new_real_images': 0},
        'source_sha256_text_lf': {
            path: hashlib.sha256((ROOT/path).read_text(encoding='utf-8').encode('utf-8')).hexdigest()
            for path in source_files},
        'suite_sha256': hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
        'case_count': len(cases), 'observation_count': len(rows),
        'mismatch_count': sum(bool(row['mismatches']) for row in rows),
        'metrics': metrics(rows),
        'by_condition': {condition: metrics([r for r in rows if r['condition'] == condition])
                         for condition in conditions},
        'observations': rows,
        'limits': [
            'Synthetic profile regression only; templates and evaluation share the CS-036 generator.',
            'Reused pixels, repeated frames and 100 two-slot numbers are correlated diagnostics, not independent scenes.',
            'Reference labels are hand-authored; warm-up abstentions count in symbol confusion and readable-frame OCR.',
            'OCR is numeric exact-match, including leading-zero displays normalized to integers; not general text OCR.',
            'Ambiguity is supplied via manual ROIs and synthetic corruptions; hidden heads or real applicability are not detected.',
            'No held-out real-scene accuracy, physical timing, live capture age, hardware acceptance or crossing permission.',
            'No production adapter, readiness, transport, policy or model weights are changed.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, help='New JSON evidence file; never overwrite')
    args = parser.parse_args()
    report = run()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open('x', encoding='utf-8') as output:
            output.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('task', 'case_count', 'observation_count',
                                                  'mismatch_count', 'metrics')}, indent=2))
    # Write failures before returning nonzero; never hide them to make a report green.
    raise SystemExit(1 if report['mismatch_count'] else 0)


if __name__ == '__main__':
    main()
