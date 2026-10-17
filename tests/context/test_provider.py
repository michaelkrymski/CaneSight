import base64
import io
import json
import os
import unittest
from unittest.mock import patch

from PIL import Image
from backend.context.provider import Gemini, NoRedirect, compress, strict_json, validate_result


def jpeg(size=(64, 48)):
    output = io.BytesIO()
    Image.new('RGB', size, 'gray').save(output, 'JPEG')
    return output.getvalue()


class Response:
    status = 200
    def __init__(self, value):
        self.raw = json.dumps(value).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return self.raw[:size]


class Opener:
    def __init__(self, value):
        self.value = value
        self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        return Response(self.value)


def candidate(value, reason='STOP'):
    return {'candidates': [{'finishReason': reason,
        'content': {'parts': [{'text': json.dumps(value)}]}}]}


class ProviderTests(unittest.TestCase):
    def test_header_only_key_bounded_jpeg_structured_generation_and_no_prompt_key(self):
        value = {'objects': ['chair'], 'uncertain': True}
        opener = Opener(candidate(value))
        key = 'synthetic-provider-credential-not-a-real-secret'
        with patch.dict(os.environ, {'GEMINI_API_KEY': key}):
            provider = Gemini('gemini-fixture', opener=opener)
            self.assertEqual(provider.describe(jpeg()), value)
        request = opener.requests[0]
        self.assertEqual(request.headers['X-goog-api-key'], key)
        self.assertNotIn(key, request.full_url)
        self.assertNotIn(key, request.data.decode())
        payload = json.loads(request.data)
        self.assertEqual(payload['generationConfig']['responseMimeType'], 'application/json')
        image = base64.b64decode(payload['contents'][0]['parts'][1]['inlineData']['data'])
        self.assertLessEqual(len(image), 200_000)
        self.assertNotIn(key, repr(provider))

    def test_prose_and_movement_instructions_fail_closed(self):
        for value in ['cross now', {'objects': ['go forward'], 'uncertain': True},
                      {'objects': ['chair'], 'uncertain': False},
                      {'objects': ['chair'], 'uncertain': True, 'advice': 'walk'},
                      {'objects': ['chair'] * 4, 'uncertain': True}]:
            with self.assertRaises(ValueError):
                validate_result(value)

    def test_safety_block_truncation_empty_and_multiple_candidates_rejected(self):
        for value in [{}, {'candidates': []}, {'candidates': [{}, {}]},
                      candidate({'objects': [], 'uncertain': True}, 'MAX_TOKENS')]:
            with patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-only'}):
                with self.assertRaises(ValueError):
                    Gemini('gemini-fixture', opener=Opener(value)).describe(jpeg())

    def test_model_must_be_listed_for_generation(self):
        opener = Opener({'name': 'models/gemini-fixture', 'supportedGenerationMethods': []})
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-only'}):
            with self.assertRaises(ValueError): Gemini('gemini-fixture', opener=opener).verify()

    def test_final_text_signature_is_ignored_but_thought_or_other_parts_rejected(self):
        value = {'objects': [], 'uncertain': True}
        response = candidate(value)
        response['candidates'][0]['content']['parts'][0]['thoughtSignature'] = 'opaque-fixture-signature'
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-only'}):
            self.assertEqual(Gemini('gemini-fixture', opener=Opener(response)).describe(jpeg()), value)
            response['candidates'][0]['content']['parts'][0]['thought'] = True
            with self.assertRaises(ValueError):
                Gemini('gemini-fixture', opener=Opener(response)).describe(jpeg())

    def test_model_paths_redirects_and_duplicate_json_rejected(self):
        for model in ['https://example.com', '../model', 'models/gemini-test', 'gemini-x?key=x', '']:
            with self.assertRaises(ValueError): Gemini(model)
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, None, None, 'https://example.com'))
        for raw in ['{"objects":[],"objects":["chair"]}', '{"x":NaN}']:
            with self.assertRaises(ValueError): strict_json(raw)

    def test_reencode_strips_exif_and_limits_dimensions(self):
        image = Image.new('RGB', (1200, 800), 'gray')
        exif = Image.Exif()
        exif[270] = 'synthetic private metadata'
        data = io.BytesIO()
        image.save(data, 'JPEG', exif=exif)
        output = compress(data.getvalue())
        with Image.open(io.BytesIO(output)) as decoded:
            self.assertLessEqual(max(decoded.size), 640)
            self.assertEqual(len(decoded.getexif()), 0)
        for data in [b'not-jpeg', b'x' * 1_000_001, jpeg((1921, 1))]:
            with self.assertRaises((ValueError, OSError)):
                compress(data)


if __name__ == '__main__': unittest.main()
