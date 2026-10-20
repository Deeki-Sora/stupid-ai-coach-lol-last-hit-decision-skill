# Bundled YOLO models

The workbench uses these reviewed YOLO11n detection weights only when the user
enables local YOLO annotation on the video sampling page and a CUDA device is
available.

- `unit_detector.pt`: blue/red melee, caster and siege minions.
- `minion_bar_detector.pt`: blue/red minion health bars.
- `hero_detector.pt`: blue/red hero health bars with the adjacent level badge.

Inference runs at `imgsz=1920`. Unit detections are paired with the nearest
same-side bar above the unit. The full visible bar center is saved as an
unreviewed coordinate. Side/kind-constrained Kalman matching supplies the
primary identity; BoT-SORT is a fallback through short occlusions. Manual
coordinates are never overwritten. Hero detections are selected per side and
converted from the badge-plus-bar box to the complete health-bar center before
they are written.

See `model_manifest.json` for source runs and checksums. These weights depend on
Ultralytics and are outside this repository's MIT license scope.

Training histories are `unit_training_results.csv`,
`minion_bar_training_results.csv` and `hero_training_results.csv`. The hero
model's selected validation metrics and training inputs are in
`training_summary.json`. Paired source images and labels are under
`vision/training/`; intermediate checkpoints are not needed for inference.
