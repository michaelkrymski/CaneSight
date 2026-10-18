"""CS-049 fixed software-only campaign; never reads credentials or calls Gemini.

Run from the repository root: python -m qa.denial_failure_suite --output NEW.json
GPS Swift tests are a separate command/evidence boundary, not inferred here.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    'tests.denial.test_policy_isolation',
    'tests.context.test_context_http',
    'tests.context.test_provider',
    'tests.context.test_service',
    'tests.context.test_consumer',
)


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes.append({'case': test.id(), 'result': 'pass'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes.append({'case': test.id(), 'result': 'failure'})

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes.append({'case': test.id(), 'result': 'error'})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes.append({'case': test.id(), 'result': 'skip'})

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.outcomes.append({'case': subtest.id(), 'result': 'subtest-failure'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Preserve earlier attempts, including failures. Open before running so an
    # invalid output location never loses an otherwise completed campaign.
    with args.output.open('x', encoding='utf-8') as output:
        suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
        result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
        paths = {Path(__file__), ROOT / 'tests/denial/test_policy_isolation.py',
                 ROOT / 'backend/freshness.py'}
        paths.update((ROOT / 'backend/context').glob('*.py'))
        paths.update((ROOT / 'edge').glob('*.py'))
        paths.update((ROOT / 'ios/CoarseLocation').rglob('*.swift'))
        for module in MODULES[1:]:
            paths.add(ROOT / (module.replace('.', '/') + '.py'))
        paths.update((ROOT / 'shared/protocol/v1').glob('*.json'))
        paths.update((ROOT / 'shared/protocol/v1').glob('*.py'))
        hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(
            p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for p in sorted(paths) if '.build' not in p.parts}
        passed = result.wasSuccessful() and result.testsRun > 0 and not result.skipped
        report = dict(task='CS-049', kind='synthetic-software',
            recorded_utc=datetime.now(timezone.utc).isoformat(),
            python=platform.python_version(), platform=platform.system(),
            modules=list(MODULES), tests_run=result.testsRun,
            failures=len(result.failures), errors=len(result.errors),
            skipped=len(result.skipped), software_pass=passed,
            source_sha256_utf8_lf=hashes, outcomes=result.outcomes,
            gps_swift_tests_run_by_this_command=False,
            live_gemini=False, native_permission_prompts=False,
            phone_pi_transport=False, physical_audio=False, physical_motors=False,
            limits=['Synthetic provider/client, generated image, same-clock zero-drift inputs.',
                    'FastAPI TestClient HTTP checks do not establish real TLS transport.',
                    'GPS wire contract is absent; unsupported-field rejection is not GPS integration.',
                    'Swift portable GPS run has separate evidence; no Xcode/Core Location/device claim.'])
        json.dump(report, output, indent=2)
        output.write('\n')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
