"""Build a balanced, full-resolution hero-bar YOLO dataset from reviewed candidates.

Input candidates must already have been visually reviewed. Each detection box
describes the health-bar rectangle; this builder expands it to include the level
badge at the left, matching the deployed hero detector target.
"""
from pathlib import Path
import argparse
import hashlib
import json
import random
import shutil

from PIL import Image

NAMES = ["blue_hero", "red_hero"]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def category(row):
    sides = {item["side"] for item in row["detections"]}
    if sides == {"blue", "red"}:
        return "both"
    if sides == {"blue"}:
        return "blue"
    if sides == {"red"}:
        return "red"
    raise ValueError(f"Unsupported candidate sides: {sorted(sides)}")


def select_balanced(rows, *, both, blue, red, seed):
    groups = {name: [] for name in ("both", "blue", "red")}
    seen = set()
    for row in rows:
        image = Path(row["image"])
        digest = sha256(image)
        if digest in seen:
            continue
        seen.add(digest)
        groups[category(row)].append({**row, "image_sha256": digest})
    rng = random.Random(seed)
    limits = {"both": both, "blue": blue, "red": red}
    selected = []
    for name, limit in limits.items():
        rng.shuffle(groups[name])
        if len(groups[name]) < limit:
            raise ValueError(f"Need {limit} {name} frames, found {len(groups[name])}")
        selected.extend(groups[name][:limit])
    rng.shuffle(selected)
    return selected


def write_split(rows, output, split):
    records = []
    for index, row in enumerate(rows, 1):
        source = Path(row["image"])
        name = f"hero_{split}_{index:03d}.png"
        destination = output / "images" / split / name
        shutil.copy2(source, destination)
        with Image.open(destination) as image:
            if image.size != (1920, 1080):
                raise ValueError(f"Expected 1920x1080: {source} is {image.size}")
            width, height = image.size
        labels = []
        serialized = []
        for detection in row["detections"]:
            x0, y0, x1, y1 = map(float, detection["bbox_xyxy"])
            # At 1920x1080 the level badge occupies approximately 30 px to the
            # left of the full bar. Keep a small vertical border around both.
            x0 = max(0.0, x0 - 30.0)
            y0 = max(0.0, y0 - 5.0)
            y1 = min(float(height), y1 + 7.0)
            cls = NAMES.index(f"{detection['side']}_hero")
            cx, cy = (x0 + x1) / 2 / width, (y0 + y1) / 2 / height
            box_width, box_height = (x1 - x0) / width, (y1 - y0) / height
            labels.append(f"{cls} {cx:.8f} {cy:.8f} {box_width:.8f} {box_height:.8f}")
            serialized.append(
                {
                    "class": NAMES[cls],
                    "bbox_xyxy": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                    "candidate_confidence": detection.get("confidence"),
                    "structural_features": detection.get("structural_features"),
                }
            )
        label = output / "labels" / split / f"hero_{split}_{index:03d}.txt"
        label.write_text("\n".join(labels) + "\n", encoding="utf-8")
        records.append(
            {
                "split": split,
                "image": destination.relative_to(output).as_posix(),
                "label": label.relative_to(output).as_posix(),
                "source": str(source),
                "source_sha256": row["image_sha256"],
                "detections": serialized,
            }
        )
    return records


def build(candidates, output, *, seed=41, review_note):
    candidates = Path(candidates)
    output = Path(output)
    rows = json.loads(candidates.read_text(encoding="utf-8"))
    for split in ("train", "val"):
        (output / "images" / split).mkdir(parents=True, exist_ok=True)
        (output / "labels" / split).mkdir(parents=True, exist_ok=True)
    train = select_balanced(rows, both=12, blue=12, red=12, seed=seed)
    used = {row["image_sha256"] for row in train}
    remaining = [row for row in rows if sha256(row["image"]) not in used]
    val = select_balanced(remaining, both=4, blue=4, red=4, seed=seed + 1)
    records = write_split(train, output, "train") + write_split(val, output, "val")
    (output / "dataset.yaml").write_text(
        "train: images/train\nval: images/val\nnames: [blue_hero, red_hero]\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "resolution": [1920, 1080],
        "classes": NAMES,
        "target": "complete hero health bar plus the level badge immediately to its left",
        "health_bar_center_from_box": {"x_fraction_from_left": 0.6071428571, "y_fraction": 0.5},
        "reviewed": True,
        "review_note": review_note,
        "candidate_file": str(candidates),
        "candidate_sha256": sha256(candidates),
        "selection_seed": seed,
        "files": records,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    provenance = {
        "schema_version": 1,
        "license_scope": "Repository-generated gameplay screenshots; source recordings are not redistributed.",
        "annotation_method": "OpenCV geometry proposals requiring team color, full-width dark border, left level badge and nameplate structure, followed by visual review.",
        "limitations": "Normal observer view only. First-person yellow self bars are not included in this version.",
    }
    (output / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"train_images": len(train), "val_images": len(val), "boxes": sum(len(item["detections"]) for item in records)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--review-note", required=True)
    parser.add_argument("--seed", type=int, default=41)
    args = parser.parse_args()
    print(json.dumps(build(args.candidates, args.output, seed=args.seed, review_note=args.review_note), ensure_ascii=False))


if __name__ == "__main__":
    main()
