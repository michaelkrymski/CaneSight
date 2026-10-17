import json
import sys
import unittest
import tempfile
import shutil
from argparse import Namespace
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from governance import has_approval, inspect_changes
from trello_sync import managed_description, project_status, START, END
from render_changelog import render
from ci_feedback import required_result
import publish_task as publisher


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

    def test_verified_pm_can_implement_self_assignment_without_merged_claim(self):
        self.task.update(owner=None, status='backlog')
        after = dict(self.task, owner='pm', status='in_progress')
        files = [{'filename': 'tasks/CS-001.json', 'status': 'modified'},
                 {'filename': 'edge/camera.py', 'status': 'added'}]
        errors, needed = self.inspect(files, author='pm', after=after)
        self.assertEqual(errors, [])
        self.assertFalse(needed)
        # The same unmerged ownership/code diff is not authorized for a teammate.
        errors, _ = self.inspect(files, author='alice', after=dict(after, owner='alice'))
        self.assertTrue(any('claim must be merged' in e for e in errors))

    def test_pm_self_assignment_does_not_exempt_scope_changes_or_reassignment(self):
        self.task.update(owner=None, status='backlog')
        after = dict(self.task, owner='pm', status='in_progress', allowed_paths=['ios/'])
        errors, needed = self.inspect(
            [{'filename': 'tasks/CS-001.json', 'status': 'modified'}],
            author='pm', after=after)
        self.assertTrue(needed)
        self.assertTrue(any('new decisions/CR-' in e for e in errors))
        self.task.update(owner='alice', status='in_progress')
        errors, needed = self.inspect(
            [{'filename': 'tasks/CS-001.json', 'status': 'modified'}],
            author='pm', after=dict(self.task, owner='pm'))
        self.assertTrue(needed)
        self.assertTrue(any('new decisions/CR-' in e for e in errors))

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


