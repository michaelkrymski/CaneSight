"""Fast offline tests: python -m unittest discover -s tests/vision -v.

Actual weight loading/inference is separately exercised by backend.vision.smoke.
These tests need neither ML packages nor network/model downloads.
"""
import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.vision import baseline


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'yolov8n.pt'
        self.data = b'trusted test fixture, not a PyTorch checkpoint'
        self.spec = baseline.manifest()
        self.spec['artifact'].update(bytes=len(self.data), sha256=hashlib.sha256(self.data).hexdigest())

    def test_exact_manifest_classes_and_unsupported_signal_capabilities(self):
        spec = baseline.manifest()
        self.assertEqual(len(spec['classes']), 80)
        self.assertEqual(spec['classes'][9], 'traffic light')
        self.assertEqual(spec['classes'][0], 'person')
        self.assertEqual(spec['license']['publisher_identifier'], 'AGPL-3.0')
        for key in ('pedestrian_signal_recognition', 'walk_hand_recognition',
                    'countdown_recognition', 'crossing_permission'):
            self.assertIs(spec['capabilities'][key], False)

    def test_verified_bytes_and_same_size_corruption(self):
        self.path.write_bytes(self.data)
        with patch.object(baseline, 'manifest', return_value=self.spec):
            self.assertEqual(baseline.verify_weights(self.path), self.path.resolve())
            self.path.write_bytes(b'x' * len(self.data))
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                baseline.verify_weights(self.path)

    def test_truncated_and_oversize_weights_rejected(self):
        with patch.object(baseline, 'manifest', return_value=self.spec):
            for data in (self.data[:-1], self.data + b'x'):
                self.path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, 'size'):
                    baseline.verify_weights(self.path)

    def test_missing_weights_fail_before_runtime_or_model_import(self):
        with patch.object(baseline, 'runtime_versions') as runtime:
            with self.assertRaises(FileNotFoundError):
                baseline.load_baseline(self.path)
            runtime.assert_not_called()

    def response(self, data, url='https://release-assets.githubusercontent.com/weights'):
        response = io.BytesIO(data)
        response.geturl = lambda: url
        return response

    def test_explicit_download_installs_verified_artifact(self):
        with patch.object(baseline, 'manifest', return_value=self.spec), patch.object(
                baseline.urllib.request, 'urlopen', return_value=self.response(self.data)) as download:
            self.assertEqual(baseline.download_weights(self.path), self.path.resolve())
            self.assertEqual(self.path.read_bytes(), self.data)
            self.assertEqual(download.call_args.args[0], self.spec['artifact']['url'])
            self.assertEqual(list(self.path.parent.glob('*.part')), [])

    def test_download_rejects_corrupt_oversize_and_partial_artifacts(self):
        for data in (b'x' * len(self.data), self.data[:-1], self.data + b'x' * 100000):
            with self.subTest(size=len(data)), patch.object(baseline, 'manifest', return_value=self.spec), patch.object(
                    baseline.urllib.request, 'urlopen', return_value=self.response(data)):
                with self.assertRaises(ValueError):
                    baseline.download_weights(self.path)
                self.assertFalse(self.path.exists())
                self.assertEqual(list(self.path.parent.glob('*.part')), [])

    def test_existing_corrupt_model_is_not_silently_replaced(self):
        self.path.write_bytes(b'x' * len(self.data))
        with patch.object(baseline, 'manifest', return_value=self.spec), patch.object(
                baseline.urllib.request, 'urlopen') as download:
            with self.assertRaises(ValueError):
                baseline.download_weights(self.path)
            download.assert_not_called()

    def test_download_requires_final_https_url(self):
        with patch.object(baseline, 'manifest', return_value=self.spec), patch.object(
                baseline.urllib.request, 'urlopen', return_value=self.response(self.data, 'http://example.com')):
            with self.assertRaisesRegex(ValueError, 'HTTPS'):
                baseline.download_weights(self.path)
            self.assertFalse(self.path.exists())

    def test_runtime_accepts_cpu_local_suffix_and_rejects_version_drift(self):
        spec = baseline.manifest()
        def version(package):
            return spec['runtime'][package] + ('+cpu' if package in ('torch', 'torchvision') else '')
        with patch.object(baseline.metadata, 'version', side_effect=version):
            self.assertEqual(baseline.runtime_versions()['torch'], '2.7.1+cpu')
        with patch.object(baseline.metadata, 'version', return_value='0.0.0'):
            with self.assertRaisesRegex(ValueError, 'requires'):
                baseline.runtime_versions()
        with patch.object(baseline.metadata, 'version', return_value='8.3.221+unreviewed'):
            with self.assertRaisesRegex(ValueError, 'requires'):
                baseline.runtime_versions()

    def test_loaded_class_mapping_must_match_every_id_and_name(self):
        names = dict(enumerate(baseline.manifest()['classes']))
        self.assertEqual(baseline.check_classes(names), list(names.values()))
        for changed in ({**names, 9: 'pedestrian signal'}, {**names, 80: 'WALK'},
                        {k: v for k, v in names.items() if k != 9}, list(names.values())):
            with self.subTest(mapping=type(changed)), self.assertRaises(ValueError):
                baseline.check_classes(changed)

    def test_config_parent_exists_before_ultralytics_import(self):
        root = Path(self.directory.name)
        with patch.object(baseline, 'ROOT', root), patch.dict(os.environ):
            baseline.configure_runtime()
            self.assertTrue((root / 'artifacts/runtime').is_dir())
            self.assertEqual(os.environ['YOLO_CONFIG_DIR'], str(root / 'artifacts/runtime'))
            self.assertEqual(os.environ['YOLO_OFFLINE'], 'true')
            self.assertEqual(os.environ['YOLO_AUTOINSTALL'], 'false')


if __name__ == '__main__':
    unittest.main()
