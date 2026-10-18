"""CS-014 fixture/source audit only. Does not compile or execute Swift/ARKit."""
import argparse
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import re

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'ios/DepthSectors'
FIXTURES = PACKAGE / 'Tests/CaneSightDepthTests/Fixtures/replay.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def audit(syntax=False):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate fixture key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('Use explicit nonfinite sample strings, not invalid JSON numbers')
    pack = json.loads(FIXTURES.read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    require(set(pack) == {'version', 'mode', 'origin', 'license', 'author', 'limits', 'cases'}, 'Unexpected fixture metadata')
    require(pack['version'] == 1 and pack['mode'] == 'replay'
            and pack['origin'] == 'original_synthetic_depth_arrays' and pack['license'] == 'CC0-1.0',
            'Fixture provenance/mode changed')
    require(1 <= len(pack['cases']) <= 32, 'Unbounded fixture cases')
    seen = set()
    for case in pack['cases']:
        require(set(case) == {'id', 'width', 'height', 'metres', 'confidence', 'timestamp', 'tracking',
                              'expectedDistances', 'expectedFractions', 'expectedTimestamp', 'expectedReason'}, 'Unexpected fixture case field')
        require(case['id'] not in seen, 'Duplicate case')
        seen.add(case['id'])
        w, h = case['width'], case['height']
        require(type(w) is int and type(h) is int and 3 <= w <= 2048 and 1 <= h <= 2048
                and w * h <= 262144, 'Invalid fixture dimensions')
        require(len(case['metres']) == w * h and all(finite(v) or v in ('nan', '+inf', '-inf') for v in case['metres']),
                'Invalid depth fixture samples')
        levels = case['confidence']
        require(levels is None or len(levels) == w * h and all(type(v) is int and 0 <= v <= 255 for v in levels),
                'Invalid fixture confidence bytes')
        require(finite(case['timestamp']) or case['timestamp'] == 'nan', 'Invalid authored timestamp encoding')
        require(case['tracking'] in ('normal', 'limited', 'unavailable'), 'Unexpected tracking annotation')
        require(case['expectedReason'] in ('processedFrame', 'missingConfidence', 'trackingUnavailable', 'invalidTimestamp'),
                'Unexpected required reason')
        distances, fractions = case['expectedDistances'], case['expectedFractions']
        require(len(distances) == len(fractions) == 3, 'Three expected image columns required')
        require(all(v is None or finite(v) and v > 0 for v in distances), 'Invalid expected distance annotation')
        require(all(v is None or finite(v) and 0 <= v <= 1 for v in fractions), 'Invalid expected coverage annotation')
        expected_time = None if case['timestamp'] == 'nan' else case['timestamp']
        require(case['expectedTimestamp'] == expected_time, 'Fixture must preserve authored source time')

    files = sorted(PACKAGE.rglob('*.swift'))
    result = {
        'task': 'CS-014', 'mode': 'replay', 'fixture_cases': len(seen), 'fixture_structure': 'passed',
        'python': platform.python_version(), 'swift_source_files': len(files),
        'authored_xctest_methods': sum(len(re.findall(r'func test\w+\(', p.read_text(encoding='utf-8'))) for p in files),
        'source_sha256_text_lf': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest()
                                for p in [*files, FIXTURES]},
        'swift_syntax_parser': 'not_run', 'swift_compilation': 'not_run_no_toolchain',
        'xctest_execution': 'not_run_no_toolchain', 'xcode_ios_build': 'not_run_no_mac',
        'physical_device_checks': 'not_run',
        'limits': ['Structure/provenance/source audit, not execution of depth-processing code.',
                   'Expected fixture outputs are authored requirements, not observed results.',
                   'Syntax parser, when requested, cannot validate types, SDK APIs, linking or runtime behavior.'],
    }
    if syntax:
        from tree_sitter import Language, Parser
        import tree_sitter_swift
        parser = Parser(Language(tree_sitter_swift.language()))
        errors = []
        for path in files:
            root = parser.parse(path.read_bytes()).root_node
            if root.has_error:
                stack = [root]
                while stack:
                    node = stack.pop()
                    if node.is_error or node.is_missing:
                        errors.append({'file': path.relative_to(ROOT).as_posix(), 'line': node.start_point.row + 1,
                                       'type': node.type})
                    stack.extend(reversed(node.children))
        result['swift_syntax_parser'] = {
            'tree_sitter': version('tree-sitter'), 'swift_grammar': version('tree-sitter-swift'),
            'files': len(files), 'errors': errors, 'status': 'failed' if errors else 'passed'}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--syntax', action='store_true', help='Optional Tree-sitter syntax audit, not Swift compiler')
    parser.add_argument('--report', type=Path, help='New evidence JSON file; never overwrite')
    args = parser.parse_args()
    result = audit(args.syntax)
    if args.report:
        with args.report.open('x', encoding='utf-8') as output:
            output.write(json.dumps(result, indent=2) + '\n')
    summary = {key: value for key, value in result.items() if key != 'source_sha256_text_lf'}
    print(json.dumps(summary, indent=2))
    return int(isinstance(result['swift_syntax_parser'], dict) and result['swift_syntax_parser']['status'] == 'failed')


if __name__ == '__main__':
    raise SystemExit(main())
