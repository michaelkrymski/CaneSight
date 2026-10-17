"""Separate viewer authorization; synthetic observations, never real devices."""
import json
import asyncio
import io
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import time
import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient
import httpx
from PIL import Image
import trustme
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from backend.app import create_app
from backend.sessions import SessionRequest
from backend.server import server_config
from backend.telemetry.live import COOKIE, DashboardManager, install_dashboard


OPERATOR = 'synthetic-operator-only-' + 'o'*40
ORIGIN = 'https://dashboard.example.test'


class LiveDashboardTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.manager = DashboardManager(OPERATOR, clock=lambda:self.now)
        self.pair = self.manager.create(SessionRequest.model_validate({
            'mode':'replay', 'ttl_seconds':60,
            'pi':{'source_id':'pi','boot_id':'pi-boot'},
            'phone':{'source_id':'phone','boot_id':'phone-boot'}}))
        self.app = install_dashboard(create_app(session_manager=self.manager),self.manager,ORIGIN)
        self.client = TestClient(self.app,base_url=ORIGIN)
        self.addCleanup(self.client.close)

    def issue(self):
        response=self.client.post('/v1/dashboard-viewers',json={'session_id':self.pair['session_id']},
            headers={'Authorization':'Bearer '+OPERATOR})
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.headers['cache-control'],'no-store')
        return response.json()['viewer_token']

    def login(self,token=None):
        token=self.issue() if token is None else token
        response=self.client.post('/dashboard/api/login',json={'viewer_token':token},headers={'Origin':ORIGIN})
        self.assertEqual(response.status_code,204)
        return token,response

    def test_distinct_scoped_cookie_no_native_role_privileges(self):
        token,response=self.login()
        cookie=response.headers['set-cookie']
        for flag in ('Secure','HttpOnly','SameSite=strict','Path=/'): self.assertIn(flag,cookie)
        self.assertNotIn('Domain=',cookie)
        data=self.client.get('/dashboard/api/snapshot').json()
        self.assertEqual(data['session_id'],self.pair['session_id'])
        self.assertEqual(data['mode'],'replay')
        for secret in (token,OPERATOR,self.pair['pi']['token'],self.pair['phone']['token']):
            self.assertNotIn(secret,json.dumps(data))
        self.assertEqual(self.client.delete('/v1/sessions/'+self.pair['session_id'],
            headers={'Authorization':'Bearer '+token}).status_code,401)
        self.assertEqual(self.client.post('/v1/dashboard-viewers',json={'session_id':self.pair['session_id']}).status_code,401)
        for secret in (OPERATOR,self.pair['pi']['token'],self.pair['phone']['token']):
            self.assertEqual(self.client.post('/dashboard/api/login',json={'viewer_token':secret},headers={'Origin':ORIGIN}).status_code,401)

    def test_no_auth_no_cross_origin_no_query_and_no_insecure_transport(self):
        self.assertEqual(self.client.get('/dashboard/api/snapshot').status_code,401)
        token=self.issue()
        for origin in (None,'https://attacker.example.test','null'):
            headers={} if origin is None else {'Origin':origin}
            self.assertEqual(self.client.post('/dashboard/api/login',json={'viewer_token':token},headers=headers).status_code,403)
        self.assertEqual(self.client.get('/?token=not-accepted').status_code,403)
        self.assertEqual(self.client.get('/',headers={'Host':'attacker.example.test'}).status_code,403)
        self.assertEqual(self.client.post('/v1/dashboard-viewers',json={'session_id':self.pair['session_id']},
            headers={'Authorization':'Bearer '+OPERATOR,'Origin':ORIGIN}).status_code,403)
        with TestClient(self.app,base_url='http://dashboard.example.test') as insecure:
            self.assertEqual(insecure.get('/').status_code,403)

    def test_revocation_expiry_logout_and_poll_bounds(self):
        token,_=self.login()
        self.assertEqual(self.client.get('/dashboard/api/snapshot').status_code,200)
        self.assertEqual(self.client.get('/dashboard/api/snapshot').status_code,429)
        self.now+=.25
        self.assertEqual(self.client.get('/dashboard/api/snapshot').status_code,200)
        self.assertEqual(self.client.post('/dashboard/api/logout',headers={'Origin':ORIGIN}).status_code,204)
        self.assertEqual(self.client.get('/dashboard/api/snapshot').status_code,401)
        with self.assertRaises(HTTPException): self.manager.viewer(token)
        self.login();self.manager.revoke(self.pair['session_id'])
        self.assertEqual(self.client.get('/dashboard/api/snapshot').status_code,401)
        self.assertEqual(len(self.manager.projections),0)
        self.assertEqual(len(self.manager.viewers),0)

    def test_viewer_expiry_tracks_original_session_deadline_and_capacity(self):
        self.now+=59
        token=self.issue()
        self.now+=1
        with self.assertRaises(HTTPException): self.manager.viewer(token)
        other=DashboardManager(OPERATOR,clock=lambda:0)
        pair=other.create(SessionRequest.model_validate({'mode':'live','ttl_seconds':600,
            'pi':{'source_id':'p','boot_id':'b'},'phone':{'source_id':'f','boot_id':'c'}}))
        for _ in range(16): other.issue_viewer(pair['session_id'])
        with self.assertRaises(HTTPException): other.issue_viewer(pair['session_id'])

    def test_already_admitted_native_data_has_unknown_capture_age_and_no_private_payload(self):
        session,pi=self.manager.authenticate('Bearer '+self.pair['pi']['token'],'pi')
        _,phone=self.manager.authenticate('Bearer '+self.pair['phone']['token'],'phone')
        pi_socket=self.manager.attach(session,'pi')
        phone_socket=self.manager.attach(session,'phone')
        message={'schema_version':1,'type':'depth_observation','session_id':session.session_id,
            'source_id':'phone','boot_id':'phone-boot','mode':'replay','seq':1,
            'capture_monotonic_ms':987654321,'capture_utc':None,'tracking':'normal',
            'sectors':{key:{'distance_m':1.2,'valid_fraction':.9} for key in ('left','center','right')}}
        self.manager.relay(session,phone,phone_socket,message)
        # Observing never consumes the paired Pi's native message queue.
        self.assertEqual(pi_socket.queue.get_nowait(),message)
        self.login();snapshot=self.client.get('/dashboard/api/snapshot').json()
        source=snapshot['sources'][0]
        self.assertEqual(source['capture']['capture_monotonic_ms'],987654321)
        self.assertIsNone(source['capture_age_upper_ms'])
        self.assertEqual(source['packet_age_ms'],0)
        self.assertNotIn('distance_m',json.dumps(snapshot))
        self.assertNotIn('jpeg',json.dumps(snapshot))
        with self.assertRaises(ValueError): self.manager.relay(session,phone,phone_socket,message)
        self.manager.detach(session,phone_socket);self.now+=1
        self.assertTrue(all(not item['connected'] for item in self.client.get('/dashboard/api/snapshot').json()['sources']))

    def test_viewer_cannot_select_another_session_and_projection_is_bounded(self):
        self.login()
        other=self.manager.create(SessionRequest.model_validate({'mode':'live',
            'pi':{'source_id':'other-pi','boot_id':'b'},'phone':{'source_id':'other-phone','boot_id':'c'}}))
        data=self.client.get('/dashboard/api/snapshot').json()
        self.assertEqual(data['session_id'],self.pair['session_id'])
        self.assertNotIn(other['session_id'],json.dumps(data))
        self.assertEqual(self.client.get('/dashboard/api/snapshot?session_id='+other['session_id']).status_code,403)

    def test_closed_login_body_and_security_headers(self):
        for content in ('{"viewer_token":"x","viewer_token":"y"}', '{"viewer_token":"x","extra":1}', '['*20+']'*20, 'x'*513):
            response=self.client.post('/dashboard/api/login',content=content,
                headers={'Content-Type':'application/json','Origin':ORIGIN})
            self.assertIn(response.status_code,(400,413))
        page=self.client.get('/')
        self.assertEqual(page.status_code,200)
        self.assertIn('data-feed="live"',page.text)
        self.assertIn("connect-src 'self'",page.headers['content-security-policy'])
        self.assertIn("frame-ancestors 'none'",page.headers['content-security-policy'])
        self.assertEqual(page.headers['cache-control'],'no-store')
        self.assertNotIn('access-control-allow-origin',page.headers)
        self.assertEqual(self.client.get('/.env').status_code,404)
        self.assertEqual(self.client.post('/dashboard/api/snapshot').status_code,405)

    def test_frame_and_vision_metadata_observed_without_consuming_extra_result(self):
        class Worker:
            value=None
            def submit(self,grant,metadata,jpeg):
                self.value={key:value for key,value in metadata.items() if key!='jpeg_bytes'}
                self.value.update(type='vision_observation',model_version='synthetic-only',processing_ms=1,
                    detections=[],signal={'candidate_count':0,'symbol':'unknown','confidence':None,'countdown_s':None})
            def discard_source(self,grant): self.value=None
            def take_result(self,grant):
                value=self.value;self.value=None;return value
        self.manager.bind_inference_worker(Worker())
        session,grant=self.manager.authenticate('Bearer '+self.pair['pi']['token'],'pi')
        connection=self.manager.attach(session,'pi')
        stream=io.BytesIO();Image.new('RGB',(8,8),'black').save(stream,format='JPEG');jpeg=stream.getvalue()
        metadata=dict(schema_version=1,type='frame_metadata',session_id=session.session_id,
            source_id='pi',boot_id='pi-boot',mode='replay',seq=1,frame_id='frame-1',
            capture_monotonic_ms=9000,capture_utc=None,image={'width':8,'height':8},jpeg_bytes=len(jpeg))
        response=self.client.post('/v1/frames',headers={'Authorization':'Bearer '+self.pair['pi']['token']},
            data={'metadata':json.dumps(metadata)},files={'image':('frame.jpg',jpeg,'image/jpeg')})
        self.assertEqual(response.status_code,202)
        offered=self.manager.take_vision(session,grant,connection)
        self.assertEqual(offered['frame_id'],'frame-1')
        self.assertIsNone(self.manager.take_vision(session,grant,connection))
        self.login();data=self.client.get('/dashboard/api/snapshot').json()
        self.assertEqual(data['sources'][1]['model_version'],'synthetic-only')
        self.assertIsNone(data['sources'][1]['capture_age_upper_ms'])
        self.assertNotIn('detections',json.dumps(data))


