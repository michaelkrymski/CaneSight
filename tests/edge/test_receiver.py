"""CS-024 lineage, clock and native transport tests; no physical motor output."""
import asyncio
import copy
import json
import io
from pathlib import Path
import secrets
import socket
import ssl
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stdout

import httpx
from PIL import Image
import trustme
import uvicorn
from websockets.exceptions import InvalidStatus
from websockets.http11 import Response
from websockets.datastructures import Headers

from backend.app import create_app
from backend.server import server_config
from backend.sessions import SessionManager
from edge.receiver import NoRedirectConnect, VisionReceiver
from edge.uploader import Latest, Sender, Transport, make_frame
from edge import uploader


def credential(**values):
    return dict(base_url='https://127.0.0.1', session_id='session', source_id='pi',
                boot_id='boot', mode='live', token='t'*40, **values)


def captured(now, seq=1, session=None):
    session = credential() if session is None else session
    return make_frame(Image.new('RGB', (640,480), 'black'),
        {'SensorTimestamp': int(now*1_000_000), 'ExposureTime': 1000},
        session_id=session['session_id'], source_id=session['source_id'],
        boot_id=session['boot_id'], seq=seq, now=now)


def result(metadata):
    message = {k:copy.deepcopy(v) for k,v in metadata.items() if k != 'jpeg_bytes'}
    message.update(type='vision_observation', model_version='synthetic-test', processing_ms=1,
        detections=[], signal={'candidate_count':0,'symbol':'unknown','confidence':None,'countdown_s':None})
    return message


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.now=1000
        self.receiver=VisionReceiver(credential(),clock=lambda:self.now)
        self.latest=Latest()
        self.sender=Sender(self.latest,Mock(),clock=lambda:self.now,receiver=self.receiver)
        self.receiver.connected=True
        self.receiver.set_camera_ready(True)
        self.now=1100

    def record(self,seq=1):
        frame=captured(self.now,seq)
        with self.sender.lock:
            self.sender.ledger.append((frame.metadata,frame.mapping))
            self.assertTrue(self.receiver.record_frame(frame))
        return frame

    def test_valid_original_lineage_and_mapping_then_independent_expiry(self):
        frame=self.record()
        self.now+=100
        value=self.receiver.receive(json.dumps(result(frame.metadata)))
        self.assertEqual(value.message['capture_monotonic_ms'],frame.metadata['capture_monotonic_ms'])
        self.assertEqual(self.receiver.current()[1],frame.mapping)
        # Expiry is anchored to capture, not receive or a later heartbeat.
        self.now=frame.metadata['capture_monotonic_ms']+1501
        self.assertIsNone(self.receiver.tick())
        self.assertEqual(self.receiver.expired,1)

    def test_identity_image_capture_and_mode_mutations_rejected(self):
        for field,value in [('boot_id','other'),('session_id','other'),('source_id','other'),
                ('mode','replay'),('seq',8),('capture_monotonic_ms',1000),
                ('capture_utc','2026-10-17T00:00:00Z'),('image',{'width':1,'height':1})]:
            with self.subTest(field=field):
                self.setUp();frame=self.record();message=result(frame.metadata);message[field]=value
                self.assertIsNone(self.receiver.receive(json.dumps(message).encode()))
                self.assertIsNone(self.receiver.current())

    def test_stale_future_unrecorded_and_evicted_results_unavailable(self):
        frame=self.record()
        self.now+=1600
        self.assertIsNone(self.receiver.receive(json.dumps(result(frame.metadata)).encode()))
        self.setUp()
        frame=captured(self.now+500)
        self.assertFalse(self.receiver.record_frame(frame))
        self.assertIsNone(self.receiver.receive(json.dumps(result(frame.metadata)).encode()))
        first=self.record(1)
        self.now+=1;self.record(2)
        self.now+=1;self.record(3)
        self.assertEqual(len(self.sender.ledger),2)
        self.assertEqual(len(self.receiver.gate.frames),2)
        self.assertIsNone(self.receiver.receive(json.dumps(result(first.metadata)).encode()))

    def test_duplicate_result_and_disconnect_never_restore_evidence(self):
        message=json.dumps(result(self.record().metadata)).encode()
        self.assertIsNotNone(self.receiver.receive(message))
        self.assertIsNone(self.receiver.receive(message))
        self.receiver.invalidate()
        self.assertIsNone(self.receiver.current())
        self.assertFalse(self.receiver.record_frame(captured(self.now,2)))
        self.assertIsNone(self.receiver.receive(message))
        self.assertFalse(self.receiver.gate.local_ready)

    def test_malformed_depth_and_heartbeat_cannot_supply_or_refresh_vision(self):
        frame=self.record()
        self.receiver.receive(json.dumps(result(frame.metadata)).encode())
        for raw in [b'{}',b'x',b'{"x":1,"x":2}',b'x'*8193,b'\xff',b'['*20+b']'*20,
                    json.dumps(dict(result(frame.metadata),type='heartbeat')).encode()]:
            self.assertIsNone(self.receiver.receive(raw))
        self.now=frame.metadata['capture_monotonic_ms']+1501
        self.assertIsNone(self.receiver.current())

    def test_clock_reversal_invalidates_state(self):
        self.receiver.receive(json.dumps(result(self.record().metadata)).encode())
        self.now=10
        with self.assertRaises(ValueError): self.receiver.tick()
        self.receiver.invalidate()
        self.assertEqual(self.receiver.gate.observations,{})

    def test_sender_records_before_request_and_skips_unavailable_capture(self):
        frame=captured(self.now)
        def send(value):
            self.assertIn(value.metadata['frame_id'],self.receiver.gate.frames)
            self.latest.close()
        self.sender.transport.send.side_effect=send
        self.latest.put(frame);self.sender.run()
        self.assertEqual(self.sender.accepted,1)
        self.receiver.invalidate();self.latest=Latest();self.sender.latest=self.latest
        self.latest.put(captured(self.now,2))
        original=self.latest.take
        def take():
            frame=original();self.latest.close();return frame
        self.latest.take=take
        self.sender.run()
        self.assertEqual(self.sender.dropped,1)
        self.assertEqual(self.sender.transport.send.call_count,1)

    def test_closed_credential_and_secure_origin(self):
        for changes in [{'phone':{}},{'base_url':'http://localhost'},{'base_url':'https://u:p@localhost'},
                        {'base_url':'https://localhost/?token=x'},{'mode':'replay'},{'token':'short'}]:
            pair=credential();pair.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError): VisionReceiver(pair)
        self.assertTrue(self.receiver.context.check_hostname)
        self.assertEqual(self.receiver.context.verify_mode,ssl.CERT_REQUIRED)

    def test_redirect_is_terminal_and_does_not_follow_location(self):
        connection=NoRedirectConnect('wss://127.0.0.1/v1/events')
        error=InvalidStatus(Response(302,'Found',Headers({'Location':'wss://other.invalid/v1/events'})))
        self.assertIs(connection.process_redirect(error),error)

    def test_camera_unavailable_purges_evidence_and_old_captures_cannot_recover(self):
        frame=self.record()
        self.receiver.receive(json.dumps(result(frame.metadata)).encode())
        self.receiver.set_camera_ready(False)
        self.assertIsNone(self.receiver.current())
        self.now+=100
        self.receiver.set_camera_ready(True)
        self.assertFalse(self.receiver.record_frame(frame))
        self.assertIsNone(self.receiver.current())

    def test_uploader_initialization_failure_stops_receiver(self):
        camera_module=Mock()
        camera_module.Picamera2.side_effect=RuntimeError('Synthetic camera startup failure')
        receiver=Mock(error=None)
        receiver_class=Mock(return_value=receiver)
        with patch('sys.argv',['uploader','--session-file','private.json','--receive-vision']), \
                patch.object(uploader,'load_session',return_value=credential()), \
                patch('edge.receiver.VisionReceiver',receiver_class), \
                patch.dict('sys.modules',picamera2=camera_module), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'Synthetic camera startup failure'): uploader.main()
        receiver.start.assert_called_once()
        receiver.stop.assert_called_once()
        receiver.set_camera_ready.assert_called_with(False)

    def test_capture_only_cannot_silently_enable_receiver(self):
        with patch('sys.argv',['uploader','--capture-only','--receive-vision']), \
                patch('sys.stderr',new_callable=io.StringIO), self.assertRaises(SystemExit): uploader.main()


