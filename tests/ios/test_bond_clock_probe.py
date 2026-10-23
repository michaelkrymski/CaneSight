"""Synthetic scope/binding tests; not measured oscillator evidence."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_bond_clock_probe import same_pair


class BondClockBindingTests(unittest.TestCase):
    def test_rotated_session_or_either_peer_boot_never_reuses_model(self):
        initial = dict(session_id='session-a', peer=dict(source_id='phone-a', boot_id='phone-boot-a'),
                       device=dict(boot_id='pi-boot-a'))
        self.assertTrue(same_pair(initial, copy.deepcopy(initial)))
        self.assertFalse(same_pair(initial, None))
        for section, field in [(None, 'session_id'), ('peer', 'source_id'), ('peer', 'boot_id'), ('device', 'boot_id')]:
            changed = copy.deepcopy(initial)
            if section is None:
                changed[field] = 'new-session'
            else:
                changed[section][field] = 'new-identity'
            self.assertFalse(same_pair(initial, changed))
