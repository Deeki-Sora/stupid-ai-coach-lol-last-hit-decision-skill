"""Conditional layered evaluation for short-window last-hit decisions.

The module separates hard feasibility from quality and endpoint payoff.  A
hard-infeasible action is returned with ``eligible=False`` and no quality score;
it is never averaged into the score of executable actions.  Quality layers use
the centered interval ``[-1, 1]`` and are converted to a 0--100 score only at
the reporting boundary.
"""
import math


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + " must be finite")
    return float(value)


def _clip(value, low=-1.0, high=1.0):
    return max(low, min(high, float(value)))


def _interval(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(label + " must be a two-value interval")
    low, high = (_finite(x, label) for x in value)
    if low > high:
        raise ValueError(label + " lower bound exceeds upper bound")
    return low, high


def _ratio(value, upper, label):
    value = _finite(value, label)
    upper = _finite(upper, label + " upper bound")
    if value < 0 or upper <= 0:
        raise ValueError(label + " must be nonnegative with a positive upper bound")
    return max(0.0, min(1.0, value / upper))


def _centered_ratio(value, upper, label):
    return 2.0 * _ratio(value, upper, label) - 1.0


def _weights(layers, weights):
    weights = weights or {key: 1.0 for key in layers}
    if not isinstance(weights, dict):
        raise ValueError("weights must be an object")
    result = {}
    for key in layers:
        value = weights.get(key, 0.0)
        value = _finite(value, key + " weight")
        if value < 0:
            raise ValueError(key + " weight must be nonnegative")
        result[key] = value
    if sum(result.values()) <= 0:
        raise ValueError("at least one layer weight must be positive")
    return result


def aggregate_layers(*, eligible, layers, weights=None, reasons=None,
                     endpoint_vector=None, violations=None, uncertainty_margin=15.0):
    """Aggregate known centered quality layers after a hard eligibility gate.

    ``layers`` values are in [-1, 1] or ``None``.  Missing layers are excluded
    from the denominator and reported.  If ``eligible`` is false, ``score`` is
    ``None`` and the caller receives the observed layers without treating them
    as a legal-action score.
    """
    if eligible not in (True, False):
        raise ValueError("eligible must be True or False")
    if not isinstance(layers, dict) or not layers:
        raise ValueError("layers must be a nonempty object")
    clean = {}
    for key, value in layers.items():
        if value is None:
            clean[key] = None
        else:
            clean[key] = _clip(_finite(value, key), -1.0, 1.0)
    weight_map = _weights(clean, weights)
    known = [key for key, value in clean.items() if value is not None and weight_map[key] > 0]
    total_weight = sum(weight_map.values())
    used_weight = sum(weight_map[key] for key in known)
    coverage = used_weight / total_weight if total_weight else 0.0
    raw = (sum(weight_map[key] * clean[key] for key in known) / used_weight
           if used_weight else None)
    margin = _finite(uncertainty_margin, "uncertainty_margin")
    if margin < 0:
        raise ValueError("uncertainty_margin must be nonnegative")
    score = None if not eligible or raw is None else 50.0 + 50.0 * _clip(raw)
    interval = None
    if score is not None:
        half_width = margin * (1.0 - coverage)
        interval = [max(0.0, score - half_width), min(100.0, score + half_width)]
    return {
        "eligible": eligible,
        "score": score,
        "raw": raw,
        "layers": clean,
        "weights_used": {key: weight_map[key] for key in known},
        "coverage": coverage,
        "missing": [key for key, value in clean.items() if value is None],
        "eligibility_reasons": list(reasons or []),
        "violations": list(violations or []),
        "endpoint_vector": dict(endpoint_vector or {}),
        "interval": interval,
    }


def _slack_quality(slack, scale, label):
    slack = _finite(slack, label)
    scale = _finite(scale, label + " scale")
    if scale <= 0:
        raise ValueError(label + " scale must be positive")
    return _clip(slack / scale)


def evaluate_window(*, window_interval, arrival_interval, phase_margin_s=None,
                    phase_scale_s=1.0, receipt_value=None, receipt_upper=None,
                    weights=None, endpoint_vector=None):
    """Evaluate one last-hit route using timing, phase and receipt layers."""
    window_low, window_high = _interval(window_interval, "window_interval")
    arrival_low, arrival_high = _interval(arrival_interval, "arrival_interval")
    reasons = []
    if arrival_low < window_low or arrival_high > window_high:
        reasons.append("arrival_interval_outside_last_hit_window")
    eligible = not reasons
    layers = {
        "timing": _slack_quality(min(arrival_low - window_low, window_high - arrival_high),
                                 phase_scale_s, "timing_slack"),
        "phase": None if phase_margin_s is None else _slack_quality(phase_margin_s, phase_scale_s, "phase_margin"),
        "conversion": None if receipt_value is None or receipt_upper is None else _centered_ratio(receipt_value, receipt_upper, "receipt"),
    }
    return aggregate_layers(eligible=eligible, layers=layers, weights=weights,
                            reasons=reasons, endpoint_vector=endpoint_vector)


def evaluate_joint_schedule(*, targets, occupation_intervals=None, weights=None,
                            endpoint_vector=None):
    """Evaluate a joint schedule without replacing the event scheduler.

    Each target requires ``window`` and ``arrival`` intervals.  Optional
    occupation intervals must not overlap.  The function reports the minimum
    normalized slack and the receipt conversion of the schedule.
    """
    if not isinstance(targets, list) or not targets:
        raise ValueError("targets must be a nonempty list")
    reasons = []
    slacks = []
    receipts = 0.0
    receipt_upper = 0.0
    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            raise ValueError("target rows must be objects")
        window = _interval(target.get("window"), f"target[{index}].window")
        arrival = _interval(target.get("arrival"), f"target[{index}].arrival")
        if arrival[0] < window[0] or arrival[1] > window[1]:
            reasons.append(f"target[{index}].arrival_outside_window")
        scale = _finite(target.get("slack_scale_s", 1.0), "slack_scale_s")
        if scale <= 0:
            raise ValueError("slack_scale_s must be positive")
        slacks.append(_clip(min(arrival[0] - window[0], window[1] - arrival[1]) / scale))
        receipts += _finite(target.get("receipt", 0.0), "receipt")
        receipt_upper += _finite(target.get("receipt_upper", target.get("receipt", 0.0)), "receipt_upper")
    occupations = [_interval(row, "occupation_interval") for row in (occupation_intervals or [])]
    occupations.sort()
    for previous, current in zip(occupations, occupations[1:]):
        if current[0] < previous[1]:
            reasons.append("occupation_conflict")
            break
    layers = {
        "slack": sum(slacks) / len(slacks),
        "conversion": None if receipt_upper <= 0 else _centered_ratio(receipts, receipt_upper, "joint_receipt"),
    }
    return aggregate_layers(eligible=not reasons, layers=layers, weights=weights,
                            reasons=reasons, endpoint_vector=endpoint_vector)


def evaluate_pressure(*, free_window_s, target_timing_preserved, pressure_value,
                      pressure_upper, own_cost=None, own_cost_upper=None,
                      weights=None, endpoint_vector=None):
    """Evaluate pressure only inside a preserved last-hit free window."""
    free_window_s = _finite(free_window_s, "free_window_s")
    reasons = []
    if free_window_s <= 0:
        reasons.append("no_insertable_free_window")
    if target_timing_preserved is not True:
        reasons.append("target_minion_timing_not_preserved")
    layers = {
        "pressure": _centered_ratio(pressure_value, pressure_upper, "pressure"),
        "own_cost": None if own_cost is None or own_cost_upper is None else -_centered_ratio(own_cost, own_cost_upper, "own_cost"),
    }
    return aggregate_layers(eligible=not reasons, layers=layers, weights=weights,
                            reasons=reasons, endpoint_vector=endpoint_vector)


def evaluate_target_screen(*, legal, last_hit_probability, next_window_value=None,
                           next_window_upper=None, deadline_margin_s=None,
                           deadline_scale_s=1.0, attack_cost=None, attack_cost_upper=None,
                           weights=None, endpoint_vector=None):
    """Screen a target before full event-chain expansion."""
    reasons = [] if legal is True else ["target_not_legal"]
    layers = {
        "collection": 2.0 * _finite(last_hit_probability, "last_hit_probability") - 1.0,
        "next_window": None if next_window_value is None or next_window_upper is None else _centered_ratio(next_window_value, next_window_upper, "next_window"),
        "deadline": None if deadline_margin_s is None else _slack_quality(deadline_margin_s, deadline_scale_s, "deadline_margin"),
        "cost": None if attack_cost is None or attack_cost_upper is None else -_centered_ratio(attack_cost, attack_cost_upper, "attack_cost"),
    }
    if not 0.0 <= _finite(last_hit_probability, "last_hit_probability") <= 1.0:
        raise ValueError("last_hit_probability must be in [0,1]")
    return aggregate_layers(eligible=legal is True, layers=layers, weights=weights,
                            reasons=reasons, endpoint_vector=endpoint_vector)


def evaluate_preparatory_damage(*, branch, safety_preserved, next_window_preserved,
                                graph_value=None, graph_upper=None, endpoint_value=None,
                                endpoint_upper=None, weights=None, endpoint_vector=None):
    """Evaluate either a surviving-target or death-settlement branch once."""
    if branch not in ("survive", "death"):
        raise ValueError("branch must be 'survive' or 'death'")
    reasons = []
    if safety_preserved is not True:
        reasons.append("planned_safety_boundary_breached")
    if next_window_preserved is not True:
        reasons.append("next_window_not_preserved")
    layers = {
        "branch_value": None if endpoint_value is None or endpoint_upper is None else _centered_ratio(endpoint_value, endpoint_upper, "branch_value"),
        "graph": None if graph_value is None or graph_upper is None else _centered_ratio(graph_value, graph_upper, "graph_value"),
    }
    return aggregate_layers(eligible=not reasons, layers=layers, weights=weights,
                            reasons=reasons, endpoint_vector=endpoint_vector)


def evaluate_wait(*, legal, voi, deadline_cost, endpoint_value=None,
                  endpoint_upper=None, weights=None, endpoint_vector=None):
    """Evaluate waiting as an information action with a deadline comparison."""
    voi = _finite(voi, "voi")
    deadline_cost = _finite(deadline_cost, "deadline_cost")
    reasons = [] if legal is True else ["wait_not_legal"]
    if voi <= deadline_cost:
        reasons.append("information_value_not_above_deadline_cost")
    layers = {
        "information": _clip(voi / max(abs(deadline_cost), 1e-9)),
        "deadline": _clip(-deadline_cost),
        "endpoint": None if endpoint_value is None or endpoint_upper is None else _centered_ratio(endpoint_value, endpoint_upper, "wait_endpoint"),
    }
    return aggregate_layers(eligible=not reasons, layers=layers, weights=weights,
                            reasons=reasons, endpoint_vector=endpoint_vector)


def evaluate_branches(branches, *, lambda_risk=0.25, alpha=0.2, voi=0.0,
                      execute_cost=0.0):
    """Return expected endpoint value and tail loss for legal branches.

    Branch risk is a decision-value adjustment, not a direct player-behavior
    quality penalty.  Each branch must contain ``probability`` and ``utility``;
    optional ``loss`` defaults to the negative utility.
    """
    if not isinstance(branches, list) or not branches:
        raise ValueError("branches must be a nonempty list")
    probabilities = [_finite(row.get("probability"), "branch probability") for row in branches]
    utilities = [_finite(row.get("utility"), "branch utility") for row in branches]
    if any(value < 0 for value in probabilities) or sum(probabilities) <= 0:
        raise ValueError("branch probabilities must be nonnegative with positive mass")
    total = sum(probabilities)
    normalized = [value / total for value in probabilities]
    expected = sum(p * u for p, u in zip(normalized, utilities))
    ordered = sorted(zip(utilities, normalized))
    remaining = alpha
    tail = 0.0
    for utility, probability in ordered:
        take = min(remaining, probability)
        tail += take * utility
        remaining -= take
        if remaining <= 1e-12:
            break
    cvar = tail / alpha
    risk = max(0.0, expected - cvar)
    voi = _finite(voi, "voi")
    execute_cost = _finite(execute_cost, "execute_cost")
    decision_value = expected - lambda_risk * risk + voi - execute_cost
    return {
        "expected_endpoint_value": expected,
        "lower_cvar": cvar,
        "risk_adjustment": risk,
        "voi": voi,
        "execute_cost": execute_cost,
        "decision_value": decision_value,
        "branch_probabilities": normalized,
        "branch_utilities": utilities,
    }


def final_layer_score(strategy_layers, execution_layers, *, strategy_weights=None,
                      execution_weights=None, coverage=None, endpoint_vector=None):
    """Combine strategy and execution layer reports with the fixed 50:50 mix."""
    strategy = aggregate_layers(eligible=True, layers=strategy_layers, weights=strategy_weights)
    execution = aggregate_layers(eligible=True, layers=execution_layers, weights=execution_weights)
    coverage_values = [strategy["coverage"], execution["coverage"]]
    if coverage is not None:
        coverage_values.append(_finite(coverage, "coverage"))
    combined_coverage = sum(coverage_values) / len(coverage_values)
    if strategy["score"] is None or execution["score"] is None:
        score = None
        interval = None
    else:
        score = 0.5 * strategy["score"] + 0.5 * execution["score"]
        half_width = 15.0 * (1.0 - combined_coverage)
        interval = [max(0.0, score - half_width), min(100.0, score + half_width)]
    return {
        "eligible": True,
        "strategy": strategy,
        "execution": execution,
        "strategy_score": strategy["score"],
        "execution_score": execution["score"],
        "score": score,
        "coverage": combined_coverage,
        "endpoint_vector": dict(endpoint_vector or {}),
        "interval": interval,
    }
