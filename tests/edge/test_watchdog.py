"""CS-026 synthetic lease, blocked worker and subprocess restart evidence."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from edge.haptics import HapticScheduler, SimulatedOutput
from edge.watchdog import PolicyWatchdog

class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.now=0
        self.clock=lambda:self.now
        self.output=SimulatedOutput()
        self.scheduler=HapticScheduler(self.output,clock=self.clock)
        self.watchdog=PolicyWatchdog(self.scheduler.trip,clock=self.clock,timeout_ms=250)
        self.scheduler.set_guard(self.watchdog.deadline)
        self.addCleanup(self.scheduler.close)
        self.addCleanup(self.watchdog.close)

    def arm(self):
        self.now=210;self.assertTrue(self.watchdog.feed());self.scheduler.set_ready(True)

    def test_original_pulse_clipped_to_lease_renewal_cannot_extend_it(self):
        self.arm()
        self.assertTrue(self.scheduler.pulse('left',500,valid_until_ms=1000))
        self.assertEqual(self.scheduler.channels['left'].deadline_ms,460)
        self.now=400;self.watchdog.feed()
        self.now=460;self.scheduler.tick()
        self.assertFalse(self.output.states['left'])
        self.assertIsNone(self.scheduler.fault)
        self.assertEqual(self.scheduler.accepted,1)

    def test_expiry_is_sticky_and_late_feed_cannot_rearm(self):
        self.arm();self.scheduler.pulse('left',valid_until_ms=1000)
        self.now=460
        self.assertFalse(self.watchdog.feed())
        self.watchdog.tick()
        self.assertFalse(any(self.output.states.values()))
        self.assertFalse(self.scheduler.set_ready(True))
        self.assertFalse(self.watchdog.feed())
        self.assertIsNotNone(self.scheduler.fault)

    def test_admission_checks_lease_even_without_monitor_tick(self):
        self.arm();self.now=461
        self.assertFalse(self.scheduler.pulse('right',valid_until_ms=1000))
        self.assertEqual(self.scheduler.accepted,0)
        self.assertFalse(any(self.output.states.values()))

    def test_clock_reversal_nan_and_callback_do_not_restore_readiness(self):
        self.arm();self.now=200
        self.assertIsNone(self.watchdog.deadline())
        self.watchdog.tick()
        self.assertFalse(any(self.output.states.values()))
        self.now=float('nan');self.assertFalse(self.watchdog.feed())
        self.now=500;self.assertFalse(self.watchdog.feed())

    def test_guard_can_only_attach_before_arming_once(self):
        with self.assertRaises(ValueError):self.scheduler.set_guard(self.watchdog.deadline)
        for bad in [None,True,0,49,251,float('inf')]:
            with self.assertRaises((ValueError,TypeError)):PolicyWatchdog(lambda reason:None,timeout_ms=bad)

    def test_close_stops_and_new_epoch_has_no_queue_or_arming(self):
        self.arm();self.scheduler.pulse('right',valid_until_ms=1000)
        self.watchdog.close()
        self.assertFalse(any(self.output.states.values()))
        fresh=HapticScheduler(clock=self.clock)
        guard=PolicyWatchdog(fresh.trip,clock=self.clock)
        try:
            self.assertNotEqual(guard.epoch,self.watchdog.epoch)
            self.assertFalse(fresh.ready)
            self.assertEqual(fresh.accepted,0)
            self.assertFalse(any(fresh.snapshot()['outputs'].values()))
        finally:guard.close();fresh.close()

    def test_callback_runs_without_holding_lease_lock(self):
        completed=threading.Event()
        def callback(reason):
            t=threading.Thread(target=lambda:(self.watchdog.deadline(),completed.set()))
            t.start();t.join(.5)
        self.watchdog.on_fault=callback
        self.now=251;self.watchdog.tick()
        self.assertTrue(completed.is_set())
        self.watchdog.on_fault=self.scheduler.trip

    def test_monitor_does_not_need_policy_camera_or_network_lock(self):
        from backend.freshness import CaptureAgeGate
        from edge.policy import LocalPolicy
        clock=lambda:time.monotonic()*1000
        scheduler=HapticScheduler(clock=clock).start()
        guard=PolicyWatchdog(scheduler.trip,clock=clock,timeout_ms=250)
        scheduler.set_guard(guard.deadline);guard.start()
        gate=CaptureAgeGate('session','replay','pi','boot',clock_ms=clock)
        policy=LocalPolicy(gate,None,scheduler,clock=clock,watchdog=guard).start()
        try:
            time.sleep(.3) # Completed unavailable-policy ticks keep the lease alive.
            self.assertIsNone(guard.fault)
            with policy.lock: # Actual policy worker stalls; supervisor never needs this lock.
                guard.feed();scheduler.set_ready(True)
                self.assertTrue(scheduler.pulse('left',500,valid_until_ms=clock()+1000))
                time.sleep(.4)
                self.assertTrue(policy._thread.is_alive())
                self.assertFalse(any(scheduler.snapshot()['outputs'].values()))
                self.assertIsNotNone(guard.fault)
                self.assertFalse(scheduler.ready)
        finally:
            policy.close();guard.close();scheduler.close()

    def test_uploader_camera_start_failure_closes_real_policy_and_watchdog(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import Mock, patch
        from edge import uploader
        session=dict(base_url='https://127.0.0.1',session_id='session',source_id='pi-camera',boot_id='boot',mode='live',token='synthetic-'+'t'*40)
        camera=Mock();camera.Picamera2.side_effect=RuntimeError('Synthetic camera unavailable')
        def connected(receiver):receiver.connected=True
        from edge.receiver import VisionReceiver
        receiver_class=VisionReceiver
        clock=lambda:time.monotonic()*1000
        output=io.StringIO()
        with patch.object(uploader,'clock_ms',clock), patch('edge.receiver.VisionReceiver',side_effect=lambda *a,**kw:receiver_class(*a,clock=clock,**kw)), patch.object(receiver_class,'start',connected), patch('sys.argv',['uploader','--receive-vision','--simulate-policy','--session-file','unused-private-path']), patch.object(uploader,'load_session',return_value=session), patch.object(uploader,'Transport'), patch.dict('sys.modules',picamera2=camera), redirect_stdout(output):
            with self.assertRaises(RuntimeError):uploader.main()
        self.assertIn('Simulated outputs off=True; gpio_used=false',output.getvalue())
        self.assertNotIn(session['token'],output.getvalue())

    @unittest.skipIf(sys.platform == 'win32','Windows terminate does not deliver POSIX SIGTERM')
    def test_sigterm_runs_cli_camera_cleanup_without_hardware(self):
        import select
        code = """
