# E2 Micro diagnostic

This diagnostic does not deploy OCI resources. A1 remains preferred. The A1
Compose is unchanged. On a disposable Ubuntu AMD64 Docker host, run
`python3 -m scripts.e2_micro_fit`. Requires passwordless sudo, cgroup v2,
Docker and internet access for pulling the existing digest-pinned images.

The manual `E2 Micro fit diagnostic` workflow also runs for pull requests changing
the harness/workflow, so it can be validated before merging its dispatch definition
into the default branch. No schedules, repository secrets or deployment permissions
are used. The existing fallback scheduler is untouched.

n8n receives 640 MiB and 0.1 CPU; Caddy receives 64 MiB and 0.025 CPU.
Memory-plus-swap equals memory, prohibiting container swap. The aggregate hard
ceiling is 704 MiB, reserving at least 320 MiB of a 1 GiB budget for the host.
This reserve is a budget, not measured Ubuntu/Docker overhead. The Actions host
has more RAM and faster storage; its free RAM is not evidence of Micro headroom.
CPU quotas conservatively approximate a baseline and do not emulate OCI burst
credits, shared-host scheduling or exact OCPU/vCPU equivalence.

The harness uses an internal Docker network, loopback-only Caddy listener, external
random encryption key (0400, UID 1000), UID-owned persistent SQLite state and no
production credentials. Original orchestration is imported/exported inactive;
only a separate manual synthetic workflow calls the internal Caddy mock endpoint.
There is no outbound runtime network access. CLI operations run with the n8n
server stopped, retaining its memory ceiling and avoiding concurrent SQLite access.

Evidence includes sampled cgroup usage, peak, swap, RSS of PID 1, CPU throttling,
Docker stats, limits, exit/OOM/restart state, operation times and persistence/key
checks. RSS is sampled for PID 1 and summed across cgroup processes (shared pages
can be counted twice); cgroup accounting remains authoritative. Editor and public
settings API response times are checked through the loopback proxy.
Sum of independent service peaks is an upper bound, not a simultaneous peak.
Short-lived peaks rely on cgroup memory.peak. Five minutes of idle observation
cannot establish long-term leak freedom or production reliability.

FIT requires every check to complete, zero swap/OOM/restarts, n8n peak <=544 MiB
(15% margin below its ceiling), and startup/import/export/execution <=120 seconds.
Successful runs exceeding these margins are MARGINAL. Harness/infrastructure
errors remain NOT VALIDATED and must not be called hardware incompatibility.
OOM and failed startup/import/export require inspection of collected evidence
before assigning NOT SUITABLE. Review evidence before any OCI provisioning.

Only the measurement JSON is printed to the job summary. Database, encryption
key and workflow exports are never uploaded. Tail diagnostics on failure are
limited to this synthetic environment and redact its random key. Ephemeral state is
removed after the test. No repository artifact or production service is changed.
