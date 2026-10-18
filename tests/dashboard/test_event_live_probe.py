"""Probe failure privacy and real consumer expiry, without cloud credentials."""
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from backend.telemetry import live_probe


class LiveProbeTests(unittest.TestCase):
    def test_private_configuration_failure_never_becomes_success_or_leaks_details(self):
        with patch.dict(sys.modules, psycopg=SimpleNamespace()), \
                patch.object(live_probe, 'private_config', side_effect=ValueError('PRIVATE-SENTINEL')):
            report = live_probe.run('private-admin', 'private-runtime', 'private-reader')
        self.assertFalse(report['all_checks_passed'])
        self.assertFalse(report['deployment_verified'])
        self.assertFalse(report['provider_backup_policy_verified'])
        self.assertNotIn('PRIVATE-SENTINEL', json.dumps(report))

    def test_fault_injection_never_sends_real_credentials_to_loopback(self):
        connect = Mock()
        with patch.dict(sys.modules, psycopg=SimpleNamespace(connect=connect)):
            live_probe.unreachable_connect(host='real-private-host', port=1234,
                                           user='real-user', password='PRIVATE-SENTINEL',
                                           sslmode='verify-full')
        sent = connect.call_args.kwargs
        self.assertEqual((sent['host'], sent['port']), ('127.0.0.1', 1))
        self.assertEqual((sent['user'], sent['password']), ('synthetic', 'synthetic'))
        self.assertEqual(sent['sslmode'], 'verify-full')

    def test_actual_consumer_gate_expires_original_capture_without_database_work(self):
        live_probe.check_independent_expiry()


if __name__ == '__main__':
    unittest.main()
