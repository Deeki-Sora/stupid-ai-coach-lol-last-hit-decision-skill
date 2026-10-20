"""Video sampling and health-bar-center annotation workbench."""
from pathlib import Path
from datetime import datetime
import argparse
import json
from workbench.core import (ROOT, VIDEO_SUFFIXES, sample, seconds, calibration,
    read_json, write_json, export_tables, export_assessment, suggest_bars, default_calibration)
from workbench.operations import import_csv, fetch_hero_data, solve_matrix


def create(video, output, start, end, step, scale=None, proposals=False, first_wave_template=False):
    project = sample(Path(video).resolve(),Path(output).resolve(),seconds(start),seconds(end),float(step),first_wave_template)
    project['calibration'] = None if scale in ('0', 'pixel-only') else (calibration(scale) if scale else default_calibration())
    write_json(Path(output)/'project.json',project)
    if proposals:
        write_json(Path(output)/'proposals.json',{
            f['id']:suggest_bars(Path(output)/f['image']) for f in project['frames']})
    export_tables(output)
    print('Created:',Path(output).resolve(),flush=True)
    return Path(output)


def interactive():
    print('LOL short-window last-hit evaluation workbench')
    print('Video timestamps are source-video times, not the game clock.')
    folder_text = input('Video folder [input_videos] (or type choose for a folder dialog): ').strip()
    if folder_text.lower() == 'choose':
        from tkinter import Tk, filedialog
        root = Tk();root.withdraw()
        folder_text = filedialog.askdirectory(title='Select video folder')
        root.destroy()
        if not folder_text:
            return
    folder = Path(folder_text or ROOT/'input_videos').expanduser().resolve()
    files = sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_SUFFIXES)
    if not files:
        raise ValueError('No supported videos found. Put videos in input_videos or select another folder.')
    for i,file in enumerate(files,1):
        print(f'{i}: {file.name}')
    indices = [int(x.strip())-1 for x in input('Video number(s), comma separated: ').split(',')]
    if not indices or len(set(indices))!=len(indices) or any(i<0 or i>=len(files) for i in indices):
        raise ValueError('invalid video selection')
    step = float(input('Sampling interval, 0.1 to 0.5 seconds [0.3]: ') or '.3')
    scale = input('Pixel calibration, e.g. 189=350 [blank: use default 0.459=1; type 0 for pixels only]: ').strip()
    if scale == '0': scale = 'pixel-only'
    template = input('Use first-wave roster template (3 melee + 3 caster per side)? [y/N]: ').strip().lower()=='y'
    session = ROOT/'runs'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    workspaces=[]
    for i in indices:
        print(files[i].name)
        start=input('Clip start (seconds or MM:SS): ')
        end=input('Clip end (seconds or MM:SS): ')
        workspaces.append(create(files[i],session/f'clip_{len(workspaces)+1:02d}',start,end,step,scale,first_wave_template=template))
    from workbench.server import review
    for workspace in workspaces:
        review(workspace)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command')
    s=sub.add_parser('sample',help='Sample one video; repeat for multiple files')
    s.add_argument('--video',required=True);s.add_argument('--output',required=True)
    s.add_argument('--start',required=True);s.add_argument('--end',required=True)
    s.add_argument('--step',type=float,default=.3);s.add_argument('--scale')
    s.add_argument('--proposals',action='store_true',help='Optional color-fill candidates; require manual full-bar-center confirmation')
    s.add_argument('--review',action='store_true')
    s.add_argument('--first-wave-template',action='store_true',help='Explicit first-wave minion roster; otherwise start with heroes only')
    r=sub.add_parser('review');r.add_argument('project');r.add_argument('--no-browser',action='store_true');r.add_argument('--port',type=int,default=58392)
    e=sub.add_parser('export');e.add_argument('project')
    i=sub.add_parser('import-table');i.add_argument('project');i.add_argument('csv');i.add_argument('--encoding',default='utf-8-sig')
    f=sub.add_parser('fetch-data');f.add_argument('--version',required=True);f.add_argument('--blue',required=True)
    f.add_argument('--red',required=True);f.add_argument('--language',default='en_US');f.add_argument('--output',required=True)
    mp=sub.add_parser('fetch-matchup-prior',help='Fetch a patch-scoped matchup prior into a workbench')
    mp.add_argument('--workspace',required=True);mp.add_argument('--version',required=True);mp.add_argument('--blue',required=True);mp.add_argument('--red',required=True)
    mp.add_argument('--level',required=True,type=int);mp.add_argument('--lane',default='middle');mp.add_argument('--tier',default='emerald_plus');mp.add_argument('--provider',default='lolalytics_web')
    mp.add_argument('--no-aggregate',action='store_true');mp.add_argument('--url-template')
    mm=sub.add_parser('save-matchup-prior',help='Save a manual matchup prior; blank rates mean 50:50')
    mm.add_argument('--workspace',required=True);mm.add_argument('--version',required=True);mm.add_argument('--blue',required=True);mm.add_argument('--red',required=True)
    mm.add_argument('--level',required=True,type=int);mm.add_argument('--blue-win-rate');mm.add_argument('--red-win-rate')
    mm.add_argument('--tier',default='unknown');mm.add_argument('--lane',default='unknown');mm.add_argument('--source',default='manual user entry');mm.add_argument('--notes',default='');mm.add_argument('--level-specific',action='store_true')
    ss=sub.add_parser('search-strategy',help='Search optional champion mechanics and matchup references')
    ss.add_argument('--workspace',required=True);ss.add_argument('--version',required=True);ss.add_argument('--blue',required=True);ss.add_argument('--red',required=True)
    ss.add_argument('--level',type=int);ss.add_argument('--language',default='en');ss.add_argument('--max-results',type=int,default=5)
    vp=sub.add_parser('vision-track',help='Generate optional color-bar candidate tracks for manual confirmation')
    vp.add_argument('--workspace',required=True);vp.add_argument('--max-jump-px',type=float,default=120.0);vp.add_argument('--max-missed',type=int,default=2);vp.add_argument('--detector',choices=['auto','color','yolo','rtdetr'],default='auto');vp.add_argument('--weights');vp.add_argument('--tracker',choices=['bytetrack','botsort'],default='bytetrack')
    ho=sub.add_parser('hud-ocr',help='Generate optional OCR proposals for clock, CS, HP and cooldown text')
    ho.add_argument('--workspace',required=True);ho.add_argument('--max-frames',type=int)
    wp=sub.add_parser('plan-window',help='Rank next-window minion actions from the current observation')
    wp.add_argument('--workspace',required=True);wp.add_argument('--side',choices=['blue','red'],required=True);wp.add_argument('--frame');wp.add_argument('--source-time',type=float);wp.add_argument('--game-time',type=float);wp.add_argument('--horizon',type=float,default=3.0);wp.add_argument('--output')
    st=sub.add_parser('start',help='Start the guided workbench; opens the local browser UI')
    st.add_argument('--workspace');st.add_argument('--no-browser',action='store_true');st.add_argument('--port',type=int,default=58392)
    sst=sub.add_parser('service-start',help='Start one background workbench service and print its URL')
    sst.add_argument('--workspace');sst.add_argument('--port',type=int,default=58392)
    sub.add_parser('service-stop',help='Stop the background workbench service')
    ssr=sub.add_parser('service-restart',help='Restart the background workbench service and print its new URL')
    ssr.add_argument('--workspace');ssr.add_argument('--port',type=int,default=58392)
    sub.add_parser('service-status',help='Show the background workbench service and URL')
    m=sub.add_parser('fetch-minions',help='Fetch patch-scoped minion candidates; unresolved fields keep generic defaults')
    m.add_argument('--version',required=True);m.add_argument('--output',required=True)
    cp=sub.add_parser('import-codex',help='Parse saved Riot Codex text into an unverified reference profile')
    cp.add_argument('--input',required=True);cp.add_argument('--source',required=True);cp.add_argument('--patch')
    g=sub.add_parser('solve');g.add_argument('--matrix',required=True);g.add_argument('--output',required=True)
    gd=sub.add_parser('game-draft',help='Create an unverified optional planning task from a chosen observation')
    gd.add_argument('project');gd.add_argument('--frame',required=True);gd.add_argument('--output',required=True)
    gr=sub.add_parser('game-run',help='Run an explicitly enabled bounded event task; no solver required for comparison')
    gr.add_argument('project');gr.add_argument('--task',required=True)
    mt=sub.add_parser('mechanics-template');mt.add_argument('--output',required=True)
    me=sub.add_parser('estimate-probabilities');me.add_argument('--csv',required=True);me.add_argument('--output',required=True)
    ls=sub.add_parser('layer-score',help='Evaluate a conditional layered decision JSON specification')
    ls.add_argument('--input',required=True);ls.add_argument('--output')
    sa=sub.add_parser('skill-audit',help='Export and audit every workbench artifact for the evaluator skill')
    sa.add_argument('--workspace',required=True);sa.add_argument('--output',required=True)
    se=sub.add_parser('skill-evaluate',help='Run the evaluator skill backend against a complete workbench export')
    se.add_argument('--workspace',required=True);se.add_argument('--config');se.add_argument('--output',required=True);se.add_argument('--matchup-prior')
    vs=sub.add_parser('vision-status',help='Show optional AI-assisted visual proposal providers')
    vs.add_argument('--output')
    vi=sub.add_parser('vision-import',help='Validate AI visual proposals without accepting annotations')
    vi.add_argument('--input',required=True);vi.add_argument('--output',required=True)
    ai=sub.add_parser('assistant-import',help='Stage Skill visual proposals in the workbench for player review')
    ai.add_argument('--workspace',required=True);ai.add_argument('--input',required=True)
    aq=sub.add_parser('assistant-read',help='Find and read a pending workbench request for the AI Skill')
    aq.add_argument('--workspace');aq.add_argument('--kind',choices=['annotation','configuration','mechanics','analysis','strategy','matchup'])
    aq.add_argument('--scope',choices=['current','all']);aq.add_argument('--start',action='store_true')
    ast=sub.add_parser('assistant-status',help='Show the current workbench request')
    ast.add_argument('--workspace')
    ac=sub.add_parser('assistant-cancel',help='Cancel the current workbench request')
    ac.add_argument('--workspace')
    af=sub.add_parser('assistant-finish',help='Validate and save the Skill response for workbench refresh')
    af.add_argument('--workspace',required=True);af.add_argument('--input',required=True)
    ar=sub.add_parser('analyze',help='Run the evaluator and write a readable timeline report')
    ar.add_argument('--workspace',required=True);ar.add_argument('--language',choices=['zh','en'],default='zh')
    args=p.parse_args(argv)
    try:
        if not args.command:
            from workbench.server import review
            return review()
        if args.command=='sample':
            workspace=create(args.video,args.output,args.start,args.end,args.step,args.scale,args.proposals,args.first_wave_template)
            if args.review:
                from workbench.server import review
                review(workspace)
        elif args.command=='review':
            from workbench.server import review
            review(args.project,not args.no_browser,args.port)
        elif args.command=='export':
            print(json.dumps(export_assessment(args.project),indent=2))
        elif args.command=='import-table':
            print(json.dumps(import_csv(args.project,args.csv,args.encoding),indent=2))
        elif args.command=='fetch-data':
            write_json(args.output,fetch_hero_data(args.version,args.blue,args.red,args.language))
            print('Base data saved. Verify effective stats, runes, items, ranks and passive state before evaluation.')
        elif args.command=='fetch-matchup-prior':
            from workbench.matchup_data import fetch_matchup_prior
            result=fetch_matchup_prior(args.workspace,version=args.version,blue=args.blue,red=args.red,level=args.level,lane=args.lane,tier=args.tier,provider=args.provider,allow_aggregate=not args.no_aggregate,url_template=args.url_template)
            print(json.dumps(result,ensure_ascii=False,indent=2))
        elif args.command=='save-matchup-prior':
            from workbench.matchup_data import save_manual_matchup_prior
            result=save_manual_matchup_prior(args.workspace,version=args.version,blue=args.blue,red=args.red,level=args.level,
                blue_win_rate=args.blue_win_rate,red_win_rate=args.red_win_rate,tier=args.tier,lane=args.lane,source=args.source,
                notes=args.notes,level_specific=args.level_specific)
            print(json.dumps(result,ensure_ascii=False,indent=2))
        elif args.command=='search-strategy':
            from workbench.strategy_search import search_strategy
            result=search_strategy(args.workspace,version=args.version,blue=args.blue,red=args.red,level=args.level,
                language=args.language,max_results=args.max_results)
            print(json.dumps({'saved':'references/strategy_search.json','queries':len(result['queries']),
                              'result_groups':len(result['results']),'errors':result['errors']},ensure_ascii=False,indent=2))
        elif args.command=='vision-track':
            from workbench.vision_tracking import track_project
            result=track_project(args.workspace,max_jump_px=args.max_jump_px,max_missed=args.max_missed,detector=args.detector,weights=args.weights,tracker=args.tracker)
            print(json.dumps({'saved':'vision_candidates.json','proposals':len(result['proposals']),
                              'proposal_only':result['proposal_only']},ensure_ascii=False,indent=2))
        elif args.command=='hud-ocr':
            from workbench.hud_ocr import ocr_project
            result=ocr_project(args.workspace,max_frames=args.max_frames)
            print(json.dumps({'saved':'hud_candidates.json','frames':len(result['proposals']),
                              'proposal_only':result['proposal_only']},ensure_ascii=False,indent=2))
        elif args.command=='plan-window':
            from workbench.window_planner import plan_window, markdown
            result=plan_window(args.workspace,side=args.side,frame_id=args.frame,source_time_s=args.source_time,
                               horizon_s=args.horizon,game_time_s=args.game_time)
            target=Path(args.output) if args.output else Path(args.workspace)/'assessment'/'window_plan.md'
            target.parent.mkdir(parents=True,exist_ok=True);target.write_text(markdown(result),encoding='utf-8')
            print(json.dumps({'status':result['status'],'saved':str(target),'candidates':len(result['candidates']),
                              'missing_inputs':result['missing_inputs']},ensure_ascii=False,indent=2))
        elif args.command=='start':
            from workbench.server import review
            if args.workspace:
                review(args.workspace, not args.no_browser,args.port)
            else:
                review(None, not args.no_browser,args.port)
        elif args.command in {'service-start','service-stop','service-restart','service-status'}:
            from workbench import service_control
            if args.command=='service-start':result=service_control.start(workspace=args.workspace,port=args.port)
            elif args.command=='service-stop':result=service_control.stop()
            elif args.command=='service-restart':result=service_control.restart(workspace=args.workspace,port=args.port)
            else:result=service_control.status()
            print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        elif args.command=='fetch-minions':
            from workbench.minion_data import load_profiles
            profiles=load_profiles(Path(args.output).parent,args.version,fetch=True)
            write_json(args.output,profiles)
            print(json.dumps({'version':args.version,'sources':len(profiles['sources']),'warnings':profiles['warnings']},ensure_ascii=False))
        elif args.command=='import-codex':
            from workbench.reference_profiles import codex_text_to_reference
            reference=codex_text_to_reference(Path(args.input).read_text(encoding='utf-8'),args.source,args.patch)
            write_json(args.output,reference)
            print(json.dumps({'patch':reference['patch'],'stats':len(reference['base_stats']),'abilities':len(reference['ability_reference']),'verified':False},ensure_ascii=False))
        elif args.command=='solve':
            write_json(args.output,solve_matrix(read_json(args.matrix)))
        elif args.command=='game-draft':
            from workbench.game_tools import draft
            directory=Path(args.project)
            write_json(args.output,draft(read_json(directory/'project.json'),read_json(directory/'annotations.json'),args.frame,directory))
        elif args.command=='game-run':
            from workbench.game_tools import save_run
            saved=save_run(args.project,read_json(args.task))
            print(json.dumps({'folder':saved['folder'],'status':saved['result']['status'],'effective_horizon_s':saved['result']['effective_horizon_s'],'samples':saved['result']['samples']} if 'result' in saved else saved,indent=2))
        elif args.command=='mechanics-template':
            from workbench.mechanic_observations import template
            Path(args.output).write_text(template(),encoding='utf-8-sig')
        elif args.command=='estimate-probabilities':
            from workbench.mechanic_observations import estimate
            write_json(args.output,estimate(Path(args.csv).read_text(encoding='utf-8-sig')))
        elif args.command=='layer-score':
            from algorithms import layered_evaluation as layered
            spec=read_json(args.input)
            kind=spec.pop('kind',None)
            functions={'aggregate':layered.aggregate_layers,'window':layered.evaluate_window,
                       'joint_schedule':layered.evaluate_joint_schedule,'pressure':layered.evaluate_pressure,
                       'target':layered.evaluate_target_screen,'preparatory_damage':layered.evaluate_preparatory_damage,
                       'wait':layered.evaluate_wait,'branches':layered.evaluate_branches,
                       'final':layered.final_layer_score}
            if kind not in functions:raise ValueError('unknown layer-score kind')
            result=functions[kind](**spec)
            if args.output:write_json(args.output,result)
            else:print(json.dumps(result,ensure_ascii=False,indent=2))
        elif args.command=='skill-audit':
            from workbench.evaluation_pipeline import audit_workspace
            result=audit_workspace(args.workspace)
            write_json(args.output,{key:value for key,value in result.items() if key!='data'})
            print(json.dumps({'status':'audited','files':len(result['inventory']),'features':len(result['features'])},ensure_ascii=False))
        elif args.command=='skill-evaluate':
            from workbench.evaluation_pipeline import evaluate_workspace
            workspace=Path(args.workspace)
            config_path=Path(args.config) if args.config else workspace/'scoring_config.json'
            if not config_path.is_file():
                raise ValueError('scoring_config is required; pass --config or place scoring_config.json in the workspace')
            prior_path=Path(args.matchup_prior) if args.matchup_prior else workspace/'matchup_prior.json'
            prior=read_json(prior_path) if prior_path.is_file() else None
            result=evaluate_workspace(args.workspace,read_json(config_path),prior)
            write_json(args.output,result)
            from workbench.reports import write_evaluation_reports
            write_evaluation_reports(args.workspace,result)
            print(json.dumps({'status':result['status'],'workspace_files':result.get('backend_input_usage',{}).get('workspace_files')},ensure_ascii=False))
        elif args.command=='vision-status':
            from workbench.vision_assist import availability
            result=availability()
            if args.output:write_json(args.output,result)
            else:print(json.dumps(result,ensure_ascii=False,indent=2))
        elif args.command=='analyze':
            from workbench.analysis_task import run_analysis
            print(json.dumps(run_analysis(args.workspace,args.language),ensure_ascii=False))
        elif args.command in {'assistant-read','assistant-status','assistant-cancel','assistant-finish'}:
            from workbench import request_commands
            if args.command=='assistant-read':result=request_commands.read_request(args.workspace,kind=args.kind,scope=args.scope,start=args.start)
            elif args.command=='assistant-status':result=request_commands.request_status(args.workspace)
            elif args.command=='assistant-cancel':result=request_commands.cancel_request(args.workspace)
            else:result=request_commands.finish_request(args.workspace,read_json(args.input))
            print(json.dumps(result,ensure_ascii=False,indent=2))
        elif args.command=='assistant-import':
            from workbench.assistance import import_drafts
            print(json.dumps(import_drafts(args.workspace,read_json(args.input)),ensure_ascii=False))
        elif args.command=='vision-import':
            from workbench.vision_assist import load_proposals
            result=load_proposals(args.input)
            write_json(args.output,result)
            print(json.dumps({'proposals':len(result['proposals']),'confirmed_count':result['confirmed_count'],'writes_confirmed_annotations':False},ensure_ascii=False))
    except (ValueError,OSError,KeyError,ImportError,RuntimeError) as error:
        p.exit(2,f'Error: {error}\n')


if __name__=='__main__':
    main()
