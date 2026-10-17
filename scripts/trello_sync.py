"""One-way status projection. Reads trusted main tasks; preserves human card text."""
import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from github_api import GitHub

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {'backlog': ('Backlog', 'sky'), 'in_progress': ('In progress', 'yellow'),
            'blocked': ('Blocked', 'red'), 'review': ('Review', 'purple'), 'done': ('Done', 'green')}
START = '<!-- CANESIGHT-REPO-SYNC:START -->'
END = '<!-- CANESIGHT-REPO-SYNC:END -->'


def project_status(task, prs):
    matching = [p for p in prs if task['id'] in re.findall(r'CS-\d{3}', p['title'])]
    if task['status'] == 'blocked':
        return 'blocked', matching, task['blocker']
    if len(matching) > 1:
        return 'blocked', matching, 'Multiple open PRs for one task; PM reconciliation required.'
    if matching:
        return ('in_progress' if matching[0]['draft'] else 'review'), matching, ''
    return task['status'], [], task.get('blocker', '')


def managed_description(original, block):
    if original.count(START) != original.count(END) or original.count(START) > 1:
        raise ValueError('Ambiguous sync markers; refusing to overwrite human content')
    new = START + '\n' + block + '\n' + END
    if START in original:
        begin, finish = original.index(START), original.index(END)
        if finish < begin:
            raise ValueError('Reversed markers')
        return original[:begin] + new + original[finish + len(END):]
    return original.rstrip() + '\n\n' + new


class Trello:
    def __init__(self):
        self.key, self.token = os.environ['TRELLO_API_KEY'], os.environ['TRELLO_TOKEN']

    def request(self, method, path, data=None):
        # OAuth header keeps key/token out of URL and normal request logging.
        auth = f'OAuth oauth_consumer_key="{self.key}", oauth_token="{self.token}"'
        url = 'https://api.trello.com/1/' + path
        for attempt in range(4):
            req = urllib.request.Request(url, method=method,
                data=urllib.parse.urlencode(data).encode() if data is not None else None,
                headers={'Authorization': auth, 'Content-Type': 'application/x-www-form-urlencoded'})
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    return json.load(response)
            except urllib.error.HTTPError as err:
                if err.code in (429, 500, 502, 503, 504) and attempt < 3 and method in ('GET', 'PUT', 'DELETE'):
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f'Trello {method} failed (HTTP {err.code}); credentials/response suppressed') from None
        raise RuntimeError('Trello retry limit')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    config = json.loads((ROOT / 'trello-sync.json').read_text(encoding='utf-8'))
    tasks = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT / 'tasks').glob('CS-*.json'))]
    # Dry run is offline and requires no credentials; it shows canonical main state only.
    if args.dry_run:
        for task in tasks:
            print(task['id'], task['status'], task['trello_url'])
        print('Offline dry run: no GitHub PR discovery and no Trello writes.')
        return
    if os.environ.get('TRELLO_SYNC_ENABLED') != 'true':
        raise SystemExit('Trello sync disabled; configure Secrets and TRELLO_SYNC_ENABLED=true')
    api, trello = GitHub(), Trello()
    prs = list(api.pages('pulls?state=open'))
    board = trello.request('GET', 'boards/' + config['board_short_link'] + '?fields=id')
    board_id = board['id']
    labels = trello.request('GET', f'boards/{board_id}/labels?limit=1000&fields=id,name,color')
    status_labels = {}
    for state, (display, color) in STATUSES.items():
        name = config['status_label_prefix'] + display
        matches = [l for l in labels if l['name'] == name]
        if len(matches) > 1:
            raise RuntimeError('Duplicate managed status label: ' + name)
        status_labels[state] = matches[0]['id'] if matches else trello.request('POST', 'labels',
            {'idBoard': board_id, 'name': name, 'color': color})['id']
    owned_ids = set(status_labels.values())
    for task in tasks:
        short_link = urllib.parse.urlparse(task['trello_url']).path.split('/')[2]
        card = trello.request('GET', f'cards/{short_link}?fields=id,idBoard,desc,idLabels,closed')
        if card['idBoard'] != board_id or card['closed']:
            raise RuntimeError(task['id'] + ': wrong board or archived card; reconcile manually')
        state, matching, blocker = project_status(task, prs)
        block = f"Repository status: **{STATUSES[state][0]}**\nOwner: {task['owner'] or 'Unclaimed'}\n"
        block += f"Task: https://github.com/{config['repository']}/blob/main/tasks/{task['id']}.json\n"
        block += f"Branch: {task.get('branch') or 'Not reported'}\n"
        for pr in matching:
            block += f"PR: {pr['html_url']}\n"
        if not matching and task.get('pr_url'):
            block += f"Reported PR: {task['pr_url']}\n"
        if blocker:
            block += 'Blocker: ' + blocker + '\n'
        for evidence in task.get('evidence', []):
            block += 'Evidence: ' + evidence + '\n'
        block += 'Derived from accepted repository state and open PRs; no private-chat activity is inferred.'
        description = managed_description(card['desc'], block)
        # Label endpoints preserve every unrelated priority/human label.
        wanted = status_labels[state]
        if wanted not in card['idLabels']:
            trello.request('POST', f"cards/{card['id']}/idLabels", {'value': wanted})
        for label in owned_ids.intersection(card['idLabels']) - {wanted}:
            trello.request('DELETE', f"cards/{card['id']}/idLabels/{label}")
        if description != card['desc']:
            trello.request('PUT', f"cards/{card['id']}", {'desc': description})
        print(task['id'] + ': ' + state)
    print('Synchronized ' + str(len(tasks)) + ' cards.')


if __name__ == '__main__':
    main()
