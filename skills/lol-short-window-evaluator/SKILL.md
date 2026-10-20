---
name: lol-short-window-evaluator
description: Run the local League of Legends review workbench and process its requests from chat. Handle service controls, frame annotation, configuration filling, matchup and guide searches, observation tables, match analysis and short-window planning. Read original evidence and save reviewable results to the external workspace.
---

# 愚蠢的AI教练——一个用来分析LOL真实对局中的补兵决策的SKILL

Use the full LOL short-window last-hit decision framework. The workbench is
the data source; do not replace its tables with a prose summary.

## Installed package and external repository

This directory is a lightweight Skill package installed in the AI tool's user
`skills/` directory. The full repository, model weights, training data and
workbench stay in a separate project directory. Keep generated workspaces,
downloads and installed dependencies outside this Skill directory.

When this Skill is copied outside the repository, execute its adjacent
`runner.py` with the requested command arguments. The runner locates the full
repository from `LOL_SHORT_WINDOW_REPO`, then a one-line `repo_path.txt` beside
the runner, then the in-repository layout. Do not assume `main.py` is in the
Skill directory. If the repository cannot be located, ask for its directory
and update the path setting; do not download the complete repository into
the user's Skill directory. The `python main.py ...` examples below assume
the current directory is the external repository. The runner sets that
working directory automatically.

This Skill is user-facing. Start the guided local workbench before asking for
annotations:

```text
python main.py start
```

## Short chat commands

When this Skill is explicitly loaded, accept these standalone chat phrases
without asking the user to type a terminal command:

| Intent | Chinese examples | English examples | Execute from repository root |
|---|---|---|---|
| Start | `运行`、`运行工作台`、`运行服务`、`启动工作台` | `run`, `run workbench`, `run service`, `start workbench` | `python main.py service-start` |
| Stop | `停止`、`停止工作台`、`停止服务`、`中断工作台` | `stop`, `stop workbench`, `stop service` | `python main.py service-stop` |
| Restart | `重启`、`重启工作台`、`重启服务` | `restart`, `restart workbench`, `restart service` | `python main.py service-restart` |
| Status/address | `工作台地址`、`服务状态` | `workbench address`, `service status` | `python main.py service-status` |

Locate the repository root containing `main.py` and `workbench/`, execute the
mapped command yourself, and read its JSON output. For start, restart, or a
running status, reply immediately with the exact returned `url` as a clickable
link. Never guess the default port or token. If start reports
`already_running=true`, return the existing address instead of launching a
duplicate. Stop must execute the stop command and state that the service has
stopped. Restart must stop the previous managed process, start a new one, and
return its new address. Use the language of the user's phrase.

A bare `运行` / `run`, `停止` / `stop`, or `重启` / `restart` maps to these
actions only when this Skill is explicitly attached or the immediately prior
conversation is about this workbench. Do not start the evaluation, annotation,
or full analysis pipeline from a service-control phrase. If the user explicitly
names an existing workspace, append `--workspace <workspace>` to start or
restart; otherwise open the initial video-selection page.

## Chat commands for workbench requests

The player first presses the corresponding workbench button, then sends a
command here. These phrases authorize processing that existing request, not
merely explaining how to do it. Execute the mapped command, perform the work
with the agent's available vision/web tools, save the result, and report
completion. Do not ask the player to copy files, author JSON or run commands.

| Chinese command | English command | Command arguments after `python main.py` |
|---|---|---|
| `处理工作台请求`、`处理工作台协助请求` | `process workbench request` | `assistant-read --start` |
| `标注当前帧`、`处理当前帧标注` | `annotate current frame` | `assistant-read --start --kind annotation --scope current` |
| `标注所有帧`、`处理所有帧标注` | `annotate all frames` | `assistant-read --start --kind annotation --scope all` |
| `填写当前帧配置` | `fill current frame configuration` | `assistant-read --start --kind configuration --scope current` |
| `填写所有帧配置` | `fill all frame configurations` | `assistant-read --start --kind configuration --scope all` |
| `查询工作台胜率`、`处理工作台胜率查询请求` | `fetch workbench matchup rates` | `assistant-read --start --kind matchup` |
| `查询工作台攻略`、`处理工作台攻略请求` | `search workbench guides` | `assistant-read --start --kind strategy` |
| `填写观察表`、`请 Skill 协助填写观察表`、`处理工作台观察表请求` | `fill observation table`, `ask Skill to fill observations`, `ask Skill to help fill observations`, `process workbench observation request` | `assistant-read --start --kind mechanics` |
| `分析当前对局`、`运行分析任务`、`处理工作台分析请求` | `analyze current match` | `assistant-read --start --kind analysis` |
| `取消工作台请求` | `cancel workbench request` | `assistant-cancel` |
| `工作台请求状态` | `workbench request status` | `assistant-status` |

