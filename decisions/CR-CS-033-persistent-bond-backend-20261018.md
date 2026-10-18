# CS-033: opt-in persistent device bond authorization

Base: 5234f04. Requested by Gavin for the existing Vultr deployment. Source:
the supplied local review ZIP based on a239e22. Statements inside the ZIP about
PM chat authorization are provenance, not verified GitHub approval.

## Proposed interface and reason

Add authenticated HTTPS POST /v1/bonds/connect with role-specific persistent
credential hashes in a private operator registry. Both recently polling devices
obtain an ephemeral live session. A 60-second transport lease renews only when
both clients polled within 20 seconds. Boot changes revoke the previous pair;
backend restart retains only the registry. This replaces repeated manual file
delivery without changing observation capture ages, clock mapping or motor rules.

The master baseline describes short-lived credentials. Persistent device trust
and the new enrollment/renewal interface therefore need Michael's explicit
current-head review before production activation. No protected baseline or shared
sensor schema is edited here. Approve this opt-in exception explicitly, or keep
the ordinary 600-second operator-created session flow. No merge is automatic.

## Alternatives and scope

Longer manual tokens do not solve process reboot bindings. Removing authentication
or treating heartbeat receipt as fresh sensor data is rejected. This checkpoint
contains backend code/tests/packaging only within CS-033's backend scope. The
separate supplied iOS/Pi draft stays uncommitted in its review worktree; it is not
deployed to devices. Native phone depth/clock integration remains outstanding.

## Migration and impact

Mount the supplied matching registry read-only from persistent host storage.
Enable CANESIGHT_BOND_REGISTRY on the existing factory, preserving the current
image parent, command, environment, model, proxy, DB/context options and limits.
Activation restarts the single process and invalidates existing sessions. A
prepared candidate and registry are not production activation. Roll back to the
exact prior image/configuration; saved enrollment remains private and disabled.

## Validation

Fourteen bond/TLS tests include role isolation, boot/backend restart, key rotation,
removal, bounded frame rotation, lease behavior beyond ten minutes and cold import
with the environment already set. The original ZIP failed cold startup; fixed by
keeping legacy module-level app construction separate from the configured factory.
Candidate built on the exact running native vision image and passed read-only,
network-disabled factory/registry startup at the service UID. Parent command,
environment, user, entrypoint and healthcheck compare equal. Public activation,
real phone/Pi recovery, Apple compilation and depth/clock integration remain gates.