import runpy,sys,types,time
class Camera:
    def create_video_configuration(self,**kw):return {}
    def configure(self,*a):pass
    def start(self):print('SYNTHETIC_CAMERA_STARTED',flush=True)
    def close(self):print('SYNTHETIC_CAMERA_CLOSED',flush=True)
    def capture_request(self):time.sleep(60)
sys.modules['picamera2']=types.SimpleNamespace(Picamera2=Camera)
sys.argv=['uploader','--capture-only','--frames','0']
runpy.run_module('edge.uploader',run_name='__main__')
"""
        process=subprocess.Popen([sys.executable,'-u','-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
        try:
            deadline=time.monotonic()+8
            while True:
                remaining=deadline-time.monotonic()
                self.assertGreater(remaining,0)
                self.assertTrue(select.select([process.stdout],[],[],remaining)[0])
                line=process.stdout.readline()
                self.assertTrue(line)
                if b'SYNTHETIC_CAMERA_STARTED' in line:break
            process.terminate()
            stdout,stderr=process.communicate(timeout=5)
            self.assertEqual(process.returncode,0,stderr)
            self.assertIn(b'SYNTHETIC_CAMERA_CLOSED',stdout)
        finally:
            if process.poll() is None:process.kill();process.communicate(timeout=5)

    def test_real_process_restart_has_fresh_boot_and_off_state(self):
        command=[sys.executable,'-m','edge.watchdog','--simulate']
        runs=[json.loads(subprocess.run(command,capture_output=True,text=True,timeout=10,check=True).stdout) for _ in range(2)]
        self.assertNotEqual(runs[0]['boot_id'],runs[1]['boot_id'])
        for result in runs:
            self.assertFalse(result['initial_ready'])
            self.assertFalse(any(result['initial_outputs'].values()))
            self.assertFalse(any(result['outputs'].values()))
            self.assertFalse(result['gpio_used'])
            self.assertFalse(result['credentials_loaded'])
            self.assertIsNotNone(result['fault'])

    def test_abrupt_process_exit_requires_fresh_instance_not_cleanup_claim(self):
        crashed=subprocess.run([sys.executable,'-c',"from edge.haptics import HapticScheduler; import os; s=HapticScheduler(); os._exit(17)"],capture_output=True,timeout=10)
        self.assertEqual(crashed.returncode,17)
        fresh=json.loads(subprocess.run([sys.executable,'-m','edge.watchdog','--simulate'],capture_output=True,text=True,timeout=10,check=True).stdout)
        self.assertFalse(fresh['initial_ready'])
        self.assertFalse(any(fresh['initial_outputs'].values()))
        # No assertion about old physical output after SIGKILL/os._exit.
