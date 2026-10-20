"""Workspace handoff for a running Skill; AI values remain reviewable drafts."""
from pathlib import Path
from copy import deepcopy
import time
import re
import math

from .core import ROOT, read_json, write_json, validate_annotations, export_tables, sha256
from .mechanic_observations import template, estimate
from .vision_assist import validate_proposals


def ensure_mechanics(directory):
    folder = Path(directory)/'mechanics'
    folder.mkdir(exist_ok=True)
    observations = folder/'observations.csv'
    if not observations.exists():
        observations.write_text(template(), encoding='utf-8-sig')
    adapters = folder/'adapters.json'
    if not adapters.exists():
        write_json(adapters, read_json(ROOT/'templates/mechanic_adapters.json'))
    result = estimate(observations.read_text(encoding='utf-8-sig'))
    write_json(folder/'estimated_models.json', result)
    return {'models':result, 'observations':'mechanics/observations.csv',
            'adapters':'mechanics/adapters.json'}


def request_assistance(directory, frame_id, kind='annotation', scope='current', language='zh', context=None):
    directory = Path(directory)
    (directory/'assistant').mkdir(exist_ok=True)
    project = read_json(directory/'project.json')
    frame = next((f for f in project['frames'] if f['id']==frame_id), None)
    if frame is None or kind not in ('annotation','configuration','mechanics','analysis','strategy','matchup') or scope not in ('current','all') or language not in ('zh','en'):
        raise ValueError('Unknown frame or assistance kind')
    previous=status(directory)
    if batch_active(previous):
        raise ValueError('An all-frame task is active; finish or cancel it before starting another request')
    mechanics=ensure_mechanics(directory)
    requested=[];image_hashes={}
    for selected in (project['frames'] if scope=='all' else [frame]):
        image=(directory/selected['image']).resolve()
        if not image.is_relative_to(directory.resolve()):raise ValueError('Requested screenshot is outside the workspace')
        if image not in image_hashes:image_hashes[image]=sha256(image) if image.is_file() else None
        requested.append(dict(selected,image_sha256=image_hashes[image]))
    captured=next(f for f in requested if f['id']==frame_id)
    annotations=read_json(directory/'annotations.json')
    revision=time.time_ns()
    value = {'schema_version':1,'status':'pending','kind':kind,'revision':revision,'request_revision':revision,
             'workspace':str(directory.resolve()),'source_sha256':project.get('source_sha256'),
             'frame':captured,'scope':scope,'language':language,'context':context or {},
             'frame_context':{'frame_id':frame_id,'frame_number':project['frames'].index(frame)+1,
                 'source_time_s':frame['source_time_s'],
                 'game_time_s':annotations.get('frames',{}).get(frame_id,{}).get('game_time_s')},
             'frames':requested,'units':project['units'],
             'output':'assistant/skill_response.json','requires_review':True,
             'instructions':'Inspect original frames with available vision tools. Identify full health-bar centers and observed actions. Use registered unit IDs; retain unknowns. Return the vision proposal schema, with evidence_image and confidence. Do not infer an attack from health loss alone. For mechanics fill observations.csv only from distinct observed casts or proc opportunities; leave unknown outcomes blank.'}
    if kind=='strategy':
        value['instructions']='Use the agent web-search tool to find champion fundamentals and matchup guides for the supplied patch and champions. Synthesize practical advice in the requested language, distinguishing mechanics, community advice and your inference. Return strategy_result with language, text, sources (title/url), patch, blue and red. Cite actual pages, never invent sources or treat community advice as a rule. Include the exact request_revision and complete through assistant-finish; reply to the player.'
    if kind=='configuration':
        value['configuration']=project.get('configuration',{})
        value['instructions']='Inspect each requested original frame using its captured frame ID and video time. Return state_snapshots with frame_id, evidence_image, confidence, provider and sides; each side may contain level, spell_ranks, items, inventory_known, event_state and stat_overrides using the loadout state schema. Keep unobservable values unknown. Never change global champions, runes or summoner identities. Static attributes are calculated from the patch catalog, level, items and shards, not estimated from pixels. Include inspected_frames even if nothing can be identified. Include the exact request_revision and complete through assistant-finish. During all-frame tasks do not ask the player to refresh until every requested frame is inspected. Reply in the requested language with completion, unknowns and review items, then ask the player to refresh.'
    if kind=='mechanics':
        from .mechanic_observations import FIELDS
        value['mechanics']={**mechanics,'fields':FIELDS}
        value['instructions']='Inspect the requested frames and existing mechanics/observations.csv. Return mechanics_observations rows using the declared fields, plus inspected_frames, unknown_items and review_items. Count each distinct cast or proc opportunity once; preserve registered actor/target IDs, video seconds, context and evidence source. Unknown eligibility or outcomes remain blank; never treat them as misses. Include the exact request_revision and complete through assistant-finish. It preserves existing observations, updates the CSV and estimates, exports event/distance/action/death tables and notifies the workbench. An empty observations list is valid when no opportunity can be identified; explain unknowns in the requested language.'
    if kind=='analysis':
        value['assessment_bundle']='assessment_bundle.zip'
        value['instructions']='Read the generated assessment_bundle.zip and its project, annotations, event/distance/action/death tables, timed configuration, strategy references and assessment framework. The Skill performs the analysis; the browser only prepares evidence. Verify observations, search matchup guidance when needed, build scoring inputs from evidence and run the declared reproducible algorithms. Do not invent scores or tune weights toward a desired ranking. Return analysis_report Markdown in the requested language, including both players component and overall scores or explicit unknowns/intervals, event-by-event evidence, costs/receipts and practical advice. Always return a report even when evidence is insufficient; unsupported fields remain unknown. Preserve global fixed selections. Include the exact request_revision and complete through assistant-finish to save the report and synchronize the tables; reply in the conversation.'
    if kind=='matchup':
        value['instructions']='Use agent web search to find the all-level matchup win rate for the exact supplied patch, blue and red champion IDs. Confirm orientation and patch on the actual source page; do not substitute lane-kill rate, pick rate or another patch. Import matchup_prior with patch, blue_champion_id, red_champion_id, blue_win_rate, red_win_rate, source URL, tier, sample_size (0 plus sample_size_unknown=true if unavailable), level="all", level_specific=false. If no verified result exists, leave the prior unchanged (default 50:50), import no rate and report the unknown item. Reply in the requested language.'
    write_json(directory/'assistant/request.json',value)
    from .request_commands import remember_workspace
    remember_workspace(directory)
    return value


