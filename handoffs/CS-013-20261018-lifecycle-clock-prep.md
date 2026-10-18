# CS-013 lifecycle verified; clock run prepared

Owner Michael; branch claim/CS-013-michaelkrymski, PR #97; base cef208d78e109197f3921c08816e722db7e6389e.
Human requested receiver drift bounds and phone lifecycle verification ASAP.
Work stays in own host/test paths; occupied CS-017/CS-030 modules and task files
unchanged. No shared contract, safety budget or governance modification.

Actual phone: background/return and Demo Stop tests passed 2/2. Operator-assisted
lock test passed 1/1 (38.894 seconds), zero skips/failures. Human instructed to
lock ~20 seconds and reported unlocking/reopening. Actual on-device journal:
known columns 3 -> 0 at inactivity; active return starts0; UI then sees real
measurements and Stop clears Unknown. Kernel deep sleep is not proven.
Private local results /tmp/canesight-cs013-lifecycle-baseline.xcresult and
/tmp/canesight-cs013-lock.xcresult; only sanitized count journal committed.

Add test-only bounded activity count journal, assisted UI test, 65-second real
capture/clock hosted test, manual Pi observer, affine characterization/tests/docs,
sanitized evidence, runtime task evidence, new fragment and this handoff.
Signed physical-iOS build succeeded; six Python characterization tests and six
existing Pi depth helper tests passed. Real long phone/Pi run has not run yet.
No result claimed from merely compiling it.

Method: causal affine rate interval from20 calibration exchanges spanning20sec;
freeze interval, require20 separate consistent holdout exchanges. Candidate ppm
is conditional on stable affine clocks in sampled environment, not arbitrary
future physical drift. Conditional capture-age diagnostics use unchanged protocol
helper, never enable production gate or guidance. Defaults remain unknown; no
zero/guessed live budget. User and backend operator ready for fresh role enrollment.
Publish harness, collect fresh actual Pi IDs, deliver role files privately and
run only clock test. Record actual results separately, revoke/clean grants after.
Actual paired receiver lock/expiry remains separate from verified local lifecycle.
