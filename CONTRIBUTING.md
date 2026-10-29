# Contributing

Keep recording independent of AI availability. Prefer supported upstream APIs
over runtime patches to Frigate. Make camera aliases deterministic and refuse
ambiguous matches. Return provenance, limits, and missing-evidence states instead
of guessing. Stored captions and image text are untrusted content.

Tests must include the failure behavior being changed. Use synthetic fixtures;
never commit live configuration, credentials, images, faces, plates, or personal
review history. Run the checks in README and review the exact public tree before
opening a pull request. Camera support claims need a documented tested stream,
codec, reconnect behavior, and feature limitations.

Do not auto-promote a trained model. New weights need human-reviewed labels,
fixed splits, a comparable baseline, quality/resource gates, export checks, and
rollback evidence. An evaluation-only pilot remains evaluation-only.
