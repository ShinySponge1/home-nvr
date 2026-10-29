"""Model setup remains an explicit public-model operation, not training/startup."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import setup_models


class ModelSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "compose.yaml").write_text("services: {}\n")
        (self.root / "config").mkdir()
        self.config = self.root / "config/frigate.yml"
        self.document = {"genai": {
            "local_descriptions": {"provider": "ollama", "model": "qwen3-vl:4b-instruct", "roles": ["descriptions"]},
            "local_chat": {"provider": "ollama", "model": "qwen3-vl:4b-instruct", "roles": ["chat"]},
        }}
        self.write_config()

    def write_config(self):
        self.config.write_text(yaml.safe_dump(self.document), encoding="utf-8")

    def test_default_plan_never_runs_docker_or_downloads(self):
        with patch.object(setup_models.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup_models.main(["--project-dir", str(self.root)]), 0)
        run.assert_not_called()

    def test_explicit_pull_uses_running_compose_service_and_official_default(self):
        with patch.object(setup_models.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup_models.main(["--project-dir", str(self.root), "--pull"]), 0)
        run.assert_called_once_with(
            ["docker", "compose", "--profile", "ai", "exec", "-T", "ollama", "ollama", "pull", "qwen3-vl:4b-instruct"],
            cwd=self.root.resolve(), check=True)

    def test_disabled_ai_and_untrusted_model_cannot_trigger_docker(self):
        for config in ({}, {"genai": {"local": {"provider": "ollama", "model": "private/checkpoint"}}}):
            with self.subTest(config=config):
                self.document = config
                self.write_config()
                with patch.object(setup_models.subprocess, "run") as run:
                    with self.assertRaises(setup_models.InventoryError):
                        setup_models.pull_command(self.root)
                run.assert_not_called()

    def test_conflicting_generated_provider_models_are_rejected(self):
        self.document["genai"]["local_chat"]["model"] = "qwen3-vl:2b-instruct"
        self.write_config()
        with self.assertRaises(setup_models.InventoryError):
            setup_models.pull_command(self.root)


if __name__ == "__main__":
    unittest.main()
