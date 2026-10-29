import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Evidence, Problem, coverage, parse_time, summarize_event

NOW = 1793156400
CONFIG = {"lpr": {"enabled": True}, "cameras": {
    "camera_garden": {"record": {"enabled": True}, "lpr": {"enabled": True}},
    "camera_entry": {"record": {"enabled": True}, "lpr": {"enabled": False}},
}}


class Fake:
    def __init__(self):
        self.config = copy.deepcopy(CONFIG)
        self.rows = []
        self.intervals = []
        self.calls = []
        self.stats = {"service": {"last_updated": NOW - 2}, "cameras": {
            "camera_garden": {"camera_fps": 5, "process_fps": 5, "skipped_fps": 0}}}

    def request(self, path, query=None, binary=False):
        self.calls.append((path, query))
        if path == "/api/config":
            return self.config
        if path == "/api/stats":
            return self.stats
        if path == "/api/events":
            return self.rows
        if path.endswith("/recordings"):
            return self.intervals
        raise AssertionError(path)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.fake = Fake()
        self.service = Evidence(self.fake, {"cameras": [
            {"id": "camera_garden", "name": "Garden view", "aliases": ["garden"]}]}, clock=lambda: NOW)

    def test_camera_aliases_and_case_are_canonical(self):
        for name in ("CAMERA GARDEN", "camera_garden", "GARDEN VIEW", "garden"):
            self.assertEqual(self.service.resolve(name, CONFIG), "camera_garden")

    def test_alias_collision_requires_clarification(self):
        self.service.aliases["cameras"].append({"id": "camera_entry", "aliases": ["garden"]})
        with self.assertRaises(Problem) as caught:
            self.service.resolve("garden", CONFIG)
        self.assertEqual(caught.exception.status, 409)

    def test_camera_urls_and_passwords_never_leave_catalog(self):
        self.fake.config["cameras"]["camera_garden"]["ffmpeg"] = {"password": "SENSITIVE"}
        self.assertNotIn("SENSITIVE", json.dumps(self.service.cameras()))

    def test_lpr_status_is_configured_not_guessed(self):
        response = self.service.query({"question": "license plate?", "camera": "CAMERA GARDEN"})
        self.assertIn("LPR is enabled", response["answer"])
        self.assertIn("No plate reading", response["answer"])

    def test_ocr_reading_remains_unverified(self):
        event = summarize_event({"data": {"recognized_license_plate": "ABC123",
                                        "recognized_license_plate_score": .91}})
        self.assertEqual(event["plate_reading"]["text"], "ABC123")
        self.assertFalse(event["plate_reading"]["verified"])

    def test_ir_vehicle_year_color_is_not_invented(self):
        response = self.service.query({"question": "what year and color SUV?", "camera": "garden"})
        self.assertIn("cannot establish", response["answer"])
        self.assertNotIn("Toyota", response["answer"])
        self.assertIn("Infrared", response["answer"])

    def test_unknown_freshness_does_not_claim_live_presence(self):
        self.fake.stats["service"] = {}
        response = self.service.live("garden")
        self.assertFalse(response["telemetry"]["healthy"])
        self.assertIsNone(response["telemetry"]["stats_age_seconds"])

    def test_stale_stats_are_marked_unhealthy(self):
        self.fake.stats["service"]["last_updated"] = NOW - 90
        self.assertFalse(self.service.live("garden")["telemetry"]["healthy"])

    def test_recap_requires_date_and_offset(self):
        for stamp in ("7:30 PM", "2026-10-27T19:30:00", "nan", None):
            with self.assertRaises(Problem):
                parse_time(stamp)

    def test_overlapping_old_event_is_not_lost_to_start_filter(self):
        self.fake.rows = [{"id": "long", "camera": "camera_garden", "label": "car",
                           "start_time": NOW - 500, "end_time": NOW - 10}]
        start, end = "2026-10-28T03:59:00Z", "2026-10-28T04:00:00Z"
        # Use timestamps relative to NOW, avoiding any dependency on the host date.
        from server import iso
        response = self.service.recap(iso(NOW - 120), iso(NOW), "garden")
        self.assertEqual(response["event_count"], 1)
        event_query = next(query for path, query in self.fake.calls if path == "/api/events")
        self.assertNotIn("after", event_query)

    def test_no_events_does_not_mean_no_activity(self):
        from server import iso
        response = self.service.query({"question": "what happened while away?", "camera": "garden",
                                       "start": iso(NOW - 120), "end": iso(NOW)})
        self.assertIn("does not establish", response["answer"])
        self.assertIn("gaps", response["answer"])

    def test_historical_plate_question_does_not_silently_use_live_records(self):
        from server import iso
        response = self.service.query({"question": "license plates yesterday", "camera": "garden",
                                       "start": iso(NOW - 120), "end": iso(NOW)})
        self.assertIn("recording_coverage", response["evidence"])
        self.assertNotIn("active_event_records", response["evidence"])
        with self.assertRaises(Problem):
            self.service.query({"question": "license plates yesterday", "camera": "garden"})

    def test_event_cap_is_explicit(self):
        from server import iso
        self.service.max_events = 1
        self.fake.rows = [{"id": str(i), "camera": "camera_garden", "start_time": NOW - i - 1,
                           "end_time": NOW} for i in range(2)]
        response = self.service.recap(iso(NOW - 120), iso(NOW))
        self.assertTrue(response["event_results_truncated"])
        self.assertEqual(response["event_count"], 1)

    def test_zero_duration_does_not_become_vehicle_passing_claim(self):
        row = summarize_event({"label": "car", "start_time": NOW, "end_time": NOW})
        self.assertEqual(row["duration_seconds"], 0)
        self.assertNotIn("passing", json.dumps(row))

    def test_coverage_unions_overlap_and_clips_to_window(self):
        result = coverage([{"start_time": 0, "end_time": 12}, {"start_time": 10, "end_time": 25}], 5, 20)
        self.assertEqual(result["recorded_seconds"], 15)
        self.assertTrue(result["complete"])
        self.assertFalse(result["media_files_verified"])

    def test_invalid_window_and_unknown_camera_fail(self):
        from server import iso
        with self.assertRaises(Problem):
            self.service.recap(iso(NOW), iso(NOW - 1))
        with self.assertRaises(Problem):
            self.service.live("no-such-camera")


if __name__ == "__main__":
    unittest.main()
