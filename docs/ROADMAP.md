# Home release roadmap

The audience is home users monitoring one household with compatible streaming
cameras. Build a useful local home recorder and evidence assistant before adding
more automation. [PRODUCT-SCOPE.md](PRODUCT-SCOPE.md) defines the release boundary
and the manufacturer-agnostic camera test matrix.

## Current alpha

- Inventory-driven RTSP(S) sources and optional detection substreams.
- Frigate-based recordings, snapshots, playback, detection, and retention.
- Read-only evidence API/viewer with canonical camera aliases and UTC provenance.
- Configured LPR flags separate from available, unverified OCR readings.
- Recap events separate from recording coverage and event-list truncation.
- Optional bounded-context Ollama gateway with camera tool normalization.
- Backup-first config replacement, generated secrets, bounded logs, and tests.

This is a single-home engineering alpha. The companion's shared bearer key is
not household account management, and schema tests are not field certification
for every camera brand. The private deployment's reviewed-data training and model
promotion tools remain separately packaged work; the small initial reviewed set
does not establish production detector quality.

## First home release

- [ ] Walk a new home user through camera credentials, main/substream selection,
  codec checks, and friendly names without requiring a specific manufacturer.
  Clearly explain unsupported sources and unresolved authentication failures.
- [ ] Validate an owner-only local installation end to end, including initial
  login, secret handling, updates, backups, and recovery. Keep published ports
  local by default; document a deliberate private remote-access path separately.
- [ ] Complete the stream/codec/authentication matrix with reproducible results,
  including H.264, optional H.265 limitations, no-audio sources, shared single
  streams, main/sub streams, credential escaping, and camera reconnection.
  Record tested model/firmware versions as evidence rather than brand-wide claims.
- [ ] Add a synthetic RTSP source and automated disconnect, restart, missing-audio,
  and invalid-credential tests. A healthy process must not conceal stale video.
- [ ] Provide tested hardware setup options and measured capacity for home PCs.
  Label CPU setup mode clearly; validate GPU/accelerator configurations rather
  than promising the same camera count on every machine.
- [ ] Make recording gaps, stale frames, disk runway, cleanup delays, AI failures,
  and incomplete recaps understandable in the home UI. Preserve recording when
  optional AI or MQTT services fail.
- [ ] Verify the two-day default across recordings, object media, and snapshots
  over a seven-day soak. Explain periodic cleanup and the separate lifecycle of
  exported clips and training data. Test storage exhaustion and recovery.
- [ ] Exercise consistent database/configuration backup and restore on another
  home machine, including playable clips and their metadata. Document what is
  included, what stays on the original drive, and how to recover secrets safely.
- [ ] Complete dependency/security scanning, release notes, reproducible image
  identification, update/rollback tests, secret-history checks, and security
  reporting ownership before distributing a supported release.
- [ ] Test dated recaps, aliases, and missing-evidence responses with home-user
  wording. Keep identification, OCR, and AI descriptions explicitly uncertain
  when evidence is insufficient; assistant chat has no model-promotion controls.

Release acceptance is measured recording coverage, bounded storage, successful
reconnection and restore, understandable setup, and passing regression/security
checks on the declared home hardware and camera combinations. These are release
gates to complete, not claims that the alpha has already passed them.

## Optional home follow-ups

- [ ] Individual household accounts with owner and read-only member sessions,
  revocation, and server-enforced camera permissions. Sharing is optional; the
  first release may remain owner-only until this is implemented and tested.
- [ ] Privacy masks, controlled exports, deletion propagation, quiet hours, and
  opt-in household notifications with understandable settings.
- [ ] Package the generalized review/training workflow using private local data,
  explicit human approval, separate retention, and evaluation before model
  promotion. Preserve immutable reports and refuse retracted dataset releases.
- [ ] Broaden documented camera and hardware coverage based on measured home
  installations, and add integrations only when their maintenance is justified.

Commercial sites, managed fleets, multiple customer tenants, enterprise SSO,
central policy administration, high-availability recording failover, compliance
certification, and service-level guarantees are outside the current product
scope. They are not implied prerequisites or commitments for this home release.
