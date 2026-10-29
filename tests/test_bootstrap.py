"""Behavior tests for generation safeguards, portable sources, and auth output."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

BOOTSTRAP = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap.py"
spec = importlib.util.spec_from_file_location("bootstrap", BOOTSTRAP)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.inventory = self.root / "cameras.yml"
        self.output = self.root / "generated"
        self.document = {
            "version": 1,
            "cameras": [{"id": "warehouse", "name": "Receiving dock", "aliases": ["dock"],
                         "record_url": "rtsps://{FRIGATE_DOCK_USER}:{FRIGATE_DOCK_PASSWORD}@video.example.invalid/main",
                         "detect_url": "rtsp://video.example.invalid/low", "audio": True}],
        }
        self.write_inventory()

    def tearDown(self):
        self.temporary.cleanup()

    def write_inventory(self):
        self.inventory.write_text(yaml.safe_dump(self.document), encoding="utf-8")

    def generate(self, **kwargs):
        return bootstrap.generate(self.inventory, self.output, **kwargs)

    def test_dual_streams_friendly_aliases_and_retention_are_generated(self):
        with patch.dict(os.environ, {"FRIGATE_DOCK_USER": "pilot", "FRIGATE_DOCK_PASSWORD": "p%40ss"}, clear=True):
            report = self.generate(require_secrets=True)
        config = yaml.safe_load((self.output / "config/frigate.yml").read_text())
        inputs = config["cameras"]["warehouse"]["ffmpeg"]["inputs"]
        self.assertEqual([item["roles"] for item in inputs], [["record"], ["detect", "audio"]])
        self.assertTrue(inputs[0]["path"].startswith("rtsp://127.0.0.1:8554/"))
        self.assertEqual(config["record"]["alerts"]["retain"]["days"], 2)
        self.assertEqual(config["record"]["detections"]["retain"]["days"], 2)
        self.assertEqual(config["snapshots"]["retain"]["default"], 2)
        self.assertFalse(config["mqtt"]["enabled"])
        self.assertNotIn("p%40ss", (self.output / "config/frigate.yml").read_text())
        aliases = json.loads((self.output / "config/camera-aliases.json").read_text())
        self.assertEqual(aliases["cameras"], [{"id": "warehouse", "name": "Receiving dock", "aliases": ["dock"]}])
        self.assertFalse(report["missing_secrets"])

    def test_one_source_shares_connection_and_raw_env_preserves_dollars(self):
        self.document["cameras"][0].pop("detect_url")
        self.write_inventory()
        with patch.dict(os.environ, {"FRIGATE_DOCK_PASSWORD": "literal$cost=1#fragment"}, clear=True):
            self.generate()
        config = yaml.safe_load((self.output / "config/frigate.yml").read_text())
        self.assertEqual(len(config["go2rtc"]["streams"]), 1)
        self.assertEqual(config["cameras"]["warehouse"]["ffmpeg"]["inputs"][0]["roles"], ["record", "detect", "audio"])
        self.assertIn("FRIGATE_DOCK_PASSWORD=literal$cost=1#fragment\n", (self.output / "secrets/camera-secrets.env").read_text())

    def test_cpu_pretrained_default_enables_detection_without_ai_or_private_model(self):
        self.generate()
        config = yaml.safe_load((self.output / "config/frigate.yml").read_text())
        self.assertEqual(config["detectors"], {"cpu": {"type": "cpu", "num_threads": 3}})
        self.assertTrue(config["detect"]["enabled"])
        self.assertEqual(config["objects"]["track"], ["person", "car", "dog", "cat"])
        self.assertEqual(config["cameras"]["warehouse"]["friendly_name"], "Receiving dock")
        self.assertNotIn("genai", config)
        self.assertNotIn("model", config)
        self.assertNotIn("ffmpeg", config)

    def test_optional_ai_uses_same_official_model_in_config_and_gateway_allowlist(self):
        self.document["ai"] = {"enabled": True, "model": "qwen3-vl:2b-instruct"}
        self.write_inventory()
        report = self.generate()
        config = yaml.safe_load((self.output / "config/frigate.yml").read_text())
        self.assertEqual(config["genai"]["local_chat"]["roles"], ["chat"])
        self.assertEqual(config["genai"]["local_descriptions"]["roles"], ["descriptions"])
        self.assertEqual({provider["model"] for provider in config["genai"].values()}, {"qwen3-vl:2b-instruct"})
        ai_env = (self.output / "config/ai.env").read_text()
        self.assertIn("OLLAMA_ALLOWED_MODELS=qwen3-vl:2b-instruct", ai_env)
        self.assertIn("OLLAMA_MODEL=qwen3-vl:2b-instruct", ai_env)
        self.assertTrue(config["objects"]["genai"]["use_snapshot"])
        self.assertTrue(report["ai_enabled"])
        self.assertEqual(report["ai_model"], "qwen3-vl:2b-instruct")

    def test_nvidia_option_selects_supported_onnx_and_decode_without_private_weights(self):
        report = self.generate(hardware="nvidia")
        config = yaml.safe_load((self.output / "config/frigate.yml").read_text())
        self.assertEqual(config["detectors"], {"onnx": {"type": "onnx", "device": "0"}})
        self.assertEqual(config["model"]["path"], "/models/yolov9-t-320.onnx")
        self.assertEqual(config["model"]["model_type"], "yolo-generic")
        self.assertEqual(config["ffmpeg"]["hwaccel_args"], "preset-nvidia")
        self.assertEqual(report["hardware"], "nvidia")

    def test_ai_validation_rejects_untrusted_models_and_nonboolean_enable(self):
        for ai in ({"enabled": "yes"}, {"enabled": True, "model": "private/checkpoint"},
                   {"enabled": True, "model": "https://example.invalid/model"}, {"extra": True}):
            with self.subTest(ai=ai):
                self.document["ai"] = ai
                self.write_inventory()
                with self.assertRaises(bootstrap.InventoryError):
                    self.generate()
        self.document.pop("ai", None)
        self.write_inventory()
        with self.assertRaisesRegex(bootstrap.InventoryError, "Hardware"):
            self.generate(hardware="unknown")

    def test_replace_backs_up_all_existing_outputs_and_preserves_auth(self):
        with patch.dict(os.environ, {}, clear=True):
            self.generate()
            originals = {name: (self.output / name).read_bytes() for name in bootstrap.OUTPUTS}
            with self.assertRaises(bootstrap.InventoryError):
                self.generate()
            self.assertEqual(originals, {name: (self.output / name).read_bytes() for name in bootstrap.OUTPUTS})
            self.document["retention_days"] = 1
            self.write_inventory()
            report = self.generate(replace=True)
        backup = Path(report["backup"])
        self.assertEqual(originals, {name: (backup / name).read_bytes() for name in bootstrap.OUTPUTS})
        self.assertEqual(originals["secrets/context_api_key"], (self.output / "secrets/context_api_key").read_bytes())
        self.assertEqual(originals["secrets/camera-secrets.env"], (self.output / "secrets/camera-secrets.env").read_bytes())
        self.assertEqual(yaml.safe_load((self.output / "config/frigate.yml").read_text())["record"]["continuous"]["days"], 1)

    def test_missing_secrets_failure_writes_no_generated_files(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(bootstrap.InventoryError):
                self.generate(require_secrets=True)
        self.assertFalse(any((self.output / name).exists() for name in bootstrap.OUTPUTS))

    def test_mosquitto_hash_matches_standard_pbkdf2_format(self):
        line = bootstrap.mosquitto_hash("private-test-password").strip()
        user, formatted = line.split(":", 1)
        _, algorithm, iterations, salt, digest = formatted.split("$")
        self.assertEqual((user, algorithm), ("frigate", "7"))
        self.assertEqual(len(base64.b64decode(salt)), 12)
        expected = hashlib.pbkdf2_hmac("sha512", b"private-test-password", base64.b64decode(salt), int(iterations), 64)
        self.assertEqual(expected, base64.b64decode(digest))

    def test_literal_credentials_duplicate_ids_and_stream_collisions_are_rejected(self):
        for mode in ("literal", "duplicate", "stream_collision"):
            with self.subTest(mode=mode):
                original = json.loads(json.dumps(self.document))
                if mode == "literal":
                    self.document["cameras"][0]["record_url"] = "rtsp://private:secret@video.example.invalid/main"
                else:
                    camera = dict(self.document["cameras"][0])
                    camera["id"] = "warehouse" if mode == "duplicate" else "warehouse_sub"
                    self.document["cameras"].append(camera)
                self.write_inventory()
                with self.assertRaises(bootstrap.InventoryError) as caught:
                    self.generate()
                self.assertNotIn("secret@", str(caught.exception))
                self.document = original

    def test_yaml_duplicate_keys_and_unsafe_constructors_are_rejected(self):
        for text in ("version: 1\nversion: 1\ncameras: []\n", "!!python/object/apply:os.system ['echo unsafe']\n"):
            self.inventory.write_text(text, encoding="utf-8")
            with self.assertRaises(bootstrap.InventoryError):
                self.generate()

    @unittest.skipIf(os.name == "nt", "Creating symbolic links requires Windows privileges")
    def test_symlink_outputs_refused_even_with_replace(self):
        self.output.mkdir()
        external = self.root / "outside"
        external.mkdir()
        (self.output / "config").symlink_to(external, target_is_directory=True)
        with self.assertRaises(bootstrap.InventoryError):
            self.generate(replace=True)
        self.assertEqual(list(external.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
