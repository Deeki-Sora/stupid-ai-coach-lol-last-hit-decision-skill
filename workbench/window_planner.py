"""Evidence-bound candidate planning for the next short last-hit window."""

import csv
from pathlib import Path

from .core import read_json, write_json


def _nearest_frame(project, frame_id=None, source_time_s=None):
    frames = project.get("frames", [])
    if frame_id:
        for frame in frames:
            if frame["id"] == frame_id:
                return frame
        raise ValueError("unknown frame")
    if source_time_s is None:
        raise ValueError("frame_id or source_time_s is required")
    return min(frames, key=lambda row: abs(float(row["source_time_s"]) - float(source_time_s)))


def plan_window(directory, *, side, frame_id=None, source_time_s=None,
                horizon_s=3.0, game_time_s=None):
    """Rank observable enemy-minion candidates without inventing damage rules.

    The result answers the user's four planning questions only to the extent
    that HP, target identity, distance and action annotations are known.  It
    explicitly returns missing inputs when an exact timing or legal range
    cannot be established.
    """
    if side not in ("blue", "red"):
        raise ValueError("side must be blue or red")
    if not 0 < float(horizon_s) <= 30:
        raise ValueError("horizon_s must be between 0 and 30 seconds")
    directory = Path(directory)
    project, annotations = read_json(directory / "project.json"), read_json(directory / "annotations.json")
    frame = _nearest_frame(project, frame_id, source_time_s)
    annotation = annotations.get("frames", {}).get(frame["id"], {})
    units = {u["id"]: u for u in project.get("units", [])}
    own_hero = next((u for u in units.values() if u.get("side") == side and u.get("kind") == "hero"), None)
    if not own_hero:
        raise ValueError("workspace has no hero for selected side")
    own_row = annotation.get("units", {}).get(own_hero["id"], {})
    distance_map = {}
    distance_path = directory / "tables" / "distances.csv"
    if distance_path.exists():
        with distance_path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("frame_id") != frame["id"]:
                    continue
                first, second = row.get("first"), row.get("second")
                if first == own_hero["id"]:
                    distance_map[second] = row
                elif second == own_hero["id"]:
                    distance_map[first] = row
    candidates = []
    missing = []
    for unit in units.values():
        if unit.get("side") == side or unit.get("kind") not in {"melee", "caster", "siege", "super", "minion"}:
            continue
        observed = annotation.get("units", {}).get(unit["id"], {})
        if observed.get("visible") is False or observed.get("alive") is False or observed.get("action") == "death":
            continue
        distance = distance_map.get(unit["id"], {})
        hp = observed.get("hp")
        row = {
            "target": unit["id"], "kind": unit.get("kind"), "hp": hp,
            "distance_px": float(distance["distance_px"]) if distance.get("distance_px") else None,
            "distance_game_units_estimate": float(distance["distance_game_units_estimate"]) if distance.get("distance_game_units_estimate") else None,
            "observed_action": observed.get("action", ""), "target_of": observed.get("target", ""),
            "alive": observed.get("alive"),
        }
        if hp is None:
            row["recommendation"] = "observe_hp_before_committing"
            row["timing"] = "unknown_until_hp_and_attack_profile_are_confirmed"
            missing.append(unit["id"] + ":hp")
        else:
            row["recommendation"] = "attack_candidate_in_next_legal_window"
            row["timing"] = "submit_at_confirmed_last_hit_threshold"
        candidates.append(row)
    candidates.sort(key=lambda row: (row["hp"] is None, row["hp"] if row["hp"] is not None else float("inf"), row["target"]))
    if not candidates:
        missing.append("alive_enemy_minion_roster")
    result = {
        "schema_version": 1, "status": "advisory" if candidates else "needs_inputs",
        "side": side, "frame_id": frame["id"], "source_time_s": frame["source_time_s"],
        "game_time_s": game_time_s, "horizon_s": float(horizon_s),
        "question": "which minion, when to commit damage, when to wait, and how to schedule the next hit",
        "recommended_sequence": candidates[:3], "candidates": candidates,
        "missing_inputs": missing,
        "assumptions": [
            "This is a short-window candidate ranking, not a server-perfect simulation.",
            "Attack range, attack period, damage, projectile state, cooldowns and minion target rules must be verified before exact timing.",
            "A recommendation never treats an unknown HP or distance as zero.",
        ],
    }
    write_json(directory / "window_plan.json", result)
    return result


def markdown(result):
    lines = ["# 短时补兵窗口候选计划", "", f"- 视角：`{result['side']}`", f"- 帧：`{result['frame_id']}` / 视频时间 `{result['source_time_s']}` s", f"- 规划窗口：`{result['horizon_s']}` s", "", "## 候选动作", "", "|目标|兵种|血量|距离(px)|建议|时机|", "|---|---|---:|---:|---|---|"]
    for row in result.get("candidates", []):
        lines.append(f"|{row['target']}|{row['kind']}|{row.get('hp','未知')}|{row.get('distance_px','未知')}|{row['recommendation']}|{row['timing']}|")
    lines += ["", "## 需要补充或核验", ""]
    lines += [f"- {item}" for item in result.get("missing_inputs", [])] or ["- 当前候选所需的基础字段已存在；仍需核验攻击档位和规则适用性。"]
    lines += ["", "## 限制", ""] + [f"- {item}" for item in result.get("assumptions", [])]
    return "\n".join(lines) + "\n"
