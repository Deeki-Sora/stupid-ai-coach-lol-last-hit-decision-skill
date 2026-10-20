"""Optional OCR proposals for game clock, CS, HP/resource and cooldown text."""

from pathlib import Path
from .core import read_json, write_json


def _rows(raw):
    rows = []
    # PaddleOCR 3.x result objects expose rec_texts/rec_scores; older releases
    # return [[[box], [text, score]], ...].  Keep both adapters text-only.
    for result in raw or []:
        data = result.json if hasattr(result, "json") else result
        if callable(data):
            data = data()
        if isinstance(data, dict) and "res" in data:
            data = data["res"]
        if isinstance(data, dict) and isinstance(data.get("rec_texts"), list):
            texts, scores = data.get("rec_texts", []), data.get("rec_scores", [])
            for index, text in enumerate(texts):
                rows.append({"text": str(text), "confidence": float(scores[index]) if index < len(scores) else None})
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, list) and len(item) >= 2 and isinstance(item[1], (list, tuple)):
                    rows.append({"text": str(item[1][0]), "confidence": float(item[1][1]) if len(item[1]) > 1 else None,
                                 "box": item[0]})
    return rows


def ocr_project(directory, *, max_frames=None):
    try:
        from paddleocr import PaddleOCR
    except ImportError as error:
        raise RuntimeError("PaddleOCR is not installed; run pip install -r requirements-vision-optional.txt or choose manual review") from error
    directory = Path(directory)
    project = read_json(directory / "project.json")
    try:
        engine = PaddleOCR(lang="en", use_doc_orientation_classify=False,
                           use_doc_unwarping=False, use_textline_orientation=False)
    except TypeError:
        engine = PaddleOCR(lang="en")
    frames = project.get("frames", [])[:max_frames] if max_frames else project.get("frames", [])
    proposals = []
    for frame in frames:
        path = directory / frame["image"]
        if hasattr(engine, "predict"):
            raw = engine.predict(str(path))
        else:
            raw = engine.ocr(str(path), cls=True)
        proposals.append({"frame_id": frame["id"], "source_time_s": frame["source_time_s"],
                          "items": _rows(raw)})
    result = {"schema_version": 1, "provider": "paddleocr", "proposal_only": True,
              "proposals": proposals,
              "notes": "OCR text is not automatically mapped to clock, CS, unit HP, mana or cooldown. Confirm the HUD region and field identity before scoring."}
    write_json(directory / "hud_candidates.json", result)
    return result
