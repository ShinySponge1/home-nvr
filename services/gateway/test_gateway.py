"""Behavioral checks for the bounded gateway; no GPU or Ollama required."""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from gateway import (Aliases, Application, ClientError, Handler, MISSING_VISUAL,
                     RULES, Settings, ThreadingHTTPServer, canonicalize_tools,
                     prepare_chat, text_cost)


def chat(messages, **kwargs):
    return {"model": "qwen3-vl:4b-instruct", "messages": messages, **kwargs}


def tool_turn(question, camera="camera_entry", image="aW1hZ2U="):
    return [
        {"role": "user", "content": question},
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "get_live_context", "arguments": {"camera": camera}}}]},
        {"role": "tool", "content": json.dumps({"camera": camera, "timestamp": 123, "detections": []})},
        {"role": "user", "content": f"Here is the current live image from camera '{camera}'.", "images": [image]},
    ]


class BudgetTests(unittest.TestCase):
    def test_latest_question_tool_evidence_and_only_latest_image_survive(self):
        messages = tool_turn("first?", "camera_entry") + tool_turn("latest?", "camera_side")
        prepared = prepare_chat(chat(messages, tools=[{"name": "tool"}]), Settings())
        self.assertEqual(sum(len(m.get("images", [])) for m in prepared["messages"]), 1)
        self.assertEqual(prepared["messages"][-1]["images"], ["aW1hZ2U="])
        self.assertTrue(any(m.get("content") == "latest?" for m in prepared["messages"]))
        self.assertEqual([m["content"] for m in prepared["messages"] if m["role"] == "tool"],
                         [m["content"] for m in messages if m["role"] == "tool"])
        self.assertIn(MISSING_VISUAL, prepared["messages"][0]["content"])
        self.assertEqual(prepared["tools"], [{"name": "tool"}])
        self.assertEqual(messages[-1]["images"], ["aW1hZ2U="])  # Original request is untouched.

    def test_character_limit_removes_whole_older_turn_not_partial_tool_json(self):
        old = tool_turn("old?" + "x" * 5000)
        latest = tool_turn("latest?")
        prepared = prepare_chat(chat(old + latest), Settings(text_tools_chars=3000))
        self.assertFalse(any(m.get("content", "").startswith("old?") for m in prepared["messages"]))
        self.assertEqual([m for m in prepared["messages"] if m["role"] == "tool"],
                         [m for m in latest if m["role"] == "tool"])
        self.assertEqual(len([m for m in prepared["messages"] if m.get("tool_calls")]), 1)
        self.assertLessEqual(text_cost(prepared), 3000)

    def test_oversized_latest_turn_rejected_without_truncating_question_or_system(self):
        with self.assertRaises(ClientError) as raised:
            prepare_chat(chat([{"role": "system", "content": "preserve"},
                               {"role": "user", "content": "x" * 9000}]),
                         Settings(text_tools_chars=3000))
        self.assertEqual(raised.exception.status, 413)

    def test_retry_keeps_system_latest_question_and_its_tool_results_without_images(self):
        systems = [{"role": "system", "content": "original pinned instructions"}]
        latest = tool_turn("latest?")
        prepared = prepare_chat(chat(systems + tool_turn("old?") + latest), Settings(), retry=True)
        self.assertEqual(prepared["messages"][0], systems[0])
        self.assertFalse(any("images" in m for m in prepared["messages"]))
        self.assertFalse(any(m.get("content") == "old?" for m in prepared["messages"]))
        self.assertTrue(any(m.get("content") == "latest?" for m in prepared["messages"]))
        self.assertEqual([m for m in prepared["messages"] if m["role"] == "tool"],
                         [m for m in latest if m["role"] == "tool"])
        self.assertIn(MISSING_VISUAL, prepared["messages"][1]["content"])

    def test_context_and_output_reserve_cannot_be_overridden(self):
        request = chat([{"role": "user", "content": "question"}],
                       options={"num_ctx": 65536, "num_predict": -1, "temperature": 0})
        result = prepare_chat(request, Settings())
        self.assertEqual(result["options"], {"num_ctx": 8192, "num_predict": 1024, "temperature": 0})
        self.assertEqual(result["stream"], False)
        self.assertIn(RULES, result["messages"][0]["content"])

    def test_malformed_messages_and_tools_rejected(self):
        for value in ({}, {"messages": []}, {"messages": ["invalid"]},
                      {"messages": [{"role": "user", "content": []}]},
                      {"messages": [{"role": "user", "content": "q", "images": [123]}]},
                      {"messages": [{"role": "user", "content": "q"}], "tools": {}}):
            with self.subTest(value=value), self.assertRaises(ClientError):
                prepare_chat(value, Settings())


