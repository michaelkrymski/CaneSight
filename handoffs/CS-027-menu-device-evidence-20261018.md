# CS-027 GPIO21 spoken-menu operator evidence — 18 October 2026

Owner: bondmila. Branch: task/CS-027-production-menu. Follow-up PR #83.
Session base: bf0240203298fcc9d30325bf2f05da7f4b1ff901.
Accepted main integrated without conflict: 3769c4bc46b81afb5fcf8d2f475fc0b2d06363fa.
This includes merged CS-040 route-monitoring PR #80 at f2a6dca.
User-reported Pi checkout: f2a6dca6df87ffe1daf0a9f265590ca9ba6a393e.
No implementation or protected baseline edits. Only own task runtime, two new
operator evidence files, this handoff and a new changelog fragment/generated log.

## Evidence, preserving both attempts

The operator ran the current-main separate-clone edge.menu_bench with --speak,
--audio-confirmed, --consent, --synthetic-adapters, --gpio21 and a private report.
The pasted output is console snapshots rather than the complete saved JSON. A
later git rev-parse HEAD response identifies the same checkout; this source/run
association is operator supplied, not an agent-observed hardware execution.

First snapshot: GPIO used; no fault; context=2, entry=2, selection=7,
confirmation=0, activate=0, cancel=2; final reason timeout, state closed.
This establishes recorded cycling/entry and a final timeout, not timing/label
order/wrap, successful confirmation or a physical request.

Focused rerun snapshot: GPIO used; no fault; entry=1, selection=1,
confirmation=1, activate=1, cancel=1; no context gestures; final cancellation
reason manual with pedestrian_signal, state closed. The enum manual does not
alone distinguish the physical button from terminal cancellation. The requested
procedure was new button hold/confirmation release followed by a fresh press.

On a direct follow-up about the focused run, the operator selected exactly:
“Clear speech; stopped promptly”. The question explicitly included no noticeable
continuing sound after cancellation. Preserve that as qualitative human audio
observation; no measured audible stop latency, exact threshold measurement,
independent electrical validation or PM acceptance is inferred.

Both snapshots explicitly report synthetic interaction only, no automatic route
detection, no live observations, no phone/backend/Gemini/context requests/motor
GPIO and physical_audio_accepted=false. Confirmation/activation is an interaction
state; no real scenario analysis job ran. Earlier incomplete runs remain intact.

## Verification and publishing

Previous accepted-base rerun: 205 edge, 83 context and 195 shared tests passed
with pinned requirements in isolated Python 3.13; initial system-environment
failures are disclosed in the prior handoff. After integrating accepted #80,
rerun edge and context suites; exact results are appended below when complete.
Checked publishing reruns repository/shared/changelog/governance/whitespace checks.
JSON evidence is decoded strictly before publishing. No new Pi run by the agent.

## Remaining gates

Review this evidence checkpoint independently. Full CS-027 status remains
blocked pending Michael's physical acceptance and actual source/provider/scenario
integration prerequisites. PR #80 code availability is now accepted, but neither
Pi snapshot configures or exercises automatic route monitoring. Bluetooth-loss/
reconnect, stale-source/provider preemption and paired-device timing cannot be
claimed from these runs. Evaluated CS-037/038 capabilities remain unavailable;
no other task is edited or taken over. No task Done, merge, road-use or motor claim.

Final integrated software rerun: all 205 edge tests and all 100 context tests
passed, no skips, with pinned test requirements on Python 3.13/macOS.

Publishing race: main advanced with assignment-only PR #85. The helper
refused publication before staging/pushing; inspected accepted changes, then
merged 3baf4de without conflict or implementation edits and retried.
