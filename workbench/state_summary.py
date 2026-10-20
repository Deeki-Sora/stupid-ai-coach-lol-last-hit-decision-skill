"""Read-only current-frame status summary for the browser workbench."""

from pathlib import Path
import re

from .core import read_json


def frame_summary(directory, frame_id):
    directory = Path(directory)
    project, annotations = read_json(directory / "project.json"), read_json(directory / "annotations.json")
    frame = next((item for item in project.get("frames", []) if item["id"] == frame_id), None)
    if frame is None:
        raise ValueError("unknown frame")
    annotation = annotations.get("frames", {}).get(frame_id, {})
    roster = {u["id"]: u for u in project.get("units", [])}
    configuration = None
    if project.get("configuration"):
        try:
            from .loadouts import configuration_at
            configuration = configuration_at(directory, project, frame["source_time_s"])
        except (OSError, KeyError, ValueError):
            configuration = None
    units = []
    for uid, unit in roster.items():
        observed = annotation.get("units", {}).get(uid, {})
        if observed.get('visible') is False:
            continue
        row = {"id": uid, "side": unit.get("side"), "kind": unit.get("kind"),
               "center_px": observed.get("center"), "hp_observed": observed.get("hp"),
               "alive": observed.get("alive"), "action": observed.get("action", ""),
               "target": observed.get("target", ""), "phase": observed.get("phase", "")}
        units.append(row)
    heroes = {}
    if configuration:
        for side, data in configuration.items():
            if not isinstance(data, dict) or side not in ("blue", "red"):
                continue
            state = data.get("effective_state") or {}
            event_state = state.get("event_state") or {}
            heroes[side] = {
                "champion": data.get("champion"), "level": state.get("level"),
                "hp": event_state.get("hp"), "resource": event_state.get("resource_value"),
                "resource_type": event_state.get("resource_type"), "items": state.get("items", []),
                "spell_ranks": state.get("spell_ranks", {}),
            }
    last_hit_actions = [u for u in units if u["kind"] in {"melee", "caster", "siege", "super", "minion"}
                        and re.search(r"last.?hit|attack", u["action"], re.I) and u["target"]]
    # A conservative CS estimate is possible only when a hero's annotated
    # target is followed by that minion's confirmed death.  Do not count a
    # generic attack label as a last hit by itself.
    cs_estimate = {"blue": 0, "red": 0}
    death_times = {}
    prior_events = []
    for frame_item in project.get("frames", []):
        t = frame_item["source_time_s"]
        for uid, observed in annotations.get("frames", {}).get(frame_item["id"], {}).get("units", {}).items():
            unit = roster.get(uid, {})
            if observed.get("alive") is False or observed.get("action") == "death":
                death_times.setdefault(uid, t)
            if unit.get("kind") == "hero" and observed.get("target") and re.search(r"last.?hit|attack", observed.get("action", ""), re.I):
                prior_events.append((t, unit.get("side"), observed.get("target")))
    for target, death_time in death_times.items():
        candidates = [row for row in prior_events if row[2] == target and row[0] <= death_time]
        if candidates and candidates[-1][1] in cs_estimate:
            cs_estimate[candidates[-1][1]] += 1
    return {"schema_version": 1, "frame_id": frame_id, "source_time_s": frame["source_time_s"],
            "game_time_s": annotation.get("game_time_s"), "heroes": heroes, "units": units,
            "annotated_last_hit_actions": last_hit_actions, "cs_estimate": cs_estimate,
            "notes": "HP/resource values are automatic only when supplied by the configuration or observation source; blanks remain unknown. CS is estimated only from an explicitly annotated hero target followed by a confirmed minion death; otherwise it remains incomplete."}
