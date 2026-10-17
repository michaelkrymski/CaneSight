# CS-024 manual Pi setup and backend reachability boundary

Base: 6a386675d24e88082fce9f3e063f101098c1e7bd.
Branch: task/CS-024-pi-receiver-expiry; draft PR #32.
Manual test snapshot: 17441cee512bb29ae6ad5bd327706a45c0a8f107.

The human explicitly requested manual commands rather than retrying the rejected
automated SSH runner. That runner was not retried or routed around.
The human reports receiver/camera imports OK after preparing the separate Pi
checkout/environment and reports the exact snapshot SHA above. No receiver test
summary or actual matched vision count has been supplied.

A fresh uploader identity was supplied for enrollment. The enrollment attempt
did not confirm success: operator-side connections to the Vultr host on SSH/HTTPS
timed out. The private local JSON was verified to belong to an earlier boot and
was explicitly withheld from transfer. The Pi's manual curl to the public
https://64.177.50.116/healthz also timed out after 5002 ms. A separate operator-side
GitHub HTTPS request succeeded. These observations establish endpoint reachability
failure from both clients, not which VM/firewall/network/service component failed.

No credentials, process boot ID, session ID or images are recorded. No real Pi
receiver result count, packet rejection count or upload/vision summary can be
claimed for this attempt. Existing successful synthetic TLS tests remain separate.
No camera/GPIO/motor behavior was established by dependency imports.

Next: Michael checks VM status, assigned IP and ingress/network state through
the Vultr console. After verified HTTPS recovery, start a new waiting uploader,
enroll its fresh boot for 600 seconds and privately install only the matching
Pi credential with correct ownership/mode 600. Collect both final uploader and
vision summaries. Preserve the existing CS-022 checkout. Full CS-024 policy
integration still depends on CS-023. Task remains blocked, not Done.
