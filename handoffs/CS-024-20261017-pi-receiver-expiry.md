# CS-024 Pi receiver and capture expiry checkpoint

Base: 6a386675d24e88082fce9f3e063f101098c1e7bd.
Branch: task/CS-024-pi-receiver-expiry.
Owner: gmarcialcalleja, assigned by Michael's approved/merged claim PR #31.

## Changes
edge/receiver.py adds one native WSS connection, header auth, verified certificate/
hostname, redirect refusal, bounded receive queue and no reconnect backlog.
It enrolls only the originating Pi in the accepted CaptureAgeGate; it does not
invent a phone binding or clock calibration. Sender records the exact captured
frame before HTTP, under its ledger lock. WSS reception uses that same two-entry
ledger, boot/process and CLOCK_BOOTTIME. Mapping remains the original camera
stream mapping. Two gate entries and one current observation are bounded copies;
the existing gate's seen-frame history remains capped at 4096 per session.

edge/uploader.py adds explicit --receive-vision and registers before upload.
It connects WSS before capture and independently expires every nominal 50 ms.
Clock reversal, disconnect, revocation, camera failure and shutdown invalidate
evidence. Initialization failure cleans up the receiver; ordinary capture-only
and upload-only behavior stays compatible. No GPIO/haptics are introduced.
edge/requirements-receiver.txt reuses the accepted backend gate's dependencies,
without ML. edge/README.md documents private enrollment, isolated Pi environment,
six-field credential, limitations and commands. New tests are in tests/edge/.

## Tests actually run
Windows pinned Python 3.12: 26 edge tests passed. Linux Python 3.12 on Vultr,
isolated source directory with existing test environment: all 26 passed.
Tests cover original lineage/mapping, all identity/time/image mutations,
stale/future/unrecorded/evicted results, replay, malformed/oversized/deep wire,
clock reversal, camera readiness recovery, initialization failure, TLS options,
redirect refusal, registration before HTTP and no upload after invalidation.
A real certificate-verified local HTTPS/WSS service with an explicitly synthetic
backend worker accepts a generated JPEG, returns a matched observation, expires
it while recv is blocked, accepts a new capture and revokes while it is fresh.
Both socket and worker threads shut down.
Windows backend regression: 128 discovered, 121 passed and seven environment/
opt-in skips. Shared checks/structure/changelog/whitespace run before publishing.
Existing dependency deprecation warnings remain; no unrun CI step is claimed.
The protected CI does not discover tests/edge automatically; run it explicitly.

## Remaining work and limits
This checkpoint is not the whole CS-024 local hazard/motor policy. CS-023 is an
unchanged outstanding dependency. Keep phone data unavailable until an explicit
trusted phone binding and verified clock drift/mapping are integrated.
Real Pi receiver execution against actual model results remains pending; prior
20/20 camera ingestion is different evidence. libcamera sensor-delay defaults
remain unverified. The nominal expiry tick is not a hard real-time guarantee.
A copied current() observation cannot be cached as a continued eligibility lease.
No detector accuracy, all-clear/crossing permission, phone connection, electrical
validation or motor readiness is established. Full system status is unavailable.
Review the checkpoint, coordinate an isolated Pi run, and complete scheduler/
policy integration when its dependency is accepted. Status remains in progress.
