"""Exercise the manual schematic parser on accepted CS-036 replay frames."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform

import PIL
from PIL import Image

from .signal_fixtures import PACK, verify
from .signal_parser import PROFILE, ReplaySignalParser


def run():
    pack = verify()
    doc = json.loads((PACK/'manifest.json').read_text(encoding='utf-8'))
    cases = []
    for case in doc['cases']:
        parser = ReplaySignalParser()
        frames = []
        for i, frame in enumerate(case['frames']):
            # Content/digit annotations are intentionally not parser inputs.
            with Image.open(PACK/frame['file']) as image:
                result = parser.observe(image,mode='replay',sequence=i,
                                        replay_ms=frame['relative_replay_ms'],
                                        target_id=frame['authored_target_id'] or case['id'],
                                        manual_rois=frame['manual_rois'])
            frames.append({'file':frame['file'],'relative_replay_ms':frame['relative_replay_ms'],
                           'result':asdict(result)})
        cases.append({'id':case['id'],'frames':frames})
    by_id = {case['id']:case['frames'] for case in cases}
    assert by_id['countdown'][-1]['result']['countdown_s'] == 11
    assert by_id['flashing'][-1]['result']['temporal_state'] == 'flashing_or_uncertain'
    for case in ('no_signal','generic_traffic_light','multiple_heads','occluded','glare','low_resolution','track_loss'):
        assert all(frame['result']['symbol']=='unknown' for frame in by_id[case])
    return {
        'task':'CS-037','profile':PROFILE,'mode':'replay',
        'python':platform.python_version(),'pillow':PIL.__version__,
        'fixture_manifest_sha256':hashlib.sha256((PACK/'manifest.json').read_bytes()).hexdigest(),
        'fixture_cases':pack['cases'],'fixture_frames':pack['frames'],
        'template_sources':['CS-036 walk_like-00.png','CS-036 hand_like-00.png'],
        'template_license':'CC0-1.0','training_performed':False,
        'cases':cases,
        'limits':[
            'Known schematic profile and manually annotated replay ROIs only; not automatic real-world recognition.',
            'Single-frame positive silhouettes remain unconfirmed; countdown sequence confirms only drawn 11.',
            'Similarity thresholds are hand-set engineering rules, not calibrated confidence.',
            'No held-out evaluation, real-scene/OCR accuracy, live timing, transport, hardware or crossing permission.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,help='New JSON evidence file; never overwrite')
    args = parser.parse_args()
    result = run()
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        with args.report.open('x',encoding='utf-8') as output:
            output.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'profile':PROFILE,'mode':'replay','cases':result['fixture_cases'],
                      'frames':result['fixture_frames'],'regression_checks':'passed'},indent=2))


if __name__ == '__main__':
    main()
