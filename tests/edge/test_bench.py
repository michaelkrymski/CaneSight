"""CS-025 repeatability, original clock bounds and bounded private evidence."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from edge.bench import run
from edge.trace import DecisionTrace

EVENT=dict(session_id='synthetic-session',source_id='synthetic-phone',boot_id='synthetic-boot',seq=1,mode='replay',capture_monotonic_ms=1000,received_ms=1030,capture_deadline_ms=1500,software_command_observed_ms=1035,capture_age_interval_ms=[35,35],hazards={'left':'nearby','center':'unknown','right':'unknown'},channels=['left'],accepted=True,reason='accepted')

class BenchTests(unittest.TestCase):
    def test_repeatable_mapping_capture_bounds_and_idle_expiry(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'events.jsonl'
            result=run(output,3)
            events=[json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['stimuli_accepted'],dict(left=3,center=3,right=3))
            self.assertTrue(result['trace']['complete'])
            self.assertEqual(len(events),18)
            accepted=[e for e in events if e['accepted']]
            self.assertEqual(len(accepted),9)
            self.assertEqual([e['channels'] for e in accepted],[['left'],['left','right'],['right']]*3)
            for e in events:
                self.assertEqual(e['input_kind'],'synthetic-fixture')
                self.assertEqual(e['output_mode'],'simulation')
                self.assertEqual(e['mode'],'replay')
                self.assertEqual(e['capture_age_interval_ms'],[30,30])
                self.assertEqual(e['capture_deadline_ms'],e['capture_monotonic_ms']+500)
                self.assertLess(e['software_command_observed_ms'],e['capture_deadline_ms'])
                self.assertNotIn('token',e)
                self.assertNotIn('sectors',e)
            self.assertFalse(any(result['outputs'].values()))
            self.assertFalse(result['physical_acceptance'])

    def test_private_new_output_closed_fields_and_json_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'events.jsonl'
            trace=DecisionTrace(output)
            try:
                with self.assertRaises(FileExistsError):DecisionTrace(output)
                with self.assertRaises(ValueError):trace.record(dict(EVENT,token='do-not-log'))
                with self.assertRaises(ValueError):trace.record(dict(EVENT,received_ms=float('nan')))
                self.assertTrue(trace.record(EVENT))
            finally:summary=trace.close()
            self.assertTrue(summary['complete'])
            self.assertFalse(trace.record(EVENT))
            self.assertNotIn('do-not-log',output.read_text())
            if hasattr(__import__('os'),'getuid'):
                self.assertEqual(output.stat().st_mode&0o777,0o600)
        with self.assertRaises(ValueError):DecisionTrace(Path(__file__).parent/'forbidden.jsonl')

    def test_blocked_disk_drops_at_queue_bound_and_reports_incomplete(self):
        release=threading.Event()
        original=DecisionTrace._run
        def blocked(trace):release.wait(2);original(trace)
        with tempfile.TemporaryDirectory() as folder, patch.object(DecisionTrace,'_run',blocked):
            trace=DecisionTrace(Path(folder)/'events.jsonl')
            try:
                for _ in range(64):self.assertTrue(trace.record(EVENT))
                self.assertFalse(trace.record(EVENT))
                self.assertEqual(trace.pending.qsize(),64)
            finally:release.set();summary=trace.close()
            self.assertEqual(summary['written'],64)
            self.assertEqual(summary['dropped'],1)
            self.assertFalse(summary['complete'])

    def test_disk_error_is_reported_without_raw_error_or_policy_io(self):
        import os
        original=os.fdopen
        class Broken:
            def __init__(self,fd,*args,**kw):self.real=original(fd,*args,**kw)
            def write(self,*args):raise OSError('sensitive filesystem detail')
            def close(self):self.real.close()
        with tempfile.TemporaryDirectory() as folder, patch('edge.trace.os.fdopen',Broken):
            trace=DecisionTrace(Path(folder)/'events.jsonl')
            trace.record(EVENT);trace.thread.join(1);summary=trace.close()
            self.assertTrue(summary['error'])
            self.assertFalse(summary['complete'])
            self.assertNotIn('sensitive',json.dumps(summary))

    def test_repetition_bounds_do_not_open_output(self):
        for value in [0,21,True,1.5]:
            with self.assertRaises(ValueError):run(Path('not-created'),value)