`处理工作台识别请求` also reads the current annotation request, without
changing its current/all scope. Keep bare `运行` / `run` as service-start.
Treat Skill/skill/SKILL and optional spaces in the observation-table phrases
equivalently. `请skill协助填写观察表` is an executable command too.

The installed `runner.py` accepts all these command arguments. `assistant-read`
locates the active browser workspace, or the single pending workspace recorded
by the workbench. It returns the exact workspace, request revision, language,
scope and absolute evidence image paths. If several offline workspaces have
pending requests, ask which workspace to use, then pass `--workspace`.
If there is no pending request or its kind/scope differs, report that and ask
the player to use the matching workbench button; do not create a different task.

"Current frame" means the frame captured when the player pressed the webpage
request button, not the browser's later slider position. Read `frame_context`:
confirm its frame ID, one-based frame number, source-video time and known game
time in the acknowledgement. Inspect the returned exact image. Keep each
proposal/snapshot tied to that frame ID and evidence path. The backend verifies
the recording, frame time/path and screenshot checksum before accepting output;
if they changed, request a fresh task instead of guessing the target frame.

Read the returned request and follow its kind-specific instructions below.
Annotation/configuration results use `proposals`, `frame_observations`,
`unit_proposals` and/or `state_snapshots`, plus `inspected_frames`.
For a guide, place the cited guide object under `strategy_result`. For a
matchup rate, use `matchup_prior`. For analysis, audit/evaluate the evidence
and place the complete readable Markdown report under `analysis_report`.
Observation-table requests return `mechanics_observations` as row objects
using the request's `mechanics.fields`; use an empty list when nothing can
be identified and explain the missing evidence in `unknown_items`.
Unknown search results use `unknown_items` and preserve existing data.
Every response includes the exact returned `request_revision`; retain it
across batches. Never round it or replace it with the latest status revision.

Write this JSON response to the returned `result_file`, then execute:

```text
python main.py assistant-finish --workspace <returned-workspace> --input <returned-result-file>
```

This validates the current request, preserves manual values, saves the results
to workspace files, rebuilds the event/distance/action/death tables and marks
completion or partial progress. Workbench pages
read these files when refreshed. Do not edit `review.html`, browser DOM values
or rendering code to simulate a saved result. Use `assistant-status --workspace`
before each batch and stop if cancelled or replaced. After completion, reread
the saved result/status, list unknowns and review items, and tell the player to
refresh. A successful `assistant-read` alone is not completed work.

Insufficient evidence never prevents a readable analysis report. Return the
supported timeline and advice; label unavailable components and overall scores
unknown and list the missing evidence. Missing screenshots in an analysis
request have `available=false`; use the remaining tables/evidence without
inventing what those pictures show. Do not wait for every field or a numeric
score before returning the report. If a direct workspace-file correction is
needed, run `export <workspace>` before final completion so all dependent tables
and the assessment bundle agree with the saved records. Never edit only a
displayed HTML value or only one derived CSV.

### Other analysis-page commands

These direct chat commands do not require a pending AI request. Locate the
active workspace with `assistant-status` or an explicit user path. They use
the same calculations as the page buttons and save state that the workbench
reloads on refresh.

| Chinese command / button wording | English command | Arguments after `python main.py` |
|---|---|---|
| `刷新观察表`、`刷新工作区观察表`、`重新统计观察表` | `refresh observation table`, `recalculate observations` | `planning-command refresh --workspace <workspace>` |
| `生成下一短时窗口计划`、`生成短时计划` | `plan next short window` | `planning-command plan --workspace <workspace> --frame-number <N> --side <blue-or-red>` |
| `以当前帧生成任务`、`生成推演任务` | `draft task at current frame`, `draft planning task` | `planning-command draft --workspace <workspace> --frame-number <N>` |
| `将统计模型写入任务`、`将观察统计写入任务` | `apply observation statistics to task` | `planning-command apply-observations --workspace <workspace>` |
| `运行已核验任务`、`运行已核验推演` | `run verified task`, `run verified simulation` | `planning-command run --workspace <workspace>` |

