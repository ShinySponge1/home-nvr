# Dependency and model notices

Original companion code and templates in this directory use the included MIT
license. This does not relicense upstream applications, Python packages, model
weights, datasets, or trademarks. Images and weights are fetched separately.

- [Frigate source/license](https://github.com/blakeblackshear/frigate/blob/v0.18.1/LICENSE):
  MIT code; Frigate branding is separately governed. This is an independent
  integration, not an official Frigate edition.
- [go2rtc](https://github.com/AlexxIT/go2rtc): bundled by Frigate; retain applicable
  upstream notices if redistributing.
- [Ollama](https://github.com/ollama/ollama): retain its distribution notices;
  each served model has its own terms.
- [Eclipse Mosquitto](https://mosquitto.org/): consult the upstream licenses and
  image notices when redistributing it.
- [Ultralytics licensing](https://www.ultralytics.com/license): no Ultralytics
  training pipeline or custom checkpoints are included here. If one is added,
  review its AGPL/commercial terms and the selected weights separately; this
  repository's MIT license does not relicense external training libraries.
- Qwen, detector checkpoints, face models, LPR models, embeddings, CUDA, FFmpeg
  codecs, and camera firmware each need their actual selected version's notices
  recorded in the release inventory. No blanket model-license claim is made here.

Before a public release, enumerate the exact images and weights, preserve their
notices, select a compatible distribution policy, pin tested image digests, and
complete the license/security review of the resulting product. Do not distribute
the private deployment's cached weights or training data by accident.
