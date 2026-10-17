"""Verify a configured model with one generated neutral image, never a real scene.

The key comes from the server environment or a non-echoing terminal prompt.
Only availability and the selected model ID are printed; provider errors and
credentials are suppressed. This probe does not certify descriptions or safety.
"""
import argparse
import asyncio
import getpass
import os
from .provider import Gemini
from .service import ContextService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    try:
        Gemini(args.model)
    except ValueError:
        parser.error('Invalid Gemini model ID')
    if not os.environ.get('GEMINI_API_KEY'):
        os.environ['GEMINI_API_KEY'] = getpass.getpass('Server-only Gemini API key (hidden): ')
    async def verify():
        service = ContextService(args.model)
        await service.verify()
        print('Model:', args.model, 'Available:', service.ready)
        if service.verification_http_status is not None:
            print('Verification HTTP status:', service.verification_http_status)
        await service.close()
        return service.ready
    raise SystemExit(0 if asyncio.run(verify()) else 1)


if __name__ == '__main__':
    main()
