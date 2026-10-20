"""Human-readable reports produced after the structured evaluator run."""

from pathlib import Path
import json


def _fmt(value):
    if value is None:
        return "未知"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def write_evaluation_reports(directory, result):
    directory = Path(directory)
    assessment = directory / "assessment"
    assessment.mkdir(exist_ok=True)
    lines = ["# LOL 短时补兵决策评估报告", "", f"状态：`{result.get('status', 'unknown')}`", ""]
    scores = result.get("scores") or {}
    lines += ["## 双方分项评分", "", "|一方|CS|XP|补刀间隔压制|相对状态|策略分|执行分|综合分|区间|", "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for side, data in scores.items():
        if not isinstance(data, dict):
            continue
        layered = data.get("layered_score") or {}
        lines.append("|{}|{}|{}|{}|{}|{}|{}|{}|{}|".format(
            side, _fmt(data.get("cs")), _fmt(data.get("xp")), _fmt(data.get("pressure")),
            _fmt(data.get("state_score")), _fmt(layered.get("strategy_score")),
            _fmt(layered.get("execution_score")), _fmt(layered.get("score")),
            _fmt(layered.get("interval"))))
    lines += ["", "### 分项可用性", ""]
    for side, data in scores.items():
        if isinstance(data, dict):
            layered = data.get("layered_score") or {}
            missing = list(dict.fromkeys((data.get("missing") or []) + (layered.get("missing") or [])))
            lines.append(f"- `{side}`：缺失层 `{', '.join(missing) if missing else '无'}`；使用权重 `{json.dumps(data.get('weights', {}), ensure_ascii=False)}`。")
    lines += ["", "## 评分依据", "", "CS、经验和金币是窗口内绝对到账；生命、资源、冷却、召唤师技能和消耗品按双方相对可用储备结算。补刀间隔压制只在小兵死亡顺序得到证据支持时计入。策略分与执行分按 50:50 合成。", ""]
    prior = result.get("matchup_prior")
    if prior:
        lines += ["## 对位先验", "", f"- 来源：`{prior.get('prior', {}).get('source', 'unknown')}`", f"- 比例：蓝方 `{_fmt(prior.get('prior', {}).get('blue'))}` / 红方 `{_fmt(prior.get('prior', {}).get('red'))}`", f"- 等级专属：`{prior.get('prior', {}).get('level_specific', 'unknown')}`", f"- 样本量：`{prior.get('prior', {}).get('sample_size', 'unknown')}`（未知不伪造）", ""]
    usage = result.get("backend_input_usage", {})
    lines += ["## 数据覆盖", "", f"- 工作区文件：`{usage.get('workspace_files', 'unknown')}`", f"- 输入摘要：`{usage.get('all_workspace_data_digest', 'unknown')}`", f"- 观测覆盖度：`{_fmt(usage.get('workspace_observation_coverage'))}`", ""]
    derived = usage.get("derived_workspace_metrics") or {}
    if derived:
        lines += ["## 工作区派生输入", "", f"- 已确认死亡单位：`{derived.get('confirmed_deaths', 'unknown')}`", f"- 表格确认补刀：`{json.dumps(derived.get('confirmed_last_hits', {}), ensure_ascii=False)}`", f"- 攻略参考文件：`{len(derived.get('strategy_reference_files', []))}`", ""]
    lines += ["## 改进建议", "", "优先检查报告区间较宽的一方：补齐血条中心、距离、攻击阶段（前摇/弹道中/命中/后摇）、目标小兵、技能/召唤师冷却和符文层数。对未来窗口，使用 `window_plan` 输出的候选目标，再以版本数据核验攻击前摇、伤害、弹道与小兵转火规则。", ""]
    (assessment / "assessment_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    uncertainty = ["# 不确定性报告", "", "点分数只在已知层上计算；未知层从对应权重分母中排除，并扩大区间。", "", "```json", json.dumps({"status": result.get("status"), "scores": scores, "backend_input_usage": usage}, ensure_ascii=False, indent=2), "```", ""]
    (assessment / "uncertainty_report.md").write_text("\n".join(uncertainty), encoding="utf-8")
    return {"assessment_report": str(assessment / "assessment_report.md"),
            "uncertainty_report": str(assessment / "uncertainty_report.md")}
