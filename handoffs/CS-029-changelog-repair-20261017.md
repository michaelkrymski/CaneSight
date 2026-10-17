# CS-029 — PR14 generated changelog correction

PM repair based on PR14 head 00b1ed6619d924864cc4240a8bea9c1f8886090d.
The browser merge resolution preserved entries but omitted the renderer's blank
line before the CS-030 claim. Local render_changelog.py --check reproduces the
failure. Add a new repair fragment and regenerate CHANGELOG.md; never remove
or edit existing immutable fragments. No application, test, protected baseline,
ownership or task requirements changed.

Before push: repository structure, root/shared/governance tests, exact generated
log and whitespace checks. The application code is unchanged from the earlier
reviewed head whose 36 backend cases passed, including real HTTPS/WSS. Inspect
current-head GitHub CI after publishing. Review is still required for merge;
no approval, merge or hardware verification is performed by this repair.