class StubWorker:
    """Deterministic synthetic backend observation, not a real inference claim."""
    def __init__(self): self.results={}
    def start(self): pass
    def stop(self): pass
    def health(self): return {'model_available':True,'worker_healthy':True}
    def submit(self,grant,metadata,jpeg): self.results[grant.session_id]=result(metadata)
    def take_result(self,grant): return self.results.pop(grant.session_id,None)
    def discard_source(self,grant): self.results.pop(grant.session_id,None)


class ReceiverTlsTests(unittest.TestCase):
    def test_actual_https_upload_wss_receive_idle_expiry_and_revocation(self):
        operator=secrets.token_urlsafe(40)
        app=create_app(session_manager=SessionManager(operator),inference_worker=StubWorker())
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ca=trustme.CA();cert=ca.issue_cert('127.0.0.1')
            cert.private_key_pem.write_to_path(root/'key.pem')
            cert.cert_chain_pems[0].write_to_path(root/'cert.pem')
            ca.cert_pem.write_to_path(root/'ca.pem')
            context=ssl.create_default_context();ca.configure_trust(context)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1',0));listener.listen(128);port=listener.getsockname()[1]
                server=uvicorn.Server(server_config(app,port=port,ssl_keyfile=str(root/'key.pem'),ssl_certfile=str(root/'cert.pem')))
                thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
                receiver=None;sender_thread=None;latest=Latest()
                try:
                    deadline=time.monotonic()+10
                    while not server.started:
                        self.assertTrue(thread.is_alive());self.assertLess(time.monotonic(),deadline);time.sleep(.01)
                    base='https://127.0.0.1:'+str(port)
                    with httpx.Client(base_url=base,verify=context,trust_env=False) as client:
                        response=client.post('/v1/sessions',headers={'Authorization':'Bearer '+operator},json={
                            'mode':'live','ttl_seconds':60,'pi':{'source_id':'pi','boot_id':'boot'},
                            'phone':{'source_id':'bench-unconnected','boot_id':'phone-boot'}})
                        self.assertEqual(response.status_code,201)
                        pair=response.json();session={k:pair['pi'][k] for k in ('source_id','boot_id','token')}
                        session.update(base_url=base,session_id=pair['session_id'],mode='live')
                        clock=lambda:time.monotonic()*1000
                        receiver=VisionReceiver(session,clock=clock,ca_file=str(root/'ca.pem'))
                        sender=Sender(latest,Transport(base,session['token'],ca_file=str(root/'ca.pem')),clock=clock,receiver=receiver)
                        receiver.start();receiver.set_camera_ready(True)
                        # A real capture must start after readiness; old captures cannot recover.
                        time.sleep(.03)
                        frame=captured(clock(),session=session)
                        sender_thread=threading.Thread(target=sender.run);sender_thread.start();latest.put(frame)
                        deadline=time.monotonic()+3
                        while receiver.accepted!=1:
                            self.assertLess(time.monotonic(),deadline,
                                f'accepted={sender.accepted}, dropped={sender.dropped}, failed={sender.failed}, '
                                f'rejected={receiver.rejected}, transport_error={receiver.error}, sender_error={sender.error}')
                            time.sleep(.01)
                        self.assertEqual(receiver.current()[0].message['frame_id'],frame.metadata['frame_id'])
                        # Leave socket receive blocked: independent expiry must still execute.
                        deadline=time.monotonic()+3
                        while receiver.expired!=1:
                            self.assertLess(time.monotonic(),deadline);time.sleep(.02)
                        self.assertIsNone(receiver.current())
                        self.assertEqual(sender.accepted,1)
                        latest.put(captured(clock(),seq=2,session=session))
                        deadline=time.monotonic()+3
                        while receiver.accepted!=2:
                            self.assertLess(time.monotonic(),deadline);time.sleep(.01)
                        self.assertIsNotNone(receiver.current())
                        client.delete('/v1/sessions/'+pair['session_id'],headers={'Authorization':'Bearer '+operator})
                        deadline=time.monotonic()+3
                        while receiver.connected:
                            self.assertLess(time.monotonic(),deadline);time.sleep(.01)
                        self.assertIsNotNone(receiver.error)
                        self.assertIsNone(receiver.current())
                finally:
                    latest.close()
                    if sender_thread: sender_thread.join(3)
                    if receiver: receiver.stop()
                    server.should_exit=True;thread.join(10)
                    self.assertFalse(thread.is_alive())
                    if receiver: self.assertFalse(receiver._thread.is_alive())


if __name__=='__main__': unittest.main()
