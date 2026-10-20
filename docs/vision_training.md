# Vision training workflow

The repository ships full-resolution minion, minion-bar and hero-bar training
subsets and YOLO11n weights under `vision/`. The training subsets do not include
their complete source recordings.

| Detector | Training / validation images | Classes |
| --- | --- | --- |
| Unit model | 16 / 5 | Blue/red melee, caster and siege minions |
| Minion health bar | 12 / 5 | Blue/red minion health bars |
| Hero health bar | 36 / 12 | Blue/red hero bars, including the left level badge |

All 86 supplied images are 1920x1080 PNGs with paired YOLO text labels. Each
dataset has a `dataset.yaml`, image/label checksums in `manifest.json`, and
available source information in `provenance.json`. Model checksums and class
order are recorded in `vision/models/yolo11n/model_manifest.json`. The hero
training summary and all three training-result tables are kept beside the
weights. See [the dataset guide](../vision/training/README.md) for retraining
commands using the supplied files.

To build an additional hero dataset from reviewed health-bar coordinates:

```text
python tools/build_hero_detector_dataset.py --candidates <reviewed-candidates.json> --output <dataset> --review-note "Reviewed full health bars and team colors"
```

The input is a JSON list. Each entry contains the image path and detections
with `side` (`blue` or `red`) and `bbox_xyxy` (`left, top, right, bottom`) for
the full health bar, excluding the badge. The builder adds the level badge to
the left. It requires at least 16 images showing both sides, 16 showing only
blue and 16 showing only red, with no duplicate image hashes. It selects 36
training and 12 validation images. Only use already reviewed candidates; this
tool does not discover or confirm labels on its own.

For minion examples, preserve the class order in the corresponding
`dataset.yaml`. Label the unit model separately from its complete health bar;
only living minions with visible bars are positive examples. Keep hero bars
out of minion-bar labels. Keep original 1920x1080 images and review team color,
weapon/head shape, bar ownership and occlusion before adding them. Preserve a
separate validation split and check new recordings before deploying new weights.

The bundled hero detector currently has two classes: `blue_hero` and
`red_hero`. Its target box includes the complete visible hero health bar and the
level badge immediately to its left. The workbench converts that expanded box
back to the full-bar center before writing an automatic, unreviewed coordinate.
First-person yellow self/ally/enemy hero classes are not trained by this
detector and are not silently mapped to the normal-view classes.

Ultralytics and gameplay-derived images have separate license conditions; see
[third-party notices](../THIRD_PARTY_NOTICES.md) and
[license scope](../LICENSE_SCOPE.md). The supplied subsets are small; the
recorded validation results do not establish accuracy on every recording.