def status(directory):
    path=Path(directory)/'assistant/request.json'
    return read_json(path) if path.exists() else {'status':'idle','revision':None}


def validate_request_frames(directory, request, project=None, require_images=False):
    """Bind a result to the exact video/frame/image captured by the request."""
    directory=Path(directory).resolve()
    project=project or read_json(directory/'project.json')
    if request.get('source_sha256') is not None and request['source_sha256']!=project.get('source_sha256'):
        raise ValueError('The workspace recording changed; create a new request')
    current={frame['id']:frame for frame in project['frames']}
    evidence=[];hashes={}
    for frame in request.get('frames',[]):
        actual=current.get(frame['id'])
        if actual is None or actual['image']!=frame['image'] or actual['source_time_s']!=frame['source_time_s']:
            raise ValueError('Requested frame identity or video time changed; create a new request')
        image=(directory/frame['image']).resolve()
        if not image.is_relative_to(directory):raise ValueError('Requested screenshot is outside the workspace')
        available=image.is_file()
        if require_images and not available:raise ValueError('Requested original frame is missing')
        if available and frame.get('image_sha256'):
            if image not in hashes:hashes[image]=sha256(image)
            if hashes[image]!=frame['image_sha256']:
                raise ValueError('Requested screenshot changed; create a new request')
        evidence.append({'frame_id':frame['id'],'source_time_s':frame['source_time_s'],
                         'image':str(image),'available':available})
    return evidence


def batch_active(request):
    return (request.get('kind') in ('annotation','configuration') and request.get('scope')=='all'
            and request.get('status') in ('pending','partial','running'))


def cancel(directory):
    request=status(directory)
    request.update(status='cancelled',revision=time.time_ns())
    write_json(Path(directory)/'assistant/request.json',request)
    return request


def _merge_unknown(current, incoming):
    """Fill missing state values; never overwrite a player's existing observation."""
    if isinstance(current,dict) and isinstance(incoming,dict):
        result=deepcopy(current)
        for key,value in incoming.items():
            result[key]=_merge_unknown(result.get(key),value)
        return result
    return deepcopy(incoming) if current is None or current=='' or current=='auto' else deepcopy(current)


