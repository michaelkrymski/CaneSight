"""Durable role credentials which automatically obtain fresh native sessions.

The saved bond is permanent until removed from the operator's registry. Captures,
queues, clock mappings, consent and actuator state are never persisted.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from .limits import strict_object
from .sessions import SessionRequest, bearer, require_tls

IDENTITY = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


class BondGrant:
    """Stable grant identity with a renewable transport lease, not capture age.

    Constructed before any native credential is returned. Worker and HTTP/WS
    handlers retain this same object throughout the session.
    """
    def __init__(self, grant, lease):
        self._grant, self._lease = grant, lease

    @property
    def expires_at(self):
        return self._lease['deadline']

    def __getattr__(self, name):
        return getattr(self._grant, name)


def private_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(data, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())


def origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('Use an HTTPS backend origin')
    return value.rstrip('/')


def provision(directory, base_url, bond_id, phone_id, pi_id):
    base_url = origin(base_url)
    if not all(IDENTITY.fullmatch(x) for x in (bond_id, phone_id, pi_id)) or phone_id == pi_id:
        raise ValueError('Use distinct phone/Pi identities and a valid bond ID')
    directory = Path(directory)
    # New folder prevents accidental replacement of another bond or credentials.
    directory.mkdir(parents=True, exist_ok=False)
    record = {'bond_id': bond_id}
    for role, source_id in [('phone', phone_id), ('pi', pi_id)]:
        token = secrets.token_urlsafe(32)
        record[role] = {'source_id': source_id,
                        'token_sha256': hashlib.sha256(token.encode()).hexdigest()}
        private_write(directory / f'{role}-bond.json', dict(schema_version=1,
                      base_url=base_url, bond_id=bond_id, role=role,
                      source_id=source_id, token=token))
    private_write(directory / 'registry.json', {'schema_version': 1, 'bonds': [record]})


class BondRegistry:
    def __init__(self, path, manager):
        self.path, self.manager = Path(path), manager
        self.pending = {}
        self.pairs = {}
        self.records()  # Validate operator configuration at startup.

    def records(self):
        if self.path.stat().st_size > 16384:
            raise ValueError('Oversized bond registry')
        data = strict_object(self.path.read_bytes())
        if set(data) != {'schema_version', 'bonds'} or data['schema_version'] != 1:
            raise ValueError('Invalid bond registry')
        if not isinstance(data['bonds'], list) or not 0 <= len(data['bonds']) <= 8:
            raise ValueError('At most eight bonds')
        records, hashes, sources = {}, set(), set()
        for item in data['bonds']:
            if set(item) != {'bond_id', 'phone', 'pi'} or not IDENTITY.fullmatch(item['bond_id']):
                raise ValueError('Invalid bond')
            if item['bond_id'] in records:
                raise ValueError('Duplicate bond')
            for role in ('phone', 'pi'):
                device = item[role]
                if (set(device) != {'source_id', 'token_sha256'}
                        or not IDENTITY.fullmatch(device['source_id'])
                        or not re.fullmatch(r'[0-9a-f]{64}', device['token_sha256'])
                        or device['token_sha256'] in hashes or device['source_id'] in sources):
                    raise ValueError('Invalid or duplicate device')
                hashes.add(device['token_sha256'])
                sources.add(device['source_id'])
            records[item['bond_id']] = item
        return records

    def connect(self, bond_id, role, boot_id, authorization):
        token_hash = hashlib.sha256(bearer(authorization).encode()).hexdigest()
        with self.manager.lock:
            records = self.records()  # Operator removal takes effect on the next poll.
            # Revoke sessions for deleted bonds, including any old active sockets.
            for removed in list(self.pairs):
                if removed not in records:
                    old = self.pairs.pop(removed)
                    if old['session_id'] in self.manager.sessions:
                        self.manager.revoke(old['session_id'])
                    self.pending.pop(removed, None)
            record = records.get(bond_id)
            if record is None or not hmac.compare_digest(token_hash, record[role]['token_sha256']):
                raise HTTPException(401, 'Invalid device bond')
            now = self.manager.clock()
            peers = self.pending.setdefault(bond_id, {})
            previous = peers.get(role)
            changed = previous is not None and previous[0] != boot_id
            peers[role] = (boot_id, now)
            pair = self.pairs.get(bond_id)
            fingerprint = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
            current_session = self.manager.sessions.get(pair['session_id']) if pair else None
            frame_limit = current_session is not None and any(
                len(seen) >= 4000 for seen in current_session.ingress.seen_ids.values())
            if pair and (changed or pair['_registry_digest'] != fingerprint or frame_limit
                         or any(pair[r]['boot_id'] != peers[r][0] for r in peers)):
                if pair['session_id'] in self.manager.sessions:
                    self.manager.revoke(pair['session_id'])
                self.pairs.pop(bond_id)
                pair = None
            self.manager.expire()
            if pair and pair['session_id'] not in self.manager.sessions:
                self.pairs.pop(bond_id)
                pair = None
            # Both clients must be polling now; an old offline registration cannot
            # silently create a new live session after restart or expiration.
            if pair is None:
                if any(r not in peers or now - peers[r][1] > 20 for r in ('phone', 'pi')):
                    return {'schema_version': 1, 'state': 'waiting_for_peer'}, 202
                pair = self.manager.create(SessionRequest.model_validate(dict(
                    mode='live', ttl_seconds=600,
                    **{r: dict(source_id=record[r]['source_id'], boot_id=peers[r][0])
                       for r in ('phone', 'pi')})))
                session = self.manager.sessions[pair['session_id']]
                lease = {'deadline': now + 60}
                session.expires_at = lease['deadline']
                session.ingress.grants = tuple(BondGrant(grant, lease) for grant in session.ingress.grants)
                pair['_lease'] = lease
                pair['_registry_digest'] = fingerprint
                self.pairs[bond_id] = pair
            session = self.manager.sessions[pair['session_id']]
            # Both devices renew the connection together. This changes only the
            # credential lease; original capture ages and watchdogs are untouched.
            if all(now - peers[r][1] <= 20 for r in ('phone', 'pi')):
                pair['_lease']['deadline'] = now + 60
                session.expires_at = now + 60
            return {'schema_version': 1, 'state': 'paired',
                    'session_id': pair['session_id'], 'mode': 'live',
                    'expires_in_seconds': max(0, session.expires_at - now),
                    'device': dict(pair[role]),
                    'peer': {k: pair['pi' if role == 'phone' else 'phone'][k]
                             for k in ('source_id', 'boot_id')}}, 200


def install_bonds(app, manager, path):
    registry = BondRegistry(path, manager)
    app.state.bonds = registry

    @app.post('/v1/bonds/connect')
    async def connect(request: Request):
        require_tls(request)
        if request.query_params:
            raise HTTPException(422, 'No query parameters')
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > 1024:
                raise HTTPException(413, 'Bond request too large')
            raw.extend(chunk)
        try:
            body = strict_object(bytes(raw))
            if (set(body) != {'bond_id', 'role', 'boot_id'}
                    or body['role'] not in ('phone', 'pi')
                    or not all(isinstance(body[k], str) and IDENTITY.fullmatch(body[k])
                               for k in ('bond_id', 'boot_id'))):
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(422, 'Invalid bond request') from None
        data, status = registry.connect(**body, authorization=request.headers.get('authorization'))
        return JSONResponse(data, status_code=status, headers={'Cache-Control': 'no-store'})
    return registry


def main():
    parser = argparse.ArgumentParser(description='Create private, durable demo device enrollment files')
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--bond-id', default='demo-cane')
    parser.add_argument('--phone-id', default='demo-phone')
    parser.add_argument('--pi-id', default='pi-camera')
    args = parser.parse_args()
    provision(args.directory, args.base_url, args.bond_id, args.phone_id, args.pi_id)
    print('Created registry.json, phone-bond.json and pi-bond.json in the private directory. No tokens printed.')


if __name__ == '__main__':
    main()
