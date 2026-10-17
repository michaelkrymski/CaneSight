"""CS-037: manual-ROI replay parser for the CS-036 schematic profile only.

No live recognition, calibrated probabilities, transport or movement output.
Hand-authored silhouette/segment rules are not trained weights or general OCR.
"""
from collections import deque
from dataclasses import dataclass
import re

from PIL import Image, ImageChops, ImageDraw

from .signal_fixtures import PACK, verify

PROFILE = 'cs036-schematic-v1'
TTL_MS = 1500
SEGMENTS = {'0':'abcdef', '1':'bc', '2':'abdeg', '3':'abcdg', '4':'bcfg',
            '5':'acdfg', '6':'acdefg', '7':'abc', '8':'abcdefg', '9':'abcdfg'}
RECTS = {'a':(4,0,24,4), 'b':(24,4,28,22), 'c':(24,26,28,44),
         'd':(4,44,24,48), 'e':(0,26,4,44), 'f':(0,4,4,22), 'g':(4,22,24,26)}
WINDOWS = {'a':(6,1,22,4), 'b':(25,6,28,21), 'c':(25,28,28,43),
           'd':(6,45,22,48), 'e':(1,28,4,43), 'f':(1,6,4,21), 'g':(6,23,22,26)}


def foreground(image):
    # Brightness segments a silhouette; color never assigns the symbol.
    return image.convert('L').point(lambda value: 255 if value >= 150 else 0)


def area(mask):
    return mask.width * mask.height - mask.histogram()[0]


def iou(a, b):
    union = area(ImageChops.lighter(a,b))
    return area(ImageChops.darker(a,b)) / union if union else 0.0


def segment_template(value):
    image = Image.new('L',(29,49))
    draw = ImageDraw.Draw(image)
    for segment in SEGMENTS[value]:
        draw.rectangle(RECTS[segment],fill=255)
    return image


def read_digit(image):
    mask = foreground(image)
    if area(mask) == 0:
        return ''
    on = []
    for name, box in WINDOWS.items():
        window = mask.crop(box)
        coverage = area(window)/(window.width*window.height)
        if coverage >= .9:
            on.append(name)
        elif coverage > .1:
            return None
    pattern = set(on)
    for value, segments in SEGMENTS.items():
        if set(segments) == pattern:
            # Reject filled blocks, stray strokes and incomplete segment shapes.
            return value if iou(mask,segment_template(value)) >= .94 else None
    return None


def read_countdown(panel):
    digits = [read_digit(panel.crop((x,180,x+29,229))) for x in (64,106)]
    if any(value is None for value in digits) or not digits[1]:
        return None
    return int(''.join(digits))


@dataclass(frozen=True)
class ReplayResult:
    mode: str = 'replay'
    profile: str = PROFILE
    automatic_pedestrian_recognition: bool = False
    symbol: str = 'unknown'
    countdown_s: int | None = None
    confidence: None = None  # Shape similarity is not a calibrated probability.
    temporal_state: str = 'unknown'
    reason: str = 'no_evidence'
    shape_iou: float | None = None


