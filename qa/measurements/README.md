# CS-045: offline latency and depth-error analysis

This tool prepares analysis for the master plan's measurement procedure. It does
not connect to a phone, Pi, camera, socket, GPIO or motor. It has no new transport
contract. Real measurements, clock evidence and PM acceptance are still required.

```powershell
python -m unittest tests.measurements.test_analysis -v
python -m qa.measurements.analyze qa/measurements/example-synthetic.json
python -m qa.measurements.analyze C:/private/normalized-bench.json
```

Run from the repository root with Python 3.12 or newer; no extra dependencies.
The CLI emits an allowlisted aggregate report to stdout. Invalid input returns 2
with a generic error and no rejected values or traceback. Keep real inputs and
reports private until sanitized and reviewed. Never include credentials, images,
location tracks, exact GPS, or free-text device logs. Unknown fields are rejected.
Input is limited to 1 MiB and 10,000 entries per sample collection. Duplicate JSON
keys, nonfinite/bool numerics and malformed timing/identity fields are rejected.

## Collect before analyzing

1. Record the exact tested application commit, one source/boot identity and one
   run ID. Split different builds, source boots, test configurations and endpoint
   types into separate files. Use opaque, nonsecret IDs of 1–64 letters, digits,
   underscores or hyphens. A run ID is not a credential or a device serial number.
2. For key latency paths collect at least 20 **observed** trials, retaining every
   unavailable, cancelled or missing trial too. Preserve strictly increasing
   capture sequence and original source capture time in milliseconds. Do not use
   heartbeat/send/receipt time as a replacement for capture time.
3. Normalize timing events to one reference monotonic clock using independently
   measured conservative mapping bounds. Retain the actual mapping, drift limits,
   validity interval, clock units and measurement method privately under
   `clock_evidence_id`. The analyzer does not derive, validate or certify mappings.
   Unbounded mappings do not supply valid timing measurements: record
   `measurement_missing` with a documented capture bound, or defer the timing run
   entirely when capture itself cannot be bounded. Do not substitute zero error.
4. Every stage is `{ "lower_ms": ..., "upper_ms": ... }` in that reference clock.
   Include mapping **and** instrumentation/video resolution uncertainty. Optional
   stages, in causal order, are `phone_send`, `backend_receive`, `pi_receive` and
   `software_command`; `capture` and the selected observed endpoint are required.
   Missing intermediate stages are counted as missing, never estimated. The input
   order is chronological; a replayed capture time or sequence is rejected.
5. Choose `software_command` for decision/command timestamps. Choose
   `physical_onset` only for independently measured onset (for example synchronized
   stimulus/onset video with bounded frame exposure/resolution). A trace command
   is not physical onset; never relabel `edge.trace` command records as onset.
   The existing trace also does not by itself establish the missing phone capture
   clock relation. This tool intentionally does not auto-convert such traces.
6. For depth, use measured stationary targets at the plan's 0.5, 1, 1.5 and 2 m
   positions where the setup supports them. Record left/center/right separately,
   calibrated phone orientation/mount, measurement method and environmental
   conditions in private run notes. `estimated_m: null` means unavailable, never
   zero distance or a clear path. Zero is a numeric estimate if actually produced.
   Split materially different conditions/configurations into separate runs.

## Input and interpretation

The example is **synthetic**, deliberately has fewer than 20 observations, and
uses an all-zero placeholder commit. Replace it with the exact tested 40-character
commit for real data; syntactic commit validation does not prove provenance.
Top-level `origin` is `synthetic` or `operator_bench`. Operator attribution is a
declaration requiring review, not authentication or proof of measured hardware.

Each latency row supplies `capture_sequence`, `original_capture_ms`, `outcome`
and `stages`. Outcomes are `observed`, `unavailable`, `cancelled` or
`measurement_missing`. Only observed rows have the selected endpoint. The report
shows attempted, observed, every outcome count and whether 20 observed samples
exist; failures are never hidden behind an observed-only denominator.

For capture interval `[c0,c1]` and endpoint interval `[e0,e1]`, latency lies in
`[max(0,e0-c1), e1-c0]`. Overlapping intervals give a zero lower bound, not a
precise zero latency. Reports give median, nearest-rank p95 and maximum for lower
and upper bounds separately, plus combined endpoint interval widths. Use upper
bounds when evaluating the plan's initial timing targets; meeting a timing target
alone does not establish acceptance. Stage ordering must admit a causal sequence.

Depth groups remain separate by sector and measured distance. Reports include
total, valid, unavailable, coverage, mean signed error and median/p95/max absolute
error. No arbitrary accuracy pass threshold is introduced. Empty groups/cohorts
have null metrics rather than fabricated zeros. No night, road, curb or broader
accuracy claims can be derived from a small controlled indoor dataset.

Every synthetic report stays `synthetic_only`, even with 20+ samples. Bench data
stays `requires_pm_evidence_review`; no automatic Done, readiness, physical-off
or crossing-permission verdict exists. Review data provenance, omissions and
clock evidence before accepting results. No scene description or model output
may alter this measurement interpretation.
