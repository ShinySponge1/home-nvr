# Home quality-of-life priorities

These are proposed improvements, not a claim that they already ship. The first
release serves one home and its owner. Keep recording dependable, explain what
the system knows, and make routine setup and maintenance understandable.

| Priority | Improvement | A useful completion check |
| --- | --- | --- |
| First | Guided camera onboarding from a generic inventory | A new owner adds one compatible RTSP camera, tests main/sub streams and audio, and sees an actionable failure without exposing a password. |
| First | Plain camera health | A card distinguishes unreachable stream, stale evidence, disabled detection, recording gaps, and a healthy current connection. It never substitutes a model guess for status. |
| First | Understandable storage and retention | Show the configured retention, last cleanup, used/free space, estimated daily growth, and separately retained exports. Warn before a nearly full disk interrupts recording. |
| First | A recoverable first setup | Preview changes, back up configuration and credentials, and document a tested restore that preserves recordings. |
| First | Quiet, useful owner notifications | Notify on a sustained camera failure, storage risk, recording recovery, or explicitly chosen activity; combine repeats and respect quiet hours. |
| Next | Faster review of events | Timeline filters, useful keyboard controls, clear event times, and easy links from every summary to its source camera and interval. |
| Next | Sensible activity tuning | Help owners exclude busy sidewalks, parked vehicles, branches, and pets through zones and thresholds; show the consequences before applying a change. |
| Next | Honest local AI controls | One visible switch, a model/memory readiness check, explicit downloads, bounded latency, and a clear return to recording-only mode when AI is slow. |
| Next | Stream compatibility feedback | Explain H.264/H.265 and audio playback differences in household browsers, without implying that every camera brand or battery camera works. |
| Next | Private diagnostic bundle | Export version, redacted configuration shape, short error categories, and health counters. Exclude credentials, footage, plate text, faces, and event captions by default. |
| Later | Optional household sharing | Separate owner/viewer sessions and enforced camera permissions, with clear revocation and private remote-access guidance. |
| Later | Owner-approved accuracy improvement | An optional review flow for missed objects and false positives, with exact image/label provenance and no automatic approval or deployment. Pretrained defaults remain sufficient to start. |

Choose small features that can be checked on a real home setup. Prioritize camera
health, storage, recovery, and event review before expanding AI scope. Commercial
fleet management, tenants, enterprise identity, automatic cloud uploads, and
high-availability recording are outside this first home release.
