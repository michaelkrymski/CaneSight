# Optional context narration — CS-040

`narration.py` is an independently testable local gate, with a synthetic speech
adapter in tests. It is not installed in the backend, iOS app, or Pi agent yet.
No context messages are added to the accepted shared observation protocol.

Provider output must have exactly this private shape:

```json
{"objects": ["chair", "table"], "uncertain": true}
```

Only one to three labels from `narration.OBJECTS` are accepted. All spoken words
come from a fixed template of at most 20 words, labeled as an uncertain AI
description. Provider instructions/prose, unknown labels, extra properties,
missing uncertainty and invalid structures produce `Description unavailable.`
This restricts language, not factual accuracy: a permitted object can still be
hallucinated. Scene text is untrusted data. No walking-symbol interpretation,
crossing permission, motor command, or movement recommendation exists here.

## Consumer integration

1. Provide a nonblocking local speech adapter with `speak(text)` and immediate
   `stop()`. Calls are serialized; adapters must not reenter the controller.
2. Drive `set_priority(hazard=..., unavailable=...)` from trusted local health
   and obstacle policy. Startup/unknown is unavailable. Gemini never sets these
   flags. Either priority stops current audio and invalidates pending speech.
3. Only with explicit scene-sharing consent, call `begin` with the conservative
   capture-age upper bound in seconds measured on the receiving device. Unknown,
   negative, nonfinite or eight-second-old age is rejected. Do not compare raw
   clocks across devices or reset age at network receipt.
4. Correlate the returned ticket with the context request. Pass the structured
   result to `deliver`. New requests supersede old tickets; delivery is single
   use. The deadline is eight seconds from the bounded capture time.
5. Call `tick()` on an independent local timer while audio is active, even if
   network/provider work is blocked. Expiry stops audio. Call `cancel()` for
   manual cancel, backgrounding, session/epoch change or disconnect, and cancel
   provider work separately. Recovery needs a new request. Call `close()` during
   teardown; a failing stop adapter permanently disables this controller.

Every begin, delivery and tick checks the clock against the highest previous
reading. A reversal, exception, invalid or nonfinite reading stops audio and
invalidates the pending ticket. Cancellation/new requests do not reset clock
history. After reversal, new requests are refused until a valid reading reaches
the previous high-water mark; recovery never revives the old ticket.

This gate has no authority to change health, haptic patterns, signal state or
permissions. Integration still requires CS-039 (provider), CS-027 (button) and
CS-018 (accessible phone audio/manual cancel). No hardware audio, VoiceOver,
background execution or GPIO behavior has been verified.

Run from the repository root:

```sh
python3 -m unittest discover -s tests/context -v
```
