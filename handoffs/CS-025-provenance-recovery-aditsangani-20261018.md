# CS-025 / PR #75 — delegated provenance repair

Collaborator: aditsangani. Overall task owner / PR author: gmarcialcalleja unchanged.
Branch: task/CS-025-swift-policy. Original PR head/base: d0f2cc4a5cb5f0a3113a1727e343931761551a7b.
Accepted main integrated: d7f2a4f8eb663e88152cfdb10029a31004872b78.
PM authorization: https://github.com/michaelkrymski/CaneSight/pull/75#issuecomment-6247261989

Michael explicitly assigned Adit the narrowly scoped existing-branch review fix,
not overall task ownership or physical acceptance. Isolated managed worktree:
C:/Users/adits/.codex/worktrees/cs025-provenance/CaneSight. No competing PR,
force-push, ownership change, author rewriting or new implementation branch.

## Cause and exact repair

The committed LF manifest hashes to
485e784c3af7cf1d6569b6fb8650e2566aa5d4b2d7f78810b65889ea7af03941.
The identical JSON with CRLF endings hashes exactly to the original fixture's
recorded 0dc93b079a96ed76857d536c578e4b2e8572cda3be223bbe966e8fc5c48e723e.
Recovered those exact bytes using only LF-to-CRLF conversion, with unchanged JSON
semantics and all original pins. This is the explicitly authorized generating-
manifest recovery route, not an expected-digest replacement or new generation.

Fixture-local .gitattributes marks only review-inputs.json as -text and recognizes
cr-at-eol for whitespace checking. The raw manifest is thereby retained in Git
and fresh checkouts; default repository text handling remains intact elsewhere.
Original synthetic-wire.json and all four expected fixture/generator digests
remain unchanged. Verified all eight pinned Swift source Git blobs independently.
No generator/test/Swift source or production behavior changed.

## Changed files relative to the original PR checkpoint

- tests/edge/swift_policy_fixture/review-inputs.json — exact generating bytes
- tests/edge/swift_policy_fixture/.gitattributes — file-specific byte preservation
- tests/edge/swift_policy_fixture/README.md — recovery/provenance explanation
- tests/edge/evidence/CS-025-manifest-recovery-20261018.json — actual audit/results
- changes/20261018-cs-025-provenance-recovery-aditsangani.json
- this new handoff
- CHANGELOG.md — regenerated after preserving fragments from both merge parents

The merge also brings accepted-main files unchanged. Only CHANGELOG conflicted;
it was regenerated from the union of immutable fragments, not hand-edited.
Tasks/CS-025.json remains identical to Gavin's original PR version, retaining his
owner, blocked status, original requirements and physical acceptance limits.

## Verification and publishing

Before: unmodified Git archive reproduced six focused passes / one provenance
failure. After: all seven focused tests passed. Full-suite counts and staged Git
blob/archive checks are recorded in the new recovery evidence JSON after running.
Use the explicit edge suite: root CI does not discover tests/edge.

```
python -m unittest discover -s tests/edge -p test_swift_policy.py -v
python -m unittest discover -s tests/edge -v
python -m unittest discover -s tests -v
python scripts/validate_repo.py
python scripts/render_changelog.py
python scripts/render_changelog.py --check
git diff --cached --check
```

No new Swift/Docker generation was run: this computer has a separate Swift 6.0.3
WSL toolchain, but not the generator's pinned Docker runtime. No substitution was
represented as the recorded compiler-image run. The unchanged original artifact
retains its original compiler provenance. This repair verifies exact source bytes
and pinned input blobs rather than inventing a new generation result.

The generic local publish_task helper assumes the caller owns the task and cannot
represent this PM-delegated existing-PR collaboration. The direct PM instruction
requires a normal push on this same branch. Run its repository/shared/changelog/
whitespace and trusted-base scope/governance checks with the VERIFIED existing PR
metadata (PR author Gavin, collaborator Adit), then commit as Adit and push normally.
No helper/governance/CI code or protection is changed; current-head required GitHub
Actions remain authoritative. The current-head PM authorization is recorded above;
ask Michael to re-review after CI, and do not self-merge.

## Limits / next steps

All replay packets, offset +200ms and zero-drift values remain synthetic. No native
actor/socket runtime, phone/Pi/camera/GPIO/motor, calibration, audible response or
physical timing was tested. Full task acceptance and prior blockers remain intact.
Michael reviews this repair and merges if acceptable; no Done or hardware claim.

## Final observed validation

- Focused: 7 executed, all passed, no skips.
- Edge: 193 executed, 185 passed, 8 explicit Windows/POSIX skips, no failures.
- Shared: 191 executed, 184 passed, 7 explicit Windows/POSIX skips, no failures.
- Repository structure and generated changelog check passed.
- All four staged Git source blobs match the unchanged fixture's original hashes.
- All eight pinned Swift Git blobs match the unchanged source manifest.
- Staged whitespace check passed with the file-local CRLF convention.

The skipped cases were not represented as passing device or POSIX tests.
