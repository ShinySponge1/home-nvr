# Pretrained models and optional local AI

You can use this home-camera starter without collecting a training dataset,
labeling private footage, buying a model subscription, or uploading images to a
cloud provider. Docker supplies Frigate's bundled pretrained detector. Optional
local AI uses an explicitly downloaded public Qwen model. This repository ships
source and configuration examples, not model weights or personal footage.

## Default: CPU setup, with AI disabled

Bootstrap generates an explicit CPU detector, enables detection, and tracks
`person`, `car`, `dog`, and `cat`. Frigate supplies the pretrained TensorFlow Lite
model at `/cpu_model.tflite`; bootstrap does not download weights. Camera IDs,
names, RTSP/RTSPS URLs, optional substreams, codecs, and audio settings come from
your inventory. No manufacturer, camera count, network address, or GPU is assumed.

This CPU configuration is a portable setup/testing baseline. It is not a promise
that a particular computer can analyze all its cameras in real time. Frigate
recommends hardware acceleration for ordinary NVR workloads and notes that
OpenVINO CPU can be more efficient than the basic CPU detector. Intel, AMD,
Apple, and other accelerators need their own validated configuration; the NVIDIA
override below should not be used for them. See the upstream
[detector guide](https://docs.frigate.video/configuration/object_detectors/).

## Optional: official Qwen vision model

Add this top-level inventory section:

```yaml
ai:
  enabled: true
  model: qwen3-vl:4b-instruct
```

Supported initial choices are `qwen3-vl:2b-instruct`, `qwen3-vl:4b-instruct`
(default), and `qwen3-vl:8b-instruct`. These are public tags from the
[official Ollama model registry](https://ollama.com/library/qwen3-vl/tags).
Larger choices need more memory; a CPU-only machine may be too slow for useful
vision chat. Prefer a smaller model or leave AI disabled if it interferes with
recording. No model performance or accuracy is guaranteed for a particular home.

Generate configuration before starting the optional services:

```sh
.venv/bin/python scripts/bootstrap.py config/cameras.yml --require-secrets
# If replacing earlier generated output, add --replace: it backs up first.
docker compose --profile ai up -d ollama
.venv/bin/python scripts/setup_models.py
# Inspect the printed plan. Download only when explicitly requested:
.venv/bin/python scripts/setup_models.py --pull
docker compose --profile ai up -d --build
```

Use the virtual environment's corresponding Python executable on Windows.
`setup_models.py` invokes `ollama pull` in the already-running Compose service;
it never starts/restarts Frigate, trains a model, reads footage, accepts arbitrary
model URLs, or downloads a private checkpoint. The public model persists in the
Docker-managed `ollama_data` volume. The default plan mode performs no download.
There is no automatic model pull during bootstrap or container startup.

Bootstrap configures two Frigate provider roles using the **same inventory tag**:
descriptions go directly to `http://ollama:11434`, and chat uses
`http://chat-gateway:8081`. Generated `config/ai.env` keeps the gateway's allowed
model tag aligned. Do not independently set `OLLAMA_MODEL` in
`.env`; change the inventory and regenerate with a backup instead.

The generated providers use an 8192-token context. Object descriptions use one
snapshot at object end, not a ten-image sequence. Chat reserves up to 1024 output
tokens and passes through the bounded gateway. Review summaries, face recognition,
LPR, semantic embeddings, and custom classifiers are not silently enabled by
turning on Qwen. Each needs its own use case, hardware budget, and validation.
These provider roles follow the upstream
[GenAI configuration](https://docs.frigate.video/configuration/genai/genai_config/).

If `ai.enabled` is false or absent, no GenAI provider is generated. Keep the `ai`
Compose profile off. Recording and deterministic evidence routes do not require
the LLM. Starting the profile alone does not rewrite an AI-disabled Frigate config.

## Optional: desktop NVIDIA detection and decoding

This path is for a compatible NVIDIA GPU with working container GPU access on
Linux or Windows/WSL. Validate the host driver and NVIDIA Container Toolkit /
Docker GPU support first. It is not the NVIDIA Jetson configuration.

The override selects Frigate `0.18.1-tensorrt`, one NVIDIA GPU reservation,
`preset-nvidia` video decode, and an **ONNX** detector on device `"0"`. The desktop
image name does not require the legacy `type: tensorrt` detector. Frigate's ONNX
backend uses CUDA acceleration and supported CUDA Graph optimizations; TensorRT
execution-provider compilation is a separate memory-intensive opt-in. The
starter does not force it, especially when Qwen shares the GPU. See the pinned
[Frigate 0.18.1 provider selection](https://github.com/blakeblackshear/frigate/blob/v0.18.1/frigate/util/model.py)
and [runner implementation](https://github.com/blakeblackshear/frigate/blob/v0.18.1/frigate/detectors/detection_runners.py).

The GPU detector needs a public pretrained **YOLOv9 tiny, 320-pixel ONNX export**.
Do not substitute personal fine-tuned weights or an unrelated ONNX architecture.
Follow Frigate's official [YOLOv9 export instructions](https://docs.frigate.video/configuration/object_detectors/#onnx),
using `MODEL_SIZE=t`, `IMG_SIZE=320`, and `--output ./data/models`. Those instructions
download public pretrained weights from the model author's official release and
convert them; this is inference-format conversion, not training on your cameras.
Keep the resulting file at `data/models/yolov9-t-320.onnx`. Exporting can download
large build dependencies, so it is a separate operator action.

Then generate the matching configuration and use both Compose files:

```sh
.venv/bin/python scripts/bootstrap.py config/cameras.yml --hardware nvidia --require-secrets
# Add --replace when regenerating existing output.
docker compose -f compose.yaml -f compose.gpu.yaml config --quiet
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
# Add --profile ai only if the inventory enabled it and the Qwen model was pulled.
```

The override bind-mounts `data/models` read-only at `/models`; model caches and the
database remain in `frigate_config`. It also gives the optional Ollama service
GPU access while retaining its `ai` profile. Do not start the GPU configuration
until the exported model exists. The plain CPU setup does not need this file or
override. Docker does not isolate GPU VRAM between Frigate and Ollama: measure
memory use and inference latency, and preserve recording priority.

## Before sharing or upgrading

Record the container image digest, exact model tag and digest (`ollama show` /
`ollama list`), exported ONNX SHA-256, and exporter source revision locally.
Tags and exporter dependencies can change; compare a new version on your home
scenes before replacing it. Pin validated container images in `.env` when needed.
Generated config, secrets, downloaded weights, build output, and recordings stay
outside the public source tree. No custom training is required for first use.

The project's source license does not replace third-party licenses. Consult the
[Qwen model card](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct),
[YOLOv9 license](https://github.com/WongKinYiu/yolov9/blob/main/LICENSE.md), and
the notices for Frigate, Ollama, their bundled models, and all distributed
artifacts before redistributing a combined image or weights.
