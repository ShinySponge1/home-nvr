import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Evidence, Server, handler_for
from test_evidence import Fake


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = "test-" + "x" * 40
        cls.server = Server(("127.0.0.1", 0), handler_for(Evidence(Fake()), cls.key))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(5)

    def call(self, path, data=None, authorized=True):
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer " + self.key
        request = Request(self.base + path, data=data, headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, dict(response.headers), response.read()
        except HTTPError as error:
            with error:
                return error.code, dict(error.headers), error.read()

    def test_health_is_public_but_camera_data_is_not(self):
        self.assertEqual(self.call("/healthz", authorized=False)[0], 200)
        status, _, body = self.call("/v1/cameras", authorized=False)
        self.assertEqual(status, 401)
        self.assertNotIn(self.key.encode(), body)

    def test_static_viewer_assets_are_available_without_camera_credentials(self):
        for route in ("/", "/app.js", "/style.css"):
            with self.subTest(route=route):
                status, _, body = self.call(route, authorized=False)
                self.assertEqual(status, 200)
                self.assertGreater(len(body), 100)
                self.assertNotIn(self.key.encode(), body)

    def test_authenticated_response_has_no_store_and_request_id(self):
        status, headers, body = self.call("/v1/cameras")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("request_id", json.loads(body))
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_json_errors_are_stable_and_do_not_leak_input(self):
        status, _, body = self.call("/v1/query", b'{"secret": "DO-NOT-ECHO"')
        self.assertEqual(status, 400)
        self.assertNotIn(b"DO-NOT-ECHO", body)

    def test_oversized_body_is_rejected(self):
        status, _, _ = self.call("/v1/query", b"x" * 17000)
        self.assertEqual(status, 413)

    def test_repeated_query_parameter_and_unsupported_route_fail(self):
        self.assertEqual(self.call("/v1/live?camera=camera_entry&camera=camera_garden")[0], 400)
        self.assertEqual(self.call("/v1/admin/delete")[0], 404)


if __name__ == "__main__":
    unittest.main()
