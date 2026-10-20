# Third-party model and asset notices

The MIT license in this repository covers the original workbench, algorithms,
documentation and adapters. It does not relicense third-party frameworks,
model weights, datasets, game artwork or screenshots.

| Component | Use | License / status | Distribution rule |
|---|---|---|---|
| Pillow | Image loading and color proposals | HPND | Optional dependency; retain its notice |
| OpenCV | Image processing | Apache-2.0 | Optional dependency; retain its notice |
| PaddleDetection / RT-DETR | Detector/tracker backend | Apache-2.0 upstream | Install separately; train a detector for this UI |
| MMDetection / RTMDet | Alternative detector backend | Apache-2.0 upstream | Generic COCO weights are not LoL unit weights |
| Ultralytics YOLO | Runtime and training backend for bundled YOLO11n weights | AGPL-3.0 by default; Enterprise terms may apply | Python package is optional; comply with Ultralytics terms |
| LeagueAI | LoL synthetic-data reference | Check upstream terms | Reference only; no weights or Riot assets bundled |
| Riot/Data Dragon/CommunityDragon artwork | Champion/minion references | Riot's respective terms | Excluded from MIT |

The repository ships project-trained YOLO11n weight files and their exact
full-resolution training subsets under `vision/`. They are excluded from the
MIT grant. The model manifest records hashes and source run names. The models
identify the six declared minion classes, two minion-bar colors and two
observer-view hero-bar classes; they do not
claim universal recognition of champions, HUD layouts, or every patch skin.

Before redistributing a custom model, record its source URL, exact version,
weight checksum, training-data provenance and license in the workspace manifest.
