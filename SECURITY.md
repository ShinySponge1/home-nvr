# Security and data boundaries

This alpha is intended for a trusted single-site host. Published HTTP ports bind
to loopback. Put TLS and a reviewed authentication boundary in front of remote
access; never expose Frigate's trusted port 5000, Ollama, the gateway, or MQTT to
the internet. The companion's single bearer key permits read access to all
configured cameras; it is not a multi-user or camera-scoped authorization model.

Context and gateway containers use nonroot users, read-only source/config mounts,
dropped capabilities, and no Docker socket. They cannot reconfigure Frigate or
deploy models through their exposed routes. However, the Docker network's
Frigate port 5000 is trusted and broader than a read-only token. These containers
are part of that trusted boundary, not an isolation guarantee against a compromised
companion. Introduce a dedicated authenticated read-only upstream facade before
hosting untrusted tenants or plugins.

The viewer does not persist its bearer key in browser storage or URLs. Static
assets contain no camera data. API replies and snapshots have `Cache-Control:
no-store`. Values from upstream are displayed as text. CSP excludes third-party
scripts and framing. Do not assume a displayed snapshot is current merely because
the request succeeded; telemetry age is reported separately.

Audit output contains request IDs, route names, status, timing, and timestamps.
It excludes prompts, images, plates, credentials, and query strings. Optional
file audit is bounded to two approximately 5 MiB files and requires an explicitly
writable directory. This is operational metadata, not an immutable forensic log.

Bootstrap stores plaintext camera environment values in an ignored private file;
Docker secrets are file mounts, not encryption at rest. Use host volume encryption
and protect host access. Credentials embedded in URL userinfo are rejected by the
inventory; use named environment placeholders with URL-encoded values. Generated
backups contain secrets and must stay private. A backup that has not been restored
is unverified.

Frigate's footage retention does not automatically delete exports, backups,
training images, weights, or derived metadata. Set explicit policies for each.
Do not publish footage, faces, plates, JWT keys, or local event-review history.
The public-tree checker is a bounded packaging check, not a complete secrets or
privacy audit; release review must inspect the exact Git diff and history.

For a private vulnerability report, contact the repository maintainer through a
private channel. The future public repository must configure its own maintainer
contact and security-advisory process before accepting external deployments.