class AliasTests(unittest.TestCase):
    def setUp(self):
        self.aliases = Aliases([
            {"id": "camera_entry", "name": "Entryway", "aliases": ["front", "shared"]},
            {"id": "camera_garden", "name": "Garden view", "aliases": ["back", "shared"]},
        ])

    def test_exact_normalized_and_friendly_names_resolve_but_collisions_do_not(self):
        self.assertEqual(self.aliases.resolve("CAMERA GARDEN"), "camera_garden")
        self.assertEqual(self.aliases.resolve("entryway"), "camera_entry")
        self.assertEqual(self.aliases.resolve("camera_entry"), "camera_entry")
        self.assertIsNone(self.aliases.resolve("shared"))
        self.assertIsNone(self.aliases.resolve("unknown"))

    def test_only_live_context_camera_argument_is_rewritten(self):
        response = {"message": {"role": "assistant", "tool_calls": [
            {"function": {"name": "get_live_context", "arguments": {"camera": "CAMERA GARDEN"}}},
            {"function": {"name": "get_live_context", "arguments": {"camera": "shared"}}},
            {"function": {"name": "set_camera_state", "arguments": {"camera": "back"}}},
        ]}}
        revised = canonicalize_tools(response, self.aliases)
        calls = revised["message"]["tool_calls"]
        self.assertEqual(calls[0]["function"]["arguments"]["camera"], "camera_garden")
        self.assertEqual(calls[1]["function"]["arguments"]["camera"], "shared")
        self.assertEqual(calls[2]["function"]["arguments"]["camera"], "back")
        self.assertEqual(response["message"]["tool_calls"][0]["function"]["arguments"]["camera"], "CAMERA GARDEN")


class ApplicationTests(unittest.TestCase):
    def test_context_overflow_retries_once_with_latest_turn_text_only(self):
        app = Application(Settings(), Aliases())
        calls = []

        def upstream(method, path, payload):
            calls.append(payload)
            if len(calls) == 1:
                return 400, b'{"error":"request exceeds the available context size"}'
            return 200, b'{"message":{"role":"assistant","content":"unknown"},"done":true}'

        app.upstream = upstream
        response = app.chat(chat(tool_turn("old?") + tool_turn("latest?")))
        self.assertEqual(response["message"]["content"], "unknown")
        self.assertEqual(len(calls), 2)
        self.assertEqual(sum(len(m.get("images", [])) for m in calls[0]["messages"]), 1)
        self.assertFalse(any("images" in m for m in calls[1]["messages"]))
        self.assertFalse(any(m.get("content") == "old?" for m in calls[1]["messages"]))

    def test_second_overflow_returns_safe_error_and_releases_slot(self):
        app = Application(Settings(), Aliases())
        calls = []
        app.upstream = lambda *args: (calls.append(1) or 400, b'{"error":"private prompt exceeds context size"}')
        with self.assertRaises(ClientError) as raised:
            app.chat(chat(tool_turn("question?")))
        self.assertEqual(len(calls), 2)
        self.assertNotIn("private", raised.exception.code)
        self.assertTrue(app.inference.acquire(blocking=False))
        app.inference.release()

    def test_parallel_inference_rejected_without_upstream_call(self):
        app = Application(Settings(), Aliases())
        app.inference.acquire()
        app.upstream = lambda *args: self.fail("Busy request must not reach Ollama")
        try:
            with self.assertRaises(ClientError) as raised:
                app.chat(chat(tool_turn("question?")))
            self.assertEqual(raised.exception.status, 429)
        finally:
            app.inference.release()

    def test_unapproved_model_is_rejected(self):
        app = Application(Settings(allowed_models=("approved",)), Aliases())
        with self.assertRaises(ClientError) as raised:
            app.chat(chat(tool_turn("question?")))
        self.assertEqual(raised.exception.status, 403)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.app = Application(Settings(api_key="test-secret", max_request_bytes=1024), Aliases())
        self.app.upstream = lambda *args: (200, b'{"message":{"role":"assistant","content":"ok"},"done":true}')
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.application = self.app
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path, payload=None, auth=True):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = "Bearer test-secret"
        data = None if payload is None else json.dumps(payload).encode()
        return urlopen(Request(self.base + path, data=data, headers=headers), timeout=2)

    def test_health_does_not_require_key_but_inference_does(self):
        with self.request("/healthz", auth=False) as response:
            self.assertEqual(response.status, 200)
        with self.assertRaises(HTTPError) as raised:
            self.request("/api/chat", chat([{ "role": "user", "content": "q"}]), auth=False)
        self.assertEqual(raised.exception.code, 401)
        raised.exception.close()

    def test_unknown_proxy_path_is_not_forwarded(self):
        with self.assertRaises(HTTPError) as raised:
            self.request("/api/delete", {"model": "private"})
        self.assertEqual(raised.exception.code, 404)
        raised.exception.close()

    def test_stream_client_receives_one_valid_complete_ndjson_record(self):
        with self.request("/api/chat", chat([{ "role": "user", "content": "q"}], stream=True)) as response:
            self.assertEqual(response.headers["Content-Type"], "application/x-ndjson")
            lines = response.read().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["message"]["content"], "ok")
        self.assertTrue(json.loads(lines[0])["done"])

    def test_request_size_limit(self):
        with self.assertRaises(HTTPError) as raised:
            self.request("/api/chat", chat([{ "role": "user", "content": "q" * 2000}]))
        self.assertEqual(raised.exception.code, 413)
        raised.exception.close()


if __name__ == "__main__":
    unittest.main()
