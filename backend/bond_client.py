"""Native durable bond exchange. Never log or forward device credentials."""
import json
from pathlib import Path
import ssl
import stat
from urllib import request, error

from .bonds import origin, IDENTITY


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BondClient:
    def __init__(self, path, role, *, ca_file=None):
        path = Path(path)
        if path.stat().st_size > 2048:
            raise ValueError('Oversized device bond file')
        import os
        if os.name == 'posix' and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ValueError('Device bond file must be chmod 600')
        data = json.loads(path.read_text(encoding='utf-8'))
        if (set(data) != {'schema_version', 'base_url', 'bond_id', 'role', 'source_id', 'token'}
                or data['schema_version'] != 1 or data['role'] != role
                or not all(IDENTITY.fullmatch(data[k]) for k in ('bond_id', 'source_id'))
                or not isinstance(data['token'], str) or not 32 <= len(data['token']) <= 128
                or not data['token'].isascii() or any(c.isspace() for c in data['token'])):
            raise ValueError('Invalid device bond file')
        self.base_url = origin(data['base_url'])
        self.source_id, self.role, self.bond_id = data['source_id'], role, data['bond_id']
        self._token = data['token']
        context = ssl.create_default_context(cafile=ca_file)
        self._opener = request.build_opener(request.ProxyHandler({}),
                                            request.HTTPSHandler(context=context), NoRedirect())

    def poll(self, boot_id):
        body = json.dumps(dict(bond_id=self.bond_id, role=self.role, boot_id=boot_id)).encode()
        req = request.Request(self.base_url + '/v1/bonds/connect', data=body, method='POST',
                              headers={'Authorization': 'Bearer ' + self._token,
                                       'Content-Type': 'application/json'})
        try:
            with self._opener.open(req, timeout=5) as response:
                raw = response.read(8193)
                if len(raw) > 8192:
                    raise ValueError('Oversized bond response')
                data = json.loads(raw)
                if response.status == 202 and data.get('state') == 'waiting_for_peer':
                    return None
                if response.status != 200 or data.get('state') != 'paired':
                    raise ValueError('Invalid bond response')
                device, peer = data['device'], data['peer']
                if (data['mode'] != 'live' or device['source_id'] != self.source_id
                        or device['boot_id'] != boot_id
                        or not all(isinstance(x, str) and IDENTITY.fullmatch(x) for x in
                                   (data['session_id'], peer['source_id'], peer['boot_id']))):
                    raise ValueError('Bond response identity mismatch')
                return data
        except error.HTTPError as exc:
            raise ConnectionError('Bond exchange failed (HTTP %s)' % exc.code) from None
        except (error.URLError, TimeoutError):
            raise ConnectionError('Bond backend unavailable; retrying') from None

    def session(self, result):
        return dict(base_url=self.base_url, session_id=result['session_id'], mode='live',
                    **{k: result['device'][k] for k in ('source_id', 'boot_id', 'token')})
