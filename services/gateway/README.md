# Bounded Ollama chat gateway

This optional service addresses the observed Frigate chat failure where replayed
camera images and conversation history exceed an 8192-token Ollama context. It is
a small, dependency-free compatibility service, not a replacement for an
authoritative camera evidence API or a guarantee that a vision model is correct.

It exposes only `GET /healthz`, `GET /api/tags`, `POST /api/show`, and
`POST /api/chat` against a fixed `OLLAMA_URL`. It cannot pull/delete models, serve
arbitrary URLs, modify Frigate settings, or forward arbitrary API paths.

For chat, it adds instructions that distinguish tool evidence from model guesses,
keeps at most the latest **one image**, caps output, and removes complete older
user turns when a conservative character ceiling is exceeded. A turn includes
the user question, assistant tool calls, all corresponding tool results, and
Frigate's injected image messages. It does not truncate tool-result JSON or drop
the latest question, latest turn's tool evidence, original system instructions,
or tool definitions. If those alone exceed the ceiling it returns HTTP 413 and
asks the client to start a new chat.

If Ollama returns HTTP 400 explicitly identifying context overflow, it retries
**once** using the latest turn and its tool evidence without images. A system
notice explicitly identifies omitted visual evidence. Other upstream failures
are not blindly retried. This is an approximate character budget, **not exact
token counting**; long tool schemas or unusual tokenization can still exceed the
model's context. A second context overflow returns a clear error.

Only `get_live_context` tool-call camera arguments are canonicalized from a
configured, collision-aware registry. Unknown and ambiguous aliases remain
unchanged. Canonical IDs always remain valid. This does not add plate readings or
LPR configuration that Frigate's built-in tools omit. Use the companion evidence
API for authoritative configuration and event fields.

The gateway forces upstream chat to non-streaming mode so it can validate the
response and canonicalize tools. If the client requested streaming, it returns
one completed NDJSON record; users see the answer after completion rather than a
token-by-token stream. One chat request runs at a time; overload returns HTTP 429
with `Retry-After: 2`. The gateway does not queue background work.

## Configuration

| Environment variable | Default / purpose |
| --- | --- |
| `OLLAMA_URL` | `http://ollama:11434`; fixed HTTP(S) upstream |
| `PORT` | `8081` |
| `GATEWAY_CONTEXT_TOKENS` | `8192`; enforced as request `options.num_ctx` |
| `GATEWAY_OUTPUT_TOKENS` | `1024`; maximum request `options.num_predict` |
| `GATEWAY_TEXT_TOOLS_CHARS` | `14000`; serialized text, instructions, and tool ceiling |
| `GATEWAY_MAX_REQUEST_BYTES` | `2097152`; request limit including images |
| `GATEWAY_MAX_RESPONSE_BYTES` | `8388608`; response limit |
| `GATEWAY_TIMEOUT_SECONDS` | `120`; upstream and request-body socket timeout |
| `GATEWAY_API_KEY_FILE` | Optional bearer-key secret file |
| `GATEWAY_API_KEY` | Optional direct bearer key, takes precedence over file |
| `OLLAMA_ALLOWED_MODELS` | Optional comma-separated exact model tags |
| `OLLAMA_MODEL` | Alternate single-model allowlist when the above is unset |
| `CAMERA_ALIASES_FILE` | Optional camera metadata file, loaded at startup |
| `CAMERA_ALIASES_JSON` | Alternate ID-to-alias-list JSON object, default `{}` |

The camera metadata format is:

```json
{"cameras":[{"id":"camera_a","name":"Front Door","aliases":["porch"]}]}
```

If using this as Frigate's chat provider, give **chat** its own named provider
and keep object descriptions pointed directly at Ollama. Set the provider's
`base_url` to the gateway, its `api_key` to the optional gateway bearer key, and
its `provider_options.options.num_ctx` to the same context as the gateway. Keep
the model tag identical to the installed Ollama model. The gateway's output cap
does not increase its upstream context. No live deployment is performed by
building or testing this directory.

Keep the service on a private container network. `/healthz` is a process-health
probe and does not prove Ollama/GPU readiness. A bearer key provides optional
shared-service authentication, not per-user authorization or TLS; use a proper
authenticated HTTPS boundary for any user-facing access. No raw prompts, images,
headers, camera names, or upstream error bodies are logged; only generated
request IDs, HTTP status, and elapsed time are logged. Requests are held in memory
only. The service has not undergone load, penetration, or production soak tests.

Run checks with:

```sh
python -m unittest discover -s . -p 'test_*.py' -v
```