class LiveDashboardTlsTests(unittest.TestCase):
    def test_real_verified_https_viewer_cookie_and_unchanged_native_origin_rejection(self):
        manager=DashboardManager(OPERATOR)
        with tempfile.TemporaryDirectory() as directory, socket.socket() as listener:
            root=Path(directory);ca=trustme.CA();cert=ca.issue_cert('127.0.0.1')
            cert.private_key_pem.write_to_path(root/'key.pem');cert.cert_chain_pems[0].write_to_path(root/'cert.pem')
            context=ssl.create_default_context();ca.configure_trust(context)
            listener.bind(('127.0.0.1',0));listener.listen(128)
            port=listener.getsockname()[1];origin='https://127.0.0.1:'+str(port)
            app=install_dashboard(create_app(session_manager=manager),manager,origin)
            server=uvicorn.Server(server_config(app,port=port,ssl_keyfile=str(root/'key.pem'),ssl_certfile=str(root/'cert.pem')))
            thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
            try:
                deadline=time.monotonic()+5
                while not server.started:
                    self.assertTrue(thread.is_alive());self.assertLess(time.monotonic(),deadline);time.sleep(.01)
                with httpx.Client(base_url=origin,verify=context,trust_env=False) as client:
                    pair=client.post('/v1/sessions',headers={'Authorization':'Bearer '+OPERATOR},json={
                        'mode':'replay','ttl_seconds':30,'pi':{'source_id':'pi','boot_id':'b'},
                        'phone':{'source_id':'phone','boot_id':'c'}}).json()
                    token=client.post('/v1/dashboard-viewers',headers={'Authorization':'Bearer '+OPERATOR},
                        json={'session_id':pair['session_id']}).json()['viewer_token']
                    self.assertEqual(client.post('/dashboard/api/login',headers={'Origin':origin},json={'viewer_token':token}).status_code,204)
                    self.assertEqual(client.get('/dashboard/api/snapshot').status_code,200)
                    async def denied():
                        for credential,options in [(pair['pi']['token'],{'origin':origin}),(token,{})]:
                            try:
                                async with connect(origin.replace('https:','wss:')+'/v1/events',ssl=context,proxy=None,
                                    additional_headers={'Authorization':'Bearer '+credential},**options):
                                    self.fail('Native role/Origin restriction changed')
                            except InvalidStatus as error: self.assertEqual(error.response.status_code,403)
                    asyncio.run(denied())
                    client.delete('/v1/sessions/'+pair['session_id'],headers={'Authorization':'Bearer '+OPERATOR})
                    self.assertEqual(client.get('/dashboard/api/snapshot').status_code,401)
            finally:
                server.should_exit=True;thread.join(5)
                self.assertFalse(thread.is_alive())


if __name__=='__main__': unittest.main()
