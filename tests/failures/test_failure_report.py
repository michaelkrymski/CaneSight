"""Reporting must retain failures/skips without serializing exception payloads."""
import json
import unittest
from qa.failure_suite import GROUPS, Result, source_manifest, git_context

class ReportTests(unittest.TestCase):
    def test_closed_campaign_contains_all_five_groups_and_unique_cases(self):
        self.assertEqual(set(GROUPS),{'N01','N02','N03','N04','N05'})
        names=[name for values in GROUPS.values() for name in values]
        self.assertEqual(len(names),25)
        self.assertEqual(len(names),len(set(names)))

    def test_failures_and_skips_cannot_be_serialized_as_pass_or_leak_details(self):
        class Bad(unittest.TestCase):
            def runTest(self):raise ValueError('private-credential-must-not-appear')
        class Skipped(unittest.TestCase):
            def runTest(self):self.skipTest('private skip detail')
        for case,status in [(Bad(),'error'),(Skipped(),'skip')]:
            result=Result();case.run(result)
            self.assertEqual(result.cases[0]['status'],status)
            self.assertNotIn('private',json.dumps(result.cases))

    def test_metrics_are_numeric_allowlist_only(self):
        class Sample(unittest.TestCase):
            def runTest(self):self.evidence=dict(median_gap_ms=2,max_gap_ms=float('nan'),token='never-report')
        result=Result();Sample().run(result)
        self.assertEqual(result.cases[0]['software_metrics'],{'median_gap_ms':2})
        self.assertNotIn('never-report',json.dumps(result.cases))

    def test_source_manifest_contains_protocol_and_runtime_not_private_files(self):
        manifest=source_manifest()
        for key in ('backend/freshness.py','edge/policy.py','edge/watchdog.py','shared/protocol/v1/messages.schema.json','qa/failure_suite.py'):
            self.assertIn(key,manifest)
            self.assertRegex(manifest[key],r'^[0-9a-f]{64}$')
        self.assertFalse(any('.env' in name or '__pycache__' in name for name in manifest))

    def test_archive_does_not_invent_a_commit_or_clean_state(self):
        from unittest.mock import patch
        with patch('qa.failure_suite.subprocess.run',side_effect=FileNotFoundError):
            self.assertEqual(git_context(),(None,None))
