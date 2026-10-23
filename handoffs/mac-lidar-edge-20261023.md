# Mac calibrated band edge fix — October 23, 2026

Branch: codex/mac-lidar-calibration. Base: dbc1038.

## Observed problem

Phone was in LEFT wizard step. Centre measured 2.11 m; left/right had
6,396/6,815 high-confidence source pixels but were wholly rejected because one
projected corner left the preview. Full-width geometry made the all-corners rule
sensitive to minor post-neutral movement.

## Change

Keep original physical sector rays. Clip their projected polygons to normalized
preview bounds; require at least 90% projected area visible per sector. Use only
real pixels within the current preview and original neutral region. Estimate
missing raster coverage from projected area loss, adding ceil(count*(1/fraction-1))
NaN/zero-confidence samples. Thus unobserved area reduces coverage rather than
acquiring depth; lower visibility leaves the entire sector Unknown. This is a
geometric operating envelope, not a confidence threshold reduction. No all-clear
inference. Overlay continues to project actual sector boundaries. Retain full
visibility diagnostic and add local visible-area/support fields. No v1 packet,
receiver, motor or drift configuration changes. No credential regeneration.

## Validation and limits

33 geometry/state tests pass, including small (1-degree) tilt retaining observed
side samples with unknown padding, and substantial area loss retaining Unknown.
Existing four real processor integration cases pass through the permanent wrapper.
Physical signed build/signature/install/launch passed. Existing yellow band
position/height survived. Latest phone snapshot authenticated waiting for Pi,
zero depth sends, no confirmed profile, awaiting fresh tracking after restart.
Requested floor scan and neutral capture again; physical post-neutral side/tilt
verification remains pending. No hardware acceptance claimed. Earlier root257,
backend145 and Simulator UI runs belong to prior checkpoint; not rerun here.
