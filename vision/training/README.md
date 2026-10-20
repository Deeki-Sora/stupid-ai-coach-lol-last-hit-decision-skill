# Full-resolution detector training data

These are the exact 1920x1080 gameplay frames and YOLO labels used by the three
bundled workbench detectors. Images have not been resized or recompressed.

- `unit_detector`: 16 training frames and 5 validation frames. The six rendered
  model-reference canvases were deliberately excluded from the accepted
  gameplay-only run.
- `minion_bar_detector`: 12 training frames and 5 validation frames. Only
  visible minion bars are positive labels; champion bars are excluded.
- `hero_detector`: 36 training frames and 12 validation frames, with 32 blue
  hero-bar boxes and 32 red hero-bar boxes in total. Each box includes the
  complete hero health bar and its left-hand level badge.

Each dataset includes `dataset.yaml`, paired `images/` and `labels/`, a
`manifest.json` listing image/label checksums, and `provenance.json` describing
the available source information. Unknown source details remain unknown.
Training and validation images have no identical file hashes within a dataset.
Keep the validation split separate when adding training examples.

The deployed weights, training results and their checksums are in
`vision/models/yolo11n/`. Unit, minion-bar and hero targets have different class
lists; do not combine their label files into a single dataset unchanged.

Example retraining commands from the repository root:

```text
yolo detect train model=vision/models/yolo11n/unit_detector.pt data=vision/training/unit_detector/dataset.yaml imgsz=1920 rect=True batch=1 epochs=120 device=0 project=runs/training name=unit_detector
yolo detect train model=vision/models/yolo11n/minion_bar_detector.pt data=vision/training/minion_bar_detector/dataset.yaml imgsz=1920 rect=True batch=1 epochs=150 device=0 project=runs/training name=minion_bar_detector
python tools/train_hero_detector.py
```

These commands continue from bundled weights; they do not reproduce the initial
training from scratch. New outputs go under `runs/training/`, outside the
published model and dataset folders. Review performance before replacing any
deployed weight file. See `docs/vision_training.md` for adding hero examples.

The screenshots contain third-party League of Legends gameplay imagery. They
are excluded from the repository's MIT grant; see `LICENSE_SCOPE.md` and
`THIRD_PARTY_NOTICES.md`.
