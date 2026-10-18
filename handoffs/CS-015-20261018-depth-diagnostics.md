# CS-015 depth diagnostic UI and reset observations

Original base 5dd5fa37009402b7eb7c9dbed3d20eacd4346c90; integrated main
5dbb6ad. Previous checkpoint 58c8537b569799367579eaff318f63ed7761dbd1.
PR #70 remains draft/blocked.

Michael explicitly confirmed on the prior installed implementation that turning
sideways/upright resets all counters, and that after a fresh Left 1/3, Stop resets
counts and clears all three distances to Unknown. While asked for background
reset, he instead reported View left mostly Unknown with occasional numerical
flashes. Status remained live portrait view; physical mapping unverified until
target check. Center/right behavior and background reset were not confirmed.
Do not infer a lifecycle pass or sensor failure cause from that report.

Changed bench UI/controller to show existing per-sector evidence: high-confidence
coverage, insufficient coverage (existing default 25%), insufficient sample count
(existing default 32), or unavailable. Diagnostics clear wherever readings clear.
No confidence threshold, expiry, mapping, recording or sensor algorithm changed;
no fallback to old numbers. This is diagnostic visibility, not a claimed fix.
Teammate CS-014 source and all protected files remain unchanged.

Signed physical-iOS SDK build passed with Xcode 27.1, strict deep codesign
verification passed, and Apple device tools installed/launched the diagnostic
build on the same iPhone. Exact source hashes are in the new evidence JSON.
No extra tests added for reversible display formatting. The previous 11 mapping
cases and 61 native dependency cases cover unchanged core/dependency logic;
checked publishing reruns all 110 shared checks. Operator has been asked to
report the new detail while Left is Unknown. No result prefilled.

Files: bench controller/view, task runtime, prior operator evidence update, new
diagnostic evidence, this handoff, README note, new changelog and generated log.
Next: inspect actual displayed evidence, reproduce/report any genuine in-scope
app failure; finish background reset check. Keep floor limitation documented and
retain unknown semantics. No motor, ground classification, range accuracy,
source-clock or final cane-mount verification claimed.
