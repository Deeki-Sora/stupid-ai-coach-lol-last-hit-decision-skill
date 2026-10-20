"""Run analysis-page actions from chat and retain their state for browser reloads."""
from pathlib import Path
from .core import read_json,write_json
from .request_commands import resolve_workspace


def _path(directory,relative):
    path=(directory/relative).resolve()
    if not path.is_relative_to(directory):raise ValueError('Planning files must stay inside the workspace')
    return path


def saved_state(directory):
    directory=Path(directory).resolve()
    path=directory/'game_analysis/planning_state.json'
    state=read_json(path) if path.is_file() else {}
    result={}
    for key in ('task','result'):
        if state.get(key) and _path(directory,state[key]).is_file():
            result[key]=read_json(_path(directory,state[key]))
    if 'result' in result:result['result_kind']=state.get('result_kind')
    return result


def perform(workspace,action,*,frame_id=None,frame_number=None,source_time_s=None,side=None,horizon=3.0,task=None,task_file=None):
    directory=resolve_workspace(workspace)
    folder=directory/'game_analysis';folder.mkdir(exist_ok=True)
    state_file=folder/'planning_state.json'
    state=read_json(state_file) if state_file.is_file() else {}
    result={'workspace':str(directory),'action':action}
    if action=='refresh':
        from .assistance import ensure_mechanics
        return {**result,**ensure_mechanics(directory)}
    if action in ('plan','draft'):
        project=read_json(directory/'project.json')
        if frame_number is not None:
            if isinstance(frame_number,bool) or not isinstance(frame_number,int) or not 1<=frame_number<=len(project['frames']):
                raise ValueError('frame_number must identify a displayed one-based frame')
            selected=project['frames'][frame_number-1]
            if frame_id and frame_id!=selected['id']:raise ValueError('Frame ID and number disagree')
            frame_id=selected['id']
        frame=next((f for f in project['frames'] if f['id']==frame_id),None)
        if frame is None and not frame_id and frame_number is None and source_time_s is not None:
            from .window_planner import _nearest_frame
            frame=_nearest_frame(project,source_time_s=source_time_s);frame_id=frame['id']
        if frame is None:raise ValueError('Specify --frame or --frame-number; do not guess the current frame')
        result['frame_context']={'frame_id':frame_id,'frame_number':project['frames'].index(frame)+1,'source_time_s':frame['source_time_s'],
            'game_time_s':read_json(directory/'annotations.json')['frames'].get(frame_id,{}).get('game_time_s')}
    if action=='plan':
        from .core import export_tables
        from .window_planner import plan_window,markdown
        export_tables(directory)
        plan=plan_window(directory,side=side,frame_id=frame_id,horizon_s=horizon)
        (directory/'assessment').mkdir(exist_ok=True)
        (directory/'assessment/window_plan.md').write_text(markdown(plan),encoding='utf-8')
        state.update(result='window_plan.json',result_kind='plan')
        result.update(status=plan['status'],result=plan)
    elif action=='draft':
        from .game_tools import draft
        task=draft(project,read_json(directory/'annotations.json'),frame_id,directory)
    elif action in ('apply-observations','run'):
        task=task if task is not None else read_json(_path(directory,task_file or state.get('task','game_analysis/draft_task.json')))
        if not isinstance(task,dict):raise ValueError('Planning task must be an object')
        if action=='apply-observations':
            from .assistance import ensure_mechanics
            from copy import deepcopy
            task=deepcopy(task)
            models=ensure_mechanics(directory)['models']['models']
            stochastic=task.setdefault('stochastic',dict(samples=16,seed=0,models=[],effects=[]))
            ids={m['id'] for m in models}
            stochastic['models']=[m for m in stochastic.get('models',[]) if m['id'] not in ids]+models
            result['model_count']=len(models)
        else:
            from .game_tools import save_run
            saved=save_run(directory,task)
            result.update(saved)
            if 'result' in saved:state.update(result=f'game_analysis/{saved["folder"]}/result.json',result_kind='run')
    else:
        raise ValueError('Unknown planning action')
    if action in ('draft','apply-observations'):
        state['task']='game_analysis/draft_task.json'
        state.pop('result',None);state.pop('result_kind',None)
        write_json(directory/state['task'],task)
        result.update(task=task,saved=state['task'])
    write_json(state_file,state)
    return result
