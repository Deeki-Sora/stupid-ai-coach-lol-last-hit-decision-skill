# LOL Short-Window Last-Hit Decision Evaluation Framework

[中文](README.md)

**Official Chinese SKILL name: 愚蠢的AI教练——一个用来分析LOL真实对局中的补兵决策的SKILL**

**Install and load the SKILL**

Keep the installation in two separate locations:

| Content | Location |
| --- | --- |
| Complete repository: workbench, model weights, training data and documentation | A normal project folder you choose, outside the AI tool's `skills/` directory |
| Lightweight Skill package: instructions, launcher and small configuration files | The AI tool's user-level `skills/lol-short-window-evaluator/` folder |

From the project folder where you want to keep the complete repository, run:

```sh
git clone https://github.com/Deeki-Sora/stupid-ai-coach-lol-last-hit-decision-skill.git
cd stupid-ai-coach-lol-last-hit-decision-skill
```

Next, copy only [`skills/lol-short-window-evaluator/`](skills/lol-short-window-evaluator/) from the repository into your AI tool's user-level `skills/` directory. This package contains instructions, a launcher and small configuration files, totaling tens of KB. The workbench, weights and training data stay in the separate repository.

The following examples use Codex. Run them from the downloaded repository directory. For another AI tool, replace the destination with that tool's user-level `skills/` directory.

Windows PowerShell:

```powershell
$skillDir = Join-Path $env:USERPROFILE '.codex\skills\lol-short-window-evaluator'
New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
Copy-Item -Path '.\skills\lol-short-window-evaluator\*' -Destination $skillDir -Recurse -Force
Set-Content -LiteralPath (Join-Path $skillDir 'repo_path.txt') -Value (Get-Location).Path -Encoding UTF8
```

macOS / Linux:

```sh
skill_dir="$HOME/.codex/skills/lol-short-window-evaluator"
mkdir -p "$skill_dir"
cp -R skills/lol-short-window-evaluator/. "$skill_dir/"
pwd > "$skill_dir/repo_path.txt"
```

The generated `repo_path.txt` records the complete repository's location on your computer so that the Skill can call the workbench there. Adjust the destination if you use a custom Codex user directory. Update the recorded path after moving the complete repository.

Before first use, prepare Python and FFmpeg as described in section 2, then reload the installed `lol-short-window-evaluator` in your AI tool. Enter `run` or “运行” to receive the workbench address. To update, run `git pull --ff-only` from the external repository directory, then repeat the copy commands for your operating system to update the installed lightweight Skill too.

## 1. Introduction

Starting from the information visible to each player, this framework reviews attack targets, last-hit timing, the ability to take subsequent last hits, and the health, mana, cooldowns and time spent obtaining resources within one minion wave or a short window of about 20–30 seconds. It assesses both sides separately and distinguishes decision quality from execution, supporting conclusions with explicit inputs, event sequences and uncertainty intervals.

**[Chinese framework](LOL_短时补兵决策评估框架_v0.91.md)** · **[English framework](LOL_Short_Window_Last_Hit_Decision_Evaluation_Framework_v0.91.md)**

The accompanying workbench turns recordings into reviewable screenshots, unit annotations, distance measurements and action tables, then exports a standalone assessment bundle for a person or AI tool to review. It supports arbitrary lane clips without relying on another project, fixed champions, external project documents or machine-specific paths. The framework covers short-window decisions, alternative choices and event simulation; the workbench's automation is described below.

| Stage | Workbench | Person / AI |
| --- | --- | --- |
| Video sampling | Extract screenshots from a selected interval, record actual frame times and save images | Choose a clip that can be observed clearly |
| Unit location | Optionally use YOLO to find heroes, minions and full health-bar centers; provide basic visual candidates when unavailable | Check teams, minion types, numbers, positions and deaths |
| Distance and action tables | Recalculate distances, movement and annotated action intervals by unit number; export tables | Record actions, targets, attack stages, times and state; review coordinates |
| Champion and strategy inputs | Champion selection in Chinese or English, patch data, rune pages, timed level/skill/item records, parameters and strategy storage | Confirm actual selections and complete inventories; verify applicable mechanics; optionally supply strategy notes |
| Scoring and future choices | Prepare assessment material and display the completed report | Have the Skill read the material, calculate both sides' scores, explain events and suggest improvements |
| Probability observations | Deduplicate opportunities and calculate hit/proc success rates, frequencies and missing coverage | Check skill, passive and rune eligibility and applicability |
| Optional short-window simulation | Event branches, a common valid endpoint, conditional scenario sampling and both sides' resources/costs | Supply valid rules, initial state, candidate actions and complex mechanic adaptations |
| Optional finite game analysis | SciPy zero-sum proxy or Nashpy independent-payoff solving | Declare payoff weights, boundary values and the applicable window |

