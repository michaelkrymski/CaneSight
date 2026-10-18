# CS-033 persistent bond rollout checkpoint

Enable only after the new authorization/renewal interface has Michael's explicit
current-head review; see decisions/CR-CS-033-persistent-bond-backend-20261018.md.
Keep existing manual sessions available. No operator token goes to either device.

Build Dockerfile.bonds on the exact inspected existing image. It copies only
app.py and bonds.py, inheriting the existing command, dependencies, environment,
user and healthcheck. A unique local parent tag may be used only after verifying
its full image ID immediately before the build; record the resolved parent and
candidate IDs. The candidate must not silently replace a context/logging factory.
Compose command overrides remain authoritative and must also be preserved.

Append compose.bonds.yaml to the actual existing overlays, with the existing
private deployment environment plus CANESIGHT_BOND_REGISTRY_HOST pointing to the
absolute persistent registry file. This adds CANESIGHT_BOND_REGISTRY and a read-only
mount; the overlay does not replace image, command, other environment or volumes.
Set BACKEND_IMAGE to the inspected candidate ID in the deployment environment.
Validate the resolved composition privately; never print its secrets. Compare the
old/new command, environment (apart from the bond variable), model/CA mounts,
limits, TLS volumes, logging options and factory before restart.

The prepared registry on Vultr is /var/lib/canesight/bonds/registry.json: root
owned, group 10001, mode 0440 inside a 0750 directory. The service UID can read it;
the image contains no registry or credential. Do not regenerate the supplied
matching enrollment. Never put the registry or device files in Git or reports.

After an agreed restart, verify normal TLS health, ordinary operator enrollment,
WSS relay/expiry/reconnect, generated vision results and bonded recovery with both
device operators ready. Check any previously enabled context/logging separately.
Do not equate a bonded transport with phone depth or capture-age eligibility.

The registry file is an individual bind mount. Replacing the host file atomically
does not replace the mounted inode: recreate the backend after such a replacement.
For immediate revocation also DELETE the active native session with the private
operator credential. Keep a valid empty registry to disable all saved bonds.

Rollback removes the bond overlay/variable and restores the exact old image and
configuration. Preserve model and Caddy volumes and private files; recreate the
backend only. Re-enroll manual sessions after either activation or rollback.
