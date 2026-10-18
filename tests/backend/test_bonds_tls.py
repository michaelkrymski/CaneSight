"""Real native bond client over generated, certificate-verified HTTPS."""
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

import trustme
import uvicorn
from backend.app import create_app
from backend.bonds import provision, install_bonds
from backend.bond_client import BondClient
from backend.sessions import SessionManager


class NativeTLSBondTests(unittest.TestCase):
    def test_native_pair_and_recovery_over_real_tls(self):
        with tempfile.TemporaryDirectory() as temporary, socket.socket() as listener:
            folder=Path(temporary)
            listener.bind(('127.0.0.1',0))
            base='https://127.0.0.1:'+str(listener.getsockname()[1])
            ca=trustme.CA()
            cert=ca.issue_cert('127.0.0.1')
            ca.cert_pem.write_to_path(folder/'ca.pem')
            cert.private_key_pem.write_to_path(folder/'key.pem')
            cert.cert_chain_pems[0].write_to_path(folder/'cert.pem')
            provision(folder/'bond',base,'fixture-cane','fixture-phone','fixture-pi')
            now=[1000.]
            manager=SessionManager('fixture-operator-only-no-real-secret-12345',clock=lambda:now[0])
            app=create_app(session_manager=manager)
            install_bonds(app,manager,folder/'bond/registry.json')
            server=uvicorn.Server(uvicorn.Config(app,access_log=False,log_level='critical',
                ssl_keyfile=str(folder/'key.pem'),ssl_certfile=str(folder/'cert.pem')))
            thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True)
            thread.start()
            try:
                deadline=time.monotonic()+5
                while not server.started and thread.is_alive() and time.monotonic()<deadline:
                    time.sleep(.02)
                self.assertTrue(server.started)
                ca_file=str(folder/'ca.pem')
                phone=BondClient(folder/'bond/phone-bond.json','phone',ca_file=ca_file)
                pi=BondClient(folder/'bond/pi-bond.json','pi',ca_file=ca_file)
                self.assertIsNone(phone.poll('phone-boot'))
                pair=pi.poll('pi-boot')
                self.assertEqual(phone.poll('phone-boot')['session_id'],pair['session_id'])
                now[0]+=601
                self.assertIsNone(phone.poll('phone-boot'))
                second=pi.poll('pi-boot')
                self.assertNotEqual(second['session_id'],pair['session_id'])
                self.assertNotEqual(second['device']['token'],pair['device']['token'])
                # Native TLS checks remain active, including for saved bonds.
                untrusted=BondClient(folder/'bond/pi-bond.json','pi')
                with self.assertRaises(ConnectionError):
                    untrusted.poll('pi-boot')
            finally:
                server.should_exit=True
                thread.join(5)
                self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
