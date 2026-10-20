"""Train the full-resolution blue/red hero health-bar detector."""
from pathlib import Path
import argparse
import json
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="vision/training/hero_detector/dataset.yaml")
    parser.add_argument("--weights", default="vision/models/yolo11n/minion_bar_detector.pt")
    parser.add_argument("--project", default="runs/training")
    parser.add_argument("--name", default="hero_detector_fullres_v1")
    parser.add_argument("--epochs", type=int, default=120)
    args = parser.parse_args()

    repository = Path(__file__).resolve().parents[1]
    data = (repository / args.data).resolve() if not Path(args.data).is_absolute() else Path(args.data)
    weights = (repository / args.weights).resolve() if not Path(args.weights).is_absolute() else Path(args.weights)
    project = (repository / args.project).resolve() if not Path(args.project).is_absolute() else Path(args.project)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(project.parent / "Ultralytics"))

    from ultralytics import YOLO

    model = YOLO(str(weights))
    model.train(
        data=str(data),
        project=str(project),
        name=args.name,
        epochs=args.epochs,
        patience=30,
        batch=1,
        nbs=16,
        imgsz=1920,
        rect=True,
        device=0,
        workers=0,
        cache=False,
        plots=False,
        amp=False,
        save=True,
        optimizer="AdamW",
        lr0=0.0005,
        lrf=0.05,
        cos_lr=True,
        cls=0.8,
        seed=41,
        deterministic=True,
        scale=0,
        translate=0,
        mosaic=0,
        mixup=0,
        cutmix=0,
        fliplr=0,
        flipud=0,
        hsv_h=0,
        hsv_s=0,
        hsv_v=0,
        degrees=0,
        shear=0,
        perspective=0,
        multi_scale=False,
        erasing=0,
    )
    run = Path(model.trainer.save_dir)
    best = YOLO(str(run / "weights" / "best.pt"))
    metrics = best.val(data=str(data), imgsz=1920, rect=True, batch=1, device=0, workers=0, plots=False)
    summary = {
        "weights": str(run / "weights" / "best.pt"),
        "names": best.names,
        "metrics": metrics.results_dict,
        "per_class_map50": metrics.box.ap50.tolist(),
        "per_class_map50_95": metrics.box.maps.tolist(),
        "training": {
            "initial_weights": str(weights),
            "epochs_requested": args.epochs,
            "imgsz": 1920,
            "batch": 1,
            "optimizer": "AdamW",
            "selection": "standard single-label validation and early stopping",
        },
    }
    (run / "training_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
