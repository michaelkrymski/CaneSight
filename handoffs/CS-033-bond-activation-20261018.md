# CS-033 reviewed bond deployment activation

Owner Gavin (`gmarcialcalleja`), branch task/CS-033-bond-backend, base a253bf6.
This is deployment evidence only, not another runtime behavior change.

Verified through GitHub metadata: PR96 merged, Michael review APPROVED at exact
head 22559a4a09f09ae8e9e142de4d83aa42a508443f explicitly accepts the new opt-in
authorization/lease design. User explicitly requested deployment and said GO.
Accepted app.py/bonds.py bytes match the prepared candidate; PM integration
changes did not change runtime source. No merge or main push performed here.

Activated image sha256:2ba85c9980bc9199d4dbbbac297aba1a4a6dec33fbab39817e7678e7bad4dde6
on the existing host. Persistent registry remains /var/lib/canesight/bonds/registry.json
(root:10001,0440,parent0750), mounted read-only at /run/canesight/registry.json.
CANESIGHT_BOND_REGISTRY points there. Did not regenerate prepared device enrollment.
Existing Compose environment retained with additive registry host setting and
image reference; compose.bonds.yaml appended after existing native/vision overlays.
Only backend recreated; prior image/environment references privately backed up
in the existing 0700 server review directory. Proxy/certificate volumes unchanged.
Actual pre/post runtime environment (except bond variable), command and existing
model/readiness mounts compare equal. Native vision remains selected; no previously
absent Gemini or DB options were silently activated. Existing prepared application
composition work is retained in accepted main and is not replaced by this layer.

Actual public tests: /healthz200, new bond endpoint rejects valid-shaped missing
credential with401. Complete accepted session probe passed HTTPS/WSS, operator
creation, role isolation, generated upload acknowledgment, duplicate/expiry,
disconnect invalidation and reconnect replay rejection. Readiness200 while enrolled
with ingestion/model/worker all true; outside active sessions ingestion may be false.
Five generated YOLO result samples passed original lineage/role/session/revocation/
expiry checks: median119.121ms, nearest-rank p95/max160.44ms. Synthetic replay only.
No token, registry record/hash, raw image or private environment in this evidence.

Prepared phone-bond.json and pi-bond.json must be delivered to their intended
bond-enabled clients from the separate source ZIP. Registry hashes are not device
credentials and cannot be used to fabricate missing role files. Client draft needs
integration with current accepted native depth/clock and GPIO work before actual
guidance claims. No actual phone/Pi bond connection, Apple build, physical recovery,
source freshness/accuracy, motor or electrical acceptance claimed by this deployment.
Do not restart the backend again merely to test clients without coordination.
Rollback restores prior image/environment and removes the new overlay, preserving
registry and existing model/TLS volumes; native in-memory sessions need reenrollment.
