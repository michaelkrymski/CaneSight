"""Artifact bytes/provenance tests using inert bytes, never model files."""
from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.vision.signal_artifacts import SignalArtifactRecord, inspect_signal_artifact
from backend.vision.scenario_adapters import live_capabilities


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'inert.bin'
        self.data = b'authored inert test bytes, not YOLO weights'
        self.path.write_bytes(self.data)
        self.record = SignalArtifactRecord(hashlib.sha256(self.data).hexdigest(), len(self.data),
            ('walk','dont_walk'), 'authored synthetic test bytes', 'CC0-1.0 (test only)',
            'no real scenes: fixture only', 'no model evaluation: fixture only', ('day',))

    def test_verified_identity_never_enables_loading_or_live_capability(self):
        result = inspect_signal_artifact(self.path,self.record)
        self.assertTrue(result.integrity_verified)
        self.assertFalse(result.live_supported)
        self.assertEqual(result.sha256,hashlib.sha256(self.data).hexdigest())
        self.assertEqual(set(live_capabilities().values()), {False})

    def test_missing_truncated_oversize_and_same_length_corruption_rejected(self):
        for data in (b'',self.data[:-1],self.data+b'x',b'x'*len(self.data)):
            self.path.write_bytes(data)
            with self.assertRaises(ValueError):
                inspect_signal_artifact(self.path,self.record)
        self.path.unlink()
        with self.assertRaises(ValueError):
            inspect_signal_artifact(self.path,self.record)

    def test_generic_coco_labels_are_not_custom_signal_classes(self):
        with self.assertRaises(ValueError):
            inspect_signal_artifact(self.path,replace(self.record,classes=('person','traffic_light')))

    def test_incomplete_malformed_and_unbounded_records_rejected_before_file_access(self):
        for fields in ({'sha256':'x'*64}, {'size_bytes':True}, {'size_bytes':100_000_001},
                       {'classes':('walk','dont_walk','walk')}, {'classes':('walk',)},
                       {'classes':('walk','dont_walk',[])},
                       {'source':''}, {'license':' '}, {'training_scene_split':''},
                       {'evaluation_report':''}, {'supported_conditions':()},
                       {'supported_conditions':('rain',)}, {'supported_conditions':('day',[])},
                       {'supported_conditions':('day','day')}):
            with self.subTest(fields=fields), patch.object(Path,'open') as opened:
                with self.assertRaises(ValueError):
                    inspect_signal_artifact(self.path,replace(self.record,**fields))
                opened.assert_not_called()

    def test_night_metadata_does_not_enable_night_adapter(self):
        result = inspect_signal_artifact(self.path,replace(self.record,supported_conditions=('day','night')))
        self.assertFalse(result.live_supported)


if __name__ == '__main__':
    unittest.main()
