import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from governance import has_approval, inspect_changes
from trello_sync import managed_description, project_status, START, END


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.policy = {'pm_github': 'pm', 'protected_files': ['AGENTS.md'],
                       'protected_prefixes': ['docs/master/', 'shared/'],
                       'runtime_fields': ['owner', 'status', 'evidence']}
        self.task = {'id': 'CS-001', 'owner': 'alice', 'status': 'in_progress',
                     'allowed_paths': ['edge/', 'tests/'], 'evidence': []}

    def inspect(self, changes, author='alice', after=None):
        rows = changes + [{'filename': 'changes/new.json', 'status': 'added'}]
        return inspect_changes(rows, self.policy, lambda p: json.dumps(self.task) if p.startswith('tasks/') else '',
                               lambda p: json.dumps(after or self.task), author, ['CS-001'])

    def test_unprotected_work_stays_in_scope(self):
        errors, needed = self.inspect([{'filename': 'edge/camera.py', 'status': 'added'}])
        self.assertEqual(errors, [])
        self.assertFalse(needed)

    def test_master_edit_requires_cr_and_pm(self):
        errors, needed = self.inspect([{'filename': 'docs/master/MASTER_PLAN.md', 'status': 'modified'}])
        self.assertTrue(needed)
        self.assertTrue(errors)

    def test_rename_cannot_evade_protection(self):
        errors, needed = self.inspect([{'filename': 'edge/plan.md', 'previous_filename': 'docs/master/MASTER_PLAN.md', 'status': 'renamed'}])
        self.assertTrue(needed)

    def test_other_lane_rejected(self):
        errors, _ = self.inspect([{'filename': 'ios/app.swift', 'status': 'added'}])
        self.assertTrue(any('scope' in e for e in errors))

    def test_history_cannot_be_edited(self):
        errors, _ = self.inspect([{'filename': 'changes/old.json', 'status': 'modified'}])
        self.assertTrue(any('immutable' in e for e in errors))

    def test_ownership_takeover_needs_pm(self):
        after = dict(self.task, owner='bob')
        errors, needed = self.inspect([{'filename': 'tasks/CS-001.json', 'status': 'modified'}], author='bob', after=after)
        self.assertTrue(needed)
        self.assertTrue(any('claim' in e for e in errors))

    def test_done_without_evidence_rejected(self):
        errors, _ = self.inspect([{'filename': 'tasks/CS-001.json', 'status': 'modified'}], after=dict(self.task, status='done'))
        self.assertTrue(any('evidence' in e for e in errors))

    def test_unmerged_claim_cannot_implement(self):
        self.task['owner'] = None
        errors, _ = self.inspect([{'filename': 'edge/camera.py', 'status': 'added'}])
        self.assertTrue(any('claim' in e for e in errors))

    def test_approval_is_identity_and_head_bound(self):
        comment = {'user': {'login': 'pm'}, 'body': 'PM-APPROVE-PLAN abc'}
        self.assertTrue(has_approval('pm', 'abc', [comment], []))
        self.assertFalse(has_approval('pm', 'def', [comment], []))
        comment['user']['login'] = 'alice'
        self.assertFalse(has_approval('pm', 'abc', [comment], []))

    def test_review_dismissal(self):
        reviews = [{'user': {'login': 'pm'}, 'commit_id': 'abc', 'state': s} for s in ['APPROVED', 'DISMISSED']]
        self.assertFalse(has_approval('pm', 'abc', [], reviews))


class TrelloTests(unittest.TestCase):
    def test_idempotent_block_preserves_human_text(self):
        original = 'Original acceptance criteria.\nHuman note.'
        updated = managed_description(original, 'Backlog')
        self.assertIn(original, updated)
        self.assertEqual(updated, managed_description(updated, 'Backlog'))
        self.assertEqual(1, updated.count(START))

    def test_duplicate_or_broken_markers_fail(self):
        for text in [START, END + START, START + END + START + END]:
            with self.assertRaises(ValueError):
                managed_description(text, 'new')

    def test_exact_task_matching_not_prefix(self):
        task = {'id': 'CS-001', 'status': 'backlog', 'blocker': ''}
        prs = [{'title': '[CS-010] Work', 'draft': False}]
        self.assertEqual(project_status(task, prs)[0], 'backlog')

    def test_pr_means_review_not_done(self):
        task = {'id': 'CS-001', 'status': 'in_progress', 'blocker': ''}
        self.assertEqual(project_status(task, [{'title': '[CS-001] Work', 'draft': False}])[0], 'review')
        self.assertEqual(project_status(task, [{'title': '[CS-001] Work', 'draft': True}])[0], 'in_progress')

    def test_multiple_prs_blocked(self):
        task = {'id': 'CS-001', 'status': 'in_progress', 'blocker': ''}
        self.assertEqual(project_status(task, [{'title': '[CS-001] A', 'draft': False}] * 2)[0], 'blocked')

    def test_explicit_blocker_overrides_pr(self):
        task = {'id': 'CS-001', 'status': 'blocked', 'blocker': 'Missing hardware'}
        self.assertEqual(project_status(task, [{'title': '[CS-001] Work', 'draft': False}])[2], 'Missing hardware')


if __name__ == '__main__':
    unittest.main()
