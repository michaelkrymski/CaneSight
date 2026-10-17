"""Run explicitly: python -m unittest discover -s tests/edge -v."""
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock
import urllib.error

from fastapi.testclient import TestClient
from PIL import Image

from backend.app import FrameIngress, SourceGrant, create_app
from edge.uploader import (Latest, Mapping, Sender, StopSession, Transport,
                           capture_time, load_session, make_frame)


def frame(seq=1):
    return make_frame(Image.new('RGB', (640, 480), 'red'),
                      {'SensorTimestamp': 1_000_000_000, 'ExposureTime': 10000,
                       'ScalerCrop': (768, 432, 3072, 1728)},
                      session_id='session', source_id='pi', boot_id='boot', seq=seq, now=1100)


class CaptureTests(unittest.TestCase):
    def test_original_capture_and_exact_letterbox(self):
        f = frame()
        self.assertEqual(f.metadata['capture_monotonic_ms'], 990)
        self.assertEqual(f.metadata['capture_utc'], None)
        self.assertEqual(f.metadata['mode'], 'live')
        self.assertEqual(f.metadata['jpeg_bytes'], len(f.jpeg))
        with Image.open(io.BytesIO(f.jpeg)) as im:
            self.assertEqual(im.size, (416, 416))
            self.assertLess(max(im.getpixel((200, 20))), 10)
            self.assertGreater(im.getpixel((200, 200))[0], 240)
        self.assertEqual(f.mapping.sensor_crop, (768, 432, 3072, 1728))

    def test_boxes_clip_padding_and_map_to_original_stream(self):
        self.assertEqual(Mapping().stream_box((0, 0, 416, 416)), (0, 0, 640, 480))
        self.assertIsNone(Mapping().stream_box((0, 0, 416, 51)))
        self.assertIsNone(Mapping().stream_box((50, 80, 40, 90)))
        with self.assertRaises(ValueError):
            Mapping().stream_box((0, 0, float('nan'), 80))

    def test_missing_bad_future_sensor_clock_rejected(self):
        for metadata in ({}, {'SensorTimestamp': True, 'ExposureTime': 1},
                         {'SensorTimestamp': 2_000_000_000, 'ExposureTime': 1},
                         {'SensorTimestamp': 1_000_000, 'ExposureTime': float('nan')},
                         {'SensorTimestamp': 1_000_000, 'ExposureTime': -1}):
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                capture_time(metadata, 1100)

    def test_actual_backend_accepts_original_metadata_and_jpeg(self):
        ingress = FrameIngress([SourceGrant('t' * 32, 'session', 'pi', 'boot', 'live', 100)], clock=lambda: 0)
        f = frame()
        with TestClient(create_app(ingress=ingress)) as client:
            response = client.post('/v1/frames', headers={'Authorization': 'Bearer ' + 't'*32},
                                   data={'metadata': json.dumps(f.metadata)},
                                   files={'image': ('frame.jpg', f.jpeg, 'image/jpeg')})
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()['frame_id'], f.metadata['frame_id'])
        self.assertEqual(ingress.latest[('session', 'pi')].metadata, f.metadata)


