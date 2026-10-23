# CS-013 — target motion and bottom-row dominance

Branch `claim/CS-013-michaelkrymski`; base
`c34520b60e85d6cd4b5efe18c94659ee236208c4`. Local only; no GitHub contact.

Operator confirmed moving trash can about a foot closer with phone fixed and
retapping solid surface. Five refreshed snapshots, still selected grid cell (7,4),
show patch median 1.0205–1.0234 m, versus prior 1.5244–1.5498 m. Across five
samples, all 512 patch pixels passed high confidence; all/retained distributions
were identical. This supports patch response to moved target, but is not calibrated
absolute distance or proof of every preview point's alignment. Approximate operator
range and requested motion differ from sensor magnitude; do not claim resolved.

Final right-sector retained p10 0.930176 m; minimum retained depth anywhere above
bottom diagnostic grid row is 0.984375 m. Thus its p10 must come from bottom row.
That row contains 1536 of 11089 retained right-sector pixels (13.85%, exceeding
production tenth percentile). Bottom-row patch medians across ALL sectors are
0.873–0.894 m, a broad near strip consistent with floor, not independently visually
verified. A near surface across the bottom can make all columns similar despite
a target elsewhere. Threshold changes were neither needed nor made.

Phone remained paired, live portrait/WSS connected, 40 completed native depth sends
across 8.409852 s (~4.756 Hz) in this interval. No new Pi receipt, clock/drift,
physical motor verification or guidance eligibility evidence. No new code/tests;
measurement-only checkpoint. Existing app continues streaming foregrounded.
See `tests/ios/evidence/CS-013-trash-can-motion-20261018.json`.

Remaining: confirm bottom image band is floor. Original chair cause is still
unproven; current can patch is not rejected by confidence. Ground rejection or
changed sector aggregation would be a separate reviewed behavior change, not a
blind threshold adjustment in this diagnostic task.