def import_drafts(directory, payload):
    directory=Path(directory)
    proposals=validate_proposals(payload)['proposals']
    project=read_json(directory/'project.json')
    original=read_json(directory/'annotations.json')
    annotations=deepcopy(original)
    frames={f['id']:f for f in project['frames']}
    units={u['id'] for u in project['units']}
    original_project=deepcopy(project)
    request=status(directory)
    if request.get('status')=='cancelled':raise ValueError('Assistance request was cancelled')
    if payload.get('request_revision') is not None and payload['request_revision']!=request.get('request_revision',request.get('revision')):
        raise ValueError('Assistance result belongs to a different request')
    request.setdefault('request_revision',request.get('revision'))
    evidence=validate_request_frames(directory,request,project)
    available={item['frame_id'] for item in evidence if item['available']}
    observed_frames={item.get('frame_id') for key in ('proposals','frame_observations','unit_proposals','state_snapshots')
                     for item in payload.get(key,[])}
    if request.get('frames') and not observed_frames.issubset(available):
        raise ValueError('Observed values require the requested original screenshot; leave missing evidence unknown')
    if request.get('kind') in ('annotation','configuration'):
        allowed={frame['id'] for frame in request.get('frames',[])}
        submitted=set(payload.get('inspected_frames',[]))
        for key in ('proposals','frame_observations','unit_proposals','state_snapshots'):
            submitted.update(item.get('frame_id') for item in payload.get(key,[]))
        if not submitted.issubset(allowed):raise ValueError('Results must stay within the requested frames')
    for unit in payload.get('unit_proposals',[]):
        fid=unit.get('frame_id');uid=unit.get('id')
        if fid not in frames or unit.get('evidence_image')!=frames[fid]['image']:
            raise ValueError('New units require original-frame evidence')
        if not isinstance(uid,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',uid) or uid in units:
            raise ValueError('New unit ID must be unique')
        if unit.get('side') not in ('blue','red') or unit.get('kind') not in ('melee','caster','siege','super','minion','summon'):
            raise ValueError('New unit side and kind are required')
        wave=unit.get('wave',0)
        if isinstance(wave,bool) or not isinstance(wave,int) or wave<0:raise ValueError('Invalid unit wave')
        project['units'].append({key:unit[key] for key in ('id','side','kind')}|{'wave':wave,'first_seen_s':frames[fid]['source_time_s'],'roster_reviewed':False})
        units.add(uid)
    fields={'center','hp','alive','action','target','phase','action_start_s','action_end_s','notes'}
    count=0;skipped=[]
    for observed in payload.get('frame_observations',[]):
        fid=observed.get('frame_id')
        if fid not in frames or observed.get('evidence_image')!=frames[fid]['image']:
            raise ValueError('Frame observations require original-frame evidence')
        current=annotations['frames'].setdefault(fid,{})
        if current.get('game_time_s') is None and observed.get('game_time_s') is not None:
            clock=observed['game_time_s']
            if not (isinstance(clock,(int,float)) and not isinstance(clock,bool) and math.isfinite(clock) and clock>=0 or isinstance(clock,str) and re.fullmatch(r'\d{1,3}:\d{2}(?:\.\d+)?',clock)):
                raise ValueError('Game clock must be nonnegative seconds or MM:SS')
            current['game_time_s']=clock;current['game_time_reviewed']=False;count+=1
    for proposal in proposals:
        fid,uid,field=proposal['frame_id'],proposal['unit_id'],proposal['field']
        if fid not in frames or uid not in units or field not in fields:
            raise ValueError('Unknown frame, unit or unsupported annotation field')
        if proposal.get('evidence_image') != frames[fid]['image']:
            raise ValueError('AI evidence must identify the original frame image')
        item=annotations['frames'].setdefault(fid,{}).setdefault('units',{}).setdefault(uid,{})
        if item.get(field) not in (None,''):
            skipped.append({'frame_id':fid,'unit_id':uid,'field':field});continue
        item[field]=proposal['value'];item['reviewed']=False
        item.setdefault('ai_evidence',{})[field]={'confidence':proposal['confidence'],
            'provider':proposal['provider'],'image':proposal['evidence_image']}
        if field=='center':item['coordinate_method']='ai_full_bar_center_unreviewed'
        count+=1
    state_frames=set()
    for observed in payload.get('state_snapshots',[]):
        from .loadouts import validate_state
        from .catalog import catalog_path
        fid=observed.get('frame_id')
        if fid not in frames or observed.get('evidence_image')!=frames[fid]['image']:
            raise ValueError('Configuration observations require original-frame evidence')
        confidence=observed.get('confidence')
        if isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not 0<=confidence<=1 or not observed.get('provider'):
            raise ValueError('Configuration observations require confidence and provider')
        config=project.get('configuration')
        if not config:raise ValueError('Choose patch and fixed match configuration before importing frame states')
        catalog=read_json(catalog_path(directory,config['match_setup']['patch']))
        snap=next((s for s in config['snapshots'] if s['source_time_s']==frames[fid]['source_time_s']),None)
        if snap is None:
            snap={'frame_id':fid,'source_time_s':frames[fid]['source_time_s'],'sides':{}}
            config['snapshots'].append(snap)
        snap['frame_id']=fid
        snap['game_time_s']=annotations['frames'].get(fid,{}).get('game_time_s')
        sides=observed.get('sides',{})
        if not isinstance(sides,dict) or not set(sides).issubset({'blue','red'}):raise ValueError('Unknown configuration side')
        for side,data in sides.items():
            if not isinstance(data,dict) or not set(data).issubset({'level','spell_ranks','items','inventory_known','event_state','stat_overrides'}):
                raise ValueError('Only per-frame configuration fields may be imported')
            # Validate before merging so malformed values cannot hide behind a manual value.
            validate_state(data,catalog)
            for spell in data.get('event_state',{}).get('summoner_spells',{}).values():
                if spell.get('id') or spell.get('name'):raise ValueError('Summoner identities are fixed match selections')
            current=snap['sides'].get(side,{})
            merged=_merge_unknown(current,data)
            if 'items' in data:
                existing={item['slot']:deepcopy(item) for item in current.get('items',[])}
                if not current.get('inventory_known'):
                    for item in data['items']:existing.setdefault(item['slot'],deepcopy(item))
                merged['items']=list(existing.values())
            if not current.get('inventory_known') and data.get('inventory_known') is True:merged['inventory_known']=True
            merged.setdefault('event_state',{})['source']='ai'
            snap['sides'][side]=validate_state(merged,catalog)
            snap.setdefault('ai_evidence',{})[side]={'image':observed['evidence_image'],'confidence':confidence,'provider':observed['provider'],'reviewed':False}
            count+=1
        for side in ('blue','red'):snap['sides'].setdefault(side,validate_state({},catalog))
        config['snapshots'].sort(key=lambda s:s['source_time_s'])
        state_frames.add(fid)
    prior=None
    if 'matchup_prior' in payload:
        from algorithms.matchup_prior import validate_prior
        from .matchup_data import _public_patch
        prior=validate_prior(payload['matchup_prior'])
        context=request.get('context',{})
        if request.get('kind')!='matchup' or prior.get('level')!='all' or prior.get('level_specific') is not False:
            raise ValueError('Matchup assistance imports all-level rates only')
        if (prior['patch']!=_public_patch(context.get('version','')) or
            prior.get('blue_champion_id')!=context.get('blue') or prior.get('red_champion_id')!=context.get('red')):
            raise ValueError('Matchup rate patch or champion orientation does not match the request')
        if not re.match(r'https?://',prior['source']):raise ValueError('A verified source URL is required')
        prior.update(provider='skill_web_search',source_kind='agent_web_search',level_scope='all_levels')
    strategy=payload.get('strategy_result')
    if strategy is not None:
        context=request.get('context',{})
        if request.get('kind')!='strategy' or not isinstance(strategy,dict):raise ValueError('Unexpected strategy result')
        if any(strategy.get(key)!=value for key,value in {'language':request['language'],'patch':context.get('patch'),
                    'blue':context.get('blue'),'red':context.get('red')}.items()):
            raise ValueError('Strategy language, patch and champions must match the request')
        if not isinstance(strategy.get('text'),str) or not strategy['text'].strip():raise ValueError('Strategy text is required')
        sources=strategy.get('sources')
        if not isinstance(sources,list) or not sources or any(not isinstance(s,dict) or not s.get('title') or
                not isinstance(s.get('url'),str) or not re.match(r'https?://[^\s]+$',s['url']) for s in sources):
            raise ValueError('Strategy needs titled source URLs')
        project['strategy_text']=strategy['text']
    report=payload.get('analysis_report')
    if report is not None and (request.get('kind')!='analysis' or not isinstance(report,str) or not report.strip()):
        raise ValueError('Analysis report must be nonempty Markdown for an analysis request')
    mechanics=None
    if 'mechanics_observations' in payload:
        from .mechanic_observations import merge_observations
        if request.get('kind')!='mechanics':raise ValueError('Unexpected mechanics observations')
        rows=payload['mechanics_observations']
        if not isinstance(rows,list):raise ValueError('mechanics_observations must be a list')
        requested=[f for f in request.get('frames',[]) if f['id'] in available]
        for row in rows:
            if not isinstance(row,dict):raise ValueError('Observation rows must be objects')
            if row.get('actor') not in units or row.get('target') and row['target'] not in units:
                raise ValueError('Observation actor and target must use workspace unit IDs')
            if any(uid.strip() not in units for uid in str(row.get('hit_unit_ids','')).split(';') if uid.strip()):
                raise ValueError('Observation hit units must use workspace IDs')
            event_time=float(row.get('source_time_s','nan'))
            source=str(row.get('source',''))
            if not requested or not min(f['source_time_s'] for f in requested)<=event_time<=max(f['source_time_s'] for f in requested):
                raise ValueError('Observation time must stay within the requested evidence')
            if not any(f['image'] in source for f in requested):
                raise ValueError('Observation source must name a requested original screenshot')
        mechanics=merge_observations((directory/'mechanics/observations.csv').read_text(encoding='utf-8-sig'),payload['mechanics_observations'])
        count+=mechanics[2]
    inspected=set(request.get('inspected_frames',[]))|{p['frame_id'] for p in proposals}|{f['frame_id'] for f in payload.get('frame_observations',[])}|state_frames|set(payload.get('inspected_frames',[]))
    if not inspected.issubset(frames):raise ValueError('Unknown inspected frame')
    remaining=[f['id'] for f in request.get('frames',[]) if f['id'] not in inspected] if request.get('kind') in ('annotation','configuration') else []
    validate_annotations(project,annotations)
    count+=int(prior is not None)+int(strategy is not None)+int(report is not None)
    revision=time.time_ns()
    latest=status(directory)
    if latest.get('status')=='cancelled' or latest.get('request_revision',latest.get('revision'))!=request['request_revision']:
        raise ValueError('Assistance request was cancelled or replaced before saving')
    (directory/'assistant/backups').mkdir(parents=True,exist_ok=True)
    write_json(directory/f'assistant/backups/annotations_{revision}.json',original)
    write_json(directory/f'assistant/backups/project_{revision}.json',original_project)
    write_json(directory/'assistant/proposals.json',payload)
    write_json(directory/'annotations.json',annotations)
    write_json(directory/'project.json',project)
    if prior is not None:write_json(directory/'matchup_prior.json',prior)
    if strategy is not None:write_json(directory/f'assistant/strategy_result_{request["language"]}.json',strategy)
    if report is not None:
        output=directory/'assessment';output.mkdir(exist_ok=True)
        (output/f'analysis_report_{request["language"]}.md').write_text(report,encoding='utf-8')
    if mechanics is not None:
        observations=directory/'mechanics/observations.csv'
        (directory/f'assistant/backups/observations_{revision}.csv').write_bytes(observations.read_bytes())
        observations.write_text(mechanics[0],encoding='utf-8-sig')
        write_json(directory/'mechanics/estimated_models.json',mechanics[1])
    export_tables(directory)
    def accumulated(key):
        result=list(request.get(key,[]))
        for item in payload.get(key,[]):
            if item not in result:result.append(item)
        return result
    request.update(status='partial' if remaining else 'filled',revision=revision,filled_fields=request.get('filled_fields',0)+count,skipped=skipped,
                   inspected_frames=sorted(inspected),remaining_frames=remaining,
                   unknown_items=accumulated('unknown_items'),review_items=accumulated('review_items'))
    if mechanics is not None:
        request['mechanics_coverage']=mechanics[1]['coverage']
        request['review_items'] += [{'observation_conflict':item,'retained':'existing value'} for item in mechanics[3]]
    write_json(directory/'assistant/request.json',request)
    return request
