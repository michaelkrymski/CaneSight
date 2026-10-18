"""Report/source integrity checks; do not require unmerged objects in CI."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from qa import crossing_failure_suite as campaign


class CrossingReportTests(unittest.TestCase):
    def test_closed_case_ids_failures_errors_skips_and_duplicates_cannot_pass(self):
        expected = ['Composition.test_one', 'Composition.test_two']
        cases = [{'id': name, 'status': 'pass'} for name in expected]
        self.assertTrue(campaign.assess(cases, expected))
        for status in ('fail', 'error', 'skip', 'unknown'):
            bad = copy.deepcopy(cases); bad[0]['status'] = status
            self.assertFalse(campaign.assess(bad, expected))
        self.assertFalse(campaign.assess(cases[:1], expected))
        self.assertFalse(campaign.assess([cases[0], cases[0]], expected))
        cases[0]['id'] = 'Other.test_not_in_campaign'
        self.assertFalse(campaign.assess(cases, expected))

    def test_modified_or_extra_prepared_python_cannot_shadow_reviewed_imports(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); module = root / 'edge/reviewed.py'
            module.parent.mkdir(); module.write_bytes(b'REVIEWED = True\n')
            manifest = {'files': [{'path': 'edge/reviewed.py',
                                   'sha256': hashlib.sha256(module.read_bytes()).hexdigest()}]}
            with patch.object(campaign, 'pins', return_value=manifest):
                self.assertEqual(campaign.verify(root), manifest)
                extra = root / 'edge/shadow.py'; extra.write_bytes(b'SHADOW = True\n')
                with self.assertRaises(ValueError): campaign.verify(root)
                extra.unlink(); module.write_bytes(b'PRIVATE_SENTINEL\n')
                with self.assertRaises(ValueError) as error: campaign.verify(root)
                self.assertNotIn('PRIVATE_SENTINEL', str(error.exception))

    def test_malformed_child_output_never_leaks_raw_error_or_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            bad_child = subprocess.CompletedProcess([], 1, b'PRIVATE_SENTINEL', b'PRIVATE_TRACEBACK')
            with patch.object(campaign, 'verify'), patch.object(campaign.subprocess, 'run', return_value=bad_child):
                result = campaign.run(Path(folder))
            self.assertFalse(result['all_software_passed'])
            self.assertFalse(result['physical_acceptance'])
            self.assertNotIn('PRIVATE_SENTINEL', json.dumps(result))
            self.assertNotIn('PRIVATE_TRACEBACK', json.dumps(result))

    def test_missing_review_object_has_no_network_or_head_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            failed = subprocess.CompletedProcess([], 128, b'', b'PRIVATE_GIT_ERROR')
            with patch.object(campaign.subprocess, 'run', return_value=failed) as run:
                with self.assertRaises(ValueError) as error: campaign.prepare(Path(folder))
            self.assertNotIn('PRIVATE_GIT_ERROR', str(error.exception))
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][:2], ['git', 'show'])


if __name__ == '__main__':
    unittest.main()
