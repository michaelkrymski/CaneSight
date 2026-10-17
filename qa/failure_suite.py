"""CS-044 bounded software-only N01..N05 campaign report; no physical acceptance."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
GROUPS={
'N01':[
 'test_fault_campaign.FaultCampaignTests.test_n01_disconnect_then_new_epoch_cannot_reuse_old_evidence',
 'test_fault_campaign.FaultCampaignTests.test_n01_silent_source_expires_depth_then_health_without_network_callbacks',
 'test_receiver.ReceiverTlsTests.test_actual_https_upload_wss_receive_idle_expiry_and_revocation',
 'test_policy_transport.PolicyTransportTests.test_verified_native_phone_clock_depth_and_interruption_cancel'],
'N02':[
 'test_fault_campaign.FaultCampaignTests.test_n02_delayed_capture_barrage_cannot_become_fresh_at_receipt',
 'test_freshness.CaptureAgeTests.test_depth_expires_independently_and_heartbeat_cannot_renew',
 'test_freshness.CaptureAgeTests.test_vision_lineage_includes_entire_capture_round_trip_and_expires',
 'test_freshness.CaptureAgeTests.test_resync_never_extends_an_existing_observation_deadline'],
'N03':[
 'test_fault_campaign.FaultCampaignTests.test_n03_combined_replay_mode_identity_future_and_reorder_after_expiry',
 'test_freshness.CaptureAgeTests.test_missing_clock_and_unverified_drift_remain_unavailable',
 'test_freshness.CaptureAgeTests.test_late_asymmetric_and_uncertain_clock_exchange',
 'test_freshness.CaptureAgeTests.test_clock_nonce_is_consumed_once_and_identity_is_bound',
 'test_freshness.CaptureAgeTests.test_authorized_source_boot_change_purges_maps_and_retires_epoch',
 'test_freshness.CaptureAgeTests.test_replay_and_reordered_observations_never_restore_expired_state'],
'N04':[
 'test_limits_integration.SlowInferenceFloodTests.test_authenticated_flood_keeps_latest_work_heap_and_same_loop_watchdog_bounded',
 'test_worker.WorkerTests.test_async_software_watchdog_runs_during_slow_process_and_flood',
 'test_watchdog.WatchdogTests.test_monitor_does_not_need_policy_camera_or_network_lock',
 'test_watchdog.WatchdogTests.test_admission_checks_lease_even_without_monitor_tick'],
'N05':[
 'test_fault_campaign.FaultCampaignTests.test_n05_malformed_wire_cannot_sustain_expired_policy',
 'test_app.IngestionTests.test_json_schema_and_wire_rejections',
 'test_app.IngestionTests.test_body_limits_even_without_content_length',
 'test_app.IngestionTests.test_dimensions_and_byte_count_must_match_actual_jpeg',
 'test_app.IngestionTests.test_invalid_image_does_not_consume_sequence_or_store_frame',
 'test_native_vision.NativeVisionTests.test_other_session_and_phone_never_consume_the_pi_result',
 'test_limits_integration.TLSQuotaTests.test_real_wss_source_quota_survives_reconnect_and_rejects_invalid_input']}


def source_manifest():
    files=set()
    for prefix in ('backend','edge','shared/protocol/v1','tests/backend','tests/edge','tests/failures'):
        files.update(p for p in (ROOT/prefix).rglob('*.py') if '__pycache__' not in p.parts)
    files.add(ROOT/'shared/protocol/v1/messages.schema.json')
    files.add(Path(__file__).resolve())
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


class Result(unittest.TestResult):
    def __init__(self):
        super().__init__();self.cases=[];self.started=None;self.outcome=None
    def startTest(self,test):
        super().startTest(test);self.started=time.perf_counter();self.outcome='unknown'
    def addSuccess(self,test):super().addSuccess(test);self.outcome='pass'
    def addFailure(self,test,err):super().addFailure(test,err);self.outcome='fail'
    def addError(self,test,err):super().addError(test,err);self.outcome='error'
    def addSkip(self,test,reason):super().addSkip(test,reason);self.outcome='skip'
    def addSubTest(self,test,subtest,err):
        super().addSubTest(test,subtest,err)
        if err is not None:self.outcome='fail'
    def stopTest(self,test):
        case=dict(id=test.id(),status=self.outcome,elapsed_ms=round((time.perf_counter()-self.started)*1000,3))
        allowed={'watchdog_gap_samples','median_gap_ms','p95_gap_ms','max_gap_ms',
                 'retained_heap_growth_bytes','flood_frames','rejected_heap_probe_requests'}
        metrics=getattr(test,'evidence',None)
        if isinstance(metrics,dict):
            case['software_metrics']={key:value for key,value in metrics.items() if key in allowed
                and type(value) in (int,float) and math.isfinite(value)}
        self.cases.append(case)
        super().stopTest(test)


def git_context():
    try:
        root=subprocess.run(['git','rev-parse','--show-toplevel'],cwd=ROOT,text=True,capture_output=True)
        if root.returncode or Path(root.stdout.strip()).resolve()!=ROOT.resolve():
            return None,None
        head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True,check=True)
        status=subprocess.run(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT,text=True,capture_output=True,check=True)
        return head.stdout.strip(),bool(status.stdout.strip())
    except (OSError,subprocess.CalledProcessError):
        return None,None # An exported archive is identified by its byte manifest.


def run():
    # Known repository tests only; no remote input chooses imports/commands.
    for directory in ('tests/backend','tests/edge','tests/failures'):
        sys.path.insert(0,str(ROOT/directory))
    before=source_manifest()
    groups={}
    for name,ids in GROUPS.items():
        result=Result();suite=unittest.TestSuite()
        for case in ids:suite.addTests(unittest.defaultTestLoader.loadTestsFromName(case))
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):suite.run(result)
        groups[name]=dict(status='software_pass' if result.wasSuccessful() and not result.skipped and result.testsRun==len(ids) and all(c['status']=='pass' for c in result.cases) else 'software_fail',
            run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),cases=result.cases)
    stable=before==source_manifest()
    commit,dirty=git_context()
    return dict(schema_version=1,task='CS-044',generated_utc=datetime.now(timezone.utc).isoformat(),
        commit=commit,worktree_dirty=dirty,git_metadata_available=commit is not None,source_files_sha256=before,source_stable_during_run=stable,
        python=platform.python_version(),platform=platform.system(),mode='software-fixtures',
        groups=groups,all_software_passed=stable and all(g['status']=='software_pass' for g in groups.values()),
        physical_acceptance=False,pi_accessed=False,camera_used=False,gpio_used=False,
        limits=['Synthetic observations and model adapters; simulated outputs only.',
                'Local verified TLS/WSS plus in-process and spawned-process fault tests; not real Wi-Fi loss.',
                'No real-phone, physical motor, electrical or frozen-GPIO evidence; CS-025 hardware acceptance pending.',
                'Case elapsed times are test execution durations, not capture-to-motor latency.',
                'Dirty worktree reports identify tested sources by SHA-256; commit alone is not an exact-head claim.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path,help='New private report outside checkout')
    args=parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT) or args.output.exists():
        parser.error('Use a new private output outside the checkout')
    report=run()
    fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(all_software_passed=report['all_software_passed'],groups={k:v['status'] for k,v in report['groups'].items()},cases=sum(g['run'] for g in report['groups'].values()),physical_acceptance=False)))
    return 0 if report['all_software_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