class QueueTests(unittest.TestCase):
    def test_slow_network_replaces_pending_and_keeps_capture_time(self):
        latest = Latest()
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        sent = []
        def send(f):
            sent.append(f.metadata.copy())
            if len(sent) == 1:
                started.set()
                if not release.wait(3):
                    raise RuntimeError('Test timeout')
            else:
                finished.set()
        transport = Mock(send=send)
        sender = Sender(latest, transport, clock=lambda: 1100)
        first, second, third = frame(1), frame(2), frame(3)
        latest.put(first)
        thread = threading.Thread(target=sender.run)
        thread.start()
        try:
            self.assertTrue(started.wait(3))
            latest.put(second)
            latest.put(third)
            self.assertEqual(latest.replaced, 1)
            release.set()
            self.assertTrue(finished.wait(3))
        finally:
            release.set()
            latest.close()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual([x['seq'] for x in sent], [1, 3])
        self.assertEqual(sent[0]['capture_monotonic_ms'], 990)
        self.assertEqual(len(sender.ledger), 2)
        self.assertIsNone(sender.error)

    def test_stale_and_future_frames_never_sent(self):
        for now in (3000, 900):
            latest = Latest()
            latest.put(frame())
            # Close after first attempted take so run exits deterministically.
            original = latest.take
            def take():
                value = original()
                latest.close()
                return value
            latest.take = take
            transport = Mock()
            sender = Sender(latest, transport, clock=lambda: now)
            sender.run()
            transport.send.assert_not_called()
            self.assertEqual(sender.dropped, 1)

    def test_network_failure_drops_frame_without_retry(self):
        latest = Latest()
        f = frame()
        latest.put(f)
        def fail(_):
            latest.close()
            raise OSError('timeout')
        transport = Mock(send=Mock(side_effect=fail))
        sender = Sender(latest, transport, clock=lambda: 1100)
        sender.run()
        self.assertEqual(transport.send.call_count, 1)
        self.assertEqual(sender.failed, 1)

    def test_auth_failure_stops_session(self):
        latest = Latest()
        latest.put(frame())
        sender = Sender(latest, Mock(send=Mock(side_effect=StopSession('HTTP 401'))), clock=lambda: 1100)
        sender.run()
        self.assertEqual(sender.error, 'HTTP 401')
        self.assertTrue(latest.closed)


class TransportTests(unittest.TestCase):
    def test_transport_multipart_parsed_by_real_ingress(self):
        ingress = FrameIngress([SourceGrant('t' * 32, 'session', 'pi', 'boot', 'live', 100)], clock=lambda: 0)
        transport = Transport('https://example.com', 't' * 32)
        f = frame()
        # In-process adapter exercises actual multipart bytes and ACK; TLS and
        # camera hardware are explicitly outside this integration test.
        with TestClient(create_app(ingress=ingress)) as client:
            def open_request(request, timeout):
                response = client.post('/v1/frames', content=request.data, headers=dict(request.header_items()))
                result = Mock(status=response.status_code)
                result.read.return_value = response.content
                context = Mock()
                context.__enter__ = Mock(return_value=result)
                context.__exit__ = Mock(return_value=False)
                return context
            transport.opener = Mock(open=open_request)
            transport.send(f)
        self.assertEqual(ingress.latest[('session', 'pi')].jpeg, f.jpeg)

    def test_https_origin_and_token_validation(self):
        for url in ('http://example.com', 'https://u:p@example.com',
                    'https://example.com/x', 'https://example.com/?token=x'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                Transport(url, 't' * 32)

    def test_multipart_and_ack_match_original_frame(self):
        f = frame()
        transport = Transport('https://example.com', 't' * 32)
        response = Mock(status=202)
        response.read.return_value = json.dumps({'schema_version': 1, 'status': 'accepted',
                                                'frame_id': f.metadata['frame_id']}).encode()
        transport.opener = Mock()
        transport.opener.open.return_value.__enter__ = Mock(return_value=response)
        transport.opener.open.return_value.__exit__ = Mock(return_value=False)
        transport.send(f)
        request = transport.opener.open.call_args.args[0]
        self.assertIn(f.jpeg, request.data)
        self.assertIn(b'"capture_monotonic_ms":990.0', request.data)
        response.read.return_value = b'{"schema_version":1,"status":"accepted","frame_id":"wrong"}'
        with self.assertRaises(StopSession):
            transport.send(f)

    def test_redirect_is_not_followed_and_auth_order_errors_are_terminal(self):
        from edge.uploader import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other'))
        for code in (302, 401, 403, 409):
            transport = Transport('https://example.com', 't' * 32)
            transport.opener = Mock()
            transport.opener.open.side_effect = urllib.error.HTTPError('https://example.com', code, 'error', {}, None)
            with self.subTest(code=code), self.assertRaises(StopSession):
                transport.send(frame())

    def test_session_file_requires_current_live_process_epoch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'session.json'
            path.write_text(json.dumps({'source_id': 'pi', 'boot_id': 'old', 'session_id': 'session', 'mode': 'live'}))
            path.chmod(0o600)
            with self.assertRaises(ValueError):
                load_session(path, 'pi', 'new')
            self.assertEqual(load_session(path, 'pi', 'old')['session_id'], 'session')


if __name__ == '__main__':
    unittest.main()