class PublishingTests(unittest.TestCase):
    def test_branch_guards(self):
        for branch in ('main', 'master', 'HEAD', 'task/CS-002-other', 'random'):
            with self.assertRaises(ValueError):
                publisher.validate_branch(branch, 'CS-001')
        publisher.validate_branch('claim/CS-001-alice', 'CS-001')

    def test_remote_and_sensitive_path_guards(self):
        publisher.validate_remote('https://github.com/michaelkrymski/CaneSight.git')
        for remote in ('https://github.com/other/CaneSight.git', 'https://github.com.evil/michaelkrymski/CaneSight'):
            with self.assertRaises(ValueError):
                publisher.validate_remote(remote)
        with tempfile.TemporaryDirectory() as folder:
            for name in ('../outside', '.git/config', '.env', 'token.pem', '.'):
                with self.assertRaises(ValueError):
                    publisher.normalize_files([name], Path(folder))

    def test_portable_mixed_case_fragment_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'changes').mkdir()
            for filename, identity in [('20261017-bootstrap.json', 'bootstrap'), ('20261017-CS-033.json', 'claim')]:
                entry = dict(id=identity, date='2026-10-17', author='alice', task='CS-033', summary='x', details='x', validation='x')
                (root / 'changes' / filename).write_text(json.dumps(entry), encoding='utf-8')
            log = render(root)
            self.assertLess(log.index('bootstrap:'), log.index('claim:'))

    def test_current_ci_rerun_wins(self):
        checks = [{'id': 1, 'name': 'repository-checks', 'status': 'completed', 'conclusion': 'success'},
                  {'id': 2, 'name': 'repository-checks', 'status': 'completed', 'conclusion': 'failure'}]
        statuses = [{'id': 1, 'context': 'governance', 'state': 'success'}]
        self.assertEqual(required_result(checks, statuses), 'failure')
        checks[1].update(status='in_progress', conclusion=None)
        self.assertEqual(required_result(checks, statuses), 'pending')
        checks[1].update(status='completed', conclusion='success')
        self.assertEqual(required_result(checks, statuses), 'success')
        statuses.append({'id': 2, 'context': 'governance', 'state': 'failure'})
        self.assertEqual(required_result(checks, statuses), 'failure')

    def test_isolated_publish_preserves_history_and_retries_after_failed_checks(self):
        # All writes/pushes stay inside a temporary local bare repository.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'clone'
            remote = Path(folder) / 'remote.git'
            root.mkdir()
            def git(*args):
                return publisher.git(*args, root=root).stdout.strip()
            git('init', '-b', 'main')
            git('config', 'user.name', 'Local test')
            git('config', 'user.email', 'test@example.invalid')
            git('config', 'commit.gpgsign', 'false')
            git('init', '--bare', str(remote))
            git('remote', 'add', 'origin', str(remote))
            for directory in ('scripts', 'changes', 'tasks', 'edge'):
                (root / directory).mkdir()
            shutil.copyfile(publisher.ROOT / 'scripts/render_changelog.py', root / 'scripts/render_changelog.py')
            policy = dict(pm_github='pm', protected_files=['AGENTS.md'], protected_prefixes=['scripts/'], runtime_fields=['owner', 'status'])
            (root / 'governance.json').write_text(json.dumps(policy), encoding='utf-8')
            (root / 'tasks/CS-001.json').write_text(json.dumps(dict(id='CS-001', owner='alice', allowed_paths=['edge/'])), encoding='utf-8')
            (root / 'CHANGELOG.md').write_text(render(root), encoding='utf-8')
            git('add', '.')
            git('commit', '-m', 'baseline')
            git('push', '-u', 'origin', 'main')
            base = git('rev-parse', 'HEAD')
            git('switch', '-c', 'task/CS-001-test')
            (root / 'edge/app.py').write_text('value = 1\n', encoding='utf-8')
            entry = dict(id='test', date='2026-10-17', author='alice', task='CS-001', summary='test', details='test', validation='isolated test')
            (root / 'changes/new.json').write_text(json.dumps(entry), encoding='utf-8')
            args = Namespace(task='CS-001', user='alice', message='test checkpoint', files=['edge/app.py', 'changes/new.json'], dry_run=False, pr=None)
            with patch.object(publisher, 'validate_remote'), patch.object(publisher, 'run_checks', side_effect=RuntimeError('test check failure')):
                with self.assertRaisesRegex(RuntimeError, 'check failure'):
                    publisher.publish(args, root)
            self.assertEqual(git('rev-parse', 'HEAD'), base)
            self.assertEqual(git('ls-remote', '--heads', 'origin', 'task/CS-001-test'), '')
            self.assertIn('CHANGELOG.md', git('diff', '--cached', '--name-only').splitlines())
            # Keep generated/staged files exactly as the failed attempt left
            # them. Retry must work without a manual reset or extra --files.
            # Unrelated work must be preserved and must prevent publication.
            (root / 'other.txt').write_text('keep me', encoding='utf-8')
            git('add', '--', 'other.txt')
            with patch.object(publisher, 'validate_remote'), self.assertRaisesRegex(ValueError, 'Unrelated files are already staged'):
                publisher.publish(args, root)
            git('restore', '--staged', '--', 'other.txt')
            with patch.object(publisher, 'validate_remote'), self.assertRaisesRegex(ValueError, 'Unselected'):
                publisher.publish(args, root)
            self.assertEqual((root / 'other.txt').read_text(), 'keep me')
            (root / 'other.txt').unlink()
            with patch.object(publisher, 'validate_remote'), patch.object(publisher, 'run_checks') as checks:
                publisher.publish(args, root)
            checks.assert_called_once_with(root)
            head = git('rev-parse', 'HEAD')
            self.assertNotEqual(head, base)
            self.assertEqual(git('rev-parse', 'HEAD^'), base)
            self.assertTrue(git('ls-remote', '--heads', 'origin', 'task/CS-001-test').startswith(head))
            self.assertTrue(git('ls-remote', '--heads', 'origin', 'main').startswith(base))
            self.assertEqual(git('status', '--porcelain'), '')


if __name__ == '__main__':
    unittest.main()
