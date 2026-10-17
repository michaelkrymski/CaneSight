"""CS-042 PostgreSQL/Tiger Data storage; imported by the isolated writer only."""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import uuid

ROOT = Path(__file__).resolve().parents[2]
KINDS = ('frame_accepted', 'depth_admitted', 'heartbeat_admitted', 'vision_offered')
INSERT = """INSERT INTO canesight_event_rows
    (event_id, stream_id, observed_minute, mode, role, event_kind, expires_at)
    SELECT %s, %s, %s, %s, %s, %s, %s
    WHERE %s > CURRENT_TIMESTAMP - INTERVAL '24 hours'
      AND %s <= CURRENT_TIMESTAMP + INTERVAL '2 minutes'
    ON CONFLICT (event_id) DO NOTHING"""
PURGE = 'DELETE FROM canesight_event_rows WHERE expires_at <= CURRENT_TIMESTAMP'
DELETE = 'DELETE FROM canesight_event_rows WHERE stream_id = %s'


def stream_id(value):
    if type(value) is not str or str(uuid.UUID(value)) != value:
        raise ValueError('Invalid event stream identifier')
    return value


@dataclass(frozen=True)
class Event:
    event_id: str
    stream_id: str
    observed_minute: int
    mode: str
    role: str
    kind: str

    def values(self):
        stream_id(self.event_id)
        stream_id(self.stream_id)
        if (type(self.observed_minute) is not int or self.observed_minute % 60
                or not 0 <= self.observed_minute <= 4102444800
                or self.mode not in ('live', 'replay') or self.role not in ('phone', 'pi')
                or self.kind not in KINDS):
            raise ValueError('Invalid minimal event')
        observed = datetime.fromtimestamp(self.observed_minute, timezone.utc)
        expires = datetime.fromtimestamp(self.observed_minute + 86400, timezone.utc)
        return (self.event_id, self.stream_id, observed, self.mode, self.role,
                self.kind, expires, observed, observed)


def private_config(path):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT) or not path.is_file() or path.stat().st_size > 8192:
        raise ValueError('Use a small private database config outside the checkout')
    if os.name != 'nt' and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('Private database config requires mode 0600')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate database setting')
            result[key] = value
        return result
    data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs)
    if (not isinstance(data, dict) or set(data) != {'host', 'port', 'dbname', 'user', 'password', 'sslrootcert'}
            or any(type(data[k]) is not str or not 1 <= len(data[k]) <= 1024
                   for k in ('host', 'dbname', 'user', 'password', 'sslrootcert'))
            or type(data['port']) is not int or not 1 <= data['port'] <= 65535
            or not re.fullmatch(r'[A-Za-z0-9.-]{1,253}', data['host'])):
        raise ValueError('Invalid database settings')
    ca = Path(data['sslrootcert'])
    if not ca.is_absolute() or not ca.is_file():
        raise ValueError('Explicit CA certificate file required')
    return dict(data, sslmode='verify-full', connect_timeout=3, autocommit=True,
                options='-c statement_timeout=2000 -c lock_timeout=1000 -c timezone=UTC',
                application_name='canesight-minimal-events')


class PostgresStore:
    def __init__(self, config_file, *, connect=None):
        self.config_file = config_file
        self.connect = connect

    def execute(self, query, values=None):
        config = private_config(self.config_file)
        connect = self.connect
        if connect is None:
            import psycopg  # Optional dependency; never imported in policy/observation callbacks.
            connect = psycopg.connect
        with connect(**config) as connection:
            connection.execute(query, values)

    def insert(self, event):
        self.execute(INSERT, event.values())

    def delete(self, identifier):
        self.execute(DELETE, (stream_id(identifier),))

    def purge(self):
        self.execute(PURGE)

    def initialize(self):
        # Explicit administration only; no DDL in the running observation service.
        for statement in Path(__file__).with_name('event_schema.sql').read_text(encoding='utf-8').split(';'):
            if statement.strip():
                self.execute(statement)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-file', type=Path, required=True)
    parser.add_argument('action', choices=('initialize', 'purge', 'delete'))
    parser.add_argument('--stream-id')
    args = parser.parse_args()
    try:
        store = PostgresStore(args.config_file)
        if args.action == 'delete':
            store.delete(args.stream_id)
        else:
            getattr(store, args.action)()
    except Exception:
        print('Event store operation failed; private details suppressed.')
        return 1
    print('Event store operation completed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
