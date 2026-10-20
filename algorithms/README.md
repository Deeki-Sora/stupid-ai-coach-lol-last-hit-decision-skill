# Model utilities

`event_queue.py` implements finite-horizon event ordering and caller-supplied state transitions, corresponding to model Sections 6–7 and 50. Supply the initial state, legal events, patch-dependent tie priorities and transition function. The module contains no champion configuration or game-mechanic defaults. It returns processed and pending events at a common endpoint.

`pixel_distance.py` measures explicit health-bar-center observations, corresponding to Section 27. It computes same-frame pixel distances and movement relative to a tracked map landmark. Missing positions remain unknown. It does not detect units, fit player skill or convert pixels into game units. `risk_value.distance_window_score()` evaluates four layers: auto-attack legality, auto-attack edge quality, spell threat/counterplay, and spell-edge quality. Edge layers require verified distances and ranges; the qualitative layers can operate on explicit boolean relations. `effective_action_range()` sets a known unavailable, controlled or committed non-interruptible action's threat range to zero, so an opponent's pressure window is evaluated before raw distance.

Both modules use the Python standard library. Run their checks from the repository root:

```sh
python -m unittest discover -s algorithms -p "test_*.py"
```

For alternative event engines, belief search or game-theoretic solvers discussed in Section 48, see [algorithm dependencies](../docs/algorithm_dependencies.md). These utilities are building blocks rather than a complete implementation of the decision model.


`risk_value.py` also exposes `relative_state_utility()`. It centers equal receipts and equal projected states at zero, reports receipt and cost advantages separately, normalizes health/mana/energy by each side's own maximum, credits natural and observed recovery, and compares cooldown, summoner-spell and consumable expenditure. `state_utility_share()` is the stricter state allocator: it converts each side's current reserve, unusable floor and within-window recovery into a bounded usable utility before sharing the 100-point component. The simple linear ratio is retained only as its explicit numeric-input special case. The published two-layer score defaults to a fixed 50:50 strategy/execution mix; callers should keep confidence and coverage separate from that mix.

`summoner_spell_share()` allocates the shared spell-state score from ready slots or remaining cooldown. `derive_cooldown_state()` fills a cooldown from a pinned base value, haste/multipliers and a time-stamped cast; the workbench accepts `last_cast_time_s`, `cooldown_multiplier` and `charges_remaining` for this purpose. This is a derived input, not an observation. `single_window_components()` returns CS, XP, free-window pressure, relative state, matchup-prior and strategy components. `improvement_recommendations()` converts measured distance, movement, phase and resource gaps into player-facing corrections.

The input provenance is explicit: visual annotation may be missing, but values derivable from version data and the event log should be resolved before a score is marked unknown. Only unsupported mechanics, missing event timing or conflicting evidence remain irreducibly unknown.

`layered_evaluation.py` provides the reusable conditional evaluation layer. It gates actions with hard feasibility, computes timing/conversion/endpoint quality layers, renormalizes only over known layers, and returns eligibility reasons, coverage, endpoint vectors and intervals. It includes adapters for last-hit windows, joint schedules, free-window pressure, target screening, preparatory-damage branches, waiting/VOI, branch risk and the fixed 50:50 strategy/execution report. Illegal actions return `eligible=false` and no quality score; their observed evidence remains available for post-action review.

`matchup_prior.py` validates patch/level-scoped blue/red win-rate priors, reports the exact prior allocation, and applies a bounded zero-sum difficulty correction. Provider data may include tier and sample size; manual entries can leave both unknown without inventing a count. A 47:53 prior therefore remains 47:53 in the reference component; the evaluator applies the resulting correction through the model's 5% matchup component and reports both raw and adjusted scores. It does not replace event receipts or relative state.

`workbench.evaluation_pipeline` is the backend entry point for the portable `skills/lol-short-window-evaluator` skill. It exports the workspace, consumes all structured workbench artifacts, hashes evidence media, records consumed fields, and refuses silent unused files. Run `python main.py skill-audit --workspace <dir> --output <audit.json>` before supplying a scoring configuration, then use `skill-evaluate` for the reproducible calculation.

During evaluation it also derives safe workspace fallbacks from confirmed
action/death pairs and measured distance/phase/movement/timing coverage. The
resolved configuration and the complete derived ledger are returned under
`backend_input_usage`; reference text and search results remain auditable
inputs without being mistaken for numeric game rules.

The same adapters are available from the public entry point with a JSON specification:

```sh
python main.py layer-score --input layered_task.json --output layered_result.json
```

Set `kind` to `aggregate`, `window`, `joint_schedule`, `pressure`, `target`, `preparatory_damage`, `wait`, `branches` or `final`; the remaining keys are the keyword arguments of the corresponding adapter.
