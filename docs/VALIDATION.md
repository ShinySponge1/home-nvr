# Validation performed

This records observed checks, not a guarantee of production capacity.

- Source checks: 67 Python tests passed locally: 12 inventory tests, four model
  setup tests, 12 publication-guard tests, one installed Frigate schema test,
  22 evidence API tests, and 16 gateway tests. The schema test uses synthetic
  URLs and is optional when no Frigate container is available.
- Generated CPU/AI and NVIDIA/AI configurations passed Frigate 0.18.1 schema
  validation without connecting to a camera. CPU and GPU Compose combinations
  also passed `docker compose config --quiet` with temporary synthetic settings.
- Evidence core/API: 22 tests passed for camera alias collisions, configured LPR state, unknown/stale
  telemetry, historical windows, overlapping long events, result caps, coverage,
  unsupported visual claims, bearer authentication, body limits, stable errors,
  and static-asset availability are covered by local tests.
- Viewer JavaScript passed Node's syntax check; browser interaction and visual QA
  remain separate acceptance work.
- Evidence integration: exercised the source against a running Frigate API
  without enabling a new service. A friendly camera ID normalized correctly,
  enabled LPR came from configuration, telemetry was fresh, and recap/recording
  APIs returned bounded results. No plate strings or images were logged.
- Gateway: sixteen isolated checks passed for message shape, complete-turn
  trimming, image limits, output bounds, overflow retry, aliases/collisions,
  upstream failures, and the single-inference semaphore.
- Public source checker: passed with no generated data, weights, recordings,
  private paths, or literal credentials outside reserved negative-test fixtures.
- Both companion images built from the digest-pinned Python base. Isolated
  containers passed process health, bearer rejection, unknown-route handling,
  upstream-unavailable responses, and the gateway model allowlist. Runtime checks
  confirmed nonroot users, read-only root filesystems, dropped capabilities,
  no host ports, no data mounts, and no access to live camera services.
Not yet exercised as a released product: browser interaction/visual QA, complete
gateway-to-Frigate chat sessions, remote authentication,
household-account permissions, cross-vendor camera compatibility, load/soak/failure recovery, media
integrity checks, restore drills, or deployment of a new model. CI definitions
run on pushes and pull requests; consult the repository's Actions page for the
current remote run status.
