"""Optional OpenCV/Pillow candidate detection and nearest-neighbour tracking.

This is a proposal generator, not an identity solver.  Champion/minion class,
side, and health-bar centers still require confirmation because camera scale,
occlusion, color effects and first-person HUD layouts can swap or hide them.
"""

from pathlib import Path
import math

from .core import read_json, suggest_bars, write_json
from .unit_model_catalog import classify_bar_size


class _ConstantVelocity2D:
    """Small dependency-free Kalman-style constant-velocity predictor."""
    def __init__(self, center):
        self.x, self.y = center
        self.vx = self.vy = 0.0
        self.p = 20.0
        self.missed = 0

    def predict(self, dt):
        self.x += self.vx * dt; self.y += self.vy * dt
        self.p += 4.0 + dt * 8.0
        return [self.x, self.y]

    def update(self, center, dt):
        gain = self.p / (self.p + 16.0)
        px, py = self.x, self.y
        self.x += gain * (center[0] - self.x); self.y += gain * (center[1] - self.y)
        if dt > 0:
            self.vx = 0.7 * self.vx + 0.3 * (self.x - px) / dt
            self.vy = 0.7 * self.vy + 0.3 * (self.y - py) / dt
        self.p *= (1.0 - gain); self.missed = 0
        return [self.x, self.y]


def _center(box):
    x, y, w, h = box
    return [round(x + w / 2.0, 2), round(y + h / 2.0, 2)]


def _opencv_bars(path):
    """Return coarse blue/red bar boxes when OpenCV is installed."""
    try:
        import cv2
    except ImportError:
        return None
    image = cv2.imread(str(path))
    if image is None:
        return []
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    masks = {
        "blue": cv2.inRange(hsv, (85, 55, 45), (135, 255, 255)),
        "red": cv2.bitwise_or(cv2.inRange(hsv, (0, 70, 45), (12, 255, 255)),
                              cv2.inRange(hsv, (165, 70, 45), (179, 255, 255))),
    }
    found = []
    for side, mask in masks.items():
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 2)))
        for contour in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            x, y, w, h = cv2.boundingRect(contour)
            if 8 <= w <= 220 and 1 <= h <= 12 and w / max(h, 1) >= 3:
                found.append({"side_guess": side, "box": [x, y, w, h], "status": "health_bar_center_coordinate_proposal", "measurement": "bar_center_only"})
    return found


def _ultralytics_bars(path, model, tracker='bytetrack'):
    """Run a user-supplied YOLO/RT-DETR health-bar detector.

    No generic LoL health-bar weights are bundled; ``model`` must be trained
    for the recording layout. The detector is still proposal-only.
    """
    result = model.track(str(path), persist=True, tracker=f'{tracker}.yaml', verbose=False)[0]
    boxes = result.boxes
    found = []
    for i, xyxy in enumerate(boxes.xyxy.cpu().tolist()):
        x1, y1, x2, y2 = xyxy
        cls = int(boxes.cls[i].item()) if boxes.cls is not None else -1
        track = int(boxes.id[i].item()) if boxes.id is not None else None
        found.append({'side_guess':'unknown','box':[x1,y1,x2-x1,y2-y1],
                      'detector_class':cls,'detector_track_id':track,
                      'status':'model_health_bar_coordinate_proposal','measurement':'bar_center_only'})
    return found


def track_project(directory, *, max_jump_px=120.0, confidence_floor=0.35, max_missed=2, detector='auto', weights=None, tracker='bytetrack'):
    """Write ``vision_candidates.json`` with color proposals linked over time."""
    directory = Path(directory)
    project = read_json(directory / "project.json")
    previous = []
    filters = {}
    previous_time = None
    counters = {"blue": 0, "red": 0}
    proposals = []
    provider = "pillow_color_fallback"
    model = None
    if detector in ('yolo','rtdetr','auto') and weights:
        try:
            from ultralytics import YOLO
            model = YOLO(weights)
            provider = 'ultralytics_'+tracker
        except ImportError:
            if detector != 'auto': raise RuntimeError('ultralytics is not installed; install requirements-vision-optional.txt')
    for frame in project.get("frames", []):
        detected = _ultralytics_bars(directory / frame["image"], model, tracker) if model else _opencv_bars(directory / frame["image"])
        provider = provider if model else ("opencv" if detected is not None else "pillow_color_fallback")
        if detected is None:
            detected = suggest_bars(directory / frame["image"])
        current = []
        used = set()
        dt = max(0.001, frame["source_time_s"] - previous_time) if previous_time is not None else 0.3
        for item in detected:
            box = item.get("box")
            if not box:
                continue
            center = _center(box)
            side = item.get("side_guess", "unknown")
            class_prior=classify_bar_size(box[2])
            best = None
            for index, prior in enumerate(previous):
                if index in used or prior["side_guess"] != side:
                    continue
                distance = math.hypot(center[0] - prior["center"][0], center[1] - prior["center"][1])
                if distance <= max_jump_px and (best is None or distance < best[0]):
                    best = (distance, index, prior)
            if best is None:
                counters.setdefault(side, 0)
                counters[side] += 1
                track_id = f"vision_{side}_candidate_{counters[side]:03d}"
            else:
                _, index, prior = best
                used.add(index)
                track_id = prior["track_id"]
            filt = filters.setdefault(track_id, _ConstantVelocity2D(center))
            predicted = filt.predict(dt)
            filtered = filt.update(center, dt)
            confidence = max(float(confidence_floor), min(0.85, 0.45 + min(box[2], 100.0) / 400.0))
            row = {"track_id": track_id, "side_guess": side, "box": box, "center": center,
                   "kind_prior": class_prior['kind'], "kind_confidence": class_prior['confidence'],
                   "filtered_center": [round(v, 2) for v in filtered],
                   "predicted_center": [round(v, 2) for v in predicted],
                   "velocity_px_s": [round(filt.vx, 2), round(filt.vy, 2)],
                   "measurement": "observed_health_bar_center", "confidence": round(confidence, 3)}
            current.append(row)
            proposals.append({"frame_id": frame["id"], "unit_id": track_id,
                              "field": "center_candidate", "value": center,
                              "confidence": round(confidence, 3), "provider": provider,
                              "evidence_image": frame["image"], "requires_confirmation": True,
                              "accepted": False, "side_guess": side, "box": box,
                              "filtered_center": row["filtered_center"], "predicted_center": row["predicted_center"],
                              "velocity_px_s": row["velocity_px_s"],
                              "kind_prior": row["kind_prior"], "kind_confidence": row["kind_confidence"],
                              "notes": "Health-bar center coordinate proposal only; a constant-velocity Kalman-style filter smooths measurements. Class, identity and side are not automatic."})
        previous = current
        previous_time = frame["source_time_s"]
    result = {"schema_version": 1, "provider": provider, "proposal_only": True,
              "max_jump_px": max_jump_px, "max_missed": max_missed, "filter": "constant_velocity_kalman_style",
              "proposals": proposals,
              "notes": "Candidate health-bar centers are linked by nearest-neighbour motion. This output estimates unit coordinates only; it does not estimate HP, identity, kind or confirmed side. Confirm the complete health-bar center manually."}
    write_json(directory / "vision_candidates.json", result)
    return result
