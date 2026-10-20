# 愚蠢的AI教练——一个用来分析LOL真实对局中的补兵决策的SKILL

# lol-short-window-evaluator

This is the lightweight Skill package for the LOL short-window evaluation
framework. Only this directory belongs in an AI tool's user-level `skills/`
folder. The complete repository, workbench, weights and training data belong
in a separate project folder. This package contains instructions, a launcher
and small configuration files; it does not contain the runtime or models.

First clone the complete repository into a separate project folder:

```sh
git clone https://github.com/Deeki-Sora/stupid-ai-coach-lol-last-hit-decision-skill.git
cd stupid-ai-coach-lol-last-hit-decision-skill
```

Then copy only `skills/lol-short-window-evaluator/` into your AI tool's user
Skill directory. Create `repo_path.txt` beside the installed `runner.py`,
containing the absolute path of the external repository directory that holds
`main.py` and `workbench/`. Alternatively, set `LOL_SHORT_WINDOW_REPO` in the
environment used by the AI tool. The environment setting takes precedence.
See the complete repository's `README.en.md` for Windows and macOS/Linux
installation commands.

To update, run `git pull --ff-only` in the external repository and copy this
small package again. Update `repo_path.txt` if the repository moves. Reload
the Skill in the AI tool after updating it. Hosts without automatic Skill
support can load `SKILL.md` directly and use the same external repository.

The repository workbench remains the measurement tool. The skill invokes its
exporter and the `skill-audit`/`skill-evaluate` backend commands; it does not
recreate sampling or distance calculations in prose.

After explicitly loading the Skill, users may say `运行工作台`, `运行服务`,
`停止服务`, `重启工作台`, or the corresponding English phrases. The Skill
executes the background service command and replies with the exact active URL.
`dialogue_templates.md` provides bilingual replies for service control,
workbench requests, annotation fallback, analysis completion and errors. Its
placeholders must be filled from actual command or request output.

After pressing a workbench request button, send `处理工作台请求` / `process
workbench request` in the AI conversation. Specific commands include
`标注当前帧`, `标注所有帧`, `填写当前帧配置`, `填写所有帧配置`,
`查询工作台胜率`, `查询工作台攻略` and `分析当前对局`; see the bilingual
command table in `SKILL.md`. The Skill discovers the current request, uses
the agent's vision or web tools, and saves results through `assistant-finish`.
The player refreshes the workbench to review them. The AI tool needs access
to the local workspace; a webpage request button alone does not start a chat.
Start the guided local UI with `python main.py start`; it opens the browser
workbench and the Skill should explain each next field in the chat. After the
two champions and patch are fixed, `search-strategy` stores optional web
mechanics and matchup references. If a clip is unfinished, `plan-window`
answers the next-minion/attack/wait question as far as the supplied evidence
allows. After scoring, the backend writes Markdown player reports under
`assessment/`.

For an installed Skill directory, use its `runner.py` as the entry point.
It locates the external repository through `LOL_SHORT_WINDOW_REPO` or the
adjacent `repo_path.txt`. Inside the complete repository it also discovers
`main.py` automatically. All `python main.py ...` examples assume the current
directory is the external repository; the installed runner handles that
directory change for you:

```text
python skills/lol-short-window-evaluator/runner.py skill-audit --workspace <workspace> --output <workspace>/assessment/skill_audit.json
```

The caller supplies the video, workbench directory, manual action labels, and
any auditable version-level matchup prior. The backend retains all workbench
artifacts as structured inputs or evidence references.

If the public matchup provider is unavailable, the loadout panel offers a
manual fallback. Enter the patch, event level, and optional blue/red rates;
blank rates remain 50:50. Tier may be left blank and sample size is recorded
as unknown. The equivalent command is:

```text
python main.py save-matchup-prior --workspace <workspace> --version 26.20 --blue Yasuo --red Veigar --level 3
```