## 2. Required tools and optional components

Required: Python 3.11+, FFmpeg (including ffprobe), and a local browser. The basic workbench uses only the Python standard library. Reopen the terminal after installing FFmpeg:

```sh
# Windows
winget install --id Gyan.FFmpeg -e
# macOS
brew install ffmpeg
# Ubuntu / Debian
sudo apt-get install ffmpeg
```

Check the tools and start the workbench:

```sh
python --version
ffmpeg -version
ffprobe -version
python main.py
```

With the `lol-short-window-evaluator` Skill loaded, these short commands control the local workbench:

| Chinese command | English command | Action |
| --- | --- | --- |
| `运行`, `运行工作台`, `运行服务` | `run`, `run workbench`, `run service` | Start the workbench and provide its address |
| `停止服务`, `停止工作台` | `stop service`, `stop workbench` | Stop the workbench |
| `重启工作台`, `重启服务` | `restart workbench`, `restart service` | Restart the workbench and provide its address |
| `工作台地址`, `服务状态` | `workbench address`, `service status` | Show whether the workbench is running and its address |
| `处理工作台请求` | `process workbench request` | Process the current request and save the results to the workbench |
| `标注当前帧`, `标注所有帧` | `annotate current frame`, `annotate all frames` | Inspect screenshots and fill annotations within the requested scope |
| `填写当前帧配置`, `填写所有帧配置` | `fill current frame configuration`, `fill all frame configurations` | Fill the levels, items and state for the requested screenshots |
| `查询工作台胜率` | `fetch workbench matchup rates` | Find and save the requested matchup win rates |
| `查询工作台攻略` | `search workbench guides` | Find and save guides with sources |
| `分析当前对局` | `analyze current match` | Read the assessment material and save the analysis report |
| `填写观察表`, `请 Skill 协助填写观察表` | `fill observation table` | Inspect casts and trigger opportunities, fill observations and recalculate statistics |
| `刷新工作区观察表`, `重新统计观察表` | `refresh observation table`, `recalculate observations` | Reload saved observations and recalculate statistics |
| `生成下一短时窗口计划` | `plan next short window` | Plan the next last-hit window from a specified screenshot and side |
| `以当前帧生成任务`, `生成推演任务` | `draft task at current frame`, `draft planning task` | Prepare a simulation draft from a specified screenshot |
| `将统计模型写入任务` | `apply observation statistics to task` | Add observations to the saved draft; their applicability still needs checking |
| `运行已核验任务` | `run verified task` | Run a checked and explicitly enabled simulation task |
| `取消工作台请求` | `cancel workbench request` | Cancel the current request and stop further imports |
| `工作台请求状态` | `workbench request status` | Show whether the current request is being processed or completed |

For filling, searches and analysis, first press the corresponding webpage button, then enter a command above in the AI conversation with the Skill loaded. You can also use `process workbench request` for any current request. The AI tool needs read/write access to the local workspace. It saves the results and reports completed fields, unknowns and review items; refresh the workbench to see them without importing files manually.

Refreshing observations, making short-window plans and working with simulation drafts can also be requested directly in chat. Specify the frame number when a screenshot is needed, for example, "Plan the next short window for blue from frame 10." If the AI cannot identify the current frame, it will check first rather than substituting the first screenshot or an old request. Refresh the page to see saved plans, drafts and simulation results.

Optional colored-region candidates (the full health-bar center still needs confirmation):

```sh
python -m pip install -r requirements-vision.txt
python main.py sample --video input_videos/match.mp4 --start 60 --end 90 --step 0.3 --output runs/demo --proposals --review
```

Optional YOLO annotation (let the computer find heroes, minions and health bars):

```sh
python -m pip install -r requirements-vision-optional.txt
python main.py vision-status
```

This feature currently requires a usable NVIDIA GPU and matching CUDA/PyTorch support. The second command above reports whether the computer is ready. Select **Use local YOLO to identify and track units automatically** when choosing a recording to use the recognition files supplied with the project. If unchecked or unable to run, the workbench uses basic Track to outline possible health bars for you to identify. Check all automatic results.

