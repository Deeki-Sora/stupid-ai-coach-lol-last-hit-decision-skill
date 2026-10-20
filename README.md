# LOL 短时补兵决策评估框架

[English](README.en.md)

**SKILL：愚蠢的AI教练——一个用来分析LOL真实对局中的补兵决策的SKILL**

**安装与加载 SKILL**

安装时分开放置两部分：

| 内容 | 存放位置 |
| --- | --- |
| 完整仓库：工作台、模型权重、训练集和文档 | 自己选择的普通项目文件夹，放在 AI 工具的 `skills/` 目录之外 |
| 轻量 Skill 包：说明、启动文件和少量配置 | AI 工具在系统用户目录下的 `skills/lol-short-window-evaluator/` 文件夹 |

先在准备存放完整仓库的项目文件夹中运行：

```sh
git clone https://github.com/Deeki-Sora/stupid-ai-coach-lol-last-hit-decision-skill.git
cd stupid-ai-coach-lol-last-hit-decision-skill
```

接着只把仓库里的 [`skills/lol-short-window-evaluator/`](skills/lol-short-window-evaluator/) 复制到 AI 工具的用户 `skills/` 目录。这个包只有说明、启动文件和少量配置，大小为几十 KB；工作台、权重和训练集留在外面的完整仓库中。

以下以 Codex 为例，在刚下载的仓库目录中执行。其他 AI 工具请把目标位置换成该工具的用户 `skills/` 目录。

Windows PowerShell：

```powershell
$skillDir = Join-Path $env:USERPROFILE '.codex\skills\lol-short-window-evaluator'
New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
Copy-Item -Path '.\skills\lol-short-window-evaluator\*' -Destination $skillDir -Recurse -Force
Set-Content -LiteralPath (Join-Path $skillDir 'repo_path.txt') -Value (Get-Location).Path -Encoding UTF8
```

macOS / Linux：

```sh
skill_dir="$HOME/.codex/skills/lol-short-window-evaluator"
mkdir -p "$skill_dir"
cp -R skills/lol-short-window-evaluator/. "$skill_dir/"
pwd > "$skill_dir/repo_path.txt"
```

上面的 `repo_path.txt` 只记录完整仓库在这台电脑上的位置，Skill 会按这个位置调用工作台。使用自定义 Codex 用户目录时，也请相应替换目标路径。移动完整仓库后，需要更新这个文件中的路径。

首次使用先按第 2 节准备 Python 和 FFmpeg，再在 AI 工具中重新加载已安装的 `lol-short-window-evaluator`，输入“运行”或 `run` 即可取得工作台打开地址。更新时，在外部仓库目录运行 `git pull --ff-only`，再执行一次对应系统的复制命令，让用户目录中的轻量 Skill 包也同步更新。

## 1. 框架简介

以双方各自可见的信息为起点，在一波小兵或约 20–30 秒的短时窗口内，评价攻击目标、补兵时机、后续补刀可行性，以及资源取得所需的生命、蓝量、冷却和时间成本。双方分别评估，区分策略选择与执行质量；用明确参数、事件链和不确定区间支持结论。

**[中文框架](LOL_短时补兵决策评估框架_v0.91.md)** · **[English framework](LOL_Short_Window_Last_Hit_Decision_Evaluation_Framework_v0.91.md)**

配套工作台将录像变成可核验的截图、单位标注、距离和动作表，再导出独立资料包供人工或 AI 工具评估。它支持任意对线片段，不依赖其他项目、固定英雄、外部工程文档或本机路径。框架公式覆盖短时决策、反事实和事件推演；工具的自动化范围见下表。

| 环节 | 工作台负责 | 人工 / AI 负责 |
| --- | --- | --- |
| 视频采样 | 时间段截取式采样、实际帧时间记录、保存截图 | 选择可观察片段 |
| 单位定位 | 可选 YOLO 自动寻找英雄、小兵和完整血条中心；不可用时提供基础画面候选 | 检查阵营、小兵种类、编号、位置和死亡情况 |
| 距离与动作表 | 按单位 ID 重算距离、位移、已标注动作间隔，导出表格 | 填写动作、目标、相位、时间与状态，复核坐标 |
| 英雄与策略预输入 | 中英文名称选择、版本目录、符文页、按时间记录的等级/加点/装备、参数与策略存储 | 确认实际配置与背包完整性；核验有效机制；可选策略文字 |
| 评分与未来分支 | 准备评估资料，在页面显示完成后的报告 | 由 Skill 读取资料，计算双方评分，解释事件并提出改进建议 |
| 概率观察 | 独立机会去重、命中/触发成功率、频率、缺失覆盖 | 核验技能、被动、符文的资格与适用条件 |
| 可选短时推演 | 事件分支、共同有效终点、条件情景抽样、双方资源/成本 | 提供有效游戏规则、初态、候选及复杂机制适配 |
| 可选有限博弈 | SciPy 零和代理或 Nashpy 双方独立收益求解 | 声明收益权重、边界价值和适用窗口 |

