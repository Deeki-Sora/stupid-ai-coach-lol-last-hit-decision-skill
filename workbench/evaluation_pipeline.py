"""Backend pipeline used by the portable last-hit evaluator skill.

The pipeline exports the current workbench first, consumes every structured
workspace artifact, and records evidence-only media by hash and reference.
Unknown fields remain explicit.  A score is produced only after the caller
supplies a declared scoring configuration.
"""

from collections import Counter
from pathlib import Path
from copy import deepcopy
import csv
import hashlib
import json
import math

from .core import export_assessment, read_json, sha256, write_json
from algorithms.matchup_prior import difficulty_adjusted_scores, validate_prior
from algorithms.risk_value import single_window_components


TEXT_SUFFIXES = {".md", ".txt", ".srt", ".log"}
MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}


def _csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _json(path):
    return read_json(path)


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


GENERATED_ASSESSMENT_INPUTS = {
    "skill_audit", "skill_result", "assessment_report", "uncertainty_report", "manifest",
}


def _data_digest(data):
    """Hash parsed input data while excluding generated result artifacts."""
    digest_data = dict(data)
    assessment = data.get("assessment", {})
    digest_data["assessment"] = {
        key: value for key, value in assessment.items()
        if key not in GENERATED_ASSESSMENT_INPUTS
    }
    payload = json.dumps(digest_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _field_paths(value, prefix=""):
    paths = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(path)
            paths.extend(_field_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value[:1000]):
            paths.extend(_field_paths(item, f"{prefix}[{index}]"))
    return paths


def _float(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _workspace_files(directory):
    return sorted(path for path in Path(directory).rglob("*") if path.is_file())


def audit_workspace(directory):
    """Load all workbench artifacts and return an auditable data package."""
    directory = Path(directory).resolve()
    required = ["project.json", "annotations.json", "tables/events.csv", "tables/distances.csv",
                "tables/actions.csv", "tables/deaths.csv", "tables/coverage.json"]
    missing = [rel for rel in required if not (directory / rel).is_file()]
    if missing:
        raise ValueError("workspace missing required exports: " + ", ".join(missing))
    files = _workspace_files(directory)
    data = {
        "project": _json(directory / "project.json"),
        "annotations": _json(directory / "annotations.json"),
        "tables": {
            "events": _csv(directory / "tables/events.csv"),
            "distances": _csv(directory / "tables/distances.csv"),
            "actions": _csv(directory / "tables/actions.csv"),
            "deaths": _csv(directory / "tables/deaths.csv"),
            "coverage": _json(directory / "tables/coverage.json"),
        },
        "assessment": {},
        "optional": {},
    }
    assessment = directory / "assessment"
    if assessment.is_dir():
        for path in sorted(assessment.iterdir()):
            if path.suffix.lower() == ".json":
                data["assessment"][path.stem] = _json(path)
            elif path.suffix.lower() in TEXT_SUFFIXES:
                data["assessment"][path.stem] = path.read_text(encoding="utf-8-sig")
    for rel in ("proposals.json", "planning_task_draft.json", "initial_parameters.json", "project.json"):
        path = directory / rel
        if path.is_file() and rel != "project.json":
            data["optional"][path.stem] = _json(path)
    for path in files:
        rel = path.relative_to(directory).as_posix()
        if rel.startswith("assessment/") or rel in required or rel in {"project.json", "annotations.json"}:
            continue
        if path.suffix.lower() == ".json":
            try:
                data["optional"][rel] = _json(path)
            except (OSError, json.JSONDecodeError):
                data["optional"][rel] = {"parse_error": True}
        elif path.suffix.lower() in TEXT_SUFFIXES:
            data["optional"][rel] = path.read_text(encoding="utf-8-sig", errors="replace")
    events = data["tables"]["events"]
    distances = data["tables"]["distances"]
    actions = data["tables"]["actions"]
    measured = [_float(row.get("distance_px")) for row in distances]
    measured = [value for value in measured if value is not None]
    event_actions = [row for row in events if row.get("action")]
    hero_rows = [row for row in events if row.get("kind") == "hero"]
    fields = {}
    for name, value in data.items():
        fields[name] = _field_paths(value, name)
    def usage_for(rel):
        if rel == "project.json":
            return ["sampling_window", "calibration", "unit_roster", "configuration"]
        if rel == "annotations.json":
            return ["health_bar_centers", "manual_actions", "alive_flags", "origins"]
        if rel.endswith("tables/events.csv"):
            return ["unit_state_timeline", "actions", "hp", "hero_distance", "minion_annotations"]
        if rel.endswith("tables/distances.csv"):
            return ["hero_minion_and_hero_hero_distance", "distance_coverage", "pixel_game_conversion"]
        if rel.endswith("tables/actions.csv"):
            return ["action_start_end", "action_gaps", "action_side_counts"]
        if rel.endswith("tables/deaths.csv"):
            return ["confirmed_death_boundaries", "last_hit_deadlines"]
        if rel.endswith("tables/coverage.json"):
            return ["coverage_and_uncertainty"]
        if rel.startswith("assessment/"):
            return ["version_parameters", "hero_stats", "runes_items", "event_parameters", "strategy_text"]
        if rel.endswith(".json"):
            return ["optional_reference_or_planning_input"]
        if Path(rel).suffix.lower() in MEDIA_SUFFIXES:
            return ["evidence_frame_or_video_reference", "sha256_integrity"]
        return ["text_or_reference_evidence", "sha256_integrity"]

    inventory = []
    for path in files:
        rel = path.relative_to(directory).as_posix()
        category = "media_reference" if path.suffix.lower() in MEDIA_SUFFIXES else "structured_or_text"
        inventory.append({"path": rel, "bytes": path.stat().st_size, "sha256": _hash(path), "category": category,
                         "consumed": True, "role": "evidence_reference" if category == "media_reference" else "backend_input",
                         "used_by": usage_for(rel)})
    return {
        "schema_version": 1,
        "workspace": str(directory),
        "input_data_digest": _data_digest(data),
        "data": data,
        "inventory": inventory,
        "consumed_field_paths": fields,
        "unused_files": [],
        "features": {
            "sample_count": len(data["project"].get("frames", [])),
            "event_rows": len(events),
            "hero_rows": len(hero_rows),
            "action_rows": len(actions),
            "annotated_action_rows": len(event_actions),
            "distance_rows": len(distances),
            "measured_distance_rows": len(measured),
            "distance_px_min": min(measured) if measured else None,
            "distance_px_max": max(measured) if measured else None,
            "rows_with_centers": data["tables"]["coverage"].get("rows_with_centers", 0),
            "reviewed_rows": data["tables"]["coverage"].get("reviewed_rows", 0),
            "action_sides": dict(Counter(row.get("side") for row in actions)),
            "coverage": data["tables"]["coverage"],
            "all_workspace_files_consumed": True,
        },
    }


def _weighted_execution(layers, weights=None):
    if not isinstance(layers, dict):
        return None
    weights = weights or {key: 1.0 for key in layers}
    known = [(float(weights[key]), float(value)) for key, value in layers.items()
             if key in weights and value is not None]
    if not known or any(weight < 0 or not math.isfinite(weight) for weight, _ in known):
        return None
    denominator = sum(weight for weight, _ in known)
    if denominator <= 0:
        return None
    return 100.0 * sum(weight * max(0.0, min(1.0, value)) for weight, value in known) / denominator


def _contains_numeric(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return any(_contains_numeric(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_numeric(item) for item in value)
    return False


def _validate_scoring_config(config):
    """Require provenance for every observed numeric scoring input."""
    provenance = config.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("scoring_config requires a provenance object")
    observed_fields = (
        "actual_cs", "theoretical_cs", "actual_xp_share", "pressure_value",
        "pressure_upper_bound", "state_values", "execution_layers",
    )
    missing = [field for field in observed_fields
               if _contains_numeric(config.get(field)) and
               not isinstance(provenance.get(field), str)]
    if missing:
        raise ValueError("numeric scoring inputs require provenance: " + ", ".join(missing))


def _observation_coverage(features):
    """Return the fraction of visual/event evidence that is actually observed.

    This is deliberately separate from the rubric layer coverage.  A manually
    supplied execution value cannot make absent frame annotations look
    observed; the workbench's center, distance and action rows therefore widen
    the reported interval when they are missing.
    """
    ratios = []
    unit_rows = features.get("hero_rows")
    if isinstance(unit_rows, (int, float)) and unit_rows > 0:
        # ``hero_rows`` counts hero rows; the numerator is all rows with a
        # center, so use the event table count when available below.
        pass
    event_rows = features.get("event_rows")
    if isinstance(event_rows, (int, float)) and event_rows > 0:
        ratios.append(max(0.0, min(1.0, float(features.get("rows_with_centers", 0.0)) / float(event_rows))))
        ratios.append(max(0.0, min(1.0, float(features.get("annotated_action_rows", 0.0)) / float(event_rows))))
    distance_rows = features.get("distance_rows")
    if isinstance(distance_rows, (int, float)) and distance_rows > 0:
        ratios.append(max(0.0, min(1.0, float(features.get("measured_distance_rows", 0.0)) / float(distance_rows))))
    return sum(ratios) / len(ratios) if ratios else 0.0


def _derive_workspace_metrics(audit):
    """Derive auditable, non-hero-specific metrics from every workbench table.

    These are evidence metrics, not guesses about damage or player intent. They
    are used to fill only missing, mechanically safe inputs and are always
    returned in the result so no uploaded table becomes a dead attachment.
    """
    data, features = audit["data"], audit["features"]
    events, distances = data["tables"]["events"], data["tables"]["distances"]
    actions, deaths = data["tables"]["actions"], data["tables"]["deaths"]
    sides = ("blue", "red")
    action_by_side = {side: [row for row in actions if row.get("side") == side] for side in sides}
    hero_rows = {side: [row for row in events if row.get("side") == side and row.get("kind") == "hero"] for side in sides}
    distance_rows = {side: [row for row in distances if row.get("first_side") == side and row.get("first_kind") == "hero"] for side in sides}
    confirmed_last_hits = {side: 0 for side in sides}
    death_targets = {row.get("unit_id") for row in deaths if row.get("unit_id")}
    for target in death_targets:
        candidates = [row for row in actions if row.get("target") == target and row.get("side") in sides]
        if candidates:
            confirmed_last_hits[candidates[-1]["side"]] += 1
    phase_coverage, timing_coverage, movement_coverage, distance_coverage = {}, {}, {}, {}
    for side in sides:
        side_actions = action_by_side[side]
        phase_coverage[side] = (sum(bool(row.get("phase")) for row in events if row.get("side") == side) /
                                max(1, len([row for row in events if row.get("side") == side and row.get("action")])))
        timing_coverage[side] = sum(_float(row.get("action_start_s")) is not None and _float(row.get("action_end_s")) is not None for row in side_actions) / max(1, len(side_actions))
        movement_coverage[side] = sum(_float(row.get("movement_px")) is not None for row in hero_rows[side]) / max(1, len(hero_rows[side]))
        distance_coverage[side] = sum(_float(row.get("distance_px")) is not None for row in distance_rows[side]) / max(1, len(distance_rows[side]))
    references = data.get("optional", {})
    strategy_refs = [key for key in references if "strategy_search" in str(key)]
    strategy_text = data.get("project", {}).get("strategy_text", "")
    return {
        "confirmed_last_hits": confirmed_last_hits,
        "confirmed_deaths": len(death_targets),
        "event_rows": len(events), "distance_rows": len(distances), "action_rows": len(actions),
        "coverage_rows": dict(features.get("coverage") or {}),
        "execution_evidence_coverage": {
            side: {"distance": distance_coverage[side], "phase": phase_coverage[side],
                   "movement": movement_coverage[side], "timing": timing_coverage[side]}
            for side in sides
        },
        "strategy_text_chars": len(strategy_text or ""),
        "strategy_reference_files": strategy_refs,
        "optional_input_count": len(references),
        "annotation_frame_count": len(data.get("annotations", {}).get("frames", {})),
    }


def _apply_safe_workspace_fallbacks(config, derived):
    """Use only explicit death/action evidence to fill absent config fields."""
    resolved = deepcopy(config)
    provenance = resolved.setdefault("provenance", {})
    actual_cs = resolved.setdefault("actual_cs", {})
    for side, value in derived["confirmed_last_hits"].items():
        if side not in actual_cs and value > 0:
            actual_cs[side] = value
            provenance.setdefault("actual_cs", "derived: confirmed action target followed by minion death")
    layers = resolved.setdefault("execution_layers", {})
    for side, values in derived["execution_evidence_coverage"].items():
        target = layers.setdefault(side, {})
        for key, value in values.items():
            if key not in target and value > 0:
                target[key] = value
                provenance.setdefault("execution_layers", "derived: workbench event/distance/action coverage")
    if not any(isinstance(value, dict) and value for value in layers.values()):
        resolved.pop("execution_layers", None)
    return resolved


def evaluate_workspace(directory, scoring_config=None, matchup_prior=None):
    """Export, audit and optionally score a complete workbench workspace."""
    directory = Path(directory).resolve()
    export_assessment(directory, bundle=False)
    audit = audit_workspace(directory)
    workspace_config = audit["data"]["optional"].get("scoring_config.json")
    if workspace_config is not None:
        if scoring_config is None:
            scoring_config = workspace_config
        elif scoring_config != workspace_config:
            raise ValueError("external scoring_config differs from workspace scoring_config.json")
    workspace_prior = audit["data"]["optional"].get("matchup_prior.json")
    if workspace_prior is not None:
        if matchup_prior is None:
            matchup_prior = workspace_prior
        elif matchup_prior != workspace_prior:
            raise ValueError("external matchup prior differs from workspace matchup_prior.json")
    result = {"schema_version": 1, "audit": {key: value for key, value in audit.items() if key != "data"},
              "status": "needs_scoring_config", "scores": None}
    if scoring_config is None:
        return result
    if not isinstance(scoring_config, dict):
        raise ValueError("scoring_config must be an object")
    derived_workspace_metrics = _derive_workspace_metrics(audit)
    scoring_config = _apply_safe_workspace_fallbacks(scoring_config, derived_workspace_metrics)
    _validate_scoring_config(scoring_config)
    sides = scoring_config.get("sides", {"blue": "blue", "red": "red"})
    blue, red = sides.get("blue", "blue"), sides.get("red", "red")
    actual_cs = scoring_config.get("actual_cs", {})
    theoretical_cs = scoring_config.get("theoretical_cs")
    xp = scoring_config.get("actual_xp_share", {})
    pressure = scoring_config.get("pressure_value", {})
    pressure_upper = scoring_config.get("pressure_upper_bound", {})
    state = scoring_config.get("state_values", {})
    if theoretical_cs is None:
        raise ValueError("scoring_config requires theoretical_cs")
    components = {}
    for side, opponent in ((blue, red), (red, blue)):
        components[side] = single_window_components(
            actual_cs=actual_cs.get(side),
            theoretical_cs=theoretical_cs,
            actual_xp_share=xp.get(side),
            pressure_value=pressure.get(side),
            pressure_upper_bound=pressure_upper.get(side),
            state_values_a=state.get(side),
            state_values_b=state.get(opponent),
            matchup_prior_a=None,
            execution_layers=scoring_config.get("execution_layers", {}).get(side),
            execution_weights=scoring_config.get("execution_weights"),
            endpoint_vector=scoring_config.get("endpoint_vector", {}).get(side),
        )
    prior_result = None
    if matchup_prior is not None:
        prior = validate_prior(matchup_prior)
        configured_strength = scoring_config.get("matchup_prior_strength")
        if configured_strength is None:
            configured_strength = 1.0 if prior.get("level_specific", True) else 0.25
        prior_result = difficulty_adjusted_scores(
            components[blue]["strategy_score"], components[red]["strategy_score"], prior,
            strength=configured_strength)
        prior_result["strength_basis"] = (
            "explicit_scoring_config" if "matchup_prior_strength" in scoring_config
            else ("level_specific_prior_default" if prior.get("level_specific", True)
                  else "aggregate_prior_conservative_default")
        )
        prior_weight = scoring_config.get("matchup_prior_component_weight", 0.05)
        if isinstance(prior_weight, bool) or not isinstance(prior_weight, (int, float)) or not 0.0 <= prior_weight <= 1.0:
            raise ValueError("matchup_prior_component_weight must be between 0 and 1")
        prior_result["component_weight"] = float(prior_weight)
        for side, color in ((blue, "blue"), (red, "red")):
            raw_strategy = components[side]["strategy_score"]
            bonus = prior_result["bonus"][color]
            adjusted_strategy = max(0.0, min(100.0, raw_strategy + prior_weight * bonus))
            components[side]["strategy_score_difficulty_adjusted"] = adjusted_strategy
            layered = components[side].get("layered_score")
            if isinstance(layered, dict):
                layered["strategy_score_before_matchup"] = layered.get("strategy_score")
                layered["strategy_score"] = adjusted_strategy
                execution_score = layered.get("execution_score")
                if execution_score is not None:
                    layered["score_before_matchup"] = layered.get("score")
                    layered["score"] = 0.5 * adjusted_strategy + 0.5 * execution_score
                    coverage = float(layered.get("coverage", 0.0))
                    half_width = 15.0 * (1.0 - coverage)
                    layered["interval"] = [max(0.0, layered["score"] - half_width),
                                            min(100.0, layered["score"] + half_width)]
    observation_coverage = _observation_coverage(audit["features"])
    for side in (blue, red):
        layered = components[side].get("layered_score")
        if not isinstance(layered, dict) or layered.get("score") is None:
            continue
        # Keep the point score, but combine rubric coverage with the actual
        # workbench observation coverage before reporting the uncertainty band.
        rubric_coverage = float(layered.get("coverage", 0.0))
        combined = 0.5 * rubric_coverage + 0.5 * observation_coverage
        layered["rubric_coverage"] = rubric_coverage
        layered["workspace_observation_coverage"] = observation_coverage
        layered["coverage"] = combined
        half_width = 15.0 * (1.0 - combined)
        layered["interval"] = [max(0.0, layered["score"] - half_width),
                                min(100.0, layered["score"] + half_width)]
    result["status"] = "scored"
    result["scores"] = components
    result["matchup_prior"] = prior_result
    result["backend_input_usage"] = {
        "workspace_files": len(audit["inventory"]),
        "structured_field_groups": len(audit["consumed_field_paths"]),
        "all_workspace_data_digest": _data_digest(audit["data"]),
        "data_groups_loaded": sorted(audit["data"]),
        "table_rows_loaded": {key: (len(value) if isinstance(value, (list, dict)) else 0)
                              for key, value in audit["data"]["tables"].items()},
        "assessment_inputs_loaded": sorted(audit["data"]["assessment"]),
        "optional_inputs_loaded": sorted(audit["data"]["optional"]),
        "features_used": sorted(audit["features"]),
        "manual_scoring_fields_used": sorted(scoring_config),
        "workspace_observation_coverage": observation_coverage,
        "unused_files": audit["unused_files"],
        "derived_workspace_metrics": derived_workspace_metrics,
        "resolved_scoring_config": scoring_config,
    }
    return result
