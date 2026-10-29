"""Optional compatibility check using an already running Frigate 0.18 container.

No deployment is created, downloaded, reconfigured, or restarted. Explicit detect
dimensions prevent network probing; camera sources are reserved .invalid names.
Run with FRIGATE_SCHEMA_CONTAINER set to the existing container name.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bootstrap_schema_test", ROOT / "scripts/bootstrap.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


@unittest.skipUnless(os.environ.get("FRIGATE_SCHEMA_CONTAINER"), "Set FRIGATE_SCHEMA_CONTAINER for the optional installed-schema check")
class FrigateSchemaTests(unittest.TestCase):
    def test_generated_config_is_valid_for_installed_frigate(self):
        inventory = bootstrap.load_inventory(ROOT / "config/cameras.example.yml")
        inventory["mqtt_enabled"] = True
        config = bootstrap.render_config(inventory)
        code = "import json,sys; from frigate.config import FrigateConfig; FrigateConfig.model_validate(json.load(sys.stdin)); print('schema-valid')"
        process = subprocess.run([
            "docker", "exec", "-i",
            "-e", "FRIGATE_ENTRANCE_USER=pilot",
            "-e", "FRIGATE_ENTRANCE_PASSWORD=synthetic-test-password",
            "-e", "FRIGATE_MQTT_PASSWORD=synthetic-test-password",
            os.environ["FRIGATE_SCHEMA_CONTAINER"], "python3", "-c", code,
        ], input=json.dumps(config), capture_output=True, text=True, timeout=60)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("schema-valid", process.stdout)


if __name__ == "__main__":
    unittest.main()
