# Home NVR

A local-first camera platform for people monitoring their own home. Record
compatible camera streams, review detections, and ask for activity evidence
without turning model guesses into facts. Camera configuration is inventory-driven
and manufacturer-agnostic. This working alpha targets one home and one owner;
optional household sharing is future work. See the concrete first-release
[product scope and camera test matrix](docs/PRODUCT-SCOPE.md).

Home users are the audience for this release. Commercial sites, managed fleets,
multiple customer tenants, and high-availability recording are outside its scope.
Compatibility depends on the camera's streams, codecs, and authentication rather
than its brand; manufacturer-agnostic does not mean every camera works.

The evidence viewer and API provide camera aliases, configuration-backed LPR
status, telemetry freshness, event citations, explicit recap windows, recording
coverage, and honest missing-evidence responses. An optional Ollama gateway
bounds multi-turn context and normalizes camera tool arguments. Frigate remains
the recorder, detector, playback UI, and source of event metadata.

## Start a new home test installation

Use Linux or WSL with Docker Compose 2.30+ and Python 3.11+. This starts a separate
project and defaults to a CPU detector for setup/testing. Select and validate a
hardware detector before using it for multiple production cameras.

```bash
git clone https://github.com/ShinySponge1/home-nvr.git
cd home-nvr
python3 -m venv .venv
.venv/bin/pip install -r requirements-bootstrap.txt
cp .env.example .env
cp config/cameras.example.yml config/cameras.yml
# Edit camera IDs, names, source URLs, and optional detection streams.
# Set the FRIGATE_* credential environment variables named in your inventory.
.venv/bin/python scripts/bootstrap.py config/cameras.yml --require-secrets
docker compose config --quiet
docker compose up -d --build
```

Open the evidence viewer at `http://localhost:8090` and Frigate at
`https://localhost:18971`. Frigate bootstraps its own login; its development
certificate may require local browser trust configuration. Read the generated
`secrets/context_api_key` locally and enter it in the viewer. The viewer holds the
key only in memory and requires it again after a reload. Do not paste it in issue
reports. The public process-health endpoint is `/healthz`; camera APIs require
the bearer key. Bootstrap starts no containers and refuses replacement without
`--replace`, which backs up generated files first.

Frigate settings are inventory-managed and mounted read-only. Update the private
inventory and regenerate with a backup instead of editing configuration in its UI.

The inventory accepts RTSP/RTSPS URLs and an optional detection substream. Actual
stream and playback support must be tested with the chosen Frigate/FFmpeg build,
camera firmware, and household browsers. H.264 is the first-release baseline;
H.265, audio, and transport/authentication combinations have separate test cases
in the [compatibility matrix](docs/PRODUCT-SCOPE.md#camera-compatibility-test-matrix).
ONVIF discovery, vendor-specific authentication, RTMP adapters, PTZ, talkback,
cloud-only cameras, and battery-camera wake behavior are not included by default.

See [BOOTSTRAP.md](BOOTSTRAP.md) for inventory rules, credentials, MQTT, storage,
and replacement behavior. Private generated configuration, recordings, API keys,
backups, and model artifacts are excluded from Git.

## Evidence API

All data routes require `Authorization: Bearer <context_api_key>`.

| Route | Behavior |
| --- | --- |
| `GET /v1/cameras` | Configured IDs, friendly names, aliases, recording/LPR flags |
| `GET /v1/live?camera=...` | Telemetry plus active event records, with freshness limits |
| `GET /v1/snapshot?camera=...` | JPEG for visual review; capture freshness is not guaranteed |
| `GET /v1/recap?start=...&end=...&camera=...` | Events overlapping a dated, offset-aware window and recording coverage |
| `POST /v1/query` | Deterministic answers from those tools; no free-form visual inference |

Recaps accept at most 48 hours and return at most 500 event records. Reaching the
cap is explicitly marked incomplete. Active event records can lag the actual
tracker. Recording coverage measures metadata intervals, not file integrity.
Zero events does not prove that nothing happened. OCR readings and stored AI
captions remain unverified. Color, vehicle year, and identity are not invented.

## Optional local AI

Enable `ai.enabled: true` and choose the official Qwen tag in your private camera
inventory, then regenerate configuration with `--replace`. Start Ollama with
`docker compose --profile ai up -d ollama`, inspect the download plan using
`.venv/bin/python scripts/setup_models.py`, and add `--pull` to download the model
explicitly. Then run `docker compose --profile ai up -d --build`. Bootstrap keeps
the generated Frigate providers and gateway model allowlist aligned.

No private dataset is needed. See [pretrained models and optional NVIDIA setup](docs/MODELS.md)
and [gateway limits](services/gateway/README.md). Larger models and GPU decoding
are explicit hardware choices; the CPU baseline remains usable for setup/testing.

The gateway uses character/image bounds, not an exact tokenizer. It can still
reject an oversized latest turn. Grounding instructions reduce mistakes but do
not guarantee model truth. The deterministic evidence API is the authoritative
path for configuration flags and recorded metadata. No camera configuration or
model-deployment tools are exposed to chat.

## Engineering status

The starter includes regression tests, portable inventory generation, bounded
logs, local-only published ports, read-only companion containers, backup-first
replacement, and separate AI failures from the recording service. It is ready
for engineering evaluation in one home. Reliable setup, understandable storage
controls, recovery tests, compatible-camera evidence, and release security checks
remain acceptance work in [ROADMAP.md](docs/ROADMAP.md).
See [home quality-of-life priorities](docs/QOL-IDEAS.md) for concrete next features
and their acceptance checks.

The current companion viewer uses one bearer key, not separate household
accounts. Optional household accounts would need individual sessions and
server-enforced viewing permissions before being called supported. Enterprise
identity systems, tenant isolation, and recording failover are not first-release
requirements. Keep remote access private and deliberate; this starter does not
make an internet-facing home service safe automatically.

The default installation uses upstream pretrained models. Personal footage,
annotation history, custom checkpoints, credentials, and runtime databases are
neither required nor included. Custom model training is future optional work;
the [training roadmap](docs/TRAINING-ROADMAP.md) describes its evaluation gates.
Setup does not train a model or upload camera images anywhere.

Run checks with Python 3.11+:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s services/context/tests -v
.venv/bin/python -m unittest discover -s services/gateway -p 'test_*.py' -v
.venv/bin/python scripts/check_public_tree.py
```

Keep runtime data separate from source control. See [SECURITY.md](SECURITY.md),
[CONTRIBUTING.md](CONTRIBUTING.md), and [dependency notices](THIRD_PARTY.md).
