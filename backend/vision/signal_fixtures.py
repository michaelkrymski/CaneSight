"""CS-036: original synthetic replay assets, not an inference adapter/parser.

Generate a new pack or verify the committed pack. No network, model, real scene,
live envelope, service activation or detector output is involved.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw

PACK = Path(__file__).resolve().parents[2] / 'qa/vision/signal-fixtures'
SIZE = (416, 416)
PANEL = (104, 96, 312, 344)
LICENSE = 'CC0-1.0'
# Original small bitmap lettering: no font files or third-party art are used.
LETTERS = {
    'R': ('11110','10001','10001','11110','10100','10010','10001'),
    'E': ('11111','10000','10000','11110','10000','10000','11111'),
    'P': ('11110','10001','10001','11110','10000','10000','10000'),
    'L': ('10000','10000','10000','10000','10000','10000','11111'),
    'A': ('01110','10001','10001','11111','10001','10001','10001'),
    'Y': ('10001','10001','01010','00100','00100','00100','00100'),
    'M': ('10001','11011','10101','10101','10001','10001','10001'),
    'N': ('10001','11001','10101','10011','10001','10001','10001'),
    'U': ('10001','10001','10001','10001','10001','10001','01110'),
    'O': ('01110','10001','10001','10001','10001','10001','01110'),
    'I': ('11111','00100','00100','00100','00100','00100','11111'),
    ' ': ('00000',)*7,
}
SEGMENTS = {'0':'abcedf', '1':'bc', '2':'abged', '3':'abgcd', '4':'fgbc',
            '5':'afgcd', '6':'afgecd', '7':'abc', '8':'abcdefg', '9':'abfgcd'}


def lettering(draw, text, y, scale=3):
    x = (416 - (len(text) * 6 - 1) * scale) // 2
    for letter in text:
        for row, bits in enumerate(LETTERS[letter]):
            for col, bit in enumerate(bits):
                if bit == '1':
                    draw.rectangle((x+col*scale, y+row*scale,
                                    x+(col+1)*scale-1, y+(row+1)*scale-1), fill='white')
        x += 6 * scale


def digit(draw, value, x, y):
    rects = {'a':(4,0,24,4), 'b':(24,4,28,22), 'c':(24,26,28,44),
             'd':(4,44,24,48), 'e':(0,26,4,44), 'f':(0,4,4,22), 'g':(4,22,24,26)}
    for segment in SEGMENTS[value]:
        x1,y1,x2,y2 = rects[segment]
        draw.rectangle((x+x1,y+y1,x+x2,y+y2), fill='#ffb040')


def panel(kind, digits=None):
    image = Image.new('RGB', (208, 248), '#101014')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0,0,207,247), outline='#808090', width=4)
    if kind == 'walk':
        draw.ellipse((92,25,116,49), fill='white')
        draw.line((104,54,104,106), fill='white', width=13)
        draw.line((104,65,73,92), fill='white', width=11)
        draw.line((104,65,135,82), fill='white', width=11)
        draw.line((104,102,80,155), fill='white', width=13)
        draw.line((104,102,134,144), fill='white', width=13)
    elif kind == 'hand':
        draw.polygon([(66,103),(54,82),(48,86),(48,110),(68,148),(119,148),
                      (141,115),(141,65),(133,62),(128,72),(128,105),
                      (120,105),(120,40),(112,36),(106,44),(106,99),
                      (99,99),(99,29),(91,26),(85,34),(85,100),
                      (78,100),(78,48),(70,45),(64,53)], fill='#ff9830')
    elif kind != 'off':
        raise ValueError('Unknown fixture panel')
    if digits is not None:
        for index, value in enumerate(digits):
            digit(draw, value, 64+index*42, 180)
    return image


def scenarios():
    # Ordered artistic content and relative replay timing, not detector truth.
    return [
        ('no_signal', [('none',None)], [0], 'No signal panel; absence is not clearance.'),
        ('generic_traffic_light', [('traffic',None)], [0], 'Vehicle-style light; not a pedestrian classifier.'),
        ('walk_like', [('walk',None)], [0], 'Original schematic walking figure, not a real signal photo.'),
        ('hand_like', [('hand',None)], [0], 'Original schematic raised hand, not a real signal photo.'),
        ('countdown', [('hand','12'),('hand','11')], [0,1000], 'Drawn digits only; no crossing-time extrapolation.'),
        ('flashing', [('hand',None),('off',None),('hand',None),('off',None)],
         [0,500,1000,1500], 'Alternation is an authored sequence; a single frame cannot establish flashing.'),
        ('multiple_heads', [('multiple',None)], [0], 'Two conflicting schematic heads; applicability is unknown.'),
        ('occluded', [('occluded',None)], [0], 'Opaque mask; no retained symbol claim.'),
        ('glare', [('glare',None)], [0], 'Synthetic white wash; not representative lighting validation.'),
        ('low_resolution', [('low_resolution',None)], [0], 'Panel reduced to 12x14 then enlarged; detail is limited.'),
        ('ambiguous_digits', [('ambiguous_digits',None)], [0], 'Broken/obscured segments; intended digit value is null.'),
        ('track_loss', [('walk',None),('none',None),('hand',None)],
         [0,500,1000], 'Target A disappears; target B must not inherit its state.'),
    ]


def render(kind, digits=None):
    image = Image.new('RGB', SIZE, '#202830')
    draw = ImageDraw.Draw(image)
    rois = []
    if kind == 'traffic':
        draw.rectangle((165,96,251,344), fill='#101014', outline='#808090', width=4)
        for y, color in ((145,'#802020'),(220,'#806020'),(295,'#30d050')):
            draw.ellipse((181,y-25,235,y+25), fill=color)
        rois.append({'box_xyxy':[165,96,252,345], 'kind':'generic_traffic_light'})
    elif kind == 'multiple':
        for box, symbol in (((24,108,192,308),'walk'),((224,108,392,308),'hand')):
            image.paste(panel(symbol).resize((box[2]-box[0],box[3]-box[1]), Image.Resampling.NEAREST), box[:2])
            rois.append({'box_xyxy':list(box), 'kind':'schematic_panel'})
    elif kind != 'none':
        symbol = 'walk' if kind in ('walk','glare','low_resolution') else 'off' if kind == 'off' else 'hand'
        target = panel(symbol, digits)
        mask = ImageDraw.Draw(target)
        if kind == 'occluded':
            mask.rectangle((15,45,190,132), fill='#505050')
        elif kind == 'glare':
            mask.ellipse((-30,0,238,230), fill='white')
        elif kind == 'low_resolution':
            target = target.resize((12,14), Image.Resampling.NEAREST).resize((208,248), Image.Resampling.NEAREST)
        elif kind == 'ambiguous_digits':
            digit(mask,'8',64,180)
            digit(mask,'3',106,180)
            mask.rectangle((64,188,139,215), fill='#505050')
        elif kind not in ('walk','hand','off'):
            raise ValueError('Unknown fixture content')
        image.paste(target, PANEL[:2])
        rois.append({'box_xyxy':list(PANEL), 'kind':'schematic_panel'})
    draw = ImageDraw.Draw(image)
    draw.rectangle((0,0,415,68), fill='#702030')
    lettering(draw,'REPLAY',10,4)
    draw.rectangle((0,365,415,415), fill='#303050')
    lettering(draw,'MANUAL ROI' if rois else 'NO ROI',380,3)
    return image, rois


def generate(destination):
    """Create a new directory only; never overwrite accepted assets/evidence."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'images').mkdir()
    cases = []
    for case_id, contents, times, note in scenarios():
        frames = []
        for index, ((kind, digits), relative_ms) in enumerate(zip(contents,times)):
            image, rois = render(kind,digits)
            name = f'images/{case_id}-{index:02}.png'
            data = io.BytesIO()
            image.save(data,format='PNG',compress_level=9)
            raw = data.getvalue()
            (destination/name).write_bytes(raw)
            for roi in rois:
                roi['provenance'] = 'manual_fixture_annotation'
            target = ('target-a' if index == 0 else 'target-b') if case_id == 'track_loss' and rois else None
            frames.append({'file':name, 'sha256':hashlib.sha256(raw).hexdigest(),
                           'rgb_sha256':hashlib.sha256(image.tobytes()).hexdigest(),
                           'relative_replay_ms':relative_ms, 'drawn_content':kind,
                           'drawn_digits':digits, 'manual_rois':rois,
                           'authored_target_id':target})
        cases.append({'id':case_id, 'note':note, 'frames':frames})
    result = {
        'fixture_pack_version':1, 'mode':'replay', 'origin':'original_procedural_schematic',
        'license':LICENSE, 'license_url':'https://creativecommons.org/publicdomain/zero/1.0/',
        'source':'backend/vision/signal_fixtures.py', 'author':'CaneSight contributors (AI-assisted)',
        'image':{'width':416,'height':416,'format':'PNG','color_mode':'RGB'},
        'automatic_pedestrian_recognition':False,
        'production_signal':{'candidate_count':0,'symbol':'unknown','confidence':None,'countdown_s':None},
        'limits':['Original schematic assets, not real scenes or a representative training/evaluation dataset.',
                  'Manual boxes and artistic content are annotations, not automatic detections.',
                  'Relative replay time is not a live source/capture timestamp.',
                  'No training, recognition accuracy, route clearance or crossing permission.'],
        'cases':cases,
    }
    (destination/'manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    return result


def verify(root=PACK):
    """Verify provenance, replay isolation, image hashes and bounded manual ROIs."""
    root = Path(root).resolve()
    with (root/'manifest.json').open('rb') as source:
        raw = source.read(131073)
    if len(raw) > 131072:
        raise ValueError('Oversized fixture manifest')
    doc = json.loads(raw)
    if (doc['fixture_pack_version'] != 1 or doc['mode'] != 'replay'
            or doc['origin'] != 'original_procedural_schematic' or doc['license'] != LICENSE
            or doc['license_url'] != 'https://creativecommons.org/publicdomain/zero/1.0/'
            or doc['source'] != 'backend/vision/signal_fixtures.py'
            or doc['image'] != {'width':416,'height':416,'format':'PNG','color_mode':'RGB'}
            or doc['automatic_pedestrian_recognition'] is not False
            or doc['production_signal'] != {'candidate_count':0,'symbol':'unknown','confidence':None,'countdown_s':None}):
        raise ValueError('Fixture provenance or replay/unknown boundary changed')
    if not 1 <= len(doc['cases']) <= 32:
        raise ValueError('Invalid fixture case count')
    seen, case_ids, count = set(), set(), 0
    for case in doc['cases']:
        if case['id'] in case_ids or not 1 <= len(case['frames']) <= 16:
            raise ValueError('Duplicate case or invalid frame count')
        case_ids.add(case['id'])
        last = -1
        for frame in case['frames']:
            path = (root/frame['file']).resolve()
            if not path.is_relative_to(root/'images') or path in seen:
                raise ValueError('Escaping or repeated fixture path')
            seen.add(path)
            if path.stat().st_size > 1000000:
                raise ValueError('Oversized fixture image')
            encoded = path.read_bytes()
            if hashlib.sha256(encoded).hexdigest() != frame['sha256']:
                raise ValueError('Fixture SHA-256 mismatch')
            with Image.open(io.BytesIO(encoded)) as image:
                if image.size != SIZE or image.mode != 'RGB' or image.format != 'PNG':
                    raise ValueError('Unexpected fixture image format')
                image.load()
                if hashlib.sha256(image.tobytes()).hexdigest() != frame['rgb_sha256']:
                    raise ValueError('Fixture pixel hash mismatch')
            when = frame['relative_replay_ms']
            if type(when) is not int or not last < when <= 60000:
                raise ValueError('Invalid replay timeline')
            last = when
            if len(frame['manual_rois']) > 4:
                raise ValueError('Unbounded manual ROI count')
            for roi in frame['manual_rois']:
                box = roi['box_xyxy']
                if (roi['provenance'] != 'manual_fixture_annotation' or len(box) != 4
                        or any(type(v) is not int for v in box)
                        or not 0 <= box[0] < box[2] <= 416 or not 0 <= box[1] < box[3] <= 416):
                    raise ValueError('Invalid manual ROI annotation')
            count += 1
    return {'mode':'replay','cases':len(case_ids),'frames':count,'license':doc['license'],
            'automatic_pedestrian_recognition':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--generate',type=Path,help='New output directory only')
    group.add_argument('--check',type=Path,default=PACK)
    args = parser.parse_args()
    if args.generate:
        generate(args.generate)
    print(json.dumps(verify(args.generate or args.check),indent=2))


if __name__ == '__main__':
    main()
