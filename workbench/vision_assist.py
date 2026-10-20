"""Optional AI-assisted visual annotation contracts.

The core workbench stays dependency-free.  Vision providers return proposals;
they never write confirmed annotations or scores.  A user or reviewer must
accept each proposal before it enters annotations.json.
"""

import importlib.util
import json
from pathlib import Path


PROVIDERS = {
    "none": {"package": None, "mode": "manual", "license": "repository"},
    "opencv": {"package": "cv2", "mode": "local_image_processing", "license": "Apache-2.0"},
    "pillow_color_fallback": {"package": "PIL", "mode": "local_color_proposal", "license": "HPND"},
    "ultralytics": {"package": "ultralytics", "mode": "local_detection_tracking", "license": "AGPL-3.0-or-later"},
    "paddleocr": {"package": "paddleocr", "mode": "local_ocr", "license": "Apache-2.0"},
    "external_json": {"package": None, "mode": "user_selected_external_ai", "license": "external"},
}


def availability():
    result = {}
    for name, meta in PROVIDERS.items():
        result[name] = dict(meta, installed=(meta["package"] is None or importlib.util.find_spec(meta["package"]) is not None),
                            proposal_only=True, writes_confirmed_annotations=False)
    from .auto_annotation import auto_annotation_availability
    automatic=auto_annotation_availability()
    result['workbench_yolo']=dict(automatic,mode='bundled_local_detection_tracking',
                                  license='AGPL-3.0-or-later runtime',
                                  installed=automatic['available'],proposal_only=True,
                                  writes_confirmed_annotations=False)
    return result


def proposal_schema():
    return {
        "schema_version": 1,
        "proposals": [{
            "frame_id": "f000001",
            "unit_id": "blue_hero",
            "field": "center",
            "value": [920.0, 424.0],
            "confidence": 0.9,
            "provider": "external_json",
            "evidence_image": "frames/frame_000001.jpg",
            "requires_confirmation": True,
            "accepted": False,
        }],
    }


def validate_proposals(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("proposals"), list):
        raise ValueError("vision proposals require a proposals list")
    cleaned = []
    for item in payload["proposals"]:
        if not isinstance(item, dict):
            raise ValueError("each vision proposal must be an object")
        for key in ("frame_id", "unit_id", "field", "value", "confidence", "provider"):
            if key not in item:
                raise ValueError("vision proposal missing " + key)
        confidence = float(item["confidence"])
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("vision proposal confidence must be between 0 and 1")
        if item["provider"] not in PROVIDERS:
            raise ValueError("unknown vision provider")
        row = dict(item)
        row["confidence"] = confidence
        row["requires_confirmation"] = True
        row["accepted"] = bool(item.get("accepted", False))
        cleaned.append(row)
    return {"schema_version": 1, "proposals": cleaned, "confirmed_count": sum(x["accepted"] for x in cleaned)}


def load_proposals(path):
    return validate_proposals(json.loads(Path(path).read_text(encoding="utf-8-sig")))
