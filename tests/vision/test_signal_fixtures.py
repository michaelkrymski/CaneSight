"""CS-036 asset/provenance checks, not recognition or accuracy tests."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image

from backend.vision import signal_fixtures as fixtures


class SignalFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.copy = Path(self.temporary.name)/'pack'

    def copied_manifest(self):
        shutil.copytree(fixtures.PACK,self.copy)
        return json.loads((self.copy/'manifest.json').read_text(encoding='utf-8'))

    def write_manifest(self,doc):
        (self.copy/'manifest.json').write_text(json.dumps(doc),encoding='utf-8')

    def test_committed_pack_has_12_cases_and_18_verified_frames(self):
        result = fixtures.verify()
        self.assertEqual((result['cases'],result['frames']), (12,18))
        self.assertEqual(result['mode'],'replay')
        self.assertFalse(result['automatic_pedestrian_recognition'])

    def test_reproduces_all_pixels_and_manual_annotations(self):
        new = fixtures.generate(self.copy)
        old = json.loads((fixtures.PACK/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(fixtures.verify(self.copy)['frames'],18)
        # Encoded PNG hashes may vary with zlib/Pillow builds; pixel and
        # annotation identity is the reproducibility contract across hosts.
        for new_case, old_case in zip(new['cases'],old['cases']):
            self.assertEqual(new_case['id'],old_case['id'])
            self.assertEqual(len(new_case['frames']),len(old_case['frames']))
            for new_frame, old_frame in zip(new_case['frames'],old_case['frames']):
                self.assertEqual({k:v for k,v in new_frame.items() if k != 'sha256'},
                                 {k:v for k,v in old_frame.items() if k != 'sha256'})
        for case in old['cases']:
            for frame in case['frames']:
                with Image.open(self.copy/frame['file']) as image:
                    self.assertEqual(hashlib.sha256(image.tobytes()).hexdigest(),frame['rgb_sha256'])

    def test_generator_never_overwrites_an_existing_directory(self):
        self.copy.mkdir()
        sentinel = self.copy/'operator-file.txt'
        sentinel.write_text('preserve',encoding='utf-8')
        with self.assertRaises(FileExistsError):
            fixtures.generate(self.copy)
        self.assertEqual(sentinel.read_text(encoding='utf-8'),'preserve')

    def test_drawing_labels_do_not_become_production_signal_observations(self):
        doc = json.loads((fixtures.PACK/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(doc['production_signal'],dict(candidate_count=0,symbol='unknown',confidence=None,countdown_s=None))
        cases = {case['id']:case for case in doc['cases']}
        self.assertEqual([f['drawn_digits'] for f in cases['countdown']['frames']],['12','11'])
        self.assertIsNone(cases['ambiguous_digits']['frames'][0]['drawn_digits'])
        self.assertEqual(cases['no_signal']['frames'][0]['manual_rois'],[])
        self.assertEqual(cases['generic_traffic_light']['frames'][0]['manual_rois'][0]['kind'],'generic_traffic_light')

    def test_flashing_and_target_loss_require_the_authored_sequence(self):
        doc = json.loads((fixtures.PACK/'manifest.json').read_text(encoding='utf-8'))
        cases = {case['id']:case for case in doc['cases']}
        self.assertEqual([f['drawn_content'] for f in cases['flashing']['frames']],['hand','off','hand','off'])
        self.assertEqual([f['relative_replay_ms'] for f in cases['flashing']['frames']],[0,500,1000,1500])
        self.assertEqual([f['authored_target_id'] for f in cases['track_loss']['frames']],['target-a',None,'target-b'])
        self.assertEqual(len(cases['multiple_heads']['frames'][0]['manual_rois']),2)

    def test_rejects_relabeling_live_or_asserting_recognition(self):
        doc = self.copied_manifest()
        for key,value in [('mode','live'),('automatic_pedestrian_recognition',True),
                          ('license','unspecified'),('source','unverified-external-image')]:
            changed = dict(doc,**{key:value})
            self.write_manifest(changed)
            with self.subTest(key=key), self.assertRaises(ValueError):
                fixtures.verify(self.copy)
        changed = dict(doc,production_signal=dict(candidate_count=1,symbol='walk',confidence=1,countdown_s=12))
        self.write_manifest(changed)
        with self.assertRaises(ValueError):
            fixtures.verify(self.copy)

    def test_rejects_changed_image_bytes(self):
        doc = self.copied_manifest()
        path = self.copy/doc['cases'][0]['frames'][0]['file']
        path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            fixtures.verify(self.copy)

    def test_rejects_escaping_paths_and_misrepresented_manual_rois(self):
        doc = self.copied_manifest()
        frame = doc['cases'][2]['frames'][0]
        for name in ('../outside.png','images/../../outside.png'):
            original = frame['file'];frame['file']=name;self.write_manifest(doc)
            with self.assertRaisesRegex(ValueError,'path'):
                fixtures.verify(self.copy)
            frame['file']=original
        roi = frame['manual_rois'][0]
        roi['provenance']='automatic_detector';self.write_manifest(doc)
        with self.assertRaisesRegex(ValueError,'ROI'):
            fixtures.verify(self.copy)
        roi['provenance']='manual_fixture_annotation';roi['box_xyxy']=[-1,0,417,416];self.write_manifest(doc)
        with self.assertRaisesRegex(ValueError,'ROI'):
            fixtures.verify(self.copy)

    def test_rejects_timeline_reversal(self):
        doc = self.copied_manifest()
        next(c for c in doc['cases'] if c['id']=='flashing')['frames'][1]['relative_replay_ms']=0
        self.write_manifest(doc)
        with self.assertRaisesRegex(ValueError,'timeline'):
            fixtures.verify(self.copy)


if __name__ == '__main__':
    unittest.main()