Model weights are in `vision/models/yolo11n/`, and training images and labels are in `vision/training/`. See [training guidance](docs/vision_training.md) to add samples or continue training.

Optional matrix solvers (unnecessary when solving is disabled):

```sh
python -m pip install -r requirements-game.txt
```

The workbench provides [SciPy](https://pypi.org/project/scipy/) and [Nashpy](https://pypi.org/project/nashpy/) download links and installation status; it does not install them automatically. Built-in event simulation and probability statistics use only the standard library. SciPy / HiGHS handles finite zero-sum proxies; Nashpy handles independent-payoff matrices. External extensions such as SimPy can be installed with requirements-algorithms.txt. See [dependency guidance](docs/algorithm_dependencies.md). FFmpeg handles video processing only.

Official data queries require HTTPS. If Python lacks root certificates, install the optional certificate package with `python -m pip install -r requirements-data.txt`. If a query fails, you can verify the information yourself and enter it manually; sampling and tables remain available.

The workbench supports Chinese / English display. Built-in champion, rune and item selectors retrieve patch-specific Riot Data Dragon data and the corresponding CommunityDragon stat-shard catalog through standard-library connections; no standalone simulator is required. Downloads are cached in the workspace, included in the assessment bundle and reusable offline. [ARAMonly](https://www.aramonly.com/lol-runes-builder/) optionally supplies rune/item names and IDs through share links; it does not supply champion selections or game values. Use the built-in selectors when the external site is unavailable. See [configuration selection and external connections](docs/loadout_selection.md).

Minion information can be cached separately with `python main.py fetch-minions --version 16.6.1 --output catalogs/16.6.1/minion_profiles.json`. Patch fields that cannot be mapped reliably fall back to a generic profile marked `verified=false`. Special champions do not require dedicated Python algorithms: the [mechanic profile adapters](docs/parameter_algorithm_mapping.md) describe multistage skills, triggers and conditional effects.

After champion selection, the workbench builds and reads the corresponding Riot Codex page automatically; no manual search or copying is needed. Results are cached under the workspace's `references/`. A patch mismatch, unavailable page or unreadable field produces a warning while local patch data remains available. Saved page text can also be imported with `python main.py import-codex ...`. All Codex results remain unverified references and must be incorporated into a generic mechanic profile before simulation.

## 3. User guide

### 3.1 Choose a recording and a short section to review

Open the workbench as described above and select **中文** or **English**. Click **Choose video** to find a recording on your computer, or **Choose folder** and select a recording from the list. You can leave the original recording where it is; no copying or uploading is needed.

Enter the start and end times. These refer to the video player's clock: `01:00` to `01:30` takes the section from one minute to one minute thirty seconds into the video, which may differ from the in-game clock. Start with a short section where the last hits are clearly visible so that checking it is easier. The end must follow the start and stay within the recording's total duration.

The sampling interval is how often a screenshot is taken. Choose `0.1` seconds for more closely spaced pictures or `0.5` seconds for fewer pictures; the default is `0.3` seconds. Enable **Use local YOLO to identify and track units automatically** to let the computer find units. Manual annotation remains available when the computer cannot use this feature.

Check the output folder, click **Generate screenshots and open workbench**, and wait for completion. By default, a new folder beside the original recording holds the screenshots and your entries; you can choose another location.

### 3.2 Check positions and actions on Evidence

Use **Previous frame**, **Next frame**, or the slider to browse screenshots. The keyboard's left and right arrows also work when you are not typing in a field. A frame here means one screenshot. Increase **Zoom** when details are hard to see.

Choose a hero or minion under **Selected unit**, then check its health-bar position. To add a position manually, click the **middle of the complete health bar**, or choose **Drag a complete health-bar box** under **Click mode** and draw around the whole bar. When health drops, include the black, depleted portion when finding the center; use the full bar's center rather than the middle of the remaining colored fill.

Enter only the in-game time, action, attack target and attack stage that the picture supports. The attack stage describes whether the attack is winding up, flying toward its target, hitting, or recovering. Use seconds from the recording for action start/end times. Leave anything obscured, unclear or uncertain blank.

Check automatic annotations for wrong teams, minion types or positions, and for two minions being treated as one. After checking Skill-filled results, expand **AI-assisted annotation** and click **Confirm recognition for this frame**. After manually entering an action, click **Record action**, then **Save** before leaving. **Automatic frame state summary** starts closed; open it when needed.

### 3.3 Add minions and handle missing or mistaken units

If a minion is missing, expand **Roster and new units**, choose its team, type and wave number, then click **Add unit**. Leave its number blank to let the workbench assign one. Keep the same number for the same minion in adjacent pictures; use new numbers for a new wave.

Select a unit and expand **Manage current unit**, then choose the action that matches what happened:

| What you see | Button to use |
| --- | --- |
| Temporarily hidden or outside the picture, with death unconfirmed | **Not visible in this frame**, which hides it in this picture only |
| The unit appears again | Enable **Show hidden or dead units**, select it, then click **Show in this frame** |
| You can confirm the unit has died | **Confirm death from this frame**, which stops recording it in later pictures |
| The unit should never have been added | **Delete mistaken unit**, which removes its records throughout the recording after keeping a backup |

The number freed by deleting a mistaken unit can be used again. A real unit confirmed dead keeps its number.

To view distances, expand **Select distance targets individually**, select the minions to measure, and click **Apply checked units**. The distance between the two heroes is always recorded. Minion distances run from each hero to enemy minions. Both positions must be entered before a result is available. Comparing distances within one picture needs no map origin. To compare how far a unit moved, mark the same fixed ground landmark in each picture so that camera movement can be accounted for.

### 3.4 Enter both sides' information on Configuration

First enter the recording's game patch and wait for its information to load. Click **Load patch catalog** if it does not appear automatically. Choose both champions, rune pages, stat shards and summoner spells, then click **Save and lock champions/runes**. These choices apply throughout the recording. To correct a choice, enable **Edit / correct fixed match configuration** first. Read the warning about clearing records before changing the patch or champion.

Return to the screenshot you want to describe, then open this page. Expand **Level, skills, items and current state** for each side and enter the level, skill ranks, items, health, mana or energy, cooldowns and other known details at that moment. Each entry saves automatically. Wait for **Saved and calculated** before changing pictures. Mark the inventory complete only after checking all the items.

Read the time labels near the bottom to confirm which screenshot, video time and known in-game time your entries belong to. When you change pictures, enter what is true at the new moment; unrecorded details stay blank. **Record this state at current frame** lets you save again manually, while **Load state for current frame** reloads the entries already saved for that picture.

**Automatic stats and manual overrides** calculates values from the patch, current level, fixed item bonuses and stat shards. Check temporary item or rune effects separately. If automatic values are missing, first check that the patch, champions, levels and items have been saved. Enter a value in the manual column only when you can confirm the actual number.

For matchup win rates, open **Fetch matchup win rates** and click **Fetch and save matchup rates**. Results come from public statistics pages and cover all levels together; the automatic query needs no level entry. If the webpage cannot be read, follow the page's instructions to ask the Skill to find the rates. A reference level is needed only for manual rate entry.

For champion tips, open **Search champion mechanics and lane guides**, click **Search and save strategy references**, then follow the page's instructions to have the Skill find and summarize advice. The completed advice returns in the same place with sources. Chinese pages receive Chinese advice; English pages receive English advice.

### 3.5 Ask the Skill to fill entries, or cancel a task

At the top of Evidence, choose **Ask SKILL to fill the current frame** or **Ask SKILL to fill all frames**. Configuration has corresponding buttons for levels, items and state in the current picture or all pictures. Choose the patch and both champions before requesting configuration help.

The current frame is the screenshot displayed when you press the request button. The request records its frame ID, video time and known in-game time. The AI confirms these details before processing. Browsing to another screenshot afterward does not change which frame receives the results.

After clicking, enter `process workbench request` or the matching annotation/configuration command from the table in your AI conversation. The AI reads the screenshots and saves the results to the workbench. Refresh and editing controls pause until an all-frame request completes or is cancelled. Wait until the Skill reports what was filled, what remains unknown and what needs review, then refresh to see the entries. To stop, click **Cancel Skill request** beside the request buttons or enter `cancel workbench request` in the conversation. Saved entries remain, and further results will no longer be filled in.

Once the results appear, check coordinates, actions and configuration before confirming them. Leave unclear health bars, unseen items and uncertain cooldowns blank.

Each import also updates the event, distance, action and death tables, so later assessment uses the updated records. Export the assessment bundle again after changing records to take the latest material with you.

### 3.6 Read the analysis on Planning

Click **Run analysis task** to gather the current annotations and configuration. Then enter `analyze current match` in your AI conversation. The Skill reads the material, analyzes it and saves the report; refresh this page after completion to view it.

A report is returned even when evidence is incomplete; you do not need to fill every field first. It includes supported event analysis and improvement advice. Component scores, overall scores and other unsupported details remain unknown, with an explanation of what is missing. Return to the corresponding screenshot to check a recommendation. After correcting or adding records, run the analysis again. You can also download an available report.

### 3.7 Save results and use short-window analysis when needed

On Evidence, click **Save and export assessment bundle**, wait for the download links to appear, then click `assessment_bundle.zip` to download screenshots, entries, tables and assessment material. If you only need one table, click its link instead. Use the complete bundle if another AI tool will continue the review. Export again after changing records so that the copy you take contains the latest entries.

The preceding steps cover ordinary replay review. To compare choices such as attacking a minion now or waiting, open **Advanced: short-window events and game analysis** and enable the option inside. First choose the starting screenshot and the player's side, then use **Plan next short window** or **Draft task at current frame**. Check damage, distance, cooldowns and both sides' actions. Click **Run verified task** only after confirming that the necessary information is available.

To record skill hits, passive activations or rune triggers, open the observation section, click **Ask Skill to fill observations**, then enter `fill observation table` or the button's full wording in your AI conversation. The Skill checks the sampled screenshots, saves supported observations and recalculates statistics. Count each cast or trigger once, and leave unclear outcomes blank. Refresh after completion; use **Cancel Skill request** beside the button to stop. The detailed short-window guide below explains these options further.

To look up a button, reopen saved records or edit tables, see the **[workbench guide](docs/workbench_guide.md)**. To hand your records to another AI tool, see **[workflow and data formats](docs/workflow.md)**. To compare different attack choices in more detail, see **[short-window analysis](docs/short_horizon.md)**.

To learn how attributes and records affect scores, see **[how scoring uses your information](docs/parameter_algorithm_mapping.md)**.

For champion, rune and item selection, saving state at different times, and using ARAMonly share links, see the **[selection guide](docs/loadout_selection.md)**. Choices shared throughout the recording, such as champions and runes, can be exported and imported again. Before using selections from another website, check that the workbench supports its sharing method.

You can find champions by Chinese name, English name, game-data ID or common nickname (for example, “大头” in Chinese); see [name aliases](docs/name_aliases.md).

## 4. Other notes

Health-bar centers are screen measurements. Game distance under a single scale is an estimate affected by projection, zoom and vertical health-bar offsets; it is not the actual attack-range check. Missing coordinates are not replaced with invented distances or actions. Timing precision is limited by the video's frame rate.

Scores require verified inputs, evidence and fixed rules. The workbench does not independently establish a reliable player-skill rating or provide in-game control or live capture; other AI projects can connect through JSON/CSV. Built-in simulation is a conditional model within an explicit mechanic scope, not a complete game-server simulator for every champion. Observed probabilities require checks before applying them elsewhere. Scenario quantiles do not automatically equal confidence intervals or win rates; arbitrary probabilities must not conceal unimplemented mechanics.

General scripts include the [entry point](main.py), [sampling and tables](workbench/core.py), [pixel distances](algorithms/pixel_distance.py), [relative resource/state accounting and risk scoring](algorithms/risk_value.py), [event simulation](algorithms/short_horizon.py), [probability and effect adaptation](algorithms/probabilistic_mechanics.py), [mechanic observations](workbench/mechanic_observations.py), [optional game analysis](workbench/game_tools.py) and the [general event queue](algorithms/event_queue.py).

Patch-specific data and selections use the [catalog connection](workbench/catalog.py), [timed selection handling](workbench/loadouts.py), [visual selectors](workbench/loadouts.js), [external share-link adaptation](workbench/external_selectors.py) and the [external-page return adapter](integrations/selector_bridge.js).

See the [file manifest](repository_manifest.json) for the supplied files and their checksums.

Original framework documents and code use [MIT](LICENSE). See [LICENSE_SCOPE.md](LICENSE_SCOPE.md) for third-party material.

LOL Short-Window Last-Hit Decision Evaluation Framework is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.
