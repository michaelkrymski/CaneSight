"""Structural task/fragment validation; no dependencies or network needed."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(root=ROOT):
    errors = []
    policy = json.loads((root / 'governance.json').read_text(encoding='utf-8'))
    solo = policy.get('collaboration_mode') == 'solo'
    tasks = {}
    for path in sorted((root / 'tasks').glob('CS-*.json')):
        t = json.loads(path.read_text(encoding='utf-8'))
        task_id = t.get('id', '')
        if not re.fullmatch(r'CS-\d{3}', task_id) or path.stem != task_id:
            errors.append(f'{path.name}: invalid ID')
        if task_id in tasks:
            errors.append(f'{task_id}: duplicate')
        tasks[task_id] = t
        for field in ([] if solo else policy['task_static_fields'] + policy['runtime_fields']):
            if field not in t:
                errors.append(f'{task_id}: missing {field}')
        if t.get('status', 'backlog' if solo else None) not in policy['statuses']:
            errors.append(f'{task_id}: invalid status')
        if t.get('owner') is not None and not re.fullmatch(r'[A-Za-z0-9-]+', t['owner']):
            errors.append(f'{task_id}: owner must be a GitHub login')
        if not solo and t.get('status') != 'backlog' and not t.get('owner'):
            errors.append(f'{task_id}: active task must have owner')
        if not solo and t.get('status') == 'done' and not t.get('evidence'):
            errors.append(f'{task_id}: done requires evidence')
        if not solo and t.get('status') == 'blocked' and not t.get('blocker'):
            errors.append(f'{task_id}: blocked requires explanation')
        if ((not solo and not t.get('allowed_paths'))
                or any(p.startswith('/') or '..' in p.split('/') for p in t.get('allowed_paths', []))):
            errors.append(f'{task_id}: invalid scope')
        if not solo and not t.get('trello_url', '').startswith('https://trello.com/c/'):
            errors.append(f'{task_id}: missing card mapping')
    visiting, seen = set(), set()

    def visit(task_id):
        if task_id in visiting:
            errors.append(f'{task_id}: dependency cycle')
            return
        if task_id in seen:
            return
        visiting.add(task_id)
        for dep in tasks[task_id].get('dependencies', []):
            if dep not in tasks:
                errors.append(f'{task_id}: unknown dependency {dep}')
            else:
                visit(dep)
        visiting.remove(task_id)
        seen.add(task_id)

    for task_id in tasks:
        visit(task_id)
    entry_ids = set()
    for path in sorted((root / 'changes').glob('*.json')):
        e = json.loads(path.read_text(encoding='utf-8'))
        for field in ('id', 'date', 'author', 'task', 'summary', 'details', 'validation'):
            if not isinstance(e.get(field), str) or not e[field].strip():
                errors.append(f'{path.name}: missing/invalid {field}')
        if e.get('id') in entry_ids:
            errors.append(f'{path.name}: duplicate entry id')
        entry_ids.add(e.get('id'))
    return errors


if __name__ == '__main__':
    problems = validate()
    if problems:
        raise SystemExit('\n'.join(problems))
    print('Repository structure valid.')