For plan/draft, obtain N from the player's stated one-based frame number or
an exact request snapshot supplied for this operation, and obtain the side
before planning. For example, `从第 10 帧为蓝方生成短时计划` selects frame 10
and blue. Bare "current frame" without a captured frame or explicit number
requires clarification; never substitute the first frame, an old analysis
request or a guessed browser slider position. Do not claim a different request
merely to discover the workspace.

Drafts save to `game_analysis/draft_task.json` and remain unverified and
disabled. Applying observations preserves `context_verified=false` and does
not enable or verify the task. Running requires a task actually checked
against evidence and explicitly enabled. Unknown inputs do not justify
changing verification flags. Explain disabled/missing-input results; after a
saved result, reply with its source frame/time and tell the player to refresh.
Do not execute these actions merely because the user asks which commands exist.

## Response templates

Use `dialogue_templates.md` for service control, workbench-request progress,
completion, cancellation, automatic-annotation fallback, analysis and error
replies. Match the user's language and use only values returned by commands or
read from the current request/result. The templates provide required factual
conditions rather than permission to claim that a button press completed work.
Adapt the wording when useful, but never invent a URL, status, frame count,
result count, source, or missing value.

Start without a workspace to open the video selection page. Tell the user the
actual printed URL: the default is http://127.0.0.1:58392/; if occupied, the
server tries 58393 and successive ports. Do not announce a port before startup
confirms it. The page accepts a video or folder path, offers local selection
dialogs, a source-video start/end time and a 0.1–0.5 second sampling interval.
Selection uses the in-page disk browser, preserving the original file path.
The page reads and displays the video duration with ffprobe and blocks intervals
outside that duration. FFmpeg creates screenshots and tables in a new
session_*/clip_01 folder beside the original video, unless the user selects
another output folder. Sampling runs in the background with frame counts,
elapsed time and explicit completion or error status, then opens annotation.
Use `start --workspace <workspace>` only when resuming existing annotations.

The workbench opens in the browser and its status area explains the next
field. If the user is unsure, explain the current page, the required field,
and the reason it affects the score; do not silently invent a value.

## Required workflow

1. Ask for or locate a workbench directory containing the video sampling,
   annotations, tables, and hero configuration.
2. Run the export and audit before scoring:

   ```text
   python main.py export <workspace>
   python main.py skill-audit --workspace <workspace> --output <workspace>/assessment/skill_audit.json
   ```
   When this directory has been copied outside the repository, run the same
   command through `runner.py` after setting `LOL_SHORT_WINDOW_REPO` to the
   repository root.

3. Read `skill_audit.json`. The audit must report every workspace file. CSV,
   JSON and text fields are backend inputs; images and video are evidence
   references whose hashes and frame paths are retained. Do not silently drop
   a file or field. If `unused_files` is non-empty, stop and report it. The
   evaluator records a digest of the complete parsed input package and the
   loaded table/assessment groups. Generated result files are excluded from
   that digest so rerunning the same workspace is reproducible. This identifies
   the complete input package even when a field is unknown and cannot
   contribute a numeric term.
4. Build `scoring_config.json` from the audited tables and manual evidence.
   Every manually supplied value must carry a provenance note. Values visible
   in the video are `manual_confirmed`; values derived from version data or
   event logs are `derived`; unresolved values remain `unknown`. Workspace
   observations determine coverage and uncertainty; declared numeric fields
   determine only their corresponding score components. Do not copy an
   unresolved field into another component merely to make it affect the point
   score. The backend rejects a numeric observed field without a provenance
   entry.
5. After both champions and the patch are fixed, query optional mechanics and
   matchup guidance:

   ```text
   python main.py search-strategy --workspace <workspace> --version 26.20 --blue <blue-id> --red <red-id> --level 3
   ```

   This saves links/snippets under `references/strategy_search.json`. It is
   reference material only; verify patch, level, rank and applicability before
   using it as a strategy input. If network access fails, continue with manual
   strategy text.
