"""Validate non-secret bootstrap settings without echoing input values."""
import ipaddress
import re
import sys


def validate(address, image):
    try:
        ip = ipaddress.ip_address(address)
        valid = ip.version == 4 and ip.is_global
    except ValueError:
        valid = bool(re.fullmatch(r'(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}', address))
        valid = valid and not address.lower().endswith(('.localhost', '.local', '.internal', '.test', '.invalid', '.example'))
    errors = []
    if not valid:
        errors.append('Use a public IPv4 address or public DNS hostname, without scheme, port or path.')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/-]*@sha256:[0-9a-f]{64}', image):
        errors.append('Use a reviewed immutable Caddy image digest.')
    return errors


if __name__ == '__main__':
    import os
    errors = validate(os.environ.get('CANESIGHT_ADDRESS', ''), os.environ.get('CADDY_IMAGE', ''))
    for error in errors:
        print(error)
    if not errors:
        print('Bootstrap inputs valid; public certificate and route tests are still required.')
    sys.exit(bool(errors))
