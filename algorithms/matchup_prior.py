"""Version- and level-scoped matchup priors.

The prior is an explicit difficulty reference, never a substitute for event
evidence.  A valid prior carries its patch, tier, level, sample size and
source so that an aggregate win rate cannot silently become a level-specific
fact.
"""

import math


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + " must be finite")
    return float(value)


def _share(value, label):
    value = _number(value, label)
    if value > 1.0:
        value /= 100.0
    if not 0.0 < value < 1.0:
        raise ValueError(label + " must be between 0 and 1 (or 0 and 100 percent)")
    return value


def validate_prior(prior):
    """Validate a declared prior and return its normalized copy."""
    if not isinstance(prior, dict):
        raise ValueError("matchup prior must be an object")
    required = ("patch", "tier", "level", "sample_size", "source")
    missing = [key for key in required if prior.get(key) in (None, "")]
    if missing:
        raise ValueError("matchup prior missing: " + ", ".join(missing))
    sample_size = _number(prior["sample_size"], "sample_size")
    # A manual prior may legitimately have no known sample count.  Preserve
    # that fact explicitly instead of inventing a population size.  Provider
    # results still require a positive count.
    if sample_size <= 0 and not (sample_size == 0 and prior.get("sample_size_unknown") is True):
        raise ValueError("sample_size must be positive, or set sample_size_unknown=true for a manual prior")
    if not isinstance(prior["source"], str):
        raise ValueError("source must be a string")
    blue = prior.get("blue_win_rate", prior.get("a_win_rate"))
    red = prior.get("red_win_rate", prior.get("b_win_rate"))
    if blue is None and isinstance(prior.get("levels"), dict):
        level = str(prior["level"])
        row = prior["levels"].get(level)
        if isinstance(row, dict):
            blue = row.get("blue_win_rate", row.get("a_win_rate"))
            red = row.get("red_win_rate", row.get("b_win_rate"))
    if blue is None or red is None:
        raise ValueError("matchup prior requires both side win rates")
    blue = _share(blue, "blue_win_rate")
    red = _share(red, "red_win_rate")
    if not math.isclose(blue + red, 1.0, abs_tol=1e-6):
        raise ValueError("blue and red win rates must sum to 1 or 100 percent")
    result = dict(prior)
    result["blue_win_rate"] = blue
    result["red_win_rate"] = red
    result["sample_size"] = sample_size
    result["schema_version"] = int(prior.get("schema_version", 1))
    return result


def prior_scores(prior):
    """Return the exact 100-point prior allocation, e.g. 47:53."""
    prior = validate_prior(prior)
    return {
        "blue": 100.0 * prior["blue_win_rate"],
        "red": 100.0 * prior["red_win_rate"],
        "sum": 100.0,
        "patch": prior["patch"],
        "tier": prior["tier"],
        "level": prior["level"],
        "sample_size": prior["sample_size"],
        "source": prior["source"],
    }


def difficulty_adjusted_scores(raw_blue, raw_red, prior, strength=1.0):
    """Apply a bounded, zero-sum difficulty correction to raw scores.

    A side below the prior 50% receives a positive correction; a side above
    it receives the same correction in the opposite direction.  The prior
    allocation itself remains separately reported and exactly preserves the
    declared ratio.
    """
    raw_blue = _number(raw_blue, "raw_blue")
    raw_red = _number(raw_red, "raw_red")
    strength = _number(strength, "strength")
    if not 0.0 <= strength <= 1.0:
        raise ValueError("strength must be between 0 and 1")
    scores = prior_scores(prior)
    bonus_blue = strength * (50.0 - scores["blue"])
    bonus_red = -bonus_blue
    return {
        "prior": scores,
        "bonus": {"blue": bonus_blue, "red": bonus_red},
        "raw": {"blue": raw_blue, "red": raw_red},
        "adjusted": {
            "blue": max(0.0, min(100.0, raw_blue + bonus_blue)),
            "red": max(0.0, min(100.0, raw_red + bonus_red)),
        },
        "strength": strength,
        "rule": "disadvantaged side receives strength*(50-prior_score) and the correction is zero-sum",
    }
