# CS-003: freeze core observation and freshness contract v1

Status: proposed; exact-current-head PM authorization pending.

Michael requested completing CS-003 so the team can implement dependent components against a common contract. Main currently has a placeholder shared README and an illustrative master-plan message, but no executable schema or conformance fixtures. This proposal assigns Michael the contract task and leaves status Review until accepted.

Smallest coherent change: shared/protocol/v1 contains JSON Schema, replay fixtures, normative protocol and Python reference checks; tests/contracts covers behavior; shared/README links the contract. CI installs the declared contract test dependency so these tests actually run in the existing discovery step. A new immutable change fragment and handoff record the result. No master-plan, dependency, acceptance, branch-protection or governance weakening is proposed.

The contract preserves 500 ms depth / 1500 ms vision / 2500 ms health starting limits and rejects permissive crossing/actuator fields. It resolves previously unspecified per-type sequence scope, camera provenance for vision results, strict null/unknown semantics, metadata transport, bounded clock request/reply fields, maximum clock-map age and uncertainty. New numerical uncertainty/drift settings are prototype engineering proposals requiring device verification, not validated safety thresholds. Invalid/unbounded timing removes guidance.

Protected paths: shared/ and .github/workflows/checks.yml. Task runtime changes only: owner, status, branch, evidence and blocker. No app implementation, real clock calibration, network/latency measurement, wiring verification or deployment acceptance is implied.

Alternatives: let each device invent its own schema (integration/replay ambiguity); trust wall UTC/receipt time (can renew stale observations); require all devices synchronized by an assumed NTP service (not available/proven); JSON schema without state tests (misses epochs/lineage/expiry). Choose closed schemas plus explicit fail-closed state and clock rules, origin-Pi timing for Pi frames, and bounded source-consumer probes for phone depth.

Migration: once this PR is approved/merged, Adit and other component owners pull accepted main and implement adapters against the contract. Existing draft code needs explicit adaptation; no silent compatibility is promised. Backend/transport still enforce auth, nonce consumption, quotas, image decoding, state clearing and independent local expiry. Tests use replay fixtures only. Incompatible later changes need a new reviewed version. Roll back through a reviewed revert and pause/mock dependent integrations until replacement agreement; keep history.

Validation: structural checks, all 34 repository/contract tests, generated changelog and whitespace checks; CI result separately verified on the PR. Acceptance requires Michael's exact-head review/authorization and a collaborator's approving review under existing protection. This file is not that authorization.
