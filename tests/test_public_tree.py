"""Source-publication guards use synthetic data, never a household's identifiers."""
import importlib.util
from pathlib import Path, PureWindowsPath
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("public_tree", Path(__file__).resolve().parents[1] / "scripts/check_public_tree.py")
public_tree = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public_tree)


class PublicTreeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else value.encode())
        return path

    def failures(self):
        return public_tree.check(self.root)

    def test_clean_source_and_placeholder_inventory_pass(self):
        self.write("README.md", "A local source-only camera application.")
        self.write(".env.example", "CONTEXT_HTTP_PORT=8090\n")
        self.write("config/cameras.example.yml", "source: rtsp://{FRIGATE_USER}:{FRIGATE_PASSWORD}@camera.example.invalid/main")
        self.assertEqual(self.failures(), [])

    def test_generic_home_paths_and_all_rfc1918_ranges_are_rejected(self):
        # Construct negative-test strings without embedding private-looking
        # deployment identifiers into the public source tree itself.
        values = ["/" + "home" + "/householder/private.conf",
                  str(PureWindowsPath("C:/") / "Users" / "householder" / "private.conf"),
                  "/" + "Users" + "/householder/private.conf",
                  "/mnt/" + "c/" + "Users/" + "householder/private.conf",
                  "10." + "21.43.65", "172." + "23.4.5", "192." + "168.31.47"]
        for value in values:
            with self.subTest(value=value):
                self.write("notes.md", value)
                self.assertTrue(any("path/address" in failure for failure in self.failures()))

    def test_loopback_and_documentation_addresses_are_not_private_network_findings(self):
        self.write("README.md", "127.0.0.1 and 192.0.2.40 are local/documentation examples.")
        self.assertEqual(self.failures(), [])

    def test_media_weights_databases_and_archives_are_rejected_even_with_text_contents(self):
        names = ("frame.webp", "video.webm", "image.avif", "checkpoint.safetensors", "detector.engine",
                 "model.gguf", "history.sqlite3", "frigate.db-wal", "session-export.7z", "events.jsonl",
                 "host-private.pem", "credential-store.pfx")
        for name in names:
            self.write(name, "not needed in a source release")
        failures = self.failures()
        self.assertEqual(len(failures), len(names))
        self.assertTrue(all("generated/private artifact" in failure for failure in failures))

    def test_generated_configuration_and_session_exports_are_rejected(self):
        names = ("config/ai.env", "config/frigate.yml", "config/cameras.yml", "config/camera-aliases.json",
                 ".env.local", ".jwt_secret", "chat-session.json", "review-history.html")
        for name in names:
            self.write(name, "synthetic generated artifact")
        self.assertEqual(len(self.failures()), len(names))

    def test_private_directories_are_rejected_but_git_and_tool_caches_are_pruned(self):
        for directory in ("secrets", "datasets", "recordings", "sessions", "model_cache"):
            self.write(directory + "/placeholder.txt", "synthetic")
        self.write(".git/objects/pack/object", b"\x80\x00")
        self.write(".venv/lib/package.py", b"\x80\x00")
        self.write("__pycache__/module.pyc", b"\x80\x00")
        failures = self.failures()
        self.assertEqual(len(failures), 5)
        self.assertTrue(all("generated/private directory" in failure for failure in failures))

    def test_non_utf8_and_nul_files_report_failures_instead_of_crashing(self):
        self.write("odd.dat", b"\xff\xfe\x80")
        self.write("looks-text.txt", b"private\x00payload")
        failures = self.failures()
        self.assertTrue(any("non-UTF8/binary" in failure for failure in failures))
        self.assertTrue(any("NUL/binary" in failure for failure in failures))

    def test_literal_credentials_are_allowed_only_in_reserved_negative_test_fixtures(self):
        credentials = "rtsp" + "://synthetic:fixture@"
        self.write("tests/test_inventory.py", credentials + "camera.example.invalid/main")
        self.assertEqual(self.failures(), [])
        self.write("README.md", credentials + "camera.example.invalid/main")
        self.assertTrue(any(failure.startswith("README.md:") and "credential" in failure for failure in self.failures()))
        (self.root / "README.md").unlink()
        self.write("tests/test_inventory.py", credentials + "camera.example.com/main")
        self.assertTrue(any("credential" in failure for failure in self.failures()))

    def test_partial_literal_userinfo_is_not_mistaken_for_all_placeholders(self):
        self.write("config/example.yml", "rtsp" + "://literal-user:{FRIGATE_PASSWORD}@camera.example.invalid/main")
        self.assertTrue(any("literal RTSP credential" in failure for failure in self.failures()))

    def test_private_event_ids_and_known_credential_formats_are_rejected(self):
        self.write("notes.md", "1712345678" + ".123456-abcdef")
        self.assertTrue(any("event identifier" in failure for failure in self.failures()))
        self.write("notes.md", "gh" + "p_" + "A" * 36)
        self.assertTrue(any("credential token" in failure for failure in self.failures()))

    def test_media_embedded_in_html_is_not_a_source_only_escape_hatch(self):
        self.write("viewer.html", "<img src='data:" + "image/jpeg;base64," + "aW1hZ2U='>")
        self.assertTrue(any("embedded media artifact" in failure for failure in self.failures()))

    def test_symlink_does_not_expose_external_source(self):
        outside = self.root.parent / (self.root.name + "-external")
        outside.write_text("synthetic")
        try:
            try:
                (self.root / "linked.txt").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation unavailable")
            self.assertTrue(any("symlink" in failure for failure in self.failures()))
        finally:
            outside.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
