"""Reject private/generated artifacts in a source-only release tree.

Checks use generic path/address/token rules, never a homeowner's identifiers.
This complements, and does not replace, review of the exact Git diff/history.
"""
from ipaddress import IPv4Address, IPv4Network
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRECTORIES = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
FORBIDDEN_PARTS = {
    "secrets", "data", "backups", "runs", "datasets", "model_cache",
    "recordings", "clips", "snapshots", "exports", "weights",
    "sessions", ".sessions", ".codex", ".aws", ".ssh", "review-history",
}
FORBIDDEN_SUFFIX = {
    # No source release should contain personal camera media, including thumbnails.
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff", ".heic",
    ".mp4", ".m4v", ".webm", ".mkv", ".avi", ".mov", ".mpeg", ".mpg", ".ts", ".mts",
    ".wav", ".mp3", ".flac", ".ogg", ".aac", ".m4a", ".opus",
    # Weights, compiled engines, serialized checkpoints, and live databases.
    ".onnx", ".pt", ".pth", ".ckpt", ".safetensors", ".weights", ".engine", ".plan",
    ".tflite", ".pb", ".h5", ".hdf5", ".pkl", ".pickle", ".bin", ".gguf", ".ggml",
    ".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".sqlite-wal", ".sqlite-shm",
    ".sqlite3-wal", ".sqlite3-shm",
    # Archives/session exports can hide private trees or binary artifacts.
    ".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z", ".rar", ".zst",
    ".jsonl", ".ndjson", ".log", ".session",
    ".pem", ".key", ".crt", ".cer", ".p12", ".pfx", ".jks", ".kdbx",
}
FORBIDDEN_NAMES = {
    "passwords", "frigate.yml", "frigate.yaml", "config.yml", "config.yaml",
    "camera-aliases.json", "cameras.yml", "cameras.yaml", "ai.env",
    ".jwt_secret", ".runtime_state.json", ".runtime_state.json.lock",
    ".search_stats.json", "backup_config.yaml", "go2rtc_homekit.yml", ".exports", ".vacuum",
}
MAX_SOURCE_BYTES = 2 * 1024 * 1024
HOME_PATH = re.compile(
    r"(?:\b[A-Z]:[\\/](?:Users|Documents and Settings)[\\/]|(?<![\w:])/(?:home|Users)/|(?<![\w:])/mnt/[a-z]/Users/)"
    r"[^\s/\\<>\"'`]+(?:[\\/]|$)", re.IGNORECASE,
)
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# Numeric network definitions keep even generic private addresses out of source.
PRIVATE_NETWORKS = (IPv4Network((0x0A000000, 8)), IPv4Network((0xAC100000, 12)),
                    IPv4Network((0xC0A80000, 16)))
RTSP_USERINFO = re.compile(r"rtsps?://([^\s/\"'<>]+)@([^\s/\"'<>]+)", re.IGNORECASE)
PLACEHOLDER = re.compile(r"\{FRIGATE_[A-Za-z0-9_]+\}")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")
KNOWN_SECRET_TOKEN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{40,}|"
    r"sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"
)
EVENT_ID = re.compile(r"\b\d{10}\.\d{3,}-[a-z0-9]{4,}\b", re.IGNORECASE)
EMBEDDED_MEDIA = re.compile(r"data:(?:image|video|audio)/[^;,\s]+;base64,", re.IGNORECASE)
SESSION_NAME = re.compile(r"(?:^|[-_.])(?:sessions?|conversations?|chat[-_]history|review[-_]history)(?:[-_.]|$)", re.IGNORECASE)


def contains_private_address(content):
    for candidate in IPV4.findall(content):
        try:
            address = IPv4Address(candidate)
        except ValueError:
            continue
        if any(address in network for network in PRIVATE_NETWORKS):
            return True
    return False


def literal_rtsp_credentials(content, relative):
    is_test = "tests" in relative.parts or relative.name.startswith("test_")
    for userinfo, authority in RTSP_USERINFO.findall(content):
        parts = userinfo.split(":", 1)
        if all(part and PLACEHOLDER.fullmatch(part) for part in parts):
            continue
        hostname = authority.split(":", 1)[0].lower()
        # Only intentionally synthetic negative-test cases at reserved .invalid
        # hosts may exercise literal credentials. Product examples use placeholders.
        if not (is_test and hostname.endswith(".invalid")):
            return True
    return False


def check(root):
    root = Path(root).resolve()
    failures = []
    def fail(relative, reason):
        failures.append(relative.as_posix() + ": " + reason)

    def unreadable(_error):
        failures.append(".: unreadable directory")

    # Prune generated tooling/Git directories instead of traversing their objects.
    for directory, directories, filenames in os.walk(root, followlinks=False, onerror=unreadable):
        base = Path(directory)
        for name in sorted(list(directories)):
            path = base / name
            relative = path.relative_to(root)
            if name.casefold() in SKIP_DIRECTORIES:
                directories.remove(name)
            elif path.is_symlink():
                fail(relative, "symlink")
                directories.remove(name)
            elif name.casefold() in FORBIDDEN_PARTS:
                fail(relative, "generated/private directory")
                directories.remove(name)
        directories.sort()
        for name in sorted(filenames):
            path = base / name
            relative = path.relative_to(root)
            if name.casefold() == ".git":
                continue  # Worktree metadata is not part of a source export.
            if path.is_symlink():
                fail(relative, "symlink")
                continue
            lowered = name.casefold()
            if (lowered in FORBIDDEN_NAMES or path.suffix.casefold() in FORBIDDEN_SUFFIX
                    or (lowered.startswith(".env") and lowered != ".env.example")
                    or (path.suffix.casefold() in {".json", ".txt", ".html"} and SESSION_NAME.search(lowered))):
                fail(relative, "generated/private artifact")
                continue
            try:
                if path.stat().st_size > MAX_SOURCE_BYTES:
                    fail(relative, "oversized source file")
                    continue
                raw = path.read_bytes()
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                fail(relative, "non-UTF8/binary artifact")
                continue
            except OSError:
                fail(relative, "unreadable source file")
                continue
            if b"\x00" in raw:
                fail(relative, "NUL/binary artifact")
                continue
            if HOME_PATH.search(content) or contains_private_address(content):
                fail(relative, "private deployment path/address")
            if literal_rtsp_credentials(content, relative):
                fail(relative, "literal RTSP credential")
            if PRIVATE_KEY.search(content) or KNOWN_SECRET_TOKEN.search(content):
                fail(relative, "private key or credential token")
            if EVENT_ID.search(content):
                fail(relative, "private event identifier")
            if EMBEDDED_MEDIA.search(content):
                fail(relative, "embedded media artifact")
    return sorted(failures)


if __name__ == "__main__":
    issues = check(ROOT)
    if issues:
        print("Public tree check failed:\n" + "\n".join(issues))
        sys.exit(1)
    print("Source-only packaging check passed. Manual secret/license review is still required.")
