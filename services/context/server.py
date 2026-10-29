"""Read-only Frigate evidence service. No model-generated assertions or Docker socket."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import math
import os
from pathlib import Path
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

LOG = logging.getLogger("context")
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
MAX_BODY = 16_384
MAX_RESPONSE = 8 * 1024 * 1024


class Problem(Exception):
    def __init__(self, status: int, code: str, message: str, **details):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def finite(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError, OverflowError):
        return None


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("offset required")
        return stamp.timestamp()
    except (ValueError, TypeError, OverflowError):
        raise Problem(400, "explicit_time_required",
                      "Use a date and time with a UTC offset, such as 2026-10-27T19:30:00-05:00.") from None


def normalized(value):
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def read_secret(name, required=False):
    value = os.environ.get(name, "")
    filename = os.environ.get(name + "_FILE")
    if filename:
        value = Path(filename).read_text(encoding="utf-8").strip()
    if required and len(value) < 32:
        raise ValueError(name + " must contain at least 32 characters")
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Frigate:
    def __init__(self, base, token="", timeout=10):
        parsed = urlsplit(base)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("FRIGATE_URL must be a fixed HTTP(S) origin without credentials")
        self.base, self.token, self.timeout = base.rstrip("/"), token, timeout
        self.opener = build_opener(NoRedirect())

    def request(self, path, query=None, binary=False):
        if not path.startswith("/api/"):
            raise ValueError("Only Frigate API paths are permitted")
        url = self.base + path + ("?" + urlencode(query) if query else "")
        headers = {"Accept": "image/jpeg" if binary else "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            with self.opener.open(Request(url, headers=headers), timeout=self.timeout) as response:
                body = response.read(MAX_RESPONSE + 1)
                if len(body) > MAX_RESPONSE:
                    raise Problem(502, "upstream_response_too_large", "Frigate returned too much data.")
                if binary:
                    if not body.startswith(b"\xff\xd8"):
                        raise Problem(502, "invalid_snapshot", "Frigate did not return a JPEG image.")
                    return body
                return json.loads(body)
        except HTTPError as error:
            raise Problem(502, "frigate_http_error", "Frigate rejected the request.",
                          upstream_status=error.code) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise Problem(503, "frigate_unavailable", "Frigate could not be reached or returned invalid data.") from None


def safe_text(value, limit=200):
    return str(value)[:limit] if value is not None else None


def summarize_event(raw):
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    start, end = finite(raw.get("start_time")), finite(raw.get("end_time"))
    plate = data.get("recognized_license_plate")
    score = finite(data.get("recognized_license_plate_score"))
    confidence = finite(data.get("top_score", raw.get("top_score")))
    return {
        "id": safe_text(raw.get("id"), 160), "camera": safe_text(raw.get("camera")),
        "label": safe_text(raw.get("label")),
        "start_time": iso(start) if start is not None else None,
        "end_time": iso(end) if end is not None else None,
        "ongoing_record": raw.get("end_time") is None,
        "duration_seconds": round(max(0, end - start), 3) if start is not None and end is not None else None,
        "top_score": confidence, "sub_label": raw.get("sub_label"),
        "zones": [safe_text(z) for z in raw.get("zones", [])][:40],
        "plate_reading": {"text": safe_text(plate, 40), "score": score,
                          "source": "event.data.recognized_license_plate",
                          "verified": False} if plate else None,
        # Captions are retained as proposals, never promoted to observed facts.
        "description_proposal": {"text": safe_text(data.get("description"), 2000),
                                 "verified": False} if data.get("description") else None,
        "source": "/api/events",
    }


def coverage(intervals, start, end):
    spans = []
    for row in intervals:
        left, right = finite(row.get("start_time")), finite(row.get("end_time"))
        if left is not None and right is not None and right > start and left < end:
            spans.append((max(start, left), min(end, right)))
    merged = []
    for left, right in sorted(spans):
        if merged and left <= merged[-1][1] + 0.1:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    total = sum(right - left for left, right in merged)
    return {"recorded_seconds": round(total, 2), "requested_seconds": round(end - start, 2),
            "fraction": round(total / (end - start), 4),
            "complete": total >= end - start - 1,
            "source": "/api/{camera}/recordings", "media_files_verified": False}


class Evidence:
    def __init__(self, upstream, aliases=None, clock=time.time, max_events=500, max_window=172800):
        self.upstream, self.aliases, self.clock = upstream, aliases or {}, clock
        self.max_events, self.max_window = max_events, max_window

    def config(self):
        value = self.upstream.request("/api/config")
        if not isinstance(value, dict) or not isinstance(value.get("cameras"), dict):
            raise Problem(502, "invalid_configuration", "Frigate's camera configuration is unavailable.")
        return value

    def catalog(self, config):
        result = []
        metadata = {c["id"]: c for c in self.aliases.get("cameras", [])}
        for camera_id, camera in config["cameras"].items():
            if not SAFE_ID.fullmatch(camera_id):
                continue
            info = metadata.get(camera_id, {})
            result.append({"id": camera_id, "name": info.get("name") or camera_id,
                           "aliases": info.get("aliases", []),
                           "enabled": camera.get("enabled", True),
                           "lpr_enabled": bool(camera.get("lpr", config.get("lpr", {})).get("enabled", False)),
                           "recording_enabled": bool(camera.get("record", {}).get("enabled", False)),
                           "source": "/api/config"})
        return result

    def resolve(self, value, config):
        cameras = self.catalog(config)
        if value in config["cameras"] and SAFE_ID.fullmatch(value):
            return value
        matches = [c["id"] for c in cameras if normalized(value) in {
            normalized(c["id"]), normalized(c["name"]), *(normalized(a) for a in c["aliases"])}]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise Problem(409, "ambiguous_camera", "This camera name matches multiple cameras.", candidates=matches)
        raise Problem(404, "unknown_camera", "No configured camera matches this name.",
                      cameras=[c["id"] for c in cameras])

    def cameras(self):
        return {"as_of": iso(self.clock()), "cameras": self.catalog(self.config())}

    def live(self, camera):
        config = self.config()
        camera = self.resolve(camera, config)
        stats = self.upstream.request("/api/stats")
        state = stats.get("cameras", {}).get(camera, {})
        service_stamp = finite(stats.get("service", {}).get("last_updated"))
        camera_fps = finite(state.get("camera_fps"))
        age = max(0, self.clock() - service_stamp) if service_stamp is not None else None
        healthy = camera_fps is not None and camera_fps > 0 and age is not None and age <= 30
        events = self.upstream.request("/api/events", {
            "cameras": camera, "in_progress": 1, "limit": self.max_events + 1, "include_thumbnails": 0})
        if not isinstance(events, list):
            raise Problem(502, "invalid_events", "Frigate returned invalid event records.")
        selected = [summarize_event(e) for e in events[:self.max_events]
                    if e.get("camera") == camera and e.get("end_time") is None]
        return {"as_of": iso(self.clock()), "camera": camera,
                "camera_configuration": next(c for c in self.catalog(config) if c["id"] == camera),
                "telemetry": {"camera_fps": camera_fps, "process_fps": finite(state.get("process_fps")),
                              "skipped_fps": finite(state.get("skipped_fps")),
                              "stats_age_seconds": round(age, 2) if age is not None else None,
                              "healthy": healthy, "source": "/api/stats"},
                "active_event_records": selected, "truncated": len(events) > self.max_events,
                "snapshot_path": "/v1/snapshot?" + urlencode({"camera": camera}),
                "limitations": ["Active event records can lag the live tracker; they do not prove current object presence.",
                                "Structured detections do not establish color, make, model year, identity, or intent.",
                                "An enabled LPR feature does not guarantee a readable plate; OCR readings are unverified."]}

    def recap(self, start, end, camera=None):
        start, end = parse_time(start), parse_time(end)
        if end <= start or end - start > self.max_window or end > self.clock() + 5:
            raise Problem(400, "invalid_window", "Choose a completed window of at most 48 hours, with end after start.")
        config = self.config()
        cameras = [self.resolve(camera, config)] if camera else [c["id"] for c in self.catalog(config) if c["enabled"]]
        rows = self.upstream.request("/api/events", {
            "cameras": ",".join(cameras), "before": end, "limit": self.max_events + 1,
            "include_thumbnails": 0})
        if not isinstance(rows, list):
            raise Problem(502, "invalid_events", "Frigate returned invalid event records.")
        events = []
        for raw in rows[:self.max_events]:
            left, right = finite(raw.get("start_time")), finite(raw.get("end_time"))
            if (raw.get("camera") in cameras and left is not None and left <= end
                    and (right is None or right >= start)):
                events.append(summarize_event(raw))
        events.sort(key=lambda e: (e["start_time"], e["id"] or ""))
        recordings = {}
        for camera_id in cameras:
            try:
                intervals = self.upstream.request("/api/" + quote(camera_id, safe="") + "/recordings",
                                                  {"after": start, "before": end})
                if not isinstance(intervals, list):
                    raise Problem(502, "invalid_recordings", "Recording metadata is invalid.")
                recordings[camera_id] = coverage(intervals, start, end)
            except Problem as error:
                recordings[camera_id] = {"complete": False, "fraction": None, "error": error.code}
        truncated = len(rows) > self.max_events
        return {"as_of": iso(self.clock()), "start": iso(start), "end": iso(end),
                "cameras": cameras, "events": events, "event_count": len(events),
                "event_results_truncated": truncated,
                "recording_coverage": recordings,
                "limitations": ["No event records does not establish that nothing happened.",
                                "Recording coverage is database metadata, not a media-integrity check.",
                                "Detection duration alone does not establish movement or intent."] +
                                (["The event cap was reached; this recap is incomplete, including possible long-running events."] if truncated else [])}

    def query(self, request):
        question = request.get("question", "")
        if not isinstance(question, str) or len(question) > 2000 or not question.strip():
            raise Problem(400, "invalid_question", "Enter a question of at most 2,000 characters.")
        camera = request.get("camera")
        lower = question.casefold()
        historical = bool(re.search(r"\b(yesterday|earlier|historical|during|between)\b|last night", lower))
        if any(word in lower for word in ("away", "recap", "happened", "activity")) or request.get("scope") == "recap" or historical:
            if not request.get("start") or not request.get("end"):
                raise Problem(400, "explicit_time_required", "Choose the date, start, and end of the recap with a timezone.")
            evidence = self.recap(request["start"], request["end"], camera)
            answer = f"Found {evidence['event_count']} event records in the requested window."
            if evidence["event_results_truncated"]:
                answer += " Results are capped and incomplete."
            if any(not item["complete"] for item in evidence["recording_coverage"].values()):
                answer += " Recording coverage has gaps or could not be verified."
            answer += " This does not establish that no other activity occurred."
            return {"answer": answer, "evidence": evidence, "mode": "deterministic_evidence"}
        if not camera:
            raise Problem(400, "camera_required", "Choose a camera. Names and configured aliases are accepted.")
        evidence = self.live(camera)
        if any(word in lower for word in ("plate", "license", "licence", "lpr")):
            enabled = evidence["camera_configuration"]["lpr_enabled"]
            plates = [e["plate_reading"] for e in evidence["active_event_records"] if e["plate_reading"]]
            answer = "LPR is " + ("enabled" if enabled else "disabled") + " for this camera. "
            answer += ("Unverified OCR readings are listed in the evidence; check their source image before use."
                       if plates else "No plate reading is available in the returned active event records.")
        elif any(word in lower for word in ("color", "colour", "year", "make", "model", "type", "truck", "suv", "identify", "who")):
            answer = ("The structured evidence cannot establish vehicle color, make, model year, or a person's identity. "
                      "Review the live image. Infrared images do not establish true paint color.")
        else:
            answer = (f"Retrieved telemetry and {len(evidence['active_event_records'])} active event records for "
                      f"{evidence['camera']}. Event records can lag the live image.")
        if not evidence["telemetry"]["healthy"]:
            answer += " Fresh camera telemetry could not be confirmed."
        return {"answer": answer, "evidence": evidence, "mode": "deterministic_evidence"}


def handler_for(evidence, api_key, audit_path=None):
    slots = threading.BoundedSemaphore(8)
    audit_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "CameraContext/0.1"

        def log_message(self, fmt, *args):
            # Do not log query strings, prompts, tokens, upstream URLs, or plate values.
            pass

        def send(self, status, body, content_type="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, allow_nan=False).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.dispatch()

        def do_POST(self):
            self.dispatch()

        def dispatch(self):
            request_id, started = uuid.uuid4().hex, time.monotonic()
            route = urlsplit(self.path).path
            status, acquired = 500, False
            try:
                if self.command == "GET" and route == "/healthz":
                    status = 200
                    return self.send(status, {"status": "ok", "version": "0.1.0"})
                static = {"/": ("index.html", "text/html; charset=utf-8"),
                          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                          "/style.css": ("style.css", "text/css; charset=utf-8")}
                if self.command == "GET" and route in static:
                    filename, content_type = static[route]
                    status = 200
                    return self.send(status, (Path(__file__).parent / "static" / filename).read_bytes(), content_type)
                supplied = self.headers.get("Authorization", "")
                if not hmac.compare_digest(supplied.encode(), ("Bearer " + api_key).encode()):
                    raise Problem(401, "unauthorized", "A valid bearer API key is required.")
                acquired = slots.acquire(blocking=False)
                if not acquired:
                    raise Problem(429, "busy", "Too many requests; try again shortly.")
                query = parse_qs(urlsplit(self.path).query, max_num_fields=12)
                if any(len(value) != 1 for value in query.values()):
                    raise Problem(400, "duplicate_parameter", "Query parameters must not be repeated.")
                value = lambda key: query.get(key, [None])[0]
                if self.command == "GET" and route == "/v1/cameras":
                    result = evidence.cameras()
                elif self.command == "GET" and route == "/v1/live":
                    result = evidence.live(value("camera") or "")
                elif self.command == "GET" and route == "/v1/recap":
                    result = evidence.recap(value("start"), value("end"), value("camera"))
                elif self.command == "GET" and route == "/v1/snapshot":
                    camera = evidence.resolve(value("camera") or "", evidence.config())
                    body = evidence.upstream.request("/api/" + quote(camera, safe="") + "/latest.jpg",
                                                     {"h": 720}, binary=True)
                    status = 200
                    return self.send(status, body, "image/jpeg")
                elif self.command == "POST" and route == "/v1/query":
                    if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                        raise Problem(415, "json_required", "Content-Type must be application/json.")
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > MAX_BODY:
                        raise Problem(413, "request_too_large", "Request exceeds the body limit.")
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict):
                        raise Problem(400, "invalid_body", "The request must be a JSON object.")
                    result = evidence.query(body)
                else:
                    raise Problem(404, "not_found", "Unknown API route.")
                result["request_id"] = request_id
                status = 200
                self.send(status, result)
            except Problem as error:
                status = error.status
                self.send(status, {"error": {"code": error.code, "message": error.message, **error.details}, "request_id": request_id})
            except (ValueError, TypeError, KeyError, OverflowError):
                status = 400
                self.send(status, {"error": {"code": "invalid_request", "message": "Invalid request or response data."}, "request_id": request_id})
            except (BrokenPipeError, ConnectionResetError):
                status = 499
            except Exception:
                LOG.error("request_id=%s unexpected_internal_error", request_id)
                status = 500
                self.send(status, {"error": {"code": "internal_error", "message": "Request failed; see the request ID."}, "request_id": request_id})
            finally:
                if acquired:
                    slots.release()
                if route.startswith("/v1/"):
                    record = {"request_id": request_id, "route": route, "status": status,
                              "elapsed_ms": round((time.monotonic() - started) * 1000, 1), "at": iso(time.time())}
                    LOG.info(json.dumps(record))
                    if audit_path:
                        with audit_lock:
                            # Bounded local metadata log; no prompts, camera names, images, or OCR.
                            path = Path(audit_path)
                            path.parent.mkdir(parents=True, exist_ok=True)
                            if path.exists() and path.stat().st_size > 5 * 1024 * 1024:
                                path.replace(path.with_suffix(".previous.jsonl"))
                            with path.open("a", encoding="utf-8") as stream:
                                stream.write(json.dumps(record) + "\n")
                                os.chmod(path, 0o600)

    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(15)
        return connection, address


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate configuration without listening")
    args = parser.parse_args()
    key = read_secret("CONTEXT_API_KEY", required=True)
    aliases_file = os.environ.get("CAMERA_ALIASES_FILE")
    aliases = json.loads(Path(aliases_file).read_text(encoding="utf-8")) if aliases_file else {}
    upstream = Frigate(os.environ.get("FRIGATE_URL", "http://frigate:5000"), read_secret("FRIGATE_API_TOKEN"))
    evidence = Evidence(upstream, aliases)
    if args.check:
        print("Context configuration valid.")
        return
    server = Server((os.environ.get("CONTEXT_BIND", "127.0.0.1"), int(os.environ.get("CONTEXT_PORT", "8090"))),
                    handler_for(evidence, key, os.environ.get("CONTEXT_AUDIT_FILE")))
    LOG.info("Context service started; read-only evidence mode.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
