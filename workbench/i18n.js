'use strict';
// UI labels only. User annotations, strategy prose and JSON retain their original text.
window.uiLang=localStorage.getItem('lol-workbench-language')==='en'?'en':'zh';
const uiTranslations = new Map([
['LOL 短时补兵决策评估工作台','LOL Short-Window Last-Hit Evaluation Workbench'],
['按完整血条中心记录坐标。蓝红颜色表示阵营；小兵需分别编号。未知内容留空，保存后重新导出表格。','Record complete health-bar centers. Blue/red indicate teams. Give each minion a unique ID. Leave unknowns blank; save and export tables again.'],
['上一帧','Previous frame'],['下一帧','Next frame'],['点击模式','Click mode'],
['当前单位血条中心','Selected unit: health-bar center'],['拖框选完整血条（取中心）','Drag a complete health-bar box (use its center)'],['固定地图纹理原点','Fixed map-texture origin'],
['橙色框仅为颜色填充候选，不能代表完整血条，也没有单位身份。请依据画面手动确认；不使用脚下模型中心。','Orange boxes are colored-fill proposals, not complete bars or unit identities. Confirm visually using the complete bar, not the model beneath it.'],
['左右方向键切帧（输入框内除外）。地图原点必须在各帧追踪同一纹理点，才能扣除镜头平移；同帧单位间距不需要原点。','Use arrow keys outside input fields to change frames. Track the same texture landmark to correct camera translation. Same-frame distances need no origin.'],
['距离小兵 ID（逗号分隔，数量不限；设定沿用至后续帧，直到重新选择）','Minion distance IDs (comma-separated, unlimited; selection persists until changed)'],
['炮车线或兵波重叠时请显式选择','Explicitly select units for cannon or overlapping waves'],
['选取名册内当前全部未确认阵亡的小兵','Select all roster minions not confirmed dead'],['只测英雄之间','Hero-to-hero only'],
['逐项选择距离对象','Select distance targets individually'],['应用勾选对象','Apply checked units'],['单位列表与新增单位','Roster and new units'],
['换波、炮车、召唤物使用新 ID，不能复用已经阵亡单位的 ID。','Use new IDs for later waves, cannons and summons. Never reuse a dead unit ID.'],
['颜色检测不识别炮车或兵种；请人工选择，或导入 AI 已区分兵种的名册。编号由程序生成，不代表自动跟踪到同一只小兵。','Color detection does not classify minions. Select a type or import an AI-reviewed roster. Generated IDs do not imply automatic identity tracking.'],
['留空自动生成永久唯一 ID','Leave blank to generate a permanent unique ID'],['近战 melee','Melee'],['远程 caster','Caster'],['炮车 siege','Siege'],['超级兵 super','Super'],['兵种待确认 minion','Unclassified minion'],['召唤物 summon','Summon'],['加入单位','Add unit'],['当前单位','Selected unit'],
['动作（未知留空）','Action (leave unknowns blank)'],['攻击目标','Attack target'],['攻击阶段（前摇/弹道中/命中/后摇）','Attack stage (wind-up/projectile/impact/recovery)'],['存活状态','Alive state'],['确认阵亡（此帧起停止记录该单位）','Confirmed dead (stop recording this unit from this frame)'],['未知 / 无目标','Unknown / no target'],['未知','Unknown'],['存活','Alive'],
['生命值或血量比例（口径写备注）','HP or HP fraction (specify convention in notes)'],['动作开始：视频秒数','Action start: source-video seconds'],['动作结束：视频秒数','Action end: source-video seconds'],['备注','Notes'],['记录此帧动作','Record action'],['清除此单位坐标','Clear unit coordinates'],['保存并导出评估包','Save and export assessment bundle'],['已保存。','Saved.'],['保存','Save'],
['导入人工或 AI 标注 JSON','Import manual or AI annotation JSON'],['格式见 docs/workflow.md。导入后覆盖当前标注；先保存备份。','See docs/workflow.md. Import replaces current annotations; back up first.'],['评估预输入','Assessment inputs'],
['距离标尺（像素=游戏单位，空白保留像素）：','Distance calibration (pixels=game units; blank for pixels only):'],
['游戏距离为用户标尺下的近似量。镜头缩放、透视和不同单位血条高度会造成误差；血条中心距离不等于游戏碰撞边缘距离。','Game distances are estimates under your calibration. Zoom, perspective and bar-height offsets introduce error; bar-center distance is not collision-edge distance.'],
['高级：英雄有效参数 JSON / 旧版数据接口','Advanced: effective hero parameters JSON / legacy interface'],
['可运行 fetch-data 查询官方基础数据，再粘贴到此处。必须核验实际攻速、射程、移速、技能等级/消耗/CD、被动与符文状态；只有基础数据不足以评分。','fetch-data downloads official static data. Verify effective attack speed, range, movement speed, skill ranks/costs/cooldowns, passive and rune states. Static data alone is insufficient for scoring.'],
['每方需有 champion、patch、runes、items、effective_state 和 verified_effective_state。后者仅在人工核验后设为 true。','Each side needs champion, patch, runes, items, effective_state and verified_effective_state. Set the last field to true only after verification.'],
['一般对线策略参考（可选）','General matchup strategy (optional)'],['纯文字策略、适用条件、来源链接、版本和访问日期','Strategy prose, applicable conditions, source links, patch and access date'],
['可选：从当前时刻进行短时事件与博弈推演','Optional: short-window event and game analysis'],['启用此项（默认关闭，不影响采样、距离或普通评估）','Enable (off by default; sampling, distances and regular assessment remain available)'],
['先选择介入帧，再生成任务。英雄/小兵机制、有效参数、攻击阶段（前摇/弹道中/命中/后摇）、地面坐标和候选动作需核验；升级、未知转火、仇恨或未实现效果会截断共同有效窗口。','Choose an entry frame and draft a task. Verify rules, effective stats, phases, ground coordinates and candidates. Level-ups, unknown retargeting/aggro or unsupported effects truncate the shared valid window.'],
['金币、经验、血蓝和冷却成本分别结算；未死小兵不视为永久损失。不自动给出胜负或玩家分数。','Report gold, XP, health, mana and cooldown costs separately. Living minions are not permanent losses. No automatic win/loss or player grade is assigned.'],
['非指向技能、被动、符文的观察概率与频率','Observed skillshot, passive and rune probabilities/frequencies'],
['每次技能释放或满足条件的触发机会只记一行，不能把多张截图当作多次机会。已知触发规则优先使用确定计数器；未知结果留空。技能命中、被动触发和符文触发分别使用不同 mechanism_id，并按距离、移动、等级等条件分组。','Record one row per cast or eligible proc opportunity, not per screenshot. Use deterministic counters for known rules; leave unknown outcomes blank. Separate skillshot/passive/rune mechanism IDs and group by distance, movement and level.'],
['下载 UTF-8 BOM 观察表模板','Download UTF-8 BOM observation CSV'],['下载通用机制 JSON 模板','Download generic mechanism JSON'],['将统计模型写入任务（仍须核验适用条件）','Copy estimated models into task (verify applicability)'],['以当前帧生成任务','Draft task at current frame'],
['仅事件分支比较（无需下载）','Event branch comparison (no download)'],['有限零和相对收益（SciPy）','Bounded zero-sum relative payoff (SciPy)'],['双方独立收益（Nashpy）','Independent player payoffs (Nashpy)'],
['生成草稿后，人工或 AI 填写并核验。没有内置任何英雄的参数。','Complete and verify the draft manually or with AI. No champion combat rules are assumed.'],['运行已核验任务','Run verified task'],['机制范围与任务格式','Supported mechanics and task format'],
['已安装','Installed'],['未安装，可选下载','Not installed; optional download'],['可选安装命令（自行在本机终端运行，不自动下载）：','Optional install command (run in your terminal; no automatic installation):'],
['血条中心：未知','Health-bar center: unknown'],['血条中心','Health-bar center'],['与敌方英雄距离：待标注双方中心','Enemy hero distance: annotate both centers'],['与敌方英雄距离：','Enemy hero distance: '],['视频','Video'],
['动作已记录，尚需保存。','Action recorded; save to persist.'],['标尺格式：189=350','Calibration format: 189=350'],['事件表 CSV','Events CSV'],['距离表 CSV','Distances CSV'],['独立评估包 ZIP','Standalone assessment ZIP'],
['不是有效标注 JSON','Invalid annotation JSON'],['已载入标注。保存时将执行结构校验。','Annotations loaded. Structure will be validated on save.'],['先导入观察 CSV','Import observation CSV first'],
['可选推演未启用；其他计算不受影响。','Optional planning is disabled; other calculations remain available.'],['任务介入时刻：视频','Task entry: video'],['草稿未核验，必须补齐参数才能运行。','Unverified draft: complete the parameters before running.'],['有效窗口','Effective window'],['结果已保存','Results saved'],['下载完整推演结果 JSON','Download full result JSON'],
['已写入观察统计。context_verified 保持 false，需核验距离、移动、机制条件及反事实适用性；触发概率不会替代确定规则。','Estimates copied. context_verified remains false; verify distance, movement, eligibility and counterfactual applicability. Proc probabilities do not replace deterministic rules.'],
['波次必须是非负整数；不确定时使用 0 并在备注中说明','Wave must be a nonnegative integer; use 0 with a note if unknown'],['ID 必须唯一；阵亡后也不复用','IDs must be unique, including dead units'],['已加入','Added'],['请在距离对象中显式选取；未知兵种可先用 minion。','Select this unit explicitly in the distance roster; use minion if its type is unknown.'],
['\u7f29\u653e','Zoom'],['\u6e38\u620f\u5185\u65f6\u95f4\uff08\u53ef\u9009\uff0c\u7559\u7a7a\u8868\u793a\u672a\u77e5\uff09','Game time (optional; blank means unknown)'],['\u5f53\u524d\u5e27\u81ea\u52a8\u72b6\u6001\u6458\u8981','Automatic frame state summary'],['\u89c4\u5212\u89c6\u89d2','Planning side'],['\u751f\u6210\u4e0b\u4e00\u77ed\u65f6\u7a97\u53e3\u8ba1\u5212','Plan next short window'],['\u653b\u51fb\u52a8\u4f5c\u9636\u6bb5\uff08\u524d\u6447/\u5f39\u9053\u4e2d/\u547d\u4e2d/\u540e\u6447\uff09','Attack timing stage (wind-up/projectile/impact/recovery)'],['\u81ea\u52a8\u8ddd\u79bb\u5019\u9009\uff08\u53cc\u65b9\u82f1\u96c4\u548c\u82f1\u96c4\u5230\u5bf9\u65b9\u5c0f\u5175\uff09','Automatic distance candidates (heroes and heroes to enemy minions)'],
['\u8bed\u8a00','Language'],['\u52fe\u9009\u8981\u6d4b\u8ddd\u79bb\u7684\u5c0f\u5175\u3002\u7a0b\u5e8f\u8ba1\u7b97\u82f1\u96c4\u5230\u654c\u65b9\u5c0f\u5175\u7684\u8ddd\u79bb\uff1b\u53cc\u65b9\u82f1\u96c4\u95f4\u7684\u8ddd\u79bb\u59cb\u7ec8\u8bb0\u5f55\u3002','Select minions to measure. The table records heroes to enemy minions and always includes the distance between the two heroes.'],['\u9ad8\u7ea7\uff1a\u6309\u7f16\u53f7\u6307\u5b9a\u5c0f\u5175','Advanced: select minions by ID'],['\u9009\u62e9\u65b0\u5f55\u50cf','Select another replay'],['\u82f1\u96c4','Champion'],['\u524d\u6447 / \u5f39\u9053\u4e2d / \u547d\u4e2d / \u540e\u6447','wind-up / projectile / impact / recovery'],['\u5237\u65b0\u5f53\u524d\u5e27','Refresh current frame'],['\u5c0f\u5175\u8ddd\u79bb\u5bf9\u8c61\uff08\u7559\u7a7a\uff1d\u5168\u90e8\uff09','Minion distance targets (blank = all)'],['\u4f8b\u5982\uff1ared_melee_w1_1','e.g. red_melee_w1_1'],['\u5e27','Frame'],['\u89c6\u9891','Video'],['\u6e38\u620f\u5185\u65f6\u95f4','Game time'],['\u6e38\u620f\u5185\u65f6\u95f4\u672a\u77e5','Game time unknown'],['\u5df2\u4fdd\u5b58\u77ed\u65f6\u7a97\u53e3\u8ba1\u5212','Short-window plan saved'],['\u5f55\u50cf\u4e0e\u6807\u6ce8','Evidence'],['\u82f1\u96c4\u4e0e\u914d\u7f6e','Configuration'],['\u8bc4\u5206\u4e0e\u63a8\u6f14','Planning'],['\u84dd\u65b9','Blue side'],['\u7ea2\u65b9','Red side'],['\u8fd1\u6218\u5175','Melee minion'],['\u8fdc\u7a0b\u5175','Caster minion'],['\u70ae\u8f66\u5175','Siege minion'],['\u8d85\u7ea7\u5175','Super minion'],['\u5f85\u786e\u8ba4\u5175\u79cd','Unclassified minion'],['\u53ec\u5524\u7269','Summon'],['\u4f8b\u5982 02:10','e.g. 02:10'],['\u6e38\u620f\u5355\u4f4d','game units'],['\u4e0a\u4e00\u9875','Previous page'],['\u5de5\u4f5c\u53f0\u5206\u9875\u5bfc\u822a','Workbench page navigation'],['\u4e0b\u4e00\u9875','Next page'],['\u5206\u9875\u5bfc\u822a','Page navigation'],['\u6709\u9650\u96f6\u548c\u76f8\u5bf9\u6536\u76ca','Bounded zero-sum relative payoff'],['\u53cc\u65b9\u72ec\u7acb\u6536\u76ca','Independent player payoffs'],['\u53ef\u9009\u5b89\u88c5\u547d\u4ee4\uff08\u81ea\u884c\u5728\u672c\u673a\u7ec8\u7aef\u8fd0\u884c\uff0c\u4e0d\u81ea\u52a8\u4e0b\u8f7d\uff09\uff1a','Optional install command (run in a local terminal; no automatic download):'],['\u914d\u7f6e\u6b65\u9aa4','Configuration steps'],['\u8f93\u5165\u5f55\u50cf\u7248\u672c\u5e76\u52a0\u8f7d\u7248\u672c\u6570\u636e\u3002','Enter the recording patch and load patch data.'],['\u5206\u522b\u9009\u62e9\u84dd\u65b9\u548c\u7ea2\u65b9\u82f1\u96c4\u3001\u4e3b\u7cfb\u7b26\u6587\u3001\u526f\u7cfb\u7b26\u6587\u548c\u5c5e\u6027\u788e\u7247\uff0c\u7136\u540e\u4fdd\u5b58\u5e76\u9501\u5b9a\u3002','Choose blue and red champions, primary/secondary runes and stat shards, then save and lock.'],['\u5728\u5f53\u524d\u622a\u56fe\u5bf9\u5e94\u7684\u65f6\u95f4\u70b9\u586b\u5199\u7b49\u7ea7\u3001\u6280\u80fd\u52a0\u70b9\u3001\u88c5\u5907\u3001\u53ec\u5524\u5e08\u6280\u80fd\u548c\u672a\u663e\u793a\u7684\u72b6\u6001\uff0c\u8bb0\u5f55\u8be5\u65f6\u95f4\u70b9\u3002','At the selected screenshot time, enter level, skill ranks, items, summoner spells and hidden state, then record the time point.'],['\u5207\u6362\u622a\u56fe\u540e\u52a0\u8f7d\u6216\u4fee\u6539\u5f53\u524d\u65f6\u95f4\u70b9\u72b6\u6001\uff1b\u4fdd\u5b58\u540e\u518d\u5bfc\u51fa\u8bc4\u4f30\u5305\u3002','After switching screenshots, load or edit the state for that time point; save before exporting.'],['\u82f1\u96c4\u540d\u79f0\u652f\u6301\u4e2d\u6587\u540d\u3001\u82f1\u6587\u540d\u3001ID \u548c\u793e\u533a\u5e38\u7528\u522b\u540d\u3002\u81ea\u52a8\u5c5e\u6027\u6765\u81ea\u7248\u672c\u6570\u636e\u548c\u88c5\u5907\uff1b\u7279\u6b8a\u4e34\u65f6\u6548\u679c\u3001\u6280\u80fd\u51b7\u5374\u548c\u7b26\u6587/\u88ab\u52a8\u5c42\u6570\u8bf7\u6309\u753b\u9762\u6838\u5bf9\u540e\u586b\u5199\u3002','Champion input accepts Chinese names, English names, IDs and community aliases. Automatic stats use patch data and items; verify temporary effects, cooldowns and rune/passive stacks from the video before entering them.'],]);
uiTranslations.set('英雄名称支持中文名、英文名、ID和社区常用别名。自动属性来自版本数据和装备；特殊临时效果、技能冷却和符文/被动层数请按画面核对后填写。','Champion input accepts Chinese names, English names, IDs and community aliases. Automatic stats use patch data and items; verify temporary effects, cooldowns and rune/passive stacks from the video.');
uiTranslations.set('距离标尺（像素=游戏单位，清空则只保留像素）：','Distance calibration (pixels=game units; clear for pixels only):');
uiTranslations.set('默认使用本项目局部技能范围试算的中点：0.459 像素/游戏单位（范围 0.453–0.465）。用户可输入其他标尺，例如 189=350；镜头缩放、透视和不同单位血条高度会造成误差，血条中心距离不等于游戏碰撞边缘距离。','The default estimate is 0.459 pixels per game unit (range 0.453–0.465). You may enter another calibration, such as 189=350. Camera zoom, perspective and health-bar height introduce error; bar-center distance differs from collision-edge distance.');
uiTranslations.set('可选安装命令（自行在本机终端运行，不自动下载）','Optional install command (run locally; no automatic download)');
uiTranslations.set('兵线波次','Minion wave number');
uiTranslations.set('AI 辅助标注','AI-assisted annotation');
uiTranslations.set('由 Skill 读取截图并回填，玩家最后复核；不会把未知项当成已确认数据。','The Skill reads screenshots and fills drafts for player review; unknowns remain unconfirmed.');
uiTranslations.set('请 Skill 识别当前帧','Ask Skill to annotate this frame');
uiTranslations.set('载入识别结果','Load recognition results');
uiTranslations.set('确认当前帧识别结果','Confirm recognition for this frame');
uiTranslations.set('观察表与机制模板自动保存在当前工作区，并自动载入；未知内容可请 Skill 协助填写。','Observation and mechanism templates are saved and loaded automatically in this workspace. Ask the Skill to help with unknown fields.');
uiTranslations.set('刷新工作区观察表','Reload workspace observations');
uiTranslations.set('请 Skill 协助填写观察表','Ask Skill to fill observations');
uiTranslations.set('导入或下载文件（可选）','Import or download files (optional)');
uiTranslations.set('已自动载入工作区观察表。独立观察机会：','Workspace observations loaded. Distinct opportunities: ');
uiTranslations.set('识别请求已准备好。请在 Skill 对话中说“处理工作台识别请求”；完成后将自动载入，供你复核。','Request ready. Ask the running Skill to process the workbench assistance request; results will load automatically for your review.');
uiTranslations.set('识别结果已载入，标为待复核。请检查坐标、动作及血量后确认。','Recognition results loaded as unreviewed drafts. Check centers, actions and HP before confirming.');
uiTranslations.set('已确认当前帧的 AI 识别结果：','AI results confirmed for this frame: ');
uiTranslations.set('请求 SKILL 协助填入当前帧','Ask SKILL to fill the current frame');
uiTranslations.set('请求 SKILL 一次性填入所有帧','Ask SKILL to fill all frames');
uiTranslations.set('对局分析','Lane analysis');
uiTranslations.set('运行分析任务','Run analysis task');
uiTranslations.set('高级：短时事件与博弈推演','Advanced: short-window events and game analysis');
uiTranslations.set('填写录像版本，自动加载该版本数据。','Enter the recording patch to load its data automatically.');
uiTranslations.set('选择双方英雄、符文、属性碎片和召唤师技能；这些选择对整段录像生效。','Choose both champions, runes, stat shards and summoner spells; these apply to the entire recording.');
uiTranslations.set('在当前帧填写等级、装备、技能加点及当前状态；编辑后自动保存，并显示视频时间和已知游戏时间。','Enter level, items, skill ranks and current state for this frame. Edits save automatically with video time and known game time.');
uiTranslations.set('自动属性只计算基础数值和固定加成；装备、符文的触发效果按当前帧核验。','Automatic attributes include base values and fixed bonuses only. Verify triggered item and rune effects at the current frame.');
uiTranslations.set('请求 SKILL 协助填入当前帧配置','Ask SKILL to fill the current frame configuration');
uiTranslations.set('请求 SKILL 一次性填入所有帧配置','Ask SKILL to fill configurations for all frames');
uiTranslations.set('取消批量任务','Cancel batch task');
uiTranslations.set('显示隐藏或阵亡的单位','Show hidden or dead units');
uiTranslations.set('管理当前单位','Manage current unit');
uiTranslations.set('当前帧不可见','Not visible in this frame');
uiTranslations.set('恢复当前帧显示','Show in this frame');
uiTranslations.set('确认此帧起阵亡','Confirm death from this frame');
uiTranslations.set('删除误建单位','Delete mistaken unit');
uiTranslations.set('不可见只影响当前帧；确认阵亡影响后续帧。删除误建单位会清除其整段录像记录，并保留备份。','Visibility affects this frame only; confirmed death affects later frames. Deleting a mistaken unit removes its records throughout the recording and retains a backup.');
uiTranslations.set('取消 Skill 请求','Cancel Skill request');
const uiOriginal=new WeakMap();
window.translateText=function(value){if(window.uiLang!=='en')return value;let text=value;for(let [zh,en] of [...uiTranslations].sort((a,b)=>b[0].length-a[0].length))text=text.split(zh).join(en);return text};
function localizeUI(root=document.body){
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;
 while((node=walker.nextNode())){
  if(node.parentElement?.closest('script,style,textarea,[data-user-content]')||node.parentElement?.closest('pre')&&!node.parentElement?.closest('[data-ui-text]'))continue;
  let previous=uiOriginal.get(node);if(!previous||node.nodeValue!==previous.rendered)previous={original:node.nodeValue};
  let rendered=window.translateText(previous.original);uiOriginal.set(node,{original:previous.original,rendered});if(node.nodeValue!==rendered)node.nodeValue=rendered;
 }
 for(let input of root.querySelectorAll('input[placeholder],textarea[placeholder]')){input.dataset.originalPlaceholder??=input.placeholder;input.placeholder=window.translateText(input.dataset.originalPlaceholder)}
 for(let node of root.querySelectorAll('[aria-label]')){node.dataset.originalAriaLabel??=node.getAttribute('aria-label');node.setAttribute('aria-label',window.translateText(node.dataset.originalAriaLabel))}
 document.documentElement.lang=window.uiLang==='en'?'en':'zh-CN';
 document.title=window.translateText('LOL 短时补兵决策评估工作台');
}
window.localizeUI=localizeUI;
document.getElementById('uiLanguage').value=window.uiLang;
document.getElementById('uiLanguage').onchange=e=>{window.uiLang=e.target.value;localStorage.setItem('lol-workbench-language',window.uiLang);localizeUI();window.dispatchEvent(new Event('languagechange'))};
localizeUI();
let localeQueued=false;
new MutationObserver(()=>{if(localeQueued)return;localeQueued=true;queueMicrotask(()=>{localeQueued=false;localizeUI()})}).observe(document.body,{subtree:true,childList:true,characterData:true});
