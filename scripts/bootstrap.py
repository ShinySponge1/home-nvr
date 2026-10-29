#!/usr/bin/env python3
"""Generate a vendor-neutral Frigate pilot without starting services.

Existing output is never overwritten unless --replace is given. Replacement
first saves a complete private copy of existing generated files, then performs
per-file atomic replacements. MQTT/API keys remain stable across regeneration.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import tempfile
from urllib.parse import urlsplit

try:
    import yaml
except ImportError as exc:
    raise SystemExit("Install requirements-bootstrap.txt before running bootstrap.") from exc

IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
PLACEHOLDER = re.compile(r"\{(FRIGATE_[A-Z0-9_]+)\}")
DEFAULT_VISION_MODEL = "qwen3-vl:4b-instruct"
SUPPORTED_VISION_MODELS = ("qwen3-vl:2b-instruct", DEFAULT_VISION_MODEL, "qwen3-vl:8b-instruct")
OUTPUTS = (
    "config/frigate.yml", "config/camera-aliases.json",
    "secrets/camera-secrets.env", "secrets/camera-secrets.env.example",
    "secrets/context_api_key", "config/ai.env", "mqtt/config/passwords",
)


class InventoryError(ValueError):
    """An actionable validation error that never includes source URLs."""


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise InventoryError("Inventory keys must be unique strings.")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def mapping(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise InventoryError(f"{label} must be a mapping with supported keys: {', '.join(allowed)}.")
    return value


def boolean(value, label):
    if not isinstance(value, bool):
        raise InventoryError(f"{label} must be true or false.")
    return value


def number(value, low, high, label, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise InventoryError(f"{label} must be a finite number.")
    if not low <= value <= high or (integer and not isinstance(value, int)):
        raise InventoryError(f"{label} must be {'an integer' if integer else 'a number'} between {low} and {high}.")
    return value


def source_url(value, label):
    if not isinstance(value, str) or len(value) > 8192 or any(ord(c) < 32 for c in value):
        raise InventoryError(f"{label} must be a single RTSP URL.")
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in {"rtsp", "rtsps"} and bool(parsed.hostname)
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise InventoryError(f"{label} must be an absolute rtsp:// or rtsps:// URL.")
    remainder = PLACEHOLDER.sub("placeholder", value)
    if "{" in remainder or "}" in remainder:
        raise InventoryError(f"{label} contains an unsupported placeholder; use {{FRIGATE_NAME}}.")
    # Never persist literal credentials in an inventory or generated YAML.
    for part in (parsed.username, parsed.password):
        if part and not PLACEHOLDER.fullmatch(part):
            raise InventoryError(f"{label} credentials must be {{FRIGATE_*}} placeholders.")
    return value


def load_inventory(path):
    raw = Path(path).read_bytes()
    if len(raw) > 1024 * 1024:
        raise InventoryError("Inventory exceeds the 1 MiB limit.")
    try:
        data = yaml.load(raw, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise InventoryError("Inventory is invalid YAML; check syntax without exposing credentials.") from exc
    mapping(data, ("version", "retention_days", "mqtt", "ai", "cameras"), "Inventory")
    if type(data.get("version")) is not int or data.get("version") != 1:
        raise InventoryError("Inventory version must be 1.")
    days = number(data.get("retention_days", 2), 0, 3650, "retention_days")
    mqtt = mapping(data.get("mqtt", {}), ("enabled",), "mqtt")
    mqtt_enabled = boolean(mqtt.get("enabled", False), "mqtt.enabled")
    ai = mapping(data.get("ai", {}), ("enabled", "model"), "ai")
    ai_enabled = boolean(ai.get("enabled", False), "ai.enabled")
    ai_model = ai.get("model", DEFAULT_VISION_MODEL)
    if ai_model not in SUPPORTED_VISION_MODELS:
        raise InventoryError("ai.model must be one of the documented official Qwen3-VL instruct tags.")
    cameras = data.get("cameras")
    if not isinstance(cameras, list) or not 1 <= len(cameras) <= 128:
        raise InventoryError("cameras must contain between 1 and 128 camera mappings.")
    seen_ids, seen_streams, result = set(), set(), []
    for index, item in enumerate(cameras):
        label = f"Camera {index + 1}"
        mapping(item, ("id", "name", "aliases", "record_url", "detect_url", "detect", "audio", "record_audio"), label)
        camera_id = item.get("id")
        if not isinstance(camera_id, str) or not IDENTIFIER.fullmatch(camera_id) or camera_id in seen_ids:
            raise InventoryError(f"{label} needs a unique lowercase id using letters, numbers, and underscores.")
        seen_ids.add(camera_id)
        name = item.get("name", camera_id.replace("_", " ").title())
        aliases = item.get("aliases", [])
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise InventoryError(f"{label} name must be a nonempty string of at most 120 characters.")
        if not isinstance(aliases, list) or len(aliases) > 20 or any(not isinstance(a, str) or not a.strip() or len(a) > 120 for a in aliases):
            raise InventoryError(f"{label} aliases must be a list of at most 20 short nonempty strings.")
        record_url = source_url(item.get("record_url"), f"{label} record_url")
        detect_url = source_url(item["detect_url"], f"{label} detect_url") if item.get("detect_url") else None
        if detect_url == record_url:
            detect_url = None
        detect = mapping(item.get("detect", {}), ("width", "height", "fps"), f"{label} detect")
        detect = {
            "width": number(detect.get("width", 640), 160, 8192, f"{label} detect.width", True),
            "height": number(detect.get("height", 360), 120, 8192, f"{label} detect.height", True),
            "fps": number(detect.get("fps", 5), 1, 30, f"{label} detect.fps"),
        }
        streams = {camera_id, f"{camera_id}_sub"} if detect_url else {camera_id}
        if seen_streams & streams:
            raise InventoryError(f"{label} id collides with another camera's generated substream name.")
        seen_streams |= streams
        result.append({"id": camera_id, "name": name.strip(), "aliases": list(dict.fromkeys(a.strip() for a in aliases)),
                       "record_url": record_url, "detect_url": detect_url, "detect": detect,
                       "audio": boolean(item.get("audio", False), f"{label} audio"),
                       "record_audio": boolean(item.get("record_audio", False), f"{label} record_audio")})
    return {"version": 1, "retention_days": days, "mqtt_enabled": mqtt_enabled,
            "ai_enabled": ai_enabled, "ai_model": ai_model, "cameras": result}


def render_config(inventory, hardware="cpu"):
    if hardware not in ("cpu", "nvidia"):
        raise InventoryError("Hardware must be cpu or nvidia.")
    days = inventory["retention_days"]
    mqtt = {"enabled": inventory["mqtt_enabled"]}
    if mqtt["enabled"]:
        mqtt.update(host="mosquitto", port=1883, topic_prefix="frigate", client_id="frigate", user="frigate",
                    password="{FRIGATE_MQTT_PASSWORD}")
    config = {"version": "0.18-0", "mqtt": mqtt, "go2rtc": {"streams": {}},
              "record": {"enabled": True, "expire_interval": 5, "continuous": {"days": days}, "motion": {"days": 0},
                         "alerts": {"retain": {"days": days, "mode": "motion"}},
                         "detections": {"retain": {"days": days, "mode": "motion"}}},
              "snapshots": {"enabled": True, "retain": {"default": days}},
              "detect": {"enabled": True}, "objects": {"track": ["person", "car", "dog", "cat"]},
              "logger": {"default": "info"}, "cameras": {}}
    if hardware == "nvidia":
        config["detectors"] = {"onnx": {"type": "onnx", "device": "0"}}
        config["model"] = {"model_type": "yolo-generic", "width": 320, "height": 320,
                           "input_tensor": "nchw", "input_pixel_format": "rgb", "input_dtype": "float",
                           "path": "/models/yolov9-t-320.onnx", "labelmap_path": "/labelmap/coco-80.txt"}
        config["ffmpeg"] = {"hwaccel_args": "preset-nvidia"}
    else:
        # This pretrained detector is bundled in Frigate; no private weights or
        # model download is required for the first CPU setup test.
        config["detectors"] = {"cpu": {"type": "cpu", "num_threads": 3}}
    if inventory.get("ai_enabled", False):
        model = inventory["ai_model"]
        config["objects"]["genai"] = {
            "enabled": True, "use_snapshot": True,
            "prompt": "Describe the visible {label} in this image concisely. State uncertainty. Do not infer identity, intent, vehicle year, or unreadable text.",
            "send_triggers": {"tracked_object_end": True},
        }
        config["genai"] = {
            "local_descriptions": {"provider": "ollama", "base_url": "http://ollama:11434", "model": model,
                                   "roles": ["descriptions"], "provider_options": {"keep_alive": "5m", "options": {"num_ctx": 8192, "num_predict": 512, "temperature": 0.2}}},
            "local_chat": {"provider": "ollama", "base_url": "http://chat-gateway:8081", "model": model,
                           "roles": ["chat"], "provider_options": {"keep_alive": "5m", "options": {"num_ctx": 8192, "num_predict": 1024, "temperature": 0.1}}},
        }
    for camera in inventory["cameras"]:
        camera_id = camera["id"]
        config["go2rtc"]["streams"][camera_id] = [camera["record_url"]]
        roles = ["record"] if camera["detect_url"] else ["record", "detect"]
        if camera["audio"] and not camera["detect_url"]:
            roles.append("audio")
        inputs = [{"path": f"rtsp://127.0.0.1:8554/{camera_id}", "input_args": "preset-rtsp-restream", "roles": roles}]
        live = {"Main": camera_id}
        if camera["detect_url"]:
            stream = f"{camera_id}_sub"
            config["go2rtc"]["streams"][stream] = [camera["detect_url"]]
            inputs.append({"path": f"rtsp://127.0.0.1:8554/{stream}", "input_args": "preset-rtsp-restream",
                           "roles": ["detect", "audio"] if camera["audio"] else ["detect"]})
            live["Sub"] = stream
        entry = {"friendly_name": camera["name"], "ffmpeg": {"output_args": {"record": "preset-record-generic-audio-aac" if camera["record_audio"] else "preset-record-generic"},
                            "inputs": inputs}, "detect": camera["detect"], "live": {"streams": live}}
        if camera["audio"]:
            entry["audio"] = {"enabled": True}
        config["cameras"][camera_id] = entry
    return config


def mosquitto_hash(password):
    # Mosquitto 2.0 $7$ format: PBKDF2-HMAC-SHA512, 12-byte salt, 64-byte hash.
    # Format verified against upstream src/password_mosq.c and mosquitto_passwd.c.
    salt = secrets.token_bytes(12)
    iterations = 210000
    digest = hashlib.pbkdf2_hmac("sha512", password.encode("utf-8"), salt, iterations, 64)
    return f"frigate:$7${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}\n"


def read_env(path):
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def verify_path(root, relative):
    path = root / relative
    current = path
    while current != root:
        if current.is_symlink():
            raise InventoryError(f"Refusing to write through a symbolic link: {relative}.")
        current = current.parent
    if path.exists() and not path.is_file():
        raise InventoryError(f"Generated output is not a regular file: {relative}.")
    return path


def generate(inventory_path, output, replace=False, require_secrets=False, hardware="cpu"):
    inventory = load_inventory(inventory_path)
    config = render_config(inventory, hardware)
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    targets = {relative: verify_path(root, relative) for relative in OUTPUTS}
    existing = [relative for relative, path in targets.items() if path.exists()]
    if existing and not replace:
        raise InventoryError("Generated files already exist; use --replace to back them up before replacement.")
    previous = read_env(targets["secrets/camera-secrets.env"])
    placeholders = sorted({key for camera in inventory["cameras"] for url in (camera["record_url"], camera["detect_url"]) if url for key in PLACEHOLDER.findall(url)})
    values = {name: os.environ.get(name, previous.get(name, "")) for name in placeholders}
    missing = [name for name, value in values.items() if not value]
    if require_secrets and missing:
        raise InventoryError("Required camera secrets are missing: " + ", ".join(missing))
    values["FRIGATE_MQTT_PASSWORD"] = previous.get("FRIGATE_MQTT_PASSWORD") or secrets.token_urlsafe(32)
    if any(any(c in value for c in "\r\n\x00") for value in values.values()):
        raise InventoryError("Secret environment values must not contain newline or NUL characters.")
    key_path = targets["secrets/context_api_key"]
    api_key = key_path.read_text(encoding="utf-8").strip() if key_path.exists() else secrets.token_urlsafe(32)
    if not 32 <= len(api_key) <= 512 or any(ord(c) < 33 for c in api_key):
        raise InventoryError("Existing context API key is invalid; repair it explicitly before replacing config.")
    aliases = {"cameras": [{key: camera[key] for key in ("id", "name", "aliases")} for camera in inventory["cameras"]]}
    payloads = {
        "config/frigate.yml": f"# Generated by scripts/bootstrap.py; {hardware} detector configuration.\n" + yaml.safe_dump(config, sort_keys=False),
        "config/camera-aliases.json": json.dumps(aliases, indent=2, ensure_ascii=False) + "\n",
        "secrets/camera-secrets.env": "# PRIVATE; Compose env_file format: raw. Do not commit.\n" + "".join(f"{key}={value}\n" for key, value in sorted(values.items())),
        "secrets/camera-secrets.env.example": "# Supply percent-encoded RTSP credentials through environment variables.\n" + "".join(f"{key}=\n" for key in placeholders),
        "secrets/context_api_key": api_key + "\n",
        "config/ai.env": ("# Generated from inventory ai.model; keep in sync by rerunning bootstrap.\n"
                          "OLLAMA_ALLOWED_MODELS=" + inventory["ai_model"] + "\n"
                          "OLLAMA_MODEL=" + inventory["ai_model"] + "\n"),
        "mqtt/config/passwords": mosquitto_hash(values["FRIGATE_MQTT_PASSWORD"]),
    }
    # Copy all old outputs before the first replacement. Failure here leaves them intact.
    backup = None
    if existing:
        backup_parent = root / "backups"
        if backup_parent.is_symlink():
            raise InventoryError("Refusing a symlink backup directory.")
        backup_parent.mkdir(mode=0o700, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
        backup = Path(tempfile.mkdtemp(prefix=stamp, dir=backup_parent))
        for relative in existing:
            destination = backup / relative
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            shutil.copy2(targets[relative], destination)
            destination.chmod(0o600)
    stage = Path(tempfile.mkdtemp(prefix=".bootstrap-", dir=root))
    try:
        for relative, text in payloads.items():
            staged = stage / relative
            staged.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            staged.write_text(text, encoding="utf-8", newline="\n")
            staged.chmod(0o600)
        for relative, path in targets.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            # Keep plaintext secret directory private on POSIX. Authorized secret
            # mounts need a readable file for a nonroot service inside Docker.
            if relative.startswith("secrets/"):
                path.parent.chmod(0o700)
            os.replace(stage / relative, path)
            path.chmod(0o644 if relative in {"secrets/context_api_key", "mqtt/config/passwords", "config/camera-aliases.json"} else 0o600)
    finally:
        shutil.rmtree(stage)
    return {"cameras": len(inventory["cameras"]), "missing_secrets": missing, "backup": str(backup) if backup else None,
            "mqtt_enabled": inventory["mqtt_enabled"], "ai_enabled": inventory["ai_enabled"],
            "ai_model": inventory["ai_model"], "hardware": hardware}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--replace", action="store_true", help="Back up existing generated files, then replace them.")
    parser.add_argument("--require-secrets", action="store_true", help="Refuse generation if camera credential environment values are missing.")
    parser.add_argument("--hardware", choices=("cpu", "nvidia"), default="cpu",
                        help="CPU setup default, or desktop NVIDIA ONNX plus hardware decode (requires compose.gpu.yaml and public ONNX model setup).")
    args = parser.parse_args(argv)
    try:
        report = generate(args.inventory, args.output, args.replace, args.require_secrets, args.hardware)
    except (InventoryError, OSError) as exc:
        parser.exit(2, f"Bootstrap failed: {exc}\n")
    print(f"Generated configuration for {report['cameras']} camera(s); no services were started.")
    if report["backup"]:
        print("Previous generated files backed up to: " + report["backup"])
    if report["missing_secrets"]:
        print("Set camera secrets before starting: " + ", ".join(report["missing_secrets"]))
    if report["mqtt_enabled"]:
        print("Start with docker compose --profile mqtt up -d; MQTT authentication is configured.")
    else:
        print("MQTT remains disabled; do not enable its profile without updating the inventory.")
    if report["ai_enabled"]:
        print("AI is configured but no model was downloaded. Follow docs/MODELS.md to pull the inventory's public Qwen model and start --profile ai.")
    if report["hardware"] == "nvidia":
        print("NVIDIA configuration requires compose.gpu.yaml and data/models/yolov9-t-320.onnx; follow docs/MODELS.md before starting Frigate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