class ReplaySignalParser:
    """Bounded sequence state for one explicit manual replay selection.

    replay_ms is authored replay position, never a device clock/capture-age
    assertion. Native source freshness and live classification remain separate.
    Call current() independently to expire results during a paused replay.
    """
    def __init__(self):
        verify(PACK)
        self.templates = {}
        for name, file in [('walk','walk_like-00.png'),('dont_walk','hand_like-00.png')]:
            with Image.open(PACK/'images'/file) as image:
                self.templates[name] = foreground(image.crop((104,96,312,344)).crop((16,16,192,170)))
        self.sequence = -1
        self.last_frame_ms = -1
        self.clock = -1
        self.captured = None
        self.clock_failed = False
        self._clear('no_evidence')

    def _clear(self, reason):
        self.target = None
        self.history = deque(maxlen=8)
        self.flashing = False
        self.previous_shape = None
        self.confirmations = 0
        self.streak_started = None
        self.previous_digit = None
        self.previous_digit_ms = None
        self.captured = None
        self.result = ReplayResult(reason=reason)
        return self.result

    def current(self, replay_ms):
        if type(replay_ms) is not int or not 0 <= replay_ms <= 2**53-1 or replay_ms < self.clock:
            self.clock_failed = True
        if self.clock_failed:
            return self._clear('replay_clock_invalid')
        self.clock = replay_ms
        if self.captured is not None and replay_ms - self.captured > TTL_MS:
            return self._clear('expired')
        return self.result

    def observe(self, image, *, mode, sequence, replay_ms, target_id, manual_rois):
        if self.clock_failed:
            return self._clear('replay_clock_invalid')
        if mode != 'replay':
            return self._clear('replay_only')
        if (type(sequence) is not int or not 0 <= sequence <= 2**53-1
                or type(replay_ms) is not int or not 0 <= replay_ms <= 2**53-1
                or sequence <= self.sequence or replay_ms < self.clock
                or replay_ms <= self.last_frame_ms):
            return self._clear('replayed_or_invalid_frame')
        self.sequence = sequence
        self.last_frame_ms = replay_ms
        self.clock = replay_ms
        if self.captured is not None and replay_ms - self.captured > TTL_MS:
            self._clear('gap')
        if (not isinstance(image,Image.Image) or image.size != (416,416) or image.mode != 'RGB'
                or not isinstance(manual_rois,list) or len(manual_rois) != 1
                or not isinstance(target_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',target_id)):
            return self._clear('missing_or_ambiguous_selection')
        roi = manual_rois[0]
        if not isinstance(roi,dict):
            return self._clear('invalid_manual_roi')
        box = roi.get('box_xyxy')
        if (roi.get('provenance') != 'manual_fixture_annotation' or roi.get('kind') != 'schematic_panel'
                or not isinstance(box,list) or len(box) != 4 or any(type(v) is not int for v in box)
                or not 0 <= box[0] < box[2] <= 416 or not 0 <= box[1] < box[3] <= 416
                or box[2]-box[0] < 64 or box[3]-box[1] < 64):
            return self._clear('invalid_manual_roi')
        selection = (target_id,tuple(box))
        if selection != self.target:
            self._clear('target_changed')
            self.target = selection
        normalized = image.crop(box).resize((208,248),Image.Resampling.NEAREST)
        mask = foreground(normalized.crop((16,16,192,170)))
        ranked = sorted(((iou(mask,template),name) for name,template in self.templates.items()),reverse=True)
        score, shape = ranked[0]
        if area(mask) <= 5:
            shape = 'off'
        elif score < .94 or score - ranked[1][0] < .3:
            return self._clear('unsupported_or_ambiguous_shape')
        self.history.append((replay_ms,shape))
        while self.history and replay_ms-self.history[0][0] > 2000:
            self.history.popleft()
        shapes = [item[1] for item in self.history]
        transitions = sum(a != b and 'off' in (a,b) for a,b in zip(shapes,shapes[1:]))
        self.flashing = self.flashing or transitions >= 2
        if shape == self.previous_shape:
            self.confirmations += 1
        else:
            self.confirmations = 1
            self.streak_started = replay_ms
        self.previous_shape = shape
        self.captured = replay_ms
        digit = read_countdown(normalized) if shape != 'off' else None
        countdown = None
        if digit is not None and self.previous_digit is not None:
            elapsed = replay_ms-self.previous_digit_ms
            if digit == self.previous_digit or (digit == self.previous_digit-1 and 500 <= elapsed <= TTL_MS):
                countdown = digit  # Never extrapolate between observations.
        self.previous_digit, self.previous_digit_ms = digit, replay_ms
        if self.flashing:
            self.result = ReplayResult(temporal_state='flashing_or_uncertain',reason='alternating_evidence')
        elif shape == 'off':
            self.result = ReplayResult(reason='unlit_or_unknown')
        elif self.confirmations < 2 or replay_ms-self.streak_started < 100:
            self.result = ReplayResult(reason='needs_temporal_confirmation',shape_iou=round(score,6))
        else:
            self.result = ReplayResult(symbol=shape,countdown_s=countdown,
                                       temporal_state='consistent_schematic',reason='manual_replay_shape',
                                       shape_iou=round(score,6))
        return self.result