6. If a version/tier/level matchup prior is available, attach a prior JSON and
   declare its patch and level. Provider results include sample size and
   source; a manual entry may leave sample size unknown. A broad aggregate
   win rate must not be labelled as a level-specific prior.
   The workbench can create this file automatically after the user selects the
   patch, blue/red champion IDs and event level. Use `fetch-matchup-prior` or
   the matching button in the loadout panel; the fetched file is then consumed
   by the evaluator. If the provider only returns an all-level aggregate, keep
   `level_specific=false` and report that limitation.
   If the provider is unavailable, use the loadout panel's manual entry or:

   ```text
   python main.py save-matchup-prior --workspace <workspace> --version 26.20 --blue Yasuo --red Veigar --level 3
   ```

   The manual command accepts optional `--blue-win-rate` and
   `--red-win-rate` (percent or 0--1); blank rates produce a neutral 50:50
   prior. `--tier` is optional metadata, and the sample count is recorded as
   unknown rather than guessed.
   If no explicit `matchup_prior_strength` is supplied, the evaluator uses a
   conservative strength for an aggregate prior and full strength only for a
   level-specific prior. An explicit strength remains an auditable user choice.
7. Run the backend evaluator:

   ```text
   python main.py skill-evaluate --workspace <workspace> --config scoring_config.json --output <workspace>/assessment/skill_result.json --matchup-prior matchup_prior.json
   ```

   Omit `--matchup-prior` only when no auditable prior exists.
   If `scoring_config.json` is stored in the workspace, `--config` may be
   omitted. An external config must exactly match the workspace copy, so a
   caller cannot bypass user-entered workbench values. The same rule applies
   to a workspace `matchup_prior.json`.
8. Produce a report containing the evidence audit, event chain, absolute
   receipt ledger, relative state ledger, component scores, intervals,
   matchup prior, counterfactuals, and missing evidence.

The backend writes `assessment/assessment_report.md` and
`assessment/uncertainty_report.md` after a scoring run. The report contains
per-component scores, evidence coverage, interval causes and player-facing
corrections. For a live or unfinished clip, provide the observed frame, side
and in-game time and run:

```text
python main.py plan-window --workspace <workspace> --side blue --game-time 130 --frame f000123
```

It ranks the next enemy-minion candidates and distinguishes attack-now,
wait-for-threshold and missing-input cases. It is a bounded advisory plan;
exact timing requires verified damage, attack period, range, projectile,
cooldowns and minion target rules. It does not replace `game-run` when a fully
specified finite event task is available.

## Automatic and assisted visual review

The video sampling page contains an explicit local-YOLO checkbox. That checkbox
is the user's authorization for automatic unit detection and coordinate
staging. When enabled, the workbench checks CUDA, Ultralytics, PyTorch,
BoT-SORT's `lap` dependency, and the bundled weights before it runs. Do not ask
for a second confirmation. When the checkbox is disabled or the GPU path is
unavailable, the workbench automatically runs the dependency-light Track path
and displays its boxes as unreviewed candidates. Provider status is available
with:

```text
python main.py vision-status
```

Use `vision_assistance.md` for provider details. Automatic output is never a
confirmed annotation. YOLO writes only missing full-bar centers and labels them
unreviewed; Track leaves identity unknown and displays candidates. Validate
external proposal files with:

```text
python main.py vision-import --input proposals.json --output validated_proposals.json
```

When the user chooses Skill assistance in the workbench, read
`assistant/request.json` inside that workspace. The web button creates a request;
it does not launch an AI service or wake an idle conversation. Process the
request when the player sends a matching chat command above. Do not begin a
different pending task just because this Skill is loaded. No API key is required for the
agent's available image-viewing tools.

Open the request's original screenshot and adjacent sampled frames with an
available image-viewing tool. Identify registered units using full health-bar
centers, verify displayed team colors against the actual sides, and record only
visible actions, targets, phases and health values. Never substitute the colored
fill midpoint for the complete bar center. If a unit is absent from the roster,
help the user register it before importing; do not silently reuse another ID.
Use OCR or local detection only when available and authorized. The bundled
YOLO detectors assign the declared blue/red melee/caster/siege minion classes
and blue/red hero health-bar classes. Hero boxes include the level badge beside
the full bar; the workbench converts them to full-bar centers. Detection still
does not confirm actions, hidden units, or temporary effects.

For `scope=all`, process every listed frame in chronological batches, maintaining
unit IDs across the sequence. Return `inspected_frames` including inspected
frames with no identifiable action, and report `unknown_items` and `review_items`.
The importer marks incomplete batches partial; do not claim that all frames are
filled when any remain. After completion, tell the player in the conversation
what was filled, what remains unknown, and which items need review, then ask them
to refresh the workbench. Never turn adjacent screenshots into separate casts.
The workbench disables its refresh/edit controls during an all-frame annotation
or configuration request. Do not replace an unfinished batch with another
request. The player may cancel it; stop importing if the request is cancelled.
Return the original request revision as `request_revision` when importing, so
results from an older request cannot enter a newer task. Browser reload cannot
be forbidden; the pending-task lock is restored after reload.

