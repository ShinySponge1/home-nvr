# One home, local first

The product is for home users who want useful recordings and understandable
answers about activity around their own home. The first release covers one home
with one owner and compatible streaming cameras. It is manufacturer-agnostic:
camera support is decided by tested stream, codec, and authentication behavior,
not by a preferred brand. A working RTSP URL alone does not prove that recording,
audio, live browser viewing, talkback, or AI features all work.

This document defines intended acceptance, not a statement that the current alpha
has completed every test. No cross-manufacturer field-certification matrix has
been completed for this starter yet.

## First-release boundary

| Home-user task | Included direction | Boundary |
| --- | --- | --- |
| Add a camera | Private inventory, friendly name/aliases, RTSP(S) source, optional detection substream, and clear connection diagnostics. | Camera discovery, proprietary cloud logins, and vendor apps are not required integrations. The homeowner must have a usable local stream. |
| See and review activity | Live viewing and recording playback through Frigate, plus a read-only evidence viewer and dated recaps. | Recording coverage and event counts are distinct; missing events do not prove that nothing happened. |
| Control storage | Two-day default retention, bounded logs, cleanup visibility, and an explicit storage location. | Exports, backups, and separately retained training data need their own lifecycle. Periodic deletion is not an exact-to-the-second wipe guarantee. |
| Ask about home activity | Camera aliases, explicit time windows, event citations, and honest unavailable/incomplete-evidence responses. Local AI is optional. | OCR, appearance, and AI descriptions are not verified identity or certainty. Chat cannot change cameras or promote models. |
| Keep control of private data | Local recording and processing, generated credentials, local-only published ports, and backup-first changes. | Remote access is an explicit setup choice. No automatic public hosting, cloud footage upload, or guaranteed privacy merely because Docker is local. |
| Recover after a failure | Tested reconnects, consistent configuration/database backups, and an exercised restore/update rollback path. | One recorder is a single point of failure; continuous failover recording is not promised. |
| Share with family | Optional later household accounts with individual sessions and viewing permissions. | Current companion access is a shared bearer key. Multi-user household authorization is not implemented by that key. |

The CPU detector is a portable setup/pilot default. Supported camera count and
AI workload must be measured for each declared hardware configuration. Reducing
detection stream resolution can reduce decode work while also reducing the detail
available for distant objects, faces, plates, and AI crops. Preserve full-quality
recordings and make that tradeoff visible rather than promising every feature on
every home PC.

## Camera compatibility test matrix

Compatibility results should include the camera model, firmware, source profile,
codec, authentication mode, host hardware, Frigate/FFmpeg build, browser, and the
date tested. A manufacturer can have both working and incompatible models; do
not extrapolate one successful test to its whole product range. Credentials and
private stream URLs must be redacted from shared test records.

| Area | Cases to exercise | First-release acceptance evidence |
| --- | --- | --- |
| Transport | RTSP over TCP baseline; RTSPS where supported; disconnect and reconnect. UDP is separately tested if offered. | Connection behavior, timeout/recovery results, and a documented certificate policy for encrypted sources; no silent bypass marketed as verified TLS. |
| Authentication | Camera-supported Basic/Digest challenges, missing/wrong credentials, password changes, and URL-escaped special characters. | Accepted/rejected cases are accurate, credential failures are understandable, and diagnostics contain no passwords. Proprietary token/cloud authentication requires a separate adapter. |
| Main video | H.264 baseline with declared resolutions/frame rates; H.265 optional by tested configuration. | Playable recorded segments and live output in declared household browsers. H.265 limitations or required conversion and its hardware cost are disclosed. |
| Detection source | Main/sub streams, a shared single source, matching aspect ratio, configured resolution/FPS, and source changes. | Correct source-role mapping, measured decoder/detector load, and usable detection quality. A single-stream camera remains eligible if capacity and quality are acceptable. |
| Audio | No audio, AAC, and supported G.711/other input conversions where audio is enabled. | Video remains stable without an audio track; enabled recording/live audio is usable. Audio detection/transcription is tested separately and stays optional. |
| Reliability | Camera power loss, network interruption, changed address/credentials, recorder restart, and optional AI/broker failure. | Recovery is observed, recording gaps are visible, and an application does not report healthy current video from stale telemetry alone. |
| Storage | More than one full retention window, disk pressure, cleanup lag, and exported clips. | Recordings/object media/snapshots follow configured retention within cleanup/segment boundaries; other stored artifacts are accounted for separately. |
| Home viewing | Supported browsers, main/sub selection, slower clients, and private remote access when offered. | Actual playback works in the declared combinations. Local container health is not substituted for browser/playback testing. |

Inventory-generation and installed-schema tests already help catch configuration
errors, but they do not certify stream interoperability. First-release results
must come from the matrix above, including independent camera implementations;
there is no promise that every streaming camera is supported.

Cloud-only cameras without a usable local stream, unreliable battery wake modes,
PTZ, two-way talk, ONVIF discovery, and non-RTSP adapters are outside the baseline.
They can be considered later as optional, explicitly tested home integrations.

## Deliberate exclusions

This release does not target shops, offices, commercial installations, managed
camera fleets, or multiple customer tenants. It does not promise enterprise SSO,
central policy administration, immutable external audit storage, compliance
certification, high-availability recording, or a service-level agreement.
Optional household accounts do not imply any of those enterprise capabilities.

The active-learning workflow may later help a homeowner improve relevant local
classes using reviewed private examples. It remains optional, has separate data
retention, and requires held-out evaluation and explicit promotion gates. An
initial annotation count alone is not evidence that a production detector is
ready or that an AI interpretation is correct.
