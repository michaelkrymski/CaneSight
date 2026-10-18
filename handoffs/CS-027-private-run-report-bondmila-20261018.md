# CS-027 private run diagnostics — 2026-10-18

Branch task/CS-027-context-button; prior head 4ac8c50; synchronized base 65d5fd96584cf9710d6c42a06d3662ee0329a7d3
includes accepted main 5dd5fa3. Merged owner bondmila. PR #58 and dependency #41 stay draft.

Changed edge/context_report.py: private/exclusive outside-checkout JSON report,
closed field allowlist, bounded counters and no identity/grant/frame/exception
payload. edge/uploader.py: opt-in --context-report requires manual mode, outer
finally writes incomplete evidence on failure and normal-return metadata on
completion. Existing cleanup remains in place. Context runtime adds status and
reads the narration bridge's single button snapshot when available. Documentation
in edge/CONTEXT_BUTTON.md; own task runtime, new immutable fragment and handoff.
No credentials, private imagery, protected paths or shared contracts changed.

Actually run: 152 combined edge tests pass without skips via external file-based
CS-040 backend.context path overlay (multiprocessing-safe main guard), using
updated local #41 modules. No dependency implementation copied into this branch.
Final standalone run: 152 tests, 147 pass and 5 explicit narration-dependency
skips. The combined run above includes all 152 with no skips.
Report tests cover private/exclusive output, symlink rejection, no secrets/errors,
startup failure reporting, normal completion separate from acceptance, command
prerequisites and status without a new request. Publisher runs shared checks.

User reports Pi ready, but only the previous synthetic speaker observations are
currently detailed evidence. Next run guided recovery in combined test checkout;
then use --context-report for a real enrolled camera/phone/backend run once its
actual readiness is confirmed. No fabricated phone binding or drift, no automatic
speaker route detection. complete is process completion, not a successful request
or physical acceptance; those flags stay false pending PM review. SIGKILL/power
loss can leave empty reports. GPIO remains unused; hardware verification separate.