Use optional `frame_observations` for game-clock readings (`frame_id`,
`game_time_s`, exact `evidence_image`) and `unit_proposals` to register observed
minions (`id`, `side`, `kind`, `wave`, `frame_id`, `evidence_image`). Every new
unit remains unreviewed. Distances are computed from the staged centers by the
workbench; do not supply invented distances in place of missing centers.

Match-wide selections are champion, rune page/stat shards and summoner spell
identities. Level, skill ranks, equipment, current resources, cooldowns, rune
stacks and temporary effects belong to frame-specific snapshots labelled with
source-video time, frame ID and observed game time. Compute automatic attributes
from patch base stats, level growth, fixed item stats and stat shards; do not
automatically include triggered item effects or rune procs.

For `kind=configuration`, fill `state_snapshots` rather than changing global
match selections. Read `workbench/loadouts.py:validate_state` for the state
schema. Each snapshot contains `frame_id`, the exact `evidence_image`,
`confidence`, `provider`, and `sides` (`blue`/`red`). Side fields are `level`,
`spell_ranks`, `items` (catalog ID and slot), `inventory_known`, `event_state`
and `stat_overrides`. Use only visible or deterministically derived values;
cooldowns, hidden rune stacks and uncertain inventory remain unknown. Import
with `proposals: []` if there are no annotation fields. Include inspected frame
IDs even when every state value is unknown. The importer fills missing values,
preserves player entries and labels evidence unreviewed. After all frames are
inspected, reply in the conversation in the requested language with completed
fields, unknowns and review items, and tell the player refresh is available.

Save proposal-schema output to `assistant/skill_response.json`, including confidence
and the exact `evidence_image` from the requested frame. Import it directly:

```text
python main.py assistant-finish --workspace <workspace> --input <workspace>/assistant/skill_response.json
```

This fills missing annotation fields, preserves existing values, backs up the
annotations, exports tables and marks AI values `reviewed=false`. The browser
automatically loads the drafts when there are no unsaved edits. Ask the player
to inspect and confirm each affected frame using the workbench review button.
Unaccepted drafts remain uncertain and must not be scored as verified facts.

For a mechanics request, read the existing `mechanics/observations.csv`,
`mechanics/adapters.json` and requested frames. Return `mechanics_observations`
row objects using the declared fields: distinct opportunity/mechanism IDs,
actor/target unit IDs, source-video seconds, a positive observation window,
eligibility, outcome, context and source frame/image. Count one cast/proc
opportunity once across screenshots. Unknown eligibility or outcomes are blank,
not misses. Include `inspected_frames`, unknowns and review items.
Use workspace unit IDs and requested image paths; observation times are video
seconds within the requested frames, not values from the in-game clock.

Finish through `assistant-finish` with the exact `request_revision`. It merges
missing cells and new opportunities while preserving existing facts, keeps a
CSV backup, recomputes `mechanics/estimated_models.json` and exports dependent
tables. Conflicting values are retained for review. Do not write the CSV first
and only afterward check whether the request was cancelled. An empty row list
is valid when nothing can be identified; it establishes no trigger probability.
Do not ask non-programmers to author JSON or install a vision package merely to
fill a few observations; use the agent's available visual tools first.

For `kind=analysis`, automatically read the request's `assessment_bundle.zip`
(including the assessment framework, project, annotations, timed state and
tables) before analysis. The workbench button prepares evidence and hands the
task to this Skill; it does not assign provisional player scores. Audit the annotated timeline and produce the declared
`scoring_config.json` from evidence under the framework, without inventing
missing inputs or adjusting weights to match an expected player ranking. Run
`skill-evaluate` for scoring and then `python main.py analyze --workspace
<workspace> --language zh` (or `en`) to refresh the readable workbench report.
The report must include both sides' components, overall scores or explicit
unknowns, chronological evidence and actionable advice supported by the data.
Include the final report Markdown as `analysis_report`, retain the original
`request_revision`, and use `assistant-finish` to save it and notify the browser.
Then tell the player to refresh. A request button does not itself run an AI model.

