This starter accepts RTSP/RTSPS cameras without vendor-specific paths, IP ranges,
or credentials. It does not discover cameras or deploy changes to an existing NVR.
The default CPU detector is for pilot testing; size and configure accelerated
decoding/detection for the target hardware before running a production workload.

Use Python 3.11+ with `requirements-bootstrap.txt`, and Docker Compose 2.30+.
Copy `config/cameras.example.yml` to a private inventory, set its source URLs and
the actual detection resolution, and export the `FRIGATE_*` variables it references.
Usernames/passwords in URLs must use placeholders. Percent-encode credential
values for use inside RTSP URLs, especially `@`, `:`, `#`, `/`, and `%`.

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-bootstrap.txt
cp config/cameras.example.yml config/cameras.yml
# Edit private inventory and export its camera credential variables first.
python3 scripts/bootstrap.py config/cameras.yml --require-secrets
docker compose config --quiet
docker compose up -d --build
```

Bootstrap prints no credentials and starts no services. It generates:

- `config/frigate.yml`: Frigate 0.18 YAML with placeholders, shared go2rtc streams,
  configurable per-camera detection dimensions/FPS, and two-day default retention.
- `config/camera-aliases.json`: IDs, names, and aliases for the context service;
  generated metadata includes no camera source URLs.
- `config/ai.env`: nonsecret public-model tag and gateway allowlist, derived from
  the same inventory setting as Frigate's generated AI providers.
- `secrets/camera-secrets.env`: actual secret values, read using Compose's raw
  env-file mode so dollar signs and quotes are not interpreted.
- `secrets/context_api_key`: a random local API key; pass its path only to the
  authorized context container. Bootstrap replacement preserves existing keys.
- `mqtt/config/passwords`: a salted Mosquitto PBKDF2-SHA512 hash, never a plaintext
  password. The corresponding random password stays in the private environment file.

Without `--require-secrets`, missing camera credentials are listed and left empty;
fill them before starting. Re-running refuses to overwrite any generated file.
`--replace` first copies all old generated files into a private timestamped
`backups/` directory, then replaces individual files atomically. It preserves
existing camera values unless explicitly supplied in the process environment,
and preserves MQTT/context keys. This backs up generated configuration and keys,
not footage or the live Frigate database. Stop services before regenerating if
you need a consistent operational cutover; generation is not a live rollout.

The default hardware selection is `--hardware cpu` and needs no downloaded custom
detector file. For optional Qwen or desktop NVIDIA, follow [MODELS.md](docs/MODELS.md).
Enable AI in the inventory before starting its profile; `setup_models.py` prints a
plan by default and downloads a public model only when called with `--pull`.

Keep the generated `secrets/` directory private. On POSIX its mode is 0700; the
API key file is readable inside an explicitly authorized container mount, while
the host directory blocks other users. Windows/NTFS requires equivalent host
ACLs; POSIX permission bits alone do not establish that protection there. The
broker's hash and the nonsecret camera metadata are readable by their nonroot
containers. Never publish generated secrets, private inventories, databases,
or backup archives; `.gitignore` is an aid, not a review of tracked history.

Omitting `detect_url` uses one shared source for recording and detection. Supply
a lower-resolution `detect_url` when available to reduce decode work. Audio
analysis is opt-in and requires an audio track in the detection source. Recording
audio is a separate opt-in and converts to AAC. Main video is copied without
re-encoding. Smaller detection frames can reduce distant-object/face/plate detail.

MQTT is optional and authenticated. Set `mqtt.enabled: true` in inventory,
regenerate, then use `docker compose --profile mqtt up -d`. No anonymous access
or host listener is configured. Home Assistant must connect to this same broker
through a deliberately configured private network path; this starter does not
complete that integration. The broker image's fresh data volume is owned by UID
1883. Frigate settings are generated and mounted read-only; use inventory changes
and regeneration rather than editing them in the Frigate UI.

Frigate's UI binds to localhost:18971 by default to avoid an existing NVR on 8971.
Port 5000 stays unpublished. Containers on the shared Docker network can access
Frigate's unauthenticated internal API; only trusted services should join that
network. Store generated database state on the named `frigate_config` volume and
select `FRIGATE_MEDIA_PATH` explicitly before production. Avoid `docker compose
down -v`, which deletes database/broker volumes. Exported clips do not expire
under recording retention and need a separate lifecycle policy.

Run generator tests with `python3 -m unittest discover -s tests -p 'test_bootstrap.py'`.
The tests validate output structure and safeguards; they do not claim camera
connectivity, detector throughput, codec compatibility, or production sizing.

Primary references: [Frigate restreaming](https://docs.frigate.video/configuration/restream/),
[recording retention](https://docs.frigate.video/configuration/record/),
[Docker env files](https://docs.docker.com/reference/compose-file/services/#env_file),
[Mosquitto authentication](https://mosquitto.org/documentation/authentication-methods/),
[Mosquitto password format](https://github.com/eclipse-mosquitto/mosquitto/blob/v2.0.22/apps/mosquitto_passwd/mosquitto_passwd.c).
