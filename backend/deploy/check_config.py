"""Fail closed on missing deployment inputs without printing their values."""
import argparse
import os
from pathlib import Path
import re
import stat
import ipaddress


def validate(root):
    errors = []
    config = {}
    path = root / '.env'
    if not path.is_file():
        return ['Missing deployment .env; copy .env.example and fill it locally.']
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, separator, value = line.partition('=')
            if not separator or key.strip() in config:
                errors.append('Invalid or duplicate deployment setting.')
            config[key.strip()] = value.strip()
    # Compose gives the shell precedence over .env; validate that same value.
    effective = {key: os.environ.get(key, config.get(key, '')) for key in
                 ('CANESIGHT_DOMAIN', 'BACKEND_IMAGE', 'CADDY_IMAGE', 'CANESIGHT_UPSTREAM')}
    domain = effective['CANESIGHT_DOMAIN']
    try:
        address = ipaddress.ip_address(domain)
        valid_domain = address.version == 4 and address.is_global
    except ValueError:
        valid_domain = bool(re.fullmatch(r'(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}', domain))
    if not valid_domain:
        errors.append('CANESIGHT_DOMAIN must be a public IPv4 address or DNS hostname without scheme, path or port.')
    if effective['CANESIGHT_UPSTREAM'] not in ('', '127.0.0.1:18083', '127.0.0.1:18081'):
        errors.append('Upstream must be the reviewed loopback backend or laptop tunnel.')
    for key in ('BACKEND_IMAGE', 'CADDY_IMAGE'):
        if not re.fullmatch(r'(?:[a-zA-Z0-9][a-zA-Z0-9._:/-]*@)?sha256:[0-9a-f]{64}', effective[key]):
            errors.append(key + ' must be an immutable image reference with sha256 digest.')
    secret = root / 'secrets' / 'backend.env'
    if not secret.is_file() or not any(line.strip() and not line.lstrip().startswith('#')
                                     for line in secret.read_text(encoding='utf-8').splitlines()):
        errors.append('Missing nonempty secrets/backend.env using the accepted backend configuration.')
    elif os.name != 'nt' and stat.S_IMODE(secret.stat().st_mode) & 0o077:
        errors.append('secrets/backend.env must not be accessible to group or other users (chmod 600).')
    else:
        lines = secret.read_text(encoding='utf-8').splitlines()
        tokens = [line.partition('=')[2] for line in lines if line.startswith('CANESIGHT_OPERATOR_TOKEN=')]
        if (len(tokens) != 1 or not 32 <= len(tokens[0]) <= 128 or not tokens[0].isascii()
                or any(char.isspace() for char in tokens[0])):
            errors.append('Configure one valid CANESIGHT_OPERATOR_TOKEN privately on the host.')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        errors = validate(args.directory)
    except (OSError, UnicodeError):
        errors = ['Cannot read deployment inputs; check paths, encoding and permissions locally.']
    for error in errors:
        print(error)
    if not errors:
        print('Deployment inputs present; application secret validity still requires live tests.')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
