import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from governance import inspect_changes
from publish_task import validate_branch
from validate_repo import validate
from ci_feedback import required_result


class SoloWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.policy = {'collaboration_mode': 'solo', 'pm_github': 'michaelkrymski',
            'protected_files': ['AGENTS.md'], 'protected_prefixes': ['shared/'],
            'runtime_fields': ['owner', 'status'], 'task_static_fields': ['id', 'trello_url'],
            'statuses': ['backlog', 'in_progress', 'done']}

    def test_owner_can_change_any_path_without_claim_task_or_fragment(self):
        rows = [{'filename': p, 'status': 'modified'} for p in
                ['AGENTS.md', 'shared/new.json', 'backend/new.py', 'ios/New.swift', 'tasks/CS-099.json']]
        self.assertEqual(inspect_changes(rows, self.policy, lambda _: None, lambda _: None,
                                       'michaelkrymski', []), ([], False))

    def test_other_authors_cannot_use_owner_solo_exemption(self):
        errors, needed = inspect_changes([{'filename': 'AGENTS.md', 'status': 'modified'}],
            self.policy, lambda _: None, lambda _: None, 'someone-else', [])
        self.assertTrue(errors)
        self.assertTrue(needed)

    def test_any_named_branch_in_solo_but_team_rules_remain(self):
        validate_branch('main', None, solo=True)
        validate_branch('feature/calibration', None, solo=True)
        with self.assertRaises(ValueError):
            validate_branch('HEAD', None, solo=True)
        with self.assertRaises(ValueError):
            validate_branch('main', 'CS-001')

    def test_new_task_needs_no_claim_owner_scope_or_trello_in_solo_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'tasks').mkdir(); (root/'changes').mkdir()
            (root/'governance.json').write_text(json.dumps(self.policy))
            (root/'tasks/CS-099.json').write_text(json.dumps({'id':'CS-099','status':'in_progress'}))
            self.assertEqual(validate(root), [])
            (root/'governance.json').write_text(json.dumps(dict(self.policy, collaboration_mode='team')))
            self.assertTrue(validate(root))

    def test_solo_ci_does_not_wait_for_retired_governance_status(self):
        checks=[{'id':1,'name':'repository-checks','status':'completed','conclusion':'success'}]
        statuses=[{'id':2,'context':'governance','state':'failure'}]
        self.assertEqual(required_result(checks,statuses,contexts=('repository-checks',)), 'success')
        self.assertEqual(required_result(checks,statuses), 'failure')


if __name__ == '__main__':
    unittest.main()
