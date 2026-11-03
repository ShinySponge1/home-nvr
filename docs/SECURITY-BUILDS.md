# Reproducible runtime security overlays

The default Compose project builds small executable overlays instead of trusting
mutable tags or publishing locally compiled binaries. Source archives, builder
images, and runtime images are pinned. Docker verifies each source archive's
SHA-256 before extraction, applies the reviewed patch, runs focused tests, and
copies only the resulting executable into the pinned upstream runtime image.

## Ollama 0.40.13-security.1

- Upstream: `ollama/ollama` tag `v0.40.13`, commit
  `04088e7c9d41cba5d33bafbf788d87a465c79d5b`.
- Source archive SHA-256:
  `17c24d7268a286722d8e02d0f1d940a94922ecb73c20fb4377d2ebd7b1f9640c`.
- Builder: `golang:1.26.10-bookworm` pinned by digest.
- Runtime: `ollama/ollama:0.40.13` pinned by digest.
- Change: `golang.org/x/net` `v0.61.0` to `v0.62.0`.

The dependency update remediates
[GO-2026-6860 / CVE-2026-78661](https://pkg.go.dev/vuln/GO-2026-6860),
an inefficient HTML parsing path classified as CWE-407, and
[GO-2026-6866 / CVE-2026-97045](https://pkg.go.dev/vuln/GO-2026-6866),
an HTML namespace/rendering issue classified as CWE-79. The public patch is
`services/ollama/xnet-v0.62.0.patch`.

## Frigate 0.18.2-security.1

- Upstream runtime: Frigate `0.18.2`, CPU or TensorRT image pinned by digest.
- go2rtc source: commit `7c05066c90ab6ad1fccb506d5f0408aa31ebe60f`.
- Source archive SHA-256:
  `10027a1558746e02c9adc22ceea8ee5ad29a19e156d3dded23404103f0e7c636`.
- Builder: `golang:1.27.3-alpine3.23` pinned by digest.
- Changes: reject negative, malformed, or over-16-MiB `Content-Length` values;
  update `golang.org/x/net` from `v0.61.0` to `v0.62.0`.

The parser change addresses
[GHSA-4xp7-86rr-9758](https://github.com/blakeblackshear/frigate/security/advisories/GHSA-4xp7-86rr-9758),
which can let a configured malicious or compromised RTSP endpoint crash go2rtc.
As of 2026-11-01, that advisory has no CVE or CWE assignment. The x/net update
also removes the two CVEs listed above. The public patch and regression tests are
in `services/frigate/go2rtc-security.patch`.

## Build and verify

```bash
docker compose build --pull frigate
docker compose --profile ai build --pull ollama
docker compose config --quiet
```

For a clean audit build, add `--no-cache`. CI builds both patched executable
stages in addition to the two companion services. Dependabot monitors every
Docker build context and the pinned GitHub Actions.

These overlays address the named executable-level findings; they do not assert
that every package present in the larger upstream Frigate image is reachable or
vulnerability-free. Re-scan final images for each release, review upstream fixes,
and replace these overlays with an official fixed release when one is available.