For `kind=strategy`, use the agent's web-search tools directly, with the patch
and both champions in `context`. Do not substitute the legacy backend search
scraper for this request. Read mechanics references and community matchup
guides, then write a concise synthesis in the request's `language` (`zh` or
`en`). Include applicable conditions and distinguish sourced mechanics,
community advice and your inference. Put the result under `strategy_result`
in the response, with `language`, `text`, `patch`, `blue`, `red` and `sources`
(each source has `title` and `url`). Complete the request with `assistant-finish`;
it saves `assistant/strategy_result_<language>.json`, and the workbench displays the text and
links and fills the strategy text field. Reply to the player when it is ready.
If web access is unavailable, report that in the same language rather than
inventing results or sources.

Automatic public matchup rates are all-level aggregates (`level="all"`,
`level_specific=false`); do not request a player level or reinterpret them as
early-lane strength. The manual rate form retains its reference level.

For `kind=matchup`, the automatic Lolalytics **webpage parser** failed; this is
not a structured public API. Use the agent's web search to inspect actual
statistics pages for the exact requested patch and champion orientation.
Import a `matchup_prior` object alongside `proposals: []`: `patch` (public
patch such as 26.6), `blue_champion_id`, `red_champion_id`, `blue_win_rate`,
`red_win_rate`, `level: "all"`, `level_specific: false`, `tier`, `source` (URL)
and `sample_size`. If the count is unknown use 0 and
`sample_size_unknown: true`; never require the player to supply it. Do not
replace win rate with lane-kill rate or silently use another patch. If no
verified rate is available, import no prior, report an unknown item and retain
the existing prior (default 50:50 when no rate is supplied). Completion replies
and unknown explanations follow the request language.

For an optional color-bar proposal and nearest-neighbour track, run:

```text
python main.py vision-track --workspace <workspace>
```

The result is `vision_candidates.json`. It does not reliably identify hero
versus minion, cannon minions, side in a first-person view, or occluded bars;
the user must map identities and accept centers before table generation.

For optional HUD text proposals (clock, CS, HP/resource and cooldown text),
run `python main.py hud-ocr --workspace <workspace>`. OCR output is raw text
evidence only; it is not automatically assigned to a side or resource field.
Confirm the HUD region and meaning before saving it to the event state.

## Coach follow-up

After the report, continue as a coach and analyst when the user asks why a
score or recommendation was produced. Search current patch notes, champion
mechanics and reputable matchup guides before answering; state the patch,
source and whether a statement is a verified rule, a community heuristic or
an inference from the recorded window. Tie every recommendation to a frame,
absolute receipt, relative state change or execution gap. For an in-progress
game, first confirm the user's side and game time, then answer the core
question— which minion to attack, when to submit damage, when to wait and how
to schedule the next hit—using `plan-window` or a fully verified `game-run`
task. Never turn an unknown cooldown, target identity or visual estimate into
a definite action.

## Accounting rules

- CS, gold, XP, and kill rewards are absolute receipts. A missed last hit is
  not recoverable later.
- Health, mana/energy, cooldowns, summoner spells, and consumables are
  relative state reserves. Normalize each side by its own maximum, floor and
  recoverability before sharing a state component.
- A free-window pressure score requires evidence that the minion death order
  was preserved. Opponent denied receipts and opponent state costs enter the
  pressure ledger; the subject's own cost enters the state ledger.
- Do not count the same health loss, spell hit, gold receipt, or XP receipt in
  two components.
- Apply hard feasibility before quality: version, range, cooldown, control,
  resource, action occupation and deadline constraints.
- Keep strategy and execution at 50:50. Report behaviour quality separately
  from resource outcome so a high-quality action is not erased by one bad
  terminal state.
- Do not infer player skill from identity, rank, prior labels or the outcome
  of the whole match.

## Matchup prior

The following is a generic numerical example, not a claim about any named
champion matchup: if a validated blue/red prior is 47%:53%, its reference
allocation is exactly 47 and 53. With strength (\eta), the disadvantaged blue
side receives `eta * (50 - 47)` in the prior component and red receives the
opposite correction. The main score applies that correction through the
declared 5% matchup component by default. The actual prior must be supplied
with patch and level; provider provenance is retained when available, while
manual rates are marked as user-entered and may have unknown sample size. It
is never inferred from the example cases or from a screenshot. Raw strategy,
weighted correction and adjusted final score are all reported.

## Required output

Return these artifacts:

- `skill_audit.json`
- `scoring_config.json`
- `skill_result.json`
- `receipt_ledger.csv`
- `state_ledger.csv`
- `assessment_report.md`
- `uncertainty_report.md`

If a required event cannot be identified, preserve it as `unknown` and give a
bounded interval. Never fill it with zero merely to obtain a single score.