## 2. 必需工具与可选项

必需：Python 3.11+、FFmpeg（含 ffprobe）、本地浏览器。基础工作台仅使用 Python 标准库。安装 FFmpeg 后重新打开终端：

```sh
# Windows
winget install --id Gyan.FFmpeg -e
# macOS
brew install ffmpeg
# Ubuntu / Debian
sudo apt-get install ffmpeg
```

检查并启动：

```sh
python --version
ffmpeg -version
ffprobe -version
python main.py
```

已加载 `lol-short-window-evaluator` Skill 时，可用以下简短命令控制本地工作台：

| 中文命令 | English command | 作用 |
| --- | --- | --- |
| `运行`、`运行工作台`、`运行服务` | `run`, `run workbench`, `run service` | 启动工作台并提供打开地址 |
| `停止服务`、`停止工作台` | `stop service`, `stop workbench` | 停止工作台 |
| `重启工作台`、`重启服务` | `restart workbench`, `restart service` | 重新启动并提供打开地址 |
| `工作台地址`、`服务状态` | `workbench address`, `service status` | 查看工作台是否正在运行及其打开地址 |
| `处理工作台请求` | `process workbench request` | 处理当前待办，完成后直接回填工作台 |
| `标注当前帧`、`标注所有帧` | `annotate current frame`, `annotate all frames` | 按已发起的范围识别截图并填写标注 |
| `填写当前帧配置`、`填写所有帧配置` | `fill current frame configuration`, `fill all frame configurations` | 填写截图对应的等级、装备和状态 |
| `查询工作台胜率` | `fetch workbench matchup rates` | 查找并回填待处理的对位胜率 |
| `查询工作台攻略` | `search workbench guides` | 查找并回填带来源的攻略 |
| `分析当前对局` | `analyze current match` | 读取评估资料并回填分析报告 |
| `取消工作台请求` | `cancel workbench request` | 取消当前待办，停止后续回填 |
| `工作台请求状态` | `workbench request status` | 查看当前请求是否正在处理或已经完成 |

填写、查询和分析时，先在网页按相应按钮，再回到已加载 Skill 的 AI 对话中输入上表命令。也可以统一输入“处理工作台请求”，AI 会读取当前待办。AI 工具需要能读取和修改本机工作区；处理完成后会告知已填写内容、未知项和复核项，刷新工作台即可查看，无需手动导入结果。

可选颜色区域候选（仍须确认完整血条中心）：

```sh
python -m pip install -r requirements-vision.txt
python main.py sample --video input_videos/match.mp4 --start 60 --end 90 --step 0.3 --output runs/demo --proposals --review
```

可选 YOLO 自动标注（让电脑自动寻找英雄、小兵和血条）：

```sh
python -m pip install -r requirements-vision-optional.txt
python main.py vision-status
```

目前这项功能需要电脑有可用的 NVIDIA 显卡和相应的 CUDA、PyTorch 支持。上面的第二条命令可查看电脑是否准备就绪。选择录像时勾选“使用本地 YOLO 自动识别并追踪单位”，工作台会使用随项目提供的识别文件；未勾选或无法运行时，改用基础 Track，先框出可能的血条位置，再由使用者确认对应单位。自动识别结果都需要检查。

模型权重放在 `vision/models/yolo11n/`，训练原图和标注放在 `vision/training/`。需要补充样本或继续训练时，见 [训练资料说明](docs/vision_training.md)。

可选矩阵求解包（不开启求解无需安装）：

```sh
python -m pip install -r requirements-game.txt
```

