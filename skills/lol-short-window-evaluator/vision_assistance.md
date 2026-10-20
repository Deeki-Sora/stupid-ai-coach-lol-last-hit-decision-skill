# Optional visual assistance

The sampling page's local-YOLO checkbox records the user's provider choice for
automatic coordinates. When checked, use the bundled GPU model without a
second confirmation. When unchecked, or when CUDA/dependencies are unavailable,
use the basic Track candidate path. Manual review remains required before an
automatic value becomes confirmed evidence.

## Provider choice

| Provider | Use | Recommendation |
|---|---|---|
| `track` | OpenCV/Pillow color-bar candidates and motion links | Automatic fallback; identity stays unknown |
| `none` | Manual frame review | Required for final confirmation |
| `opencv` | Cropping, color masks, template matching, pixel measurements | Basic Track backend; no model download |
| `paddleocr` | Clock, CS, HP/mana text and cooldown numerals | Optional OCR proposal layer |
| `ultralytics` | Bundled minion models, minion-bar model and hero-bar model with Kalman plus BoT-SORT | Checkbox opt-in; CUDA and optional dependencies required; AGPL runtime |
| `external_json` | A user-selected vision model or AI service | Optional; return only structured proposals |

The workbench uses the project-trained weights under `vision/models/yolo11n`,
not generic COCO predictions. Its declared classes are blue/red melee, caster
and siege minions, blue/red minion bars, and blue/red hero bars. Hero-bar
training boxes include the level badge; the saved coordinate is the complete
health bar's center, excluding the badge.

The provider registry is inspected with:

```text
python main.py vision-status
```

For a local candidate pass over every sampled frame, use:

```text
python main.py vision-track --workspace <workspace>
```

OpenCV is used when installed; otherwise the workbench falls back to the
existing Pillow color-run detector. The output is nearest-neighbour track
proposals only. It does not establish hero/minion class, cannon identity,
blue/red identity in a first-person view, or a collision-edge coordinate.

An external tool must return the proposal schema exposed by
`python main.py vision-import --input proposals.json --output validated.json`.
Every proposal is marked `requires_confirmation=true`; importing proposals
does not modify `annotations.json`, `events.csv`, distances, or scores.

That command only validates a proposal file. For a workbench request, use
`assistant-read --start` to capture its exact frame context and revision, then
include `request_revision` in the response and save through
`assistant-finish --workspace ... --input ...`. This fills missing values as
unreviewed drafts, backs up the original annotations and regenerates tables;
it preserves existing values. Direct staging supports `center`, `hp`, `alive`,
`action`, `target`, `phase`, `action_start_s`, `action_end_s` and `notes`.
Other proposed state fields require explicit mapping to the appropriate state
inputs; do not silently reinterpret a ratio as a health value or a cooldown.

## Proposal fields

At minimum, return `frame_id`, `unit_id`, `field`, `value`, `confidence`,
`provider`, and `evidence_image`. Useful fields include `center`, `hp_ratio`,
`resource_ratio`, `action`, `target`, `phase`, `skill_ready`,
`summoner_spell_available`, and `minion_death_observed`.

The evaluator may use a proposal only after it is accepted by the user or
reviewer. Unaccepted proposals remain candidate evidence and widen the result
interval.
