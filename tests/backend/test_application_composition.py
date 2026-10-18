"""Accepted optional backend factories compose without external services/secrets."""
import json
import os
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch


from backend.deploy import build_application

class ApplicationCompositionTests(unittest.TestCase):
    def test_builder_rejects_mutable_base_and_production_tag_before_docker(self):
        with patch.object(build_application,'inspect') as inspect:
            for reference in ('canesight:latest','sha256:short','registry/image:latest'):
                with self.assertRaises(ValueError): build_application.build(reference)
            with self.assertRaises(ValueError):
                build_application.build('sha256:'+'a'*64,tag='canesight:production')
            inspect.assert_not_called()

    def test_builder_refuses_poisoned_content_named_base_tag(self):
        with patch.object(build_application,'inspect',side_effect=['sha256:'+'a'*64,'sha256:'+'b'*64]), \
                patch.object(build_application.subprocess,'run') as docker:
            with self.assertRaises(RuntimeError): build_application.build('sha256:'+'a'*64)
            docker.assert_not_called()

    def test_overlay_preserves_native_credentials_resources_and_readonly_model_mount(self):
        root = Path(__file__).resolve().parents[2]
        deploy = root/'backend/deploy'
        environment = dict(os.environ, BACKEND_IMAGE='sha256:'+'a'*64,
            CADDY_IMAGE='caddy@sha256:'+'b'*64, CANESIGHT_DOMAIN='backend.example',
            CANESIGHT_VISION_HOST_WEIGHTS='/private/model.pt')
        result = subprocess.run(['docker','compose','-f',str(deploy/'compose.yaml'),
            '-f',str(deploy/'compose.vision.yaml'),'-f',str(deploy/'compose.application.yaml'),
            'config','--format','json','--no-env-resolution'],env=environment,
            capture_output=True,text=True)
        self.assertEqual(result.returncode,0,'Compose configuration failed; details suppressed')
        configuration=json.loads(result.stdout)
        backend=configuration['services']['backend']
        self.assertEqual(backend['network_mode'],'host')
        self.assertTrue(backend['read_only'])
        self.assertEqual(backend['user'],'10001:10001')
        self.assertEqual(int(backend['mem_limit']),2147483648)
        self.assertEqual(float(backend['cpus']),1.5)
        self.assertEqual(len(backend['env_file']),2)
        self.assertEqual(Path(backend['env_file'][0]['path']).name,'backend.env')
        self.assertEqual(Path(backend['env_file'][1]['path']).name,'application.env')
        self.assertTrue(all(Path(entry['path']).parent.name=='secrets' for entry in backend['env_file']))
        self.assertEqual(backend['command'][2],'backend.context.deployment')
        model=next(v for v in backend['volumes'] if v['target']=='/opt/canesight/models/yolov8n.pt')
        self.assertTrue(model['read_only'])
        self.assertNotIn('env_file',configuration['services']['proxy'])


if __name__ == '__main__': unittest.main()
