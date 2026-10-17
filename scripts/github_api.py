"""Small read-only GitHub client. Never prints tokens or credential-bearing URLs."""
import json
import os
import urllib.error
import urllib.request


class GitHub:
    def __init__(self, repo=None, token=None):
        self.repo = repo or os.environ['GITHUB_REPOSITORY']
        self.token = token or os.environ['GITHUB_TOKEN']

    def get(self, path):
        return self.request('GET', path)

    def request(self, method, path, data=None):
        req = urllib.request.Request('https://api.github.com/repos/' + self.repo + '/' + path,
                                     method=method,
                                     data=json.dumps(data).encode() if data is not None else None,
                                     headers={'Authorization': 'Bearer ' + self.token,
                                              'Accept': 'application/vnd.github+json',
                                              'Content-Type': 'application/json',
                                              'X-GitHub-Api-Version': '2022-11-28'})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'GitHub API request failed (HTTP {error.code}); response/credentials suppressed') from None

    def pages(self, path):
        sep = '&' if '?' in path else '?'
        for page in range(1, 101):
            rows = self.get(f'{path}{sep}per_page=100&page={page}')
            if not isinstance(rows, list):
                raise RuntimeError('Expected paginated array')
            yield from rows
            if len(rows) < 100:
                return
        raise RuntimeError('Pagination bound reached; refusing incomplete result')
