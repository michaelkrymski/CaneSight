# CS-013 — controlled trash-can patch baseline

Branch `claim/CS-013-michaelkrymski`; base
`c34520b60e85d6cd4b5efe18c94659ee236208c4`. Local only; no GitHub contact.

Operator positioned the inspection patch on a trash can and reported distance
3.5 ft (~1.067 m). Five independently refreshed local snapshots across 8.301798 s
showed 40 completed native depth sends (~4.818 Hz), stable selected grid cell (7,4),
512 positive pixels each. Retained high-confidence count 368–507 (71.9–99.0%).
All-confidence p10 1.498–1.512 m; retained p10 identical in these samples. Patch
medians ~1.524–1.550 m. Whole right sector retained p10 0.862–0.883 m.

Confidence filtering does not account for the selected patch's measured distance
in this test. Other nearer sector pixels determine the sector percentile. The
patch range disagrees with approximate operator distance, so real correspondence
is unresolved. Requested keeping phone fixed, moving can one foot closer and
retapping solid surface to compare response. Do not attribute current measurements
to the earlier chair or claim mapping verified. No changes to app code, thresholds,
clock bounds, motor controls or credentials. No new automated tests were needed
for this measurement-only checkpoint. Snapshot evidence is in
`tests/ios/evidence/CS-013-trash-can-patch-20261018.json`.
