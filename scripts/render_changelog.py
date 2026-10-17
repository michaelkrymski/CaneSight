"""Deterministic log assembled from immutable per-PR fragments."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(root=ROOT):
    text = '# CaneSight master changelog\n\nGenerated from append-only `changes/*.json`; do not edit by hand.\n\n'
    for path in sorted((root / 'changes').glob('*.json')):
        entry = json.loads(path.read_text(encoding='utf-8'))
        text += f"## {entry['date']} — {entry['id']}: {entry['summary']}\n\n"
        text += f"Author: {entry['author']} · Task: {entry['task']}\n\n"
        text += f"{entry['details']}\n\nValidation: {entry['validation']}\n\n"
    return text


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = render()
    target = ROOT / 'CHANGELOG.md'
    if args.check:
        if not target.exists() or target.read_text(encoding='utf-8') != result:
            raise SystemExit('CHANGELOG.md is stale; run python scripts/render_changelog.py')
    else:
        target.write_text(result, encoding='utf-8', newline='\n')
