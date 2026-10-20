# Dialogue templates

Use these templates for short, consistent workbench replies. Match the user's
language. Replace a placeholder only with a value returned by a command or read
from the active request. Omit a sentence when its value is unavailable; never
guess a URL, port, token, workspace, frame count, result count, or completion
state.

The wording may be adapted to the context, but the factual conditions attached
to each template are mandatory.

## Service control

### Started

Use only after `service-start` reports a running service.

- Chinese: `工作台已启动：[打开工作台]({url})`
- English: `The workbench is running: [Open the workbench]({url})`

If `already_running=true`:

- Chinese: `工作台已经在运行：[打开工作台]({url})`
- English: `The workbench is already running: [Open the workbench]({url})`

### Stopped

Use only after `service-stop` confirms that the managed service stopped.

- Chinese: `工作台服务已停止。`
- English: `The workbench service has stopped.`

If no managed service exists, say it was not running rather than claiming a
stop operation succeeded.

### Restarted

Use only after `service-restart` returns the new active URL.

- Chinese: `工作台已重启：[打开工作台]({url})`
- English: `The workbench has restarted: [Open the workbench]({url})`

### Status

- Running, Chinese: `工作台正在运行：[打开工作台]({url})`
- Running, English: `The workbench is running: [Open the workbench]({url})`
- Stopped, Chinese: `工作台当前未运行。`
- Stopped, English: `The workbench is not running.`

## Workbench requests

The player can activate an existing request with `处理工作台请求` / `process
workbench request`, or the task-specific commands in `SKILL.md`. Read/claim
the request through `assistant-read --start`; save it through
`assistant-finish`. A queued request remains waiting until the agent starts
processing it. Completed work means persisted workspace data, not a temporary
change to the browser page.

### Request accepted

Use only after reading `assistant/request.json` and confirming that the request
is current and not cancelled.

- Chinese: `已读取工作台请求：{kind}，范围为{scope}，共 {frame_count} 帧。现在开始处理。`
- English: `I loaded the workbench request: {kind}, scope {scope}, {frame_count} frames. Processing has started.`

If the frame count is not declared, omit it. Do not infer it from the total
workspace frame count unless the request explicitly selects all frames.

For a current-frame request, confirm its captured `frame_context` before work:

- Chinese: `本次处理第 {frame_number} 帧（{frame_id}），视频时间 {source_time_s} 秒；游戏内时间：{game_time_s}。`
- English: `Processing frame {frame_number} ({frame_id}), video time {source_time_s}s; in-game time: {game_time_s}.`

Use unknown for an absent game time. These values come from the request, not
the browser's current slider position.

### Progress update

- Chinese: `已检查 {inspected_count}/{requested_count} 帧；已暂存 {filled_count} 项，{review_count} 项需要复核，{unknown_count} 项仍未知。`
- English: `Checked {inspected_count}/{requested_count} frames; staged {filled_count} fields, with {review_count} needing review and {unknown_count} still unknown.`

Only report counts calculated from saved output or the active processing batch.

### Completed

Use after a successful import tied to the current `request_revision`.

- Chinese: `请求已处理并写入工作区：检查 {inspected_count} 帧，填入 {filled_count} 项。请刷新工作台查看并复核。`
- English: `The request was processed and written to the workspace: {inspected_count} frames checked and {filled_count} fields filled. Refresh the workbench to review the results.`

### Partially completed

- Chinese: `已写入可确认的结果：检查 {inspected_count}/{requested_count} 帧，填入 {filled_count} 项；仍有 {unknown_count} 项未知，{review_count} 项需要复核。请刷新工作台查看。`
- English: `Confirmed results were written: {inspected_count}/{requested_count} frames checked and {filled_count} fields filled; {unknown_count} remain unknown and {review_count} need review. Refresh the workbench to inspect them.`

List the affected frame IDs or fields after this sentence when the unknown or
review set is small. Unknown values remain blank and are never converted to
zero.

### Cancelled

Use only after the request state records cancellation or the active operation
has actually stopped.

- Chinese: `请求已取消，后续批次不会再写入工作区。`
- English: `The request was cancelled. No later batches will be written to the workspace.`

If an operation could not be interrupted, state the exact remaining operation
and do not claim cancellation is complete.

### Stale or missing request

- Chinese: `没有找到可处理的当前请求，或请求版本已经变化。请在工作台重新发起请求。`
- English: `There is no current request to process, or its revision has changed. Create a new request in the workbench.`

## Automatic annotation

### YOLO available

- Chinese: `本机依赖和仓库权重可用，将使用 YOLO 检测并把结果标记为“自动生成、待复核”。`
- English: `The local dependencies and bundled weights are available. YOLO will stage detections as automatically generated and pending review.`

### Dependency fallback

- Chinese: `YOLO 当前不可用：{reason}。工作台已回退到 Track 候选流程，结果仍需人工确认。`
- English: `YOLO is unavailable: {reason}. The workbench fell back to Track candidates, which still require manual confirmation.`

Name only the dependency or runtime error that the status command actually
reported. CUDA absence alone is not a failure when CPU inference is supported
by the configured path.

### Detection limitations

- Chinese: `已生成 {candidate_count} 个候选。模型未覆盖或置信度不足的单位保持未知；请重点复核：{review_summary}。`
- English: `Generated {candidate_count} candidates. Units outside the model classes or below confidence remain unknown; prioritize review of: {review_summary}.`

## Analysis and strategy

### Analysis completed

Use only after the evaluator and readable report both finish.

- Chinese: `分析已完成。综合结果、分项评分、事件时间轴和改进建议已写入工作台；请刷新“评分与推演”页面查看。`
- English: `Analysis is complete. The overall result, component scores, event timeline, and recommendations are in the workbench; refresh the Planning page to view them.`

If scoring is bounded by missing evidence, append the missing fields and score
interval rather than presenting a single exact score.

### Strategy search completed

- Chinese: `攻略参考已写入工作台，共保存 {source_count} 个来源。内容按 {patch} 版本整理，请在使用前核对适用条件。`
- English: `Strategy guidance was written to the workbench with {source_count} sources. It is organized for patch {patch}; verify the applicable conditions before using it.`

### Search unavailable

- Chinese: `当前未能取得可核验的公开资料：{reason}。现有配置和标注不受影响，攻略字段保持原样。`
- English: `No verifiable public sources were available: {reason}. Existing configuration and annotations are unchanged, and the strategy field was preserved.`

## Error replies

State the failed action, the concrete error, and whether any data was written.
Keep the first sentence actionable.

- Chinese: `{action}未完成：{error}。{write_status}。`
- English: `{action} did not complete: {error}. {write_status}.`

Preferred write-status phrases:

- Chinese: `没有写入工作区` / `已保留此前成功写入的批次`
- English: `Nothing was written to the workspace` / `Previously completed batches were preserved`

Never report success merely because a button was pressed or a request file was
created. A workbench request is complete only after the corresponding result is
saved and imported.
