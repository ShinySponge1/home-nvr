# Training and evaluation roadmap

Home NVR starts with upstream pretrained models and requires no private training
corpus. A custom-training workflow is not included in this release. The following
requirements define future work, not implemented features or measured accuracy.
Small pilots can test integration, but cannot establish production performance.
Keep experimental models separate from the active detector and never train on
unapproved proposals.

## Build a representative, reviewed corpus

Collect examples across every camera, multiple capture days, daylight/night,
weather, motion blur, partial objects, and occlusion. Include ordinary positives,
verified hard negatives such as tree trunks and plant pots, and frames where
the current detector missed an object entirely. A false-positive event is not
automatically a negative image: label every visible target-class object.

Use explicit class definitions, including whether delivery vehicles and buses
belong to their own classes. Preserve current production classes when changing
the model head. An annotator should inspect each image and box; local vision
models may propose coordinates but cannot approve their own labels.

Record actual snapshot capture time, not a long-lived tracked event's start.
Keep nearby frames and duplicate imagery in the same split. If capture time is
unknown, conservatively keep that camera together rather than manufacturing an
independent day. Preserve split assignments and label-retraction history across
dataset releases.

## Freeze a separate blind test

Create three partitions: training, development validation, and a locked blind
test. Hold out complete camera/capture-time groups and include a later time
period; choose whether the target is generalization to unseen cameras, future
conditions on the same cameras, or both. Document that choice before tuning.
Do not move validation or test frames into training after examining scores.

Normal count and class-coverage minimums are safeguards, not statistical proof.
Track positive objects, negative frames, and independent groups in each slice.
Expand sparse night, distant-person, occlusion, and small-object slices before
drawing conclusions. Only evaluate the frozen blind test at a planned promotion
decision; use development data for routine tuning.

## Compare against the production baseline

Evaluate the unchanged live detector and each candidate on identical reviewed
frames with the same preprocessing, class mapping, confidence thresholds, and
NMS rules. Stock COCO class IDs may differ from the custom schema; compare a
clearly defined shared ontology rather than unrelated aggregate mAP values.

Report per-class precision/recall, mAP50 and mAP50-95, missed objects, and false
alerts per camera-hour. Include day/night, camera, occlusion, and object-size
breakdowns with denominators and uncertainty intervals where practical. Report
latency percentiles, GPU memory, skipped detection FPS, recording continuity,
and throughput under the intended concurrent workload. Aggregate mAP alone can
hide regressions in a safety-relevant class or a difficult camera.

Run a candidate in shadow mode on saved frames or a separate inference worker
before promotion. Keep production recording and notifications on the current
detector. Shadow inference must not silently affect retention or overwrite the
active model.

## Tune only after the data supports it

Prioritize label completeness and useful hard negatives. Then compare a small,
predeclared set of detector sizes, input resolutions, augmentation settings,
and class-specific operating thresholds. Higher detection resolution may help
small objects but increases decoding and inference cost. Measure that tradeoff
on this hardware instead of assuming a larger model or TensorRT is faster.

Keep seeds, hyperparameters, package/runtime versions, dataset fingerprints,
checkpoint hashes, and export parity results with each run. Validate multiple
representative ONNX inputs and output decoding, not merely graph loading. Stop
promotion if a source approval is retracted, an artifact changes, a baseline
comparison is absent, or a declared per-class/resource gate fails. A corrected
dataset produces a new immutable release; it does not rehabilitate old scores.

## Separate the model responsibilities

| Component | Responsibility | Suitable evaluation |
| --- | --- | --- |
| Object detector | Boxes and tracked object classes | Per-class detection metrics and alert rates |
| Plate detector/OCR | Plate localization and text | Plate recall, exact text accuracy, latency |
| Face recognition | Matching enrolled identities | False matches, missed matches, enrollment quality |
| Semantic embedding model | Retrieving relevant events/images | Retrieval precision/recall and ranking quality |
| Vision-language model | Describing visible evidence | Unsupported-claim rate, object/count accuracy, grounded details |
| Chat/retrieval layer | Answering questions from available event evidence | Correct citations, temporal grounding, abstention, prompt-injection resistance |

Fine-tuning the detector does not improve OCR, face identity matching, semantic
embeddings, or chat reasoning automatically. Keep independent model versions and
test sets for these components.

For evidence-backed chat, include known-answer event/time queries, empty-result
queries, stale/offline cameras, deleted media, contradictory descriptions,
duplicate events, and images containing hostile instructions. An answer should
identify its supporting event/camera/time, distinguish observed facts from
uncertain interpretation, and say when the available evidence is insufficient.
Test that chat cannot change configuration, approve labels, deploy models, or
invent citations through text embedded in a scene or a retrieved description.

## Promote with a recovery path

Require a reviewed report, nonregression checks, sufficient blind-test coverage,
valid current approvals, and resource headroom. Back up configuration and model
state before deployment, preserve rollback artifacts, and verify fresh recordings
from every enabled camera after activation. A restart of a single Frigate
container briefly interrupts recording; uninterrupted recording needs a separate
recorder or another explicitly designed redundant path.
