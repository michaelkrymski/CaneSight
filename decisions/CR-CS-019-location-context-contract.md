# CR-CS-019-location-context-contract: separate consented GPS transport

Status: Proposed. No protected baseline or wire implementation changed.

- Task and author: CS-019, Gavin (`gmarcialcalleja`).
- Evidence: CS-019 acceptance requires consented coarse GPS telemetry. Master
  plan section 6.2 requires original fix time, age, accuracy and consent. Accepted
  `shared/protocol/v1/protocol.md` explicitly places GPS outside its core freeze
  and requires separately reviewed contracts. Existing additionalProperties rules
  must continue rejecting GPS fields added to depth/vision/heartbeat packets.
- Why ordinary implementation is insufficient: local consent/freshness/provider
  software fits ios scope, but no accepted GPS message/endpoint or receiver exists.
  CS-016's bounded depth transport cannot silently publish a new message type.
- Smallest proposed change: Michael assigns/reviews a separate P1 location-context
  contract, leaving current depth/vision/heartbeat behavior unchanged. Potential
  protected additions are a new `shared/protocol/location/` schema and contract,
  not relaxed v1 additionalProperties. This PR contains no such protected edits.
  Any eventual implementation touching backend scope needs a separate assignment.
- Proposed review inputs: authenticated session/source/boot/mode and increasing
  sequence; explicit consent/availability; rounded latitude/longitude only when
  available; original fix UTC, conservative original-fix monotonic capture bound,
  fix age at serialization, sensor accuracy and quantization-inclusive accuracy.
  Unavailable state must contain no coordinates. Consumer includes transport age,
  rejects unbounded clocks/stale/future/duplicate/wrong-session data and expires
  context independently. Do not trust a sender's serialization-age number as proof
  of freshness at remote receipt. No optional GPS fields on existing v1 messages.
- Consent/privacy: at most 1 Hz, default off, separate sharing consent from OS
  permission; purge pending/in-flight work on revocation/background. No default
  history, raw-image/location logging or precise-track persistence. Decide explicit
  revocation signaling and deletion/retention before enabling a remote sink.
- Alternatives: (1) local coarse display only, implemented here while review is
  pending; (2) defer all P1 GPS until P0 integration, valid schedule fallback;
  (3) add GPS keys to depth messages, rejected because it bypasses the accepted
  contract and mixes context with guidance evidence.
- Safety/interface/teammate impact: coordinate with Mila's CS-016 after its review;
  GPS never selects a signal/lane/curb or changes motor/freshness policy. CS-019
  software currently has no network sink or Codable wire model. No CS-016 files,
  backend code or other teammate task records are modified by this proposal.
- Migration/rollback: keep the publisher disabled until the reviewed schema,
  authenticated sink, receiver expiry and privacy controls exist. Roll back by
  disabling the P1 publisher; core depth/vision continues unchanged.
- Validation: existing v1 fixtures unchanged; new isolated schema fixtures for
  availability/consent, quantization, malformed/future/stale times, clock bounds,
  session/boot/sequence mismatch, rate bound, disconnect replay and revocation.
  Xcode and physical authorization/lifecycle verification still required.
- Approval: pending Michael's exact-head GitHub authorization on the eventual
  protected-contract PR. Merging this proposal alone does not change the schema
  or authorize implementation outside the assigned paths.
