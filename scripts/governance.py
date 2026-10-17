"""Trusted-base PR guard. Reads PR data; never executes or imports PR code."""
import base64
import json
import os
import re
from pathlib import Path
from urllib.parse import quote
from github_api import GitHub

ROOT = Path(__file__).resolve().parents[1]


def has_approval(pm, sha, comments, reviews):
    command = f'PM-APPROVE-PLAN {sha}'
    if any(c.get('user', {}).get('login') == pm and c.get('body', '').strip() == command for c in comments):
        return True
    # A later dismissed/changes-requested review cancels a prior approving review.
    relevant = [r for r in reviews if r.get('user', {}).get('login') == pm
                and r.get('commit_id') == sha and r.get('state') != 'COMMENTED']
    return bool(relevant and relevant[-1].get('state') == 'APPROVED')


def protected(path, policy):
    return path in policy['protected_files'] or any(path.startswith(p) for p in policy['protected_prefixes'])


def inspect_changes(files, policy, get_base, get_head, author, task_ids):
    errors, needs_approval = [], False
    new_cr = any(f['filename'].startswith('decisions/CR-') and f['status'] == 'added' for f in files)
    new_log = any(f['filename'].startswith('changes/') and f['filename'].endswith('.json') and f['status'] == 'added' for f in files)
    if not new_log:
        errors.append('Every PR needs a new changes/*.json fragment.')
    tasks = {}
    for task_id in task_ids:
        raw = get_base(f'tasks/{task_id}.json')
        if raw is None:
            errors.append(f'Unknown task {task_id}')
        else:
            tasks[task_id] = json.loads(raw)
    for f in files:
        path = f['filename']
        previous = f.get('previous_filename', path)
        if path.startswith('changes/') and f['status'] != 'added':
            errors.append('Historical changelog fragments are immutable: ' + path)
        if previous.startswith('changes/') and f['status'] == 'renamed':
            errors.append('Cannot rename historical changelog fragments.')
        if path.startswith('handoffs/') and f['status'] != 'added':
            errors.append('Handoffs are append-only: ' + path)
        guarded = protected(path, policy) or protected(previous, policy)
        if path.startswith('tasks/') and path.endswith('.json'):
            before_raw, after_raw = get_base(previous), get_head(path)
            if before_raw is None or after_raw is None:
                guarded = True
            else:
                before, after = json.loads(before_raw), json.loads(after_raw)
                changed_keys = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
                if not changed_keys.issubset(set(policy['runtime_fields'])):
                    guarded = True
                if before.get('owner') and before['owner'] != after.get('owner'):
                    guarded = True
                if author != policy['pm_github'] and after.get('owner') != author:
                    errors.append(path + ': only its owner or PM can update runtime fields')
                if after.get('status') == 'done' and not after.get('evidence'):
                    errors.append(path + ': done requires evidence')
        exempt = path == 'CHANGELOG.md' or path.startswith('changes/') or path.startswith('decisions/CR-')
        own_record = any(path == f'tasks/{t}.json' or path.startswith(f'handoffs/{t}-') for t in task_ids)
        within_scope = any(any(path.startswith(p) for p in t['allowed_paths']) for t in tasks.values())
        if not (exempt or own_record or within_scope or guarded):
            errors.append('Outside declared task scope: ' + path)
        if guarded:
            needs_approval = True
    # Non-PM authors can propose a claim but cannot implement before a merged claim.
    for task_id, task in tasks.items():
        if author != policy['pm_github'] and task.get('owner') != author:
            allowed_claim_paths = {f'tasks/{task_id}.json', 'CHANGELOG.md'}
            non_claim = [f['filename'] for f in files if f['filename'] not in allowed_claim_paths
                         and not f['filename'].startswith('changes/')]
            if task.get('owner') is not None or non_claim:
                errors.append(task_id + ': claim must be merged before implementation')
    if needs_approval and not new_cr:
        errors.append('Protected changes require a new decisions/CR-*.md explaining necessity.')
    return errors, needs_approval


def main():
    policy = json.loads((ROOT / 'governance.json').read_text(encoding='utf-8'))
    api = GitHub()
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
    number = event.get('pull_request', {}).get('number') or event.get('issue', {}).get('number')
    if not number:
        raise SystemExit('No PR number')
    pr = api.get(f'pulls/{number}')
    if pr['state'] != 'open':
        print('PR closed; no pending authorization.')
        return
    sha = pr['head']['sha']
    api.request('POST', f'statuses/{sha}', {'state': 'pending', 'context': 'governance',
                'description': 'Checking plan, ownership and append-only records'})
    files = list(api.pages(f'pulls/{number}/files'))
    if pr.get('changed_files', 0) != len(files):
        raise SystemExit('Incomplete file list; refusing validation')
    task_ids = sorted(set(re.findall(r'CS-\d{3}', pr['title'])))
    if not task_ids:
        raise SystemExit('PR title must contain its task ID, e.g. [CS-021]')
    cache = {}

    def read(path, ref):
        key = (path, ref)
        if key not in cache:
            # Only read base/head files known from change metadata or task IDs.
            matching = next((f for f in files if f['filename'] == path or f.get('previous_filename') == path), None)
            if matching and ((ref == pr['base']['sha'] and matching['status'] == 'added') or
                             (ref == sha and matching['status'] == 'removed')):
                cache[key] = None
            else:
                obj = api.get(f'contents/{quote(path, safe="/")}?ref={ref}')
                if obj.get('encoding') != 'base64':
                    raise RuntimeError('Unsupported content encoding')
                cache[key] = base64.b64decode(obj['content']).decode('utf-8')
        return cache[key]

    errors, needed = inspect_changes(files, policy, lambda p: read(p, pr['base']['sha']),
                                     lambda p: read(p, sha), pr['user']['login'], task_ids)
    if needed:
        comments = list(api.pages(f'issues/{number}/comments'))
        reviews = list(api.pages(f'pulls/{number}/reviews'))
        if not has_approval(policy['pm_github'], sha, comments, reviews):
            errors.append('Exact-head PM authorization required: PM-APPROVE-PLAN ' + sha)
    if errors:
        api.request('POST', f'statuses/{sha}', {'state': 'failure', 'context': 'governance',
                    'description': 'Plan/ownership check failed; inspect workflow log'})
        raise SystemExit('\n'.join(errors))
    api.request('POST', f'statuses/{sha}', {'state': 'success', 'context': 'governance',
                'description': 'Plan/ownership checks passed for current head'})
    print('Governance passed for ' + sha)


if __name__ == '__main__':
    main()
