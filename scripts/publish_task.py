"""Explicit-file, checked task-branch publishing. No force, merge or main push."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from governance import inspect_changes

ROOT = Path(__file__).resolve().parents[1]


def git(*args, root=ROOT, required=True):
    result = subprocess.run(['git', '--literal-pathspecs', *args], cwd=root,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if required and result.returncode:
        # Git auth/transport output may contain sensitive remote/config text.
        raise RuntimeError('Git operation failed: ' + args[0] + '; inspect locally. No force/retry applied.')
    return result


def validate_branch(branch, task, *, solo=False):
    if solo:
        if branch in ('HEAD', ''):
            raise ValueError('Use a named branch, not detached HEAD.')
        return
    if branch in ('main', 'master', 'HEAD', '') or not re.fullmatch(r'(task|claim)/CS-\d{3}-[A-Za-z0-9._/-]+', branch):
        raise ValueError('Use a named task/CS-NNN-name or claim/CS-NNN-name branch; never main or detached HEAD.')
    if not branch.startswith(('task/' + task + '-', 'claim/' + task + '-')):
        raise ValueError('Branch task ID does not match --task.')


def validate_remote(url):
    if not re.fullmatch(r'(https://github\.com/|git@github\.com:)michaelkrymski/CaneSight(?:\.git)?', url, re.I):
        raise ValueError('origin must be michaelkrymski/CaneSight on GitHub. Forks need an explicit reviewed setup.')


def normalize_files(files, root=ROOT):
    selected = []
    for item in files:
        relative = Path(item)
        if relative.is_absolute() or '..' in relative.parts or item.startswith('-'):
            raise ValueError('Provide repository-relative explicit filenames, not options, globs or parent paths.')
        resolved = (root / relative).resolve()
        if not resolved.is_relative_to(root.resolve()) or resolved.is_dir() or '.git' in relative.parts:
            raise ValueError('Refusing directory, Git metadata or path outside the repository: ' + item)
        name = relative.name.lower()
        if name == '.env' or name.startswith('.env.') or relative.suffix.lower() in ('.key', '.pem', '.p12', '.mobileprovision') or 'secrets' in relative.parts:
            raise ValueError('Refusing credential-like path: ' + item)
        selected.append(relative.as_posix())
    return sorted(set(selected))


def staged_rows(root=ROOT):
    fields = git('diff', '--cached', '--name-status', '-z', '--find-renames', 'origin/main', root=root).stdout.split('\0')
    rows = []
    index = 0
    statuses = {'A': 'added', 'M': 'modified', 'D': 'removed', 'T': 'modified'}
    while index < len(fields) and fields[index]:
        status, path = fields[index:index + 2]
        index += 2
        if status[0] in ('R', 'C'):
            target = fields[index]
            index += 1
            rows.append({'filename': target, 'previous_filename': path, 'status': 'renamed' if status[0] == 'R' else 'added'})
        else:
            rows.append({'filename': path, 'status': statuses.get(status[0], 'modified')})
    return rows


def read_git_file(ref, path, root=ROOT):
    value = git('show', ref + ':' + path, root=root, required=False)
    return value.stdout if value.returncode == 0 else None


def run_checks(root=ROOT):
    for command in ([sys.executable, 'scripts/validate_repo.py'],
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                    [sys.executable, 'scripts/render_changelog.py', '--check']):
        subprocess.run(command, cwd=root, check=True)


def publish(args, root=ROOT):
    policy = json.loads((root / 'governance.json').read_text(encoding='utf-8'))
    solo = policy.get('collaboration_mode') == 'solo' and args.user == policy['pm_github']
    branch = git('branch', '--show-current', root=root).stdout.strip()
    validate_branch(branch, args.task, solo=solo)
    validate_remote(git('remote', 'get-url', 'origin', root=root).stdout.strip())
    selected = normalize_files(args.files, root)
    staged_before = set(filter(None, git('diff', '--cached', '--name-only', '-z', root=root).stdout.split('\0')))
    # A failed check leaves our generated log staged. Allow it on retries;
    # regenerate it below before validating/committing. Other staged files
    # still require explicit selection.
    if staged_before - set(selected) - {'CHANGELOG.md'}:
        raise ValueError('Unrelated files are already staged. Reconcile them before publishing.')
    dirty = set(filter(None, git('diff', '--name-only', '-z', root=root).stdout.split('\0')))
    untracked = set(filter(None, git('ls-files', '--others', '--exclude-standard', '-z', root=root).stdout.split('\0')))
    if (dirty | untracked) - set(selected) - {'CHANGELOG.md'}:
        raise ValueError('Unselected working files would make checks differ from the commit. Preserve/reconcile them first.')
    if git('ls-files', '-u', root=root).stdout:
        raise ValueError('Resolve merge conflicts before publishing.')
    git('fetch', 'origin', 'main', root=root)
    if git('merge-base', '--is-ancestor', 'origin/main', 'HEAD', root=root, required=False).returncode:
        raise ValueError('Branch is behind/diverged from main. Reconcile with the PM; no automatic reset/rebase performed.')
    if args.dry_run:
        print('Dry run: branch/remote/selection checked; no files staged, tests run, commit or push performed.')
        print('Task:', args.task, 'Branch:', branch, 'Files:', ', '.join(selected))
        return
    # Existing historical fragments must never be auto-renamed or edited. The
    # renderer handles mixed-case old filenames portably without changing history.
    subprocess.run([sys.executable, 'scripts/render_changelog.py'], cwd=root, check=True)
    git('add', '--', *sorted(set(selected + ['CHANGELOG.md'])), root=root)
    rows = staged_rows(root)
    errors, protected_change = inspect_changes(rows,
        json.loads(read_git_file('origin/main', 'governance.json', root)),
        lambda p: read_git_file('origin/main', p, root),
        lambda p: read_git_file('', p, root), args.user, [args.task] if args.task else [])
    if protected_change:
        errors.append('Protected amendment: use the explicit PM-reviewed PR route, not routine autopublish.')
    if errors:
        raise ValueError('\n'.join(errors))
    run_checks(root)
    git('diff', '--cached', '--check', root=root)
    changed = git('diff', '--cached', '--quiet', root=root, required=False).returncode
    if changed not in (0, 1):
        raise RuntimeError('Unable to inspect staged changes.')
    if changed:
        git('commit', '-m', ('[' + args.task + '] ' if args.task else '') + args.message, root=root)
    elif not git('rev-list', 'origin/main..HEAD', root=root).stdout.strip():
        raise ValueError('No task checkpoint to publish.')
    git('push', '--set-upstream', 'origin', 'HEAD:refs/heads/' + branch, root=root)
    sha = git('rev-parse', 'HEAD', root=root).stdout.strip()
    print('Published task branch:', branch, 'Commit:', sha)
    print('Existing PRs on this branch update automatically. No merge was performed.')
    if args.pr:
        subprocess.run([sys.executable, 'scripts/ci_feedback.py', '--pr', str(args.pr),
                        '--expected-head', sha, '--wait-seconds', '180'], cwd=root, check=True)
    else:
        from urllib.parse import quote
        print('Open/find PR: https://github.com/michaelkrymski/CaneSight/compare/main...' + quote(branch, safe=''))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', help='Optional for the owner in solo mode')
    parser.add_argument('--user', help='GitHub login; defaults to repository owner in solo mode')
    parser.add_argument('--message', required=True)
    parser.add_argument('--files', nargs='+', required=True)
    parser.add_argument('--pr', type=int)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    policy = json.loads((ROOT / 'governance.json').read_text(encoding='utf-8'))
    if args.user is None and policy.get('collaboration_mode') == 'solo':
        args.user = policy['pm_github']
    solo = policy.get('collaboration_mode') == 'solo' and args.user == policy['pm_github']
    if ((args.task is None and not solo) or (args.task is not None and not re.fullmatch(r'CS-\d{3}', args.task))
            or not args.user or not re.fullmatch(r'[A-Za-z0-9-]+', args.user) or not args.message.strip()):
        parser.error('Valid task ID, GitHub login and nonempty message are required.')
    try:
        publish(args)
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error) + '\nStopped without merge/force-push. Selected files may remain staged; preserve unrelated work.') from None


if __name__ == '__main__':
    main()
