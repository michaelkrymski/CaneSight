# CS-041 session-health dashboard

Read-only session metadata and a local synthetic replay preview. Neither view
provides crossing permission, an all-clear state, or motor control.

## Synthetic preview

Run from the checkout with Python 3.11+:

```sh
python -m backend.telemetry.dashboard --port 8041
```

Open http://127.0.0.1:8041. This dependency-free loopback server accepts no
credentials. Its CSP disallows network connections. Eight scenarios exercise
recent observations, unknown depth, delayed vision, heartbeats only, clock
uncertainty, phone disconnect, Pi disconnect, and both disconnected. Pause stops
packets while display time continues; heartbeats never renew capture age. Boxes
are illustrations, never camera images. Distances and boxes disappear when their
independent source becomes stale, unknown or unavailable.

The fixture's explicit synthetic capture-age upper bound grows with local elapsed
time. Depth uses 500 ms and vision 1,500 ms; transport uses a separate 2,500 ms
deadline. Unknown never becomes zero or clear. Pedestrian signal and countdown
remain unknown in both views. The notice remains Research prototype — no crossing
permission.

## Optional authenticated metadata view

This implementation is opt-in and awaits Michael's review before public
activation. See `decisions/CR-CS-041-dashboard-viewer-interface.md`. The default
`backend.server` factory, deployed service, shared contracts and native Origin
restrictions are unchanged. Do not expose the fixture server or place operator,
phone or Pi credentials in the browser.

The separate `backend.telemetry.live` factory observes admitted native operations
without consuming peer queues. It preserves the actual session mode, source/boot,
sequence, frame, original capture timestamp and model version. It exposes no
images, GPS, detections or distances. A backend-offered vision packet does not
confirm Pi receipt or acceptance. Socket presence and backend packet age are
reported separately from capture age. Capture ages always remain **unknown**:
there is no verified device-to-backend clock mapping. Even responding transport
cannot make observations eligible. A later clock-bound interface needs separate
review; this view does not fabricate it.

The browser polls once per second, clearing metadata after logout, malformed
responses, denied requests, timeout or lost connectivity. The API limits a viewer
to four reads per second, with at most sixteen hashed viewer bindings and eight
native sessions. Events are capped at eight. No browser storage or query-string
credentials are used.

### Reviewed activation procedure

After Michael approves the current PR head and proposed interface:

1. Build from the reviewed source using an explicitly supplied immutable native
   vision image as `BASE_IMAGE`, with `backend/telemetry/Dockerfile.dashboard`.
   Its adjacent Docker ignore file allows only the required static assets and
   telemetry modules. Do not include deployment environments or credentials in
   the build context.
2. Retain existing TLS termination, loopback-only upstream, resource bounds,
   verified model mount and private `CANESIGHT_OPERATOR_TOKEN`. Configure
   `CANESIGHT_DASHBOARD_ORIGIN` to the exact HTTPS origin, with no path/trailing
   slash. The new factory supports `CANESIGHT_VISION_WEIGHTS` as the native factory
   does; its local CLI uses port 18083. Keep a single worker. Review the production
   proxy mapping before changing the service; no deployment configuration is
   changed in this PR.
3. Restarting replaces in-memory sessions. Verify health, then create fresh
   native enrollments using `backend/SESSIONS.md`, keeping device grants private.
   Issue a separate viewer for an existing session from a trusted operator host
   checkout with backend deployment requirements installed:

   ```sh
   python -m backend.telemetry.viewer --base https://BACKEND_ORIGIN \
     --operator-file /PRIVATE/backend.env --session-id SESSION_ID \
     --out /PRIVATE/new-dashboard-viewer.json
   ```

   The output must be new and outside the checkout. Use a private parent directory
   (0700 on Linux; user-only ACL on Windows). Linux output mode is 0600. The file
   contains only `base_url`, `viewer_token`, `expires_in_seconds`; it is distinct
   from the Pi enrollment file. Never paste it into chat, Git or issue trackers.
   The CLI verifies TLS and refuses redirects, environment proxies, extra response
   fields and invalid lifetimes; it never prints credentials.
4. Open the configured HTTPS origin. Privately enter **only** its viewer token in
   Viewer credential. Login clears the field and installs a Secure, HttpOnly,
   SameSite=Strict host-only cookie. Access lasts at most 600 seconds and never
   exceeds the native session lifetime. Operator/device tokens cannot log in as
   viewers. Viewer tokens cannot use native/operator routes. Disconnect revokes
   that viewer; native revocation/expiry removes all its viewers. Login/logout
   require the exact browser Origin; there is no CORS grant.
5. Verify the intended session/source/boot/mode and unknown ages. Rollback uses
   the previous native image/factory and removes the optional origin setting;
   restart again requires fresh enrollment. Do not change native Origin checks
   or weaken TLS to make a dashboard work.

Public activation and real-device dashboard evidence remain pending. Local tests
use synthetic sessions and temporary trusted TLS certificates. No phone
connectivity, model accuracy, motor, GPIO or electrical readiness is established.

## Verification

```sh
node --test tests/dashboard/model.test.mjs
python -m unittest discover -s tests/dashboard -v
python -m unittest discover -s tests -v
python -m unittest discover -s tests/backend -v
python scripts/validate_repo.py
python scripts/render_changelog.py --check
git diff --check
```

Backend tests require `backend/requirements-test.txt`. The preview HTTP tests and
Node fixture model remain dependency-free. Test cases include native/viewer role
separation, same-origin secure cookies, expiry/revocation, bounded polling,
closed request bodies, native queue preservation, original capture metadata,
verified HTTPS/native Origin denial and private issuer output. Protected CI is
unchanged. Browser checks must label synthetic harnesses explicitly and must not
present them as deployed device evidence. See the handoff for tests actually run.
