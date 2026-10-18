"""Explicit synthetic acceptance against a privately configured real event database.

This does not deploy, provision roles, restart services, or connect to devices.
Native admission uses local ASGI transport; PostgreSQL uses real verified TLS.
Only allowlisted check names/statuses enter the report. All generated streams
are deleted on exit; no existing non-test stream is selected for deletion.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone, timedelta
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
import uuid

from fastapi.testclient import TestClient
from backend.sessions import SessionRequest
from .event_store import Event, PostgresStore, private_config
from .event_writer import EventWriter
from .logging_app import LoggingManager, build_app


class ProbeFailure(ValueError):
    pass


def unreachable_connect(**config):
    """Inject a refused loopback destination without sending service credentials."""
    import psycopg
    config.update(host='127.0.0.1', port=1, user='synthetic', password='synthetic')
    return psycopg.connect(**config)


def certificate_override_connect(ca_file, **config):
    """Use a deliberately unrelated CA, retaining verify-full and service identity."""
    import psycopg
    config['sslrootcert'] = ca_file
    return psycopg.connect(**config)


def check_independent_expiry():
    """Actual accepted consumer gate; clocks/data here are explicitly synthetic."""
    from backend.freshness import CaptureAgeGate
    root = Path(__file__).resolve().parents[2] / 'shared/protocol/v1/examples'
    now = [1000]
    gate = CaptureAgeGate('demo-session', 'replay', 'pi-camera-1', 'pi-boot-1',
                          relative_drift_ppm=0, clock_ms=lambda: now[0])
    gate.enroll('phone-1', 'phone-boot-1', {'depth_observation', 'heartbeat'})
    probe = gate.start_probe('phone-1')
    now[0] += 20
    gate.finish_probe(dict(probe, type='clock_reply', t2_ms=1210, t3_ms=1210))
    now[0] += 50
    heartbeat = json.loads((root/'heartbeat.json').read_text())
    gate.receive(dict(heartbeat, state='ready', capture_monotonic_ms=now[0]+170))
    now[0] += 50
    depth = json.loads((root/'depth.json').read_text())
    require(gate.receive(dict(depth, capture_monotonic_ms=now[0]+170)) is not None)
    now[0] += 501
    gate.expire()
    require(gate.current('phone-1', 'depth_observation') is None)


def require(condition):
    if not condition:
        raise ProbeFailure('Live event check failed; private details suppressed')


def wait_for(check, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.05)
    raise ProbeFailure('Live event check timed out; private details suppressed')


class TrackingWriter:
    def __init__(self, writer):
        self.writer = writer
        self.submitted = 0

    def submit(self, event):
        self.submitted += 1
        return self.writer.submit(event)

    def delete(self, identifier):
        return self.writer.delete(identifier)

    def deletion_status(self, identifier):
        return self.writer.deletion_status(identifier)


def run(admin_file, runtime_file, analytics_file):
    import psycopg
    report = dict(task='CS-042', database='real PostgreSQL over verify-full TLS',
                  measured_at_utc=datetime.now(timezone.utc).isoformat(),
                  python=sys.version.split()[0],
                  input='synthetic replay only', native_transport='local ASGI, not deployed HTTPS/WSS',
                  checks={}, all_checks_passed=False, deployment_verified=False,
                  provider_backup_policy_verified=False)
    root = Path(__file__).resolve().parents[2]
    report['source_sha256'] = {str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), *[Path(__file__).with_name(n) for n in
            ('event_store.py','event_writer.py','logging_app.py','event_control.py','event_schema.sql')]]}
    streams = []
    recovery = None
    recovery_path = None
    def remember_stream(identifier):
        streams.append(identifier)
        recovery.seek(0)
        json.dump({'stream_ids':streams},recovery)
        recovery.truncate()
        recovery.flush()
        os.fsync(recovery.fileno())
    writer = EventWriter(str(runtime_file), capacity=2)
    tracked = TrackingWriter(writer)
    def passed(name): report['checks'][name] = 'pass'
    admin = reader = None
    try:
        configurations = [private_config(p) for p in (admin_file, runtime_file, analytics_file)]
        require(len({(c['host'], c['port'], c['dbname']) for c in configurations}) == 1)
        require(len({c['user'] for c in configurations}) == 3)
        admin = psycopg.connect(**configurations[0])
        reader = psycopg.connect(**configurations[2])
        with psycopg.connect(**configurations[1]) as runtime:
            for connection in (admin, runtime, reader):
                require(connection.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()[0])
            passed('three_distinct_roles_connect_with_verified_tls')
            privileges = runtime.execute("SELECT has_table_privilege('public.canesight_event_rows','INSERT'), has_table_privilege('public.canesight_event_rows','DELETE'), has_table_privilege('public.canesight_event_rows','SELECT'), has_column_privilege('public.canesight_event_rows','event_id','SELECT'), has_column_privilege('public.canesight_event_rows','stream_id','SELECT'), has_column_privilege('public.canesight_event_rows','expires_at','SELECT'), has_schema_privilege('public','CREATE')").fetchone()
            require(privileges == (True, True, False, True, True, True, False))
            require(runtime.execute("SELECT has_table_privilege('public.canesight_events','SELECT'), has_table_privilege('public.canesight_event_rows','UPDATE'), has_table_privilege('public.canesight_event_rows','TRUNCATE'), has_column_privilege('public.canesight_event_rows','mode','SELECT')").fetchone() == (False,)*4)
            require(reader.execute("SELECT has_table_privilege('public.canesight_events','SELECT'), has_table_privilege('public.canesight_event_rows','SELECT'), has_table_privilege('public.canesight_event_rows','INSERT'), has_table_privilege('public.canesight_event_rows','DELETE'), has_schema_privilege('public','CREATE')").fetchone() == (True, False, False, False, False))
            require(not reader.execute("SELECT has_any_column_privilege('public.canesight_event_rows','SELECT')").fetchone()[0])
            for connection in (runtime, reader):
                require(connection.execute('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone() == (False,) * 5)
                require(not connection.execute('SELECT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))').fetchone()[0])
            passed('runtime_and_analytics_least_privilege')
        columns = admin.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='canesight_event_rows'").fetchall()
        require({row[0] for row in columns} == {'event_id','stream_id','observed_minute','mode','role','event_kind','expires_at'})
        passed('only_approved_minimal_database_columns')
        # Keep deletion identifiers privately before any synthetic insertion, so
        # a disconnected administrator cannot make a failed run unrecoverable.
        recovery_path=Path(runtime_file).resolve().with_name('probe-recovery-'+uuid.uuid4().hex+'.json')
        recovery=os.fdopen(os.open(recovery_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8')
        now = [time.monotonic()]
        manager = LoggingManager(secrets.token_urlsafe(40), tracked, clock=lambda: now[0])
        app = build_app(manager, 'https://cs042-probe.example.test')
        def enroll():
            prefix = 'synthetic-' + secrets.token_hex(4)
            pair = manager.create(SessionRequest.model_validate(dict(mode='replay',ttl_seconds=600,
                phone=dict(source_id=prefix+'-phone',boot_id=prefix+'-pb'),
                pi=dict(source_id=prefix+'-pi',boot_id=prefix+'-ib'))))
            session, phone = manager.authenticate('Bearer '+pair['phone']['token'],'phone')
            source = manager.attach(session,'phone')
            sink = manager.attach(session,'pi')
            return pair, session, phone, source, sink
        def depth(enrollment, seq):
            pair, session, phone, source, sink = enrollment
            message = dict(schema_version=1,type='depth_observation',session_id=pair['session_id'],
                source_id=pair['phone']['source_id'],boot_id=pair['phone']['boot_id'],mode='replay',
                seq=seq,capture_monotonic_ms=seq*100,capture_utc=None,tracking='normal',
                sectors={k:dict(distance_m=None,valid_fraction=0) for k in ('left','center','right')})
            manager.relay(session,phone,source,message)
            require(sink.queue.get_nowait() == message)
        def count(identifier, connection=admin, relation='canesight_event_rows'):
            # Identifiers are fixed internal choices, never external input.
            require(relation in ('canesight_event_rows','canesight_events'))
            return connection.execute('SELECT count(*) FROM public.'+relation+' WHERE stream_id=%s',(identifier,)).fetchone()[0]
        writer.start()
        first, second = enroll(), enroll()
        baseline = admin.execute('SELECT count(*) FROM public.canesight_event_rows').fetchone()[0]
        depth(first,1)
        require(tracked.submitted == 0)
        require(admin.execute('SELECT count(*) FROM public.canesight_event_rows').fetchone()[0] == baseline)
        passed('native_admission_without_consent_writes_nothing')
        with closing(TestClient(app,base_url='https://cs042-probe.example.test')) as client:
            # Public operator routes are exercised by component/TLS tests. This
            # local live-DB probe uses the same manager consent operation.
            for enrollment in (first,second):
                body,status=manager.set_consent(enrollment[0]['session_id'],'enable')
                require(status == 200)
                remember_stream(body['stream_id'])
            depth(first,2)
            depth(second,1)
            wait_for(lambda: all(count(s) == 1 for s in streams))
            require(all(count(s,reader,'canesight_events') == 1 for s in streams))
            require(reader.execute('SELECT count(*) FROM public.canesight_events WHERE stream_id=ANY(%s::uuid[]) AND capture_age_upper_ms IS NOT NULL',(streams,)).fetchone()[0] == 0)
            require(admin.execute('SELECT bool_and(mode=%s AND role=%s AND event_kind=%s) FROM public.canesight_event_rows WHERE stream_id=ANY(%s::uuid[])',('replay','phone','depth_admitted',streams)).fetchone()[0])
            passed('two_consented_synthetic_streams_persist_and_are_visible')
            body,status=manager.set_consent(first[0]['session_id'],'disable')
            require(status == 202 and body['deletion_status'] == 'queued')
            submitted=tracked.submitted
            now[0]+=2
            depth(first,3)
            require(tracked.submitted == submitted)
            passed('withdrawal_stops_new_collection')
            wait_for(lambda: writer.deletion_status(streams[0]) == 'deleted')
            require(count(streams[0]) == 0 and count(streams[1]) == 1)
            passed('confirmed_deletion_preserves_other_stream')
            require(client.get('/healthz').status_code == 200)
        # Seed one already-expired synthetic row directly as administrator. The
        # production insertion adapter correctly refuses expired observations.
        expired=str(uuid.uuid4()); remember_stream(expired)
        timestamp=admin.execute("SELECT date_trunc('minute',clock_timestamp()) - INTERVAL '25 hours'").fetchone()[0]
        admin.execute('INSERT INTO public.canesight_event_rows VALUES (%s,%s,%s,%s,%s,%s,%s)',
            (str(uuid.uuid4()),expired,timestamp,'replay','phone','depth_admitted',timestamp+timedelta(hours=24)))
        require(count(expired) == 1 and count(expired,reader,'canesight_events') == 0)
        passed('expired_rows_hidden_by_database_clock')
        PostgresStore(runtime_file).purge()
        require(count(expired) == 0)
        passed('runtime_physically_purges_expired_rows')
        def failing_writer_case(factory):
            failing = EventWriter(factory=factory,capacity=2)
            try:
                failing.start()
                manager.writer = TrackingWriter(failing)
                enrollment = enroll()
                body,status = manager.set_consent(enrollment[0]['session_id'],'enable')
                require(status == 200)
                remember_stream(body['stream_id'])
                started = time.monotonic()
                depth(enrollment,1)
                require(time.monotonic()-started < 2)
                wait_for(lambda: failing.delete(streams[-1]))
                wait_for(lambda: failing.deletion_status(streams[-1]) == 'failed')
                check_independent_expiry()
            finally:
                failing.close()
        # A valid but unrelated test CA must not authenticate the actual service.
        import trustme
        with tempfile.TemporaryDirectory(prefix='cs042-invalid-ca-') as folder:
            wrong_ca=Path(folder)/'wrong-ca.pem'; trustme.CA().cert_pem.write_to_path(wrong_ca)
            config=private_config(runtime_file)
            config['sslrootcert']=str(wrong_ca)
            try:
                with psycopg.connect(**config): pass
            except psycopg.OperationalError as error:
                require('certificate verify failed' in str(error).lower())
            else: raise ProbeFailure('Unexpected certificate acceptance')
            failing_writer_case(partial(PostgresStore,str(runtime_file),
                connect=partial(certificate_override_connect,str(wrong_ca))))
        passed('unrelated_valid_ca_rejects_actual_service')
        passed('invalid_certificate_writer_does_not_block_native_admission_or_consumer_expiry')
        manager.writer = tracked
        # Hold a real table lock while submitting to the spawned DB writer.
        # The test manipulates no device or production service and releases the
        # lock on transaction exit; the configured one-second DB lock bound stays.
        with admin.transaction():
            admin.execute('LOCK TABLE public.canesight_event_rows IN ACCESS EXCLUSIVE MODE')
            event=Event(str(uuid.uuid4()),streams[1],int(time.time()//60)*60,'replay','phone','heartbeat_admitted')
            writer.submit(event)
            time.sleep(.1)
            started=time.monotonic()
            now[0]+=2
            depth(second,2)
            for _ in range(1000): writer.submit(event)
            require(time.monotonic()-started < 2 and writer.dropped > 900)
            check_independent_expiry()
            manager.revoke(second[0]['session_id'])
            require(second[0]['session_id'] not in manager.consent)
        passed('real_database_lock_and_queue_saturation_do_not_block_native_admission')
        passed('independent_consumer_capture_expiry_under_real_database_lock')
        failing_writer_case(partial(PostgresStore,str(runtime_file),connect=unreachable_connect))
        passed('unreachable_database_does_not_block_native_admission_or_consumer_expiry')
        report['all_checks_passed']=True
    except Exception as error:
        report['error']='Live acceptance incomplete; private details suppressed.'
        report['failure_category'] = type(error).__name__ if type(error).__name__ in ('OperationalError','ProgrammingError','ProbeFailure','HTTPException','TypeError','ValueError','UndefinedTable','QueryCanceled') else 'other'
        trace = error.__traceback__
        while trace.tb_next is not None: trace = trace.tb_next
        report['failure_line'] = trace.tb_lineno
    finally:
        writer.close()
        if admin is not None:
            try:
                for identifier in streams:
                    admin.execute('DELETE FROM public.canesight_event_rows WHERE stream_id=%s',(identifier,))
                report['synthetic_stream_cleanup_confirmed']=all(admin.execute('SELECT count(*) FROM public.canesight_event_rows WHERE stream_id=%s',(identifier,)).fetchone()[0] == 0 for identifier in streams)
            except Exception as error:
                report['synthetic_stream_cleanup_confirmed']=False
                report['cleanup_failure_category'] = type(error).__name__ if type(error).__name__ in ('OperationalError','ProgrammingError','ProbeFailure','HTTPException','TypeError','ValueError','UndefinedTable','QueryCanceled','InFailedSqlTransaction') else 'other'
            admin.close()
        if reader is not None: reader.close()
        if recovery is not None:
            recovery.close()
            if report.get('synthetic_stream_cleanup_confirmed',False):
                recovery_path.unlink(missing_ok=True)
            report['private_recovery_receipt_retained']=recovery_path.exists()
        report['all_checks_passed'] = report['all_checks_passed'] and report.get('synthetic_stream_cleanup_confirmed',False)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-config',type=Path,required=True)
    parser.add_argument('--runtime-config',type=Path,required=True)
    parser.add_argument('--analytics-config',type=Path,required=True)
    parser.add_argument('--output',type=Path,help='Optional sanitized report; contains no connection values')
    args=parser.parse_args()
    result=run(args.admin_config,args.runtime_config,args.analytics_config)
    encoded=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.output:
        args.output.write_text(encoded,encoding='utf-8',newline='\n')
    print(encoded,end='')
    return 0 if result['all_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
