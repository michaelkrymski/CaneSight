"""Verified TLS with synthetic phone -> real native relay -> Pi policy simulation."""
import asyncio
import json
from pathlib import Path
import secrets
import socket
import ssl
import tempfile
import threading
import time
import unittest
import httpx
import trustme
import uvicorn
from websockets.asyncio.client import connect
from backend.app import create_app
from backend.sessions import SessionManager
from backend.server import server_config
from edge.receiver import VisionReceiver
from edge.policy import LocalPolicy, PhoneBinding
from edge.haptics import HapticScheduler
from edge.uploader import Sender, Latest

class PolicyTransportTests(unittest.TestCase):
    def test_verified_native_phone_clock_depth_and_interruption_cancel(self):
        operator=secrets.token_urlsafe(40)
        with tempfile.TemporaryDirectory() as folder, socket.socket() as listener:
            root=Path(folder);ca=trustme.CA();cert=ca.issue_cert('127.0.0.1')
            cert.private_key_pem.write_to_path(root/'key.pem');cert.cert_chain_pems[0].write_to_path(root/'cert.pem');ca.cert_pem.write_to_path(root/'ca.pem')
            context=ssl.create_default_context();ca.configure_trust(context)
            listener.bind(('127.0.0.1',0));listener.listen(128);port=listener.getsockname()[1]
            server=uvicorn.Server(server_config(create_app(session_manager=SessionManager(operator)),port=port,ssl_keyfile=str(root/'key.pem'),ssl_certfile=str(root/'cert.pem')))
            thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
            receiver=policy=scheduler=None
            try:
                end=time.monotonic()+5
                while not server.started:
                    self.assertTrue(thread.is_alive());self.assertLess(time.monotonic(),end);time.sleep(.01)
                base='https://127.0.0.1:'+str(port)
                with httpx.Client(base_url=base,verify=context,trust_env=False) as client:
                    pair=client.post('/v1/sessions',headers={'Authorization':'Bearer '+operator},json=dict(mode='live',ttl_seconds=60,pi=dict(source_id='pi',boot_id='boot'),phone=dict(source_id='phone',boot_id='phone-boot'))).json()
                clock=lambda:time.monotonic()*1000
                session=dict(base_url=base,session_id=pair['session_id'],mode='live',**{k:pair['pi'][k] for k in ('source_id','boot_id','token')})
                receiver=VisionReceiver(session,clock=clock,ca_file=str(root/'ca.pem'),phone_binding=PhoneBinding('phone','phone-boot',0))
                Sender(Latest(),None,receiver=receiver)
                scheduler=HapticScheduler(clock=clock).start()
                policy=LocalPolicy(receiver.gate,'phone',scheduler,clock=clock).start();policy.arm(True)
                async def phone():
                    async with connect('wss://127.0.0.1:'+str(port)+'/v1/telemetry',ssl=context,proxy=None,additional_headers={'Authorization':'Bearer '+pair['phone']['token']}) as peer:
                        receiver.start()
                        probe=json.loads(await asyncio.wait_for(peer.recv(),3))
                        self.assertEqual(probe['type'],'clock_probe')
                        reply=dict(probe,type='clock_reply',t2_ms=clock(),t3_ms=clock())
                        await peer.send(json.dumps(reply))
                        await asyncio.sleep(.1)
                        def packet(kind,seq,**fields):
                            return dict(schema_version=1,type=kind,session_id=pair['session_id'],mode='live',source_id='phone',boot_id='phone-boot',seq=seq,capture_monotonic_ms=clock()-40,capture_utc=None,**fields)
                        await peer.send(json.dumps(packet('heartbeat',1,state='ready')))
                        await asyncio.sleep(.1)
                        sectors={name:dict(distance_m=.7 if name=='left' else 2,valid_fraction=1) for name in ('left','center','right')}
                        await peer.send(json.dumps(packet('depth_observation',1,tracking='normal',sectors=sectors)))
                        await asyncio.sleep(.1)
                        await peer.send(json.dumps(packet('depth_observation',2,tracking='normal',sectors=sectors)))
                        end=time.monotonic()+2
                        while not scheduler.snapshot()['outputs']['left']:
                            self.assertLess(time.monotonic(),end,policy.snapshot());await asyncio.sleep(.005)
                        self.assertEqual(receiver.phone_accepted,2)
                        self.assertEqual(policy.hazards['left'],'nearby')
                        self.assertFalse(scheduler.snapshot()['outputs']['right'])
                        # A ready socket/vision cannot override explicit depth interruption.
                        await peer.send(json.dumps(packet('heartbeat',2,state='unavailable')))
                        end=time.monotonic()+1
                        while policy.hazards['left']!='unknown':
                            self.assertLess(time.monotonic(),end);await asyncio.sleep(.005)
                        self.assertFalse(any(scheduler.snapshot()['outputs'].values()))
                asyncio.run(phone())
                receiver.stop();policy.tick()
                self.assertFalse(any(scheduler.snapshot()['outputs'].values()))
            finally:
                if policy:policy.close()
                if scheduler:scheduler.close()
                if receiver:receiver.stop()
                server.should_exit=True;thread.join(5)
                self.assertFalse(thread.is_alive())
