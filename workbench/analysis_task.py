"""Run the existing evaluator and expose a readable, evidence-bound review."""
from pathlib import Path
import math
from .core import read_json, write_json
from .evaluation_pipeline import evaluate_workspace
from .assistance import request_assistance


def prepare_skill_analysis(directory, frame_id, language='zh'):
    """Package evidence and request agent analysis without calculating provisional scores."""
    from .core import export_assessment
    from .assistance import status
    directory=Path(directory)
    request=request_assistance(directory,frame_id,'analysis','all',language)
    try:
        coverage=export_assessment(directory)
    except Exception:
        request=status(directory)
        request.update(status='failed')
        write_json(directory/'assistant/request.json',request)
        raise
    return {'status':'pending','request':request,'bundle':'assessment_bundle.zip','coverage':coverage}


def run_analysis(directory, language='zh'):
    directory=Path(directory)
    en=language=='en'
    text=lambda zh,english:english if en else zh
    config=next((read_json(p) for p in [directory/'scoring_config.json',directory/'assessment/scoring_config.json'] if p.exists()),None)
    result=evaluate_workspace(directory,config)
    output=directory/'assessment';output.mkdir(exist_ok=True)
    write_json(output/'skill_result.json',result)
    project,annotations=read_json(directory/'project.json'),read_json(directory/'annotations.json')
    lines=[text('# 对局分析报告','# Lane review report'),'']
    if result['status']!='scored':
        lines += [text('已根据现有标注和事件记录生成报告。证据不足的分项和综合分保留为未知；仍可查看时间轴、已知事实和改进建议，补充资料后可重新分析。','This report uses the available annotations and events. Unsupported components and overall scores remain unknown. The timeline, known facts and recommendations are available now; add evidence later to rerun the analysis.'),'']
        from .assistance import status
        current=status(directory)
        if current.get('kind')!='analysis' or current.get('status') not in ('pending','running','partial'):
            request_assistance(directory,project['frames'][0]['id'],'analysis','all',language)
    lines += [text('## 分项评分与综合分','## Component and overall scores'),'',
              text('| 一方 | CS | 经验 | 补刀间隔压制 | 相对状态 | 策略 | 执行 | 综合 | 区间 |','| Side | CS | XP | Free-window pressure | Relative state | Strategy | Execution | Overall | Interval |'),
              '|---|---|---|---|---|---|---|---|---|']
    def fmt(value):
        if value is None:return text('未知','Unknown')
        if isinstance(value,float):return f'{value:.2f}'
        return str(value)
    for side in ('blue','red'):
        score_side=(config or {}).get('sides',{}).get(side,side)
        data=(result.get('scores') or {}).get(score_side,{})
        layered=data.get('layered_score') or {}
        values=[text('蓝方','Blue') if side=='blue' else text('红方','Red')]+[fmt(data.get(k)) for k in ('cs','xp','pressure','state_score')]+[fmt(layered.get(k)) for k in ('strategy_score','execution_score','score','interval')]
        lines.append('| '+' | '.join(values)+' |')
    lines += ['',text('## 评分依据','## Scoring basis'),'',text('策略与执行按 50:50 合成。资源以实际金币、经验和补刀到账结算；状态比较双方可用储备。未知项不按零分计算；观测覆盖率不代表玩家水平。','Strategy and execution retain a 50:50 mix. Receipts use actual gold, XP and last hits; state compares usable reserves. Unknowns are not zero scores, and annotation coverage is not player skill.'),'',text('## 事件时间轴','## Event timeline'),'']
    previous={};events=0
    for frame in project['frames']:
        observed=annotations['frames'].get(frame['id'],{})
        for uid,unit in observed.get('units',{}).items():
            event={k:unit[k] for k in ('action','target','phase','alive','hp') if unit.get(k) not in (None,'')}
            if not event or previous.get(uid)==event:continue
            previous[uid]=event;events+=1
            time=observed.get('game_time_s')
            clock=(text('游戏时间 ','Game time ')+str(time)) if time is not None else text('视频 ','Video ')+f'{frame["source_time_s"]:.1f}s'
            state=text('已复核','Reviewed') if unit.get('reviewed') else text('待复核','Unreviewed')
            distance=''
            roster={u['id']:u for u in project['units']}
            current=roster.get(uid,{})
            enemy=next((u for u in project['units'] if u['kind']=='hero' and u['side']!=current.get('side')),None)
            center=unit.get('center');other=observed.get('units',{}).get(enemy['id'],{}).get('center') if enemy else None
            if center and other:
                pixels=math.hypot(center[0]-other[0],center[1]-other[1])
                distance=text('；与敌方英雄距离 ','; distance to enemy hero ')+f'{pixels:.1f} px'
                scale=project.get('calibration')
                if scale:distance+=text(' / 约 ',' / approx. ')+f'{pixels*scale["units_per_pixel"]:.1f} '+text('游戏单位','game units')
            lines.append(f'- {clock} · {uid} · '+', '.join(f'{k}={v}' for k,v in event.items())+distance+f' · {state}')
    if not events:lines.append(text('尚无可核验动作；请使用当前帧或全部帧的 Skill 协助标注。','No auditable actions yet. Use current-frame or all-frame Skill assistance.'))
    lines += ['',text('## 改进建议','## Recommendations'),'']
    for side,data in (result.get('scores') or {}).items():
        missing=(data.get('layered_score') or {}).get('missing') or data.get('missing') or []
        if missing:lines.append(f'- {side}: '+text('补齐评分证据：','Complete scoring evidence: ')+', '.join(missing))
    lines.append(text('- 逐事件比较补刀收益、对手状态消耗和自身成本。只有确认距离、动作占用和攻击阶段后，才能指出错失窗口；仅凭血量变化不能判定走位或施法错误。','- Compare receipts, opponent state costs and own costs at each event. A missed window requires distance, action occupation and phase evidence; HP loss alone does not establish a positioning or casting error.'))
    markdown='\n'.join(lines)+'\n'
    path=output/f'analysis_report_{"en" if en else "zh"}.md'
    path.write_text(markdown,encoding='utf-8')
    return {'status':result['status'],'markdown':markdown,'report':path.relative_to(directory).as_posix(),
            'scores':result.get('scores'),'requires_skill':result['status']!='scored'}