工作台提供 [SciPy 下载链接](https://pypi.org/project/scipy/)、[Nashpy 下载链接](https://pypi.org/project/nashpy/)和安装状态，不自动下载安装。内置事件推演与概率统计仅需标准库；SciPy / HiGHS 用于有限零和代理，Nashpy 用于双方独立收益矩阵。SimPy 等外部扩展可另用 requirements-algorithms.txt 安装。各工具用途见 [依赖说明](docs/algorithm_dependencies.md)。FFmpeg 只负责视频处理。

官方数据查询需要 HTTPS 连接。Python 环境缺少根证书时，可安装可选证书包：`python -m pip install -r requirements-data.txt`。查询失败也可自行核验资料后手动填写，不影响采样和表格功能。

工作台提供中文 / English 界面切换。内置英雄、符文和装备选择器使用标准库接口获取锁定版本的 Riot Data Dragon 数据，以及同补丁 CommunityDragon 属性碎片目录；无需安装独立模拟器。下载后缓存到工作区并随评估包导出，可离线复用。[ARAMonly](https://www.aramonly.com/lol-runes-builder/)是可选的名称/ID 选择入口，通过分享链接导入符文、装备，不负责英雄选择或游戏数值。外部站点不可用时继续使用内置选择器。详情见 [配置选择与外部接口](docs/loadout_selection.md)。

小兵资料可用 `python main.py fetch-minions --version 16.6.1 --output catalogs/16.6.1/minion_profiles.json` 单独缓存；无法稳定映射的版本字段会退回带有 `verified=false` 标记的通用 profile。特殊英雄不需要专用 Python 算法，使用 [机制 profile](docs/parameter_algorithm_mapping.md) 的数据适配器描述多段技能、触发器和条件效果。

选择英雄后，工作台会自动构造并读取对应的 Riot Codex 页面，不需要用户自行搜索或复制文本；结果缓存到工作区 `references/`。补丁不匹配、网页不可用或字段无法解析时，页面显示警告并继续使用本地版本目录。保存的页面文本也可用 `python main.py import-codex ...` 手动导入；所有 Codex 结果仍是未核验参考，需填入通用机制 profile 后才能参与仿真。

## 3. 操作指南

### 3.1 选择录像，取出要分析的一小段

按上面的方式打开工作台，选择页面上的“中文”或“English”。点击“选择录像文件”，找到电脑中的录像；也可以点击“选择文件夹”，再从列表里选一段录像。原录像可以留在原来的位置，无需复制或上传。

填写“开始时间”和“结束时间”。这里用的是视频播放器上的时间，例如 `01:00` 到 `01:30` 表示取出录像第 1 分钟到第 1 分 30 秒的画面，不一定对应游戏内时钟。先取一段能看清补刀过程的短片，检查起来会更方便。结束时间必须晚于开始时间，并且不能超过录像总时长。

“采样间隔”就是每隔多久截一张图：选 `0.1` 秒，画面更密；选 `0.5` 秒，图片更少；默认是 `0.3` 秒。需要电脑自动寻找单位时，勾选“使用本地 YOLO 自动识别并追踪单位”；电脑无法使用这项功能时，仍可继续手动标注。

确认“保存目录”，点击“生成截图并进入工作台”，等待页面显示完成。默认会在原录像旁边新建文件夹，保存截图和本次填写内容；也可以另选保存位置。

### 3.2 在“录像与标注”里检查位置和动作

用“上一帧”“下一帧”或滑块查看截图；没有在输入框里打字时，也可以按键盘左右方向键。一帧就是这里的一张截图。看不清时把“缩放”调大。

先在“当前单位”选择英雄或小兵，再检查它的血条位置。手动补位置时，直接点击**完整血条的正中间**；也可以在“点击模式”选择“拖框选完整血条”，把整根血条框住。血量减少后，中心仍按整根血条计算，包括已经变黑的部分，不能只点剩余彩色部分的中间。

填写画面能确认的“游戏内时间”、动作、攻击目标和攻击阶段。攻击阶段指攻击刚出手、弹道飞行、命中或收招的哪一步。需要记动作起止时间时，填写录像中的秒数。看不清、被遮挡或无法判断的内容留空。

自动标注也要检查有没有认错阵营、兵种、位置，或把两只小兵当成同一只。检查 Skill 填写的结果后，展开“AI 辅助标注”，点击“确认当前帧识别结果”。手动填动作后点击“记录此帧动作”，离开前再点“保存”。“当前帧自动状态摘要”默认收起，需要查看时再展开。

### 3.3 添加小兵、处理消失或误建的单位

缺少小兵时，展开“单位列表与新增单位”，选择阵营、兵种和兵线波次，再点击“加入单位”。编号可以留空让工作台生成；同一只小兵在相邻截图中应使用同一个编号，新一波小兵使用新的编号。

选中单位后，展开“管理当前单位”，按实际情况操作：

| 画面情况 | 使用哪个按钮 |
| --- | --- |
| 暂时被挡住或走出画面，不能确定死亡 | “当前帧不可见”，只隐藏这一张截图里的单位 |
| 单位重新出现在画面中 | 勾选“显示隐藏或阵亡的单位”，选中它，再点“恢复当前帧显示” |
| 明确看到单位已经死亡 | “确认此帧起阵亡”，后面的截图不再继续记录它 |
| 原本就不该添加这只单位 | “删除误建单位”，删除它在整段录像中的记录；工作台会先留备份 |

删除误建单位后，空出来的编号可以重新使用；已经确认阵亡的真实单位，其编号保留给原单位。

要看距离，展开“逐项选择距离对象”，勾选要测的小兵，再点“应用勾选对象”。双方英雄之间的距离始终记录；小兵距离记录的是英雄到敌方小兵的距离。双方位置都填好后才会有结果。只需比较同一张图里的距离时，不必填写地图原点；要比较走了多远，才需要在各张图里标出同一个固定地面位置，排除镜头移动的影响。

### 3.4 在“英雄与配置”里填写双方信息

先填写录像的游戏版本，等待资料加载；没有自动出现时，点击“加载此版本目录”。选择双方英雄、符文、属性碎片和召唤师技能，再点击“保存并锁定英雄和符文”。这些内容对整段录像生效。选错时，先勾选“编辑 / 纠正对局固定配置”再修改；更换版本或英雄前注意页面的清空提示。

回到要填写的截图，再进入此页，展开双方的“等级、技能、装备和当前状态”，填入这一刻的等级、技能加点、装备、生命值、蓝量或能量、冷却等。每填一项都会自动保存；等页面出现“已保存并计算属性”后，再继续切换截图。装备已经全部核对过时才勾选背包完整的选项。

查看页面下方的时间标签，确认填写内容对应哪一张截图、哪个视频时间，以及已知的游戏内时间。换到另一张截图后，要按那一刻的实际情况填写；没记录的内容会留空。“将此状态记录于当前帧”可在需要时手动再保存一次，“读取当前帧对应状态”可重新查看这张图已保存的内容。

“自动属性与人工覆盖”会根据版本、当前等级、装备的固定加成和属性碎片计算数值。装备或符文临时触发的效果需要另行核对。自动数值不全时，先检查版本、英雄、等级和装备是否已保存；能够确认实际数值时，才在旁边的人工填写栏补充。

需要对线胜率时，展开“自动查询对位胜率”，点击“查询并保存对位胜率”。结果来自公开统计页面，表示全等级的整体结果；自动查询不需要填等级。网页读取失败时，按页面提示请 Skill 帮忙查找。手动填写胜率时才需要填写参考等级。

需要英雄技巧时，展开“自动查询英雄技巧与对线攻略”，点击“查询并保存攻略参考”，再按页面提示请 Skill 查找并整理。完成后，攻略显示在原位置并附来源；中文页使用中文，英文页使用英文。

### 3.5 请 Skill 帮忙填写，或取消任务

标注页上方可选择“请求 SKILL 协助填入当前帧”或“请求 SKILL 一次性填入所有帧”。配置页也有对应按钮，用来填写当前截图或全部截图中的等级、装备和状态。请先选好版本和双方英雄，再请求填写配置。

“当前帧”以按下请求按钮时正在查看的截图为准。请求会记下帧编号、它在录像中的时间，以及已知的游戏内时间。AI 开始时会说明这些信息；之后即使翻到别的截图，也只会填回请求中指定的那一帧。

点击后，在 AI 工具对话中输入“处理工作台请求”，或使用上表对应的标注、配置命令。AI 会读取截图并把结果保存回工作台。全部截图请求完成或取消前，工作台的刷新和编辑按钮会暂时停用。等 Skill 告知已经填好，以及哪些内容未知、哪些需要复核后，再刷新查看。需要停止时，点击请求按钮旁边的“取消 Skill 请求”，或在对话中输入“取消工作台请求”；已保存的填写结果仍会保留，后续结果不再继续填入。

结果出现后，检查坐标、动作和配置，再确认。血条看不清、装备看不到或冷却无法判断时，允许继续留空。

每次回填也会同步更新事件表、距离表、动作表和死亡记录，后续评估使用的是更新后的记录。修改记录后再导出评估包，即可带走最新资料。

### 3.6 在“评分与推演”里看分析结果

点击“运行分析任务”，工作台会先把当前标注和配置整理好。然后在 AI 工具对话中输入“分析当前对局”，由 Skill 读取资料、分析并保存报告；完成后刷新本页查看。

证据不足也会返回报告，无需先把所有内容填完。报告包含有依据的事件分析和改进建议；双方各项评分、综合分或其他无法确认的项目会保留“未知”，并说明还缺什么。阅读建议时，可以回到对应时间的截图核对；补充或纠正记录后，再运行一次分析。已有报告时也可以下载保存。

### 3.7 保存结果，需要时再做短时推演

在“录像与标注”页点击“保存并导出评估包”，等待下载链接出现，再点击 `assessment_bundle.zip`，即可带走截图、填写内容、表格和评估资料。只需要某张表格时，点击对应的表格链接。要交给其他 AI 工具继续分析时，使用整个评估包。改动记录后，重新导出一份，保证带走的是最新内容。

普通录像分析按前面的步骤即可。想比较“现在打这只兵”或“再等一下”等不同选择时，再展开“高级：短时事件与博弈推演”，勾选启用此项。先选定从哪张截图开始、站在哪一方的角度，再使用“生成下一短时窗口计划”或“以当前帧生成任务”。先核对伤害、距离、冷却和双方动作，确认资料足够后才点击“运行已核验任务”。

需要记录技能命中、被动或符文触发情况时，可展开相应观察表；同一次释放或触发只记录一次，结果不清楚就留空。更详细的使用方法见下面的短时推演说明。

想查某个按钮怎么用、重新打开已保存的记录或修改表格，见 **[工作台详细指南](docs/workbench_guide.md)**；想把记录交给其他 AI 工具，见 **[操作与数据格式](docs/workflow.md)**；想进一步比较不同的出手选择，见 **[短时推演详细说明](docs/short_horizon.md)**。

想了解属性和记录怎样影响评分，见 **[评分依据说明](docs/parameter_algorithm_mapping.md)**。

想了解英雄、符文和装备怎么选、怎样按时间保存状态或使用 ARAMonly 分享链接，见 **[配置选择指南](docs/loadout_selection.md)**。整段录像共用的英雄和符文等选择可以导出，再导入使用；使用其他网站的选择结果前，请先确认工作台支持该网站的分享方式。

英雄可以用中文名、英文名、游戏资料中的编号或常见别名（例如“大头”）查找，见[名称别名](docs/name_aliases.md)。

## 4. 其他说明

血条中心是画面测量口径。统一比例下的游戏距离只是估计，受投影、缩放和血条垂直偏移影响，不直接等于攻击判定距离。截图中缺失坐标时不会虚构距离或动作。实际时间精度受视频帧率限制。

评分需要核验参数、证据和固定规则。工作台不会独立给出可靠玩家水平分数，也不提供游戏内控制或实时采集；其他 AI 工程可通过 JSON/CSV 接口接入。内置推演是明确机制范围内的条件模型，不是全英雄游戏服务器模拟器。经验概率需核验迁移条件，情景分位数不自动等于置信区间或胜率；未实现的机制不得用任意概率掩盖。

通用脚本包括 [主程序](main.py)、[采样与表格计算](workbench/core.py)、[像素距离算法](algorithms/pixel_distance.py)、[相对资源/状态账本与风险评分](algorithms/risk_value.py)、[事件推演](algorithms/short_horizon.py)、[概率与效果适配](algorithms/probabilistic_mechanics.py)、[机制观察统计](workbench/mechanic_observations.py)、[可选博弈接口](workbench/game_tools.py) 和 [通用事件队列](algorithms/event_queue.py)。

版本化资料与选择配置使用 [目录接口](workbench/catalog.py)、[时点配置解析](workbench/loadouts.py)、[可视化选择器](workbench/loadouts.js)、[外部分享链接适配](workbench/external_selectors.py)及 [网页回传适配器](integrations/selector_bridge.js)。

随项目提供的文件及其校验值见 [文件清单](repository_manifest.json)。

原创建模文档和代码采用 [MIT](LICENSE)；第三方素材的许可范围见 [LICENSE_SCOPE.md](LICENSE_SCOPE.md)。

LOL Short-Window Last-Hit Decision Evaluation Framework is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.
