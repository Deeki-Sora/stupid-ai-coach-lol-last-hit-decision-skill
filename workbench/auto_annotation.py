"""Automatic full-health-bar-center annotation with class-aware Kalman tracks."""
from pathlib import Path
import hashlib
import importlib.util
import math
import os
import sys
import tempfile
import time

from .core import read_json, write_json, export_tables
from .model_bar_association import constrain_siege_candidates
from .vision_tracking import _ConstantVelocity2D

# A workspace-local wheel can satisfy BoT-SORT on locked-down Python installs.
# It contains only ``lap``; NumPy continues to come from the main environment.
_LOCAL_PACKAGES=Path(__file__).resolve().parents[1]/'.packages'
try:
    import lap as _lap  # noqa: F401
except ImportError:
    if _LOCAL_PACKAGES.is_dir():sys.path.insert(0,str(_LOCAL_PACKAGES))


def discover_weights():
    """Find the locally trained, externally reviewed baseline detectors."""
    repository=Path(__file__).resolve().parents[1]
    bundled=repository/'vision/models/yolo11n'
    unit=bundled/'unit_detector.pt'
    bar=bundled/'minion_bar_detector.pt'
    hero=bundled/'hero_detector.pt'
    return {'unit':str(unit) if unit.is_file() else None,
            'bar':str(bar) if bar.is_file() else None,
            'hero':str(hero) if hero.is_file() else None}


def auto_annotation_availability():
    """Report whether the bundled GPU YOLO path can run on this computer."""
    weights=discover_weights()
    dependencies={name:importlib.util.find_spec(name) is not None
                  for name in ('ultralytics','torch','lap')}
    cuda=False;device_name=None;cuda_error=None
    if dependencies['torch']:
        try:
            import torch
            cuda=bool(torch.cuda.is_available())
            if cuda:device_name=torch.cuda.get_device_name(0)
        except Exception as error:  # Driver/runtime failures must select fallback.
            cuda_error=str(error)
    weights_present={key:bool(value and Path(value).is_file()) for key,value in weights.items()}
    available=all(dependencies.values()) and all(weights_present.values()) and cuda
    missing=[name for name,found in dependencies.items() if not found]
    missing += [f'{name}_weights' for name,found in weights_present.items() if not found]
    if not cuda:missing.append('cuda')
    return {'available':available,'cuda':cuda,'cuda_device':device_name,'cuda_error':cuda_error,
            'dependencies':dependencies,'weights':weights_present,'weight_paths':weights,
            'missing':missing,'fallback':'opencv_or_pillow_track'}


def _fallback_track(directory,progress=None):
    """Run dependency-light bar tracking and expose its boxes in the workbench."""
    from .vision_tracking import track_project
    if progress:progress({'stage':'tracking_fallback','frame_count':0})
    tracked=track_project(directory,detector='auto')
    grouped={}
    for row in tracked.get('proposals',[]):
        grouped.setdefault(row['frame_id'],[]).append({'box':row['box'],'track_id':row['unit_id'],
            'side_guess':row.get('side_guess'),'kind_prior':row.get('kind_prior'),
            'confidence':row.get('confidence'),'requires_confirmation':True})
    write_json(Path(directory)/'proposals.json',grouped)
    result={'schema_version':1,'status':'complete','mode':'track_fallback',
            'provider':tracked.get('provider'),'written_centers':0,
            'candidate_centers':len(tracked.get('proposals',[])),'requires_review':True,
            'notes':'YOLO was disabled or unavailable. Track candidates are shown as boxes; identity remains unknown until reviewed.'}
    write_json(Path(directory)/'auto_tracking.json',result)
    return result


def run_selected_automation(directory,use_yolo=False,progress=None,force=False):
    """Run the selected automatic path, falling back safely when CUDA is unavailable."""
    availability=auto_annotation_availability()
    if use_yolo and availability['available']:
        try:
            result=auto_annotate_project(directory,force=force,progress=progress)
            if result.get('status')=='complete':
                result['mode']='yolo_cuda'
                result['availability']=availability
                write_json(Path(directory)/'auto_tracking.json',result)
                return result
            yolo_error=result.get('reason','YOLO did not complete')
        except Exception as error:
            yolo_error=str(error)
    else:
        yolo_error=None
    result=_fallback_track(directory,progress=progress)
    result['yolo_requested']=bool(use_yolo)
    result['fallback_reason']='yolo_not_selected' if not use_yolo else 'yolo_unavailable'
    if yolo_error:
        result['fallback_reason']='yolo_runtime_error'
        result['yolo_error']=yolo_error
    result['availability']=availability
    write_json(Path(directory)/'auto_tracking.json',result)
    return result


def fill_hero_bar_centers(directory,progress=None):
    """Fill only missing blue/red hero centers without rerunning unit YOLO."""
    directory=Path(directory);project=read_json(directory/'project.json')
    annotations=read_json(directory/'annotations.json');previous={};written=0;skipped=0;records=[]
    backup=directory/'annotations.before_hero_bar_repair.json'
    if not backup.exists():write_json(backup,annotations)
    for number,frame in enumerate(project.get('frames',[]),1):
        heroes=detect_hero_bars(directory/frame['image'],previous)
        for hero in heroes:previous[hero['side']]=hero['center']
        current=annotations['frames'].setdefault(frame['id'],{}).setdefault('units',{})
        for hero in heroes:
            uid=hero['side']+'_hero';item=current.setdefault(uid,{})
            if item.get('center') not in (None,''):
                skipped+=1;continue
            item['center']=hero['center'];item['reviewed']=False
            item['coordinate_method']='opencv_full_hero_bar_center_unreviewed'
            item.setdefault('ai_evidence',{})['center']={'confidence':hero['confidence'],
                'provider':hero['provider'],'image':frame['image'],
                'observed_center':hero['center'],'matched_bar_bbox':hero['bbox_xyxy']}
            written+=1
        records.append({'frame_id':frame['id'],'sides':[hero['side'] for hero in heroes]})
        if progress:progress({'stage':'hero_bar_annotation','frame_count':number,'total_frames':len(project['frames'])})
    write_json(directory/'annotations.json',annotations)
    export_warning=None
    try:export_tables(directory)
    except ValueError as error:export_warning=str(error)
    result={'status':'complete','mode':'hero_bar_repair','written_centers':written,
            'skipped_existing_centers':skipped,'requires_review':True,'export_warning':export_warning,
            'frames_without_blue_hero':sum('blue' not in row['sides'] for row in records),
            'frames_without_red_hero':sum('red' not in row['sides'] for row in records),'records':records}
    stamp=directory/'auto_tracking.json';old=read_json(stamp) if stamp.exists() else {}
    old['hero_bar_repair']=result;write_json(stamp,old)
    return result


def _sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def _detect(model, image, *, confidence, device, tracker=None):
    arguments=dict(imgsz=1920,rect=True,conf=confidence,iou=.5,max_det=1000,
                   device=device,verbose=False)
    result=(model.track(str(image),persist=True,tracker=tracker,**arguments)[0]
            if tracker else model.predict(str(image),**arguments)[0])
    rows=[]
    for box in result.boxes:
        cls=int(box.cls.item());name=str(model.names[cls]).lower()
        rows.append({'class_name':name,'confidence':float(box.conf.item()),
                     'detector_track_id':int(box.id.item()) if box.id is not None else None,
                     'bbox_xyxy':box.xyxy[0].cpu().tolist()})
    return rows


def associate_units_with_bars(units,bars):
    """Greedily pair each unit with one same-side bar at the top of its box."""
    pairs=[]
    for ui,unit in enumerate(units):
        side=unit['class_name'].split('_',1)[0]
        x0,y0,x1,y1=unit['bbox_xyxy'];ucx=(x0+x1)/2
        for bi,bar in enumerate(bars):
            if not bar['class_name'].startswith(side+'_'):continue
            a,b,c,d=bar['bbox_xyxy'];bcx,bcy=(a+c)/2,(b+d)/2
            if not x0-10<=bcx<=x1+10:continue
            if not y0-15<=bcy<=min(y0+35,y0+(y1-y0)*.45):continue
            cost=abs(bcy-y0-4)+.3*abs(bcx-ucx)
            pairs.append((cost,ui,bi,[round(bcx,2),round(bcy,2)]))
    used_units=set();used_bars=set();matched=[]
    for _,ui,bi,center in sorted(pairs):
        if ui in used_units or bi in used_bars:continue
        used_units.add(ui);used_bars.add(bi)
        matched.append({**units[ui],'center':center,
                        'matched_bar_bbox':bars[bi]['bbox_xyxy'],
                        'kind':units[ui]['class_name'].split('_',1)[1],
                        'side':units[ui]['class_name'].split('_',1)[0]})
    return matched


def detect_hero_bars(image,previous=None):
    """Detect normal-view hero health bars from their level-badge geometry.

    The minion-bar model deliberately excludes heroes. Hero bars are wider and
    have a level badge immediately to the left, so this conservative detector
    requires both a large team-colour component and two full-width dark border
    rows. It returns measured bar centers only; it does not infer hidden bars.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []
    frame=cv2.imread(str(image))
    if frame is None:return []
    height,width=frame.shape[:2];scale=min(width/1920.0,height/1080.0)
    hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV);gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    masks={
        'blue':cv2.inRange(hsv,(85,55,45),(135,255,255)),
        'red':cv2.bitwise_or(cv2.inRange(hsv,(0,70,45),(12,255,255)),
                             cv2.inRange(hsv,(165,70,45),(179,255,255))),
    }
    kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(max(3,int(round(5*scale))),max(1,int(round(2*scale)))))
    masks={side:cv2.morphologyEx(mask,cv2.MORPH_CLOSE,kernel) for side,mask in masks.items()}
    edges=cv2.Canny(gray,30,100);candidates=[];bar_width=max(65,int(round(110*scale)))
    badge_min=max(12,int(round(18*scale)));badge_max=max(badge_min+2,int(round(38*scale)))
    lower=max(8,int(round(10*scale)));upper=max(lower+1,int(round(16*scale)))
    for contour in cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)[0]:
        x,y,w,h=cv2.boundingRect(contour)
        if not badge_min<=w<=badge_max or not badge_min<=h<=max(badge_max,int(round(40*scale))):continue
        if x<.15*width or x>.80*width or y<.075*height or y>.68*height:continue
        best=None
        for bar_x in range(max(0,x+w-int(round(4*scale))),min(width-bar_width,x+w+int(round(4*scale))+1)):
            rows=[]
            for row in range(max(0,y-int(4*scale)),min(height,y+h+int(4*scale)+1)):
                fraction=float(np.mean(gray[row,bar_x:bar_x+bar_width]<45))
                if fraction>=.82:rows.append((row,fraction))
            for top,top_score in rows:
                if top>y+int(round(10*scale)):continue
                for bottom,bottom_score in rows:
                    if not lower<=bottom-top<=upper:continue
                    areas={side:float(np.mean(mask[top+1:bottom,bar_x:bar_x+bar_width]>0))
                           for side,mask in masks.items()}
                    side=max(areas,key=areas.get);coloured=areas[side]
                    if coloured<.04:continue
                    score=top_score+bottom_score+min(.5,coloured)
                    if best is None or score>best[0]:best=(score,side,bar_x,top,bottom,coloured)
        if best:
            score,side,bar_x,top,bottom,coloured=best
            candidates.append({'side':side,'center':[round(bar_x+bar_width/2,2),round((top+bottom)/2,2)],
                'bbox_xyxy':[bar_x,top,bar_x+bar_width,bottom],
                'confidence':round(min(.95,.55+.15*(score-1.64)+coloured),4),
                'provider':'opencv_hero_bar_geometry'})
    # When a low-health fill no longer connects to the level-badge edge, the
    # large team-colour component still provides a conservative second route.
    for side,mask in masks.items():
        for contour in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
            x,y,w,h=cv2.boundingRect(contour)
            if not 70*scale<=w<=180*scale or not 8*scale<=h<=32*scale or w/max(h,1)<3:continue
            if x<.15*width or x>.80*width or y<.075*height or y>.68*height:continue
            for bar_x in range(max(0,x+int(round(18*scale))),min(width-bar_width,x+int(round(27*scale)))+1):
                dark=[]
                for row in range(max(0,y-int(6*scale)),min(height,y+h+int(10*scale)+1)):
                    fraction=float(np.mean(gray[row,bar_x:bar_x+bar_width]<45))
                    if fraction>=.82:dark.append((row,fraction))
                found=None
                for top,top_score in dark:
                    for bottom,bottom_score in dark:
                        if not lower<=bottom-top<=upper:continue
                        coloured=float(np.mean(mask[top+1:bottom,bar_x:bar_x+bar_width]>0))
                        if coloured>=.04:
                            score=top_score+bottom_score+min(.5,coloured)
                            if found is None or score>found[0]:found=(score,top,bottom,coloured)
                if found:
                    score,top,bottom,coloured=found
                    candidates.append({'side':side,'center':[round(bar_x+bar_width/2,2),round((top+bottom)/2,2)],
                        'bbox_xyxy':[bar_x,top,bar_x+bar_width,bottom],
                        'confidence':round(min(.95,.58+.14*(score-1.64)+coloured),4),
                        'provider':'opencv_hero_bar_geometry'})
    # At most one champion per side is in this two-player lane workspace.
    selected=[]
    for side in ('blue','red'):
        rows=[]
        for row in sorted((item for item in candidates if item['side']==side),key=lambda item:item['confidence'],reverse=True):
            if not any(math.hypot(row['center'][0]-kept['center'][0],row['center'][1]-kept['center'][1])<10 for kept in rows):
                rows.append(row)
        if not rows:continue
        prior=(previous or {}).get(side)
        if prior:
            near=[row for row in rows if math.hypot(row['center'][0]-prior[0],row['center'][1]-prior[1])<=300*scale]
            if near:
                selected.append(min(near,key=lambda row:math.hypot(row['center'][0]-prior[0],row['center'][1]-prior[1])-40*row['confidence']))
                continue
            rows=[row for row in rows if row['confidence']>=.9]
            if not rows:continue
        selected.append(min(rows,key=lambda row:(abs(row['center'][0]-width*.5)+.35*abs(row['center'][1]-height*.35)-300*row['confidence'])))
    return selected


class ClassAwareKalmanTracker:
    """Minimum-displacement assignment constrained by side and unit kind."""
    def __init__(self,roster,max_jump_px=120.0,max_missed=2):
        self.max_jump_px=float(max_jump_px);self.max_missed=int(max_missed)
        self.available={}
        for unit in roster:
            key=(unit.get('side'),unit.get('kind'))
            if unit.get('kind') in {'melee','caster','siege','super'}:
                self.available.setdefault(key,[]).append(unit['id'])
        for ids in self.available.values():ids.sort()
        self.tracks={};self.used_ids=set();self.serial={}
        self.detector_ids={}

    def _new_id(self,side,kind):
        available=[x for x in self.available.get((side,kind),[]) if x not in self.used_ids]
        if available:return available[0],False
        key=(side,kind);self.serial[key]=self.serial.get(key,0)+1
        while True:
            value=f'{side}_{kind}_auto_{self.serial[key]:03d}'
            if value not in self.used_ids:return value,True
            self.serial[key]+=1

    def update(self,detections,dt):
        predictions={uid:track['filter'].predict(dt) for uid,track in self.tracks.items()
                     if track['missed']<=self.max_missed}
        candidates=[]
        for uid,predicted in predictions.items():
            track=self.tracks[uid]
            for index,item in enumerate(detections):
                if (track['side'],track['kind'])!=(item['side'],item['kind']):continue
                distance=math.hypot(predicted[0]-item['center'][0],predicted[1]-item['center'][1])
                if distance<=self.max_jump_px:candidates.append((distance,uid,index))
        used_tracks=set();used_detections=set();rows=[]
        for distance,uid,index in sorted(candidates):
            if uid in used_tracks or index in used_detections:continue
            used_tracks.add(uid);used_detections.add(index)
            track=self.tracks[uid];item=detections[index]
            filtered=track['filter'].update(item['center'],dt);track['missed']=0
            detector_id=item.get('detector_track_id')
            if detector_id is not None:self.detector_ids[(item['side'],item['kind'],detector_id)]=uid
            rows.append({**item,'unit_id':uid,'center':[round(v,2) for v in filtered],
                         'observed_center':item['center'],'tracking':'kalman_minimum_displacement',
                         'match_distance_px':round(distance,2),'new_unit':False})
        for uid,track in self.tracks.items():
            if uid not in used_tracks:track['missed']+=1
        # BoT-SORT is a fallback only. It may reconnect through overlap or a
        # short occlusion, but it cannot cross side/kind boundaries.
        for index,item in enumerate(detections):
            if index in used_detections or item.get('detector_track_id') is None:continue
            key=(item['side'],item['kind'],item['detector_track_id']);uid=self.detector_ids.get(key)
            if uid is None or uid in used_tracks:continue
            track=self.tracks.get(uid)
            if track is None:
                self.tracks[uid]={'side':item['side'],'kind':item['kind'],
                                  'filter':_ConstantVelocity2D(item['center']),'missed':0}
                filtered=item['center']
            else:
                filtered=track['filter'].update(item['center'],dt);track['missed']=0
            used_tracks.add(uid);used_detections.add(index)
            rows.append({**item,'unit_id':uid,'center':[round(v,2) for v in filtered],
                         'observed_center':item['center'],'tracking':'botsort_id_fallback',
                         'match_distance_px':None,'new_unit':False})
        for index,item in enumerate(detections):
            if index in used_detections:continue
            uid,created=self._new_id(item['side'],item['kind']);self.used_ids.add(uid)
            self.tracks[uid]={'side':item['side'],'kind':item['kind'],
                              'filter':_ConstantVelocity2D(item['center']),'missed':0}
            detector_id=item.get('detector_track_id')
            if detector_id is not None:self.detector_ids[(item['side'],item['kind'],detector_id)]=uid
            rows.append({**item,'unit_id':uid,'center':item['center'],
                         'observed_center':item['center'],'tracking':'new_class_consistent_track',
                         'match_distance_px':None,'new_unit':created})
        self.tracks={uid:t for uid,t in self.tracks.items() if t['missed']<=self.max_missed}
        return rows


def _hero_bar_center_from_box(box):
    """Convert the expanded hero box (badge + full bar) to full-bar center."""
    x0,y0,x1,y1=map(float,box)
    badge_width=min(38.0,max(18.0,(x1-x0)*.24))
    return [round(x0+badge_width+(x1-x0-badge_width)/2,2),round((y0+y1)/2,2)]


def _select_hero_detections(rows,previous=None):
    selected=[]
    for side in ('blue','red'):
        choices=[row for row in rows if row.get('class_name')==side+'_hero']
        if not choices:continue
        prior=(previous or {}).get(side)
        if prior:
            choices.sort(key=lambda row: math.hypot(*(_hero_bar_center_from_box(row['bbox_xyxy'])[i]-prior[i] for i in (0,1))) - 250*row['confidence'])
        else:
            choices.sort(key=lambda row: row['confidence'],reverse=True)
        row=dict(choices[0]);row['side']=side
        row['center']=_hero_bar_center_from_box(row['bbox_xyxy']);selected.append(row)
    return selected


def auto_annotate_project(directory,*,unit_weights=None,bar_weights=None,hero_weights=None,max_jump_px=120.0,
                          max_missed=2,tracker='botsort.yaml',force=False,progress=None):
    """Detect, track and write unreviewed centers directly into a workspace."""
    directory=Path(directory);project=read_json(directory/'project.json')
    annotations=read_json(directory/'annotations.json')
    defaults=discover_weights();unit_weights=unit_weights or defaults['unit'];bar_weights=bar_weights or defaults['bar'];hero_weights=hero_weights or defaults['hero']
    if not unit_weights or not bar_weights or not hero_weights:return {'status':'unavailable','reason':'trained unit/bar/hero weights not found'}
    stamp=directory/'auto_tracking.json'
    signature={'frames':[(f['id'],f['source_time_s'],f['image']) for f in project['frames']],
               'unit_sha256':_sha(unit_weights),'bar_sha256':_sha(bar_weights),'hero_sha256':_sha(hero_weights),
               'max_jump_px':max_jump_px,'max_missed':max_missed,'fallback_tracker':tracker}
    if not force and stamp.exists():
        old=read_json(stamp)
        if old.get('signature')==signature and old.get('status')=='complete':return old
    try:
        settings=Path(tempfile.gettempdir())/'lol-workbench-ultralytics'
        settings.mkdir(parents=True,exist_ok=True)
        os.environ.setdefault('YOLO_CONFIG_DIR',str(settings))
        from ultralytics import YOLO
        import torch
    except ImportError:
        return {'status':'unavailable','reason':'ultralytics/torch is not installed'}
    device=0 if torch.cuda.is_available() else 'cpu'
    unit_model=YOLO(unit_weights);bar_model=YOLO(bar_weights);hero_model=YOLO(hero_weights)
    identity_tracker=ClassAwareKalmanTracker(project.get('units',[]),max_jump_px,max_missed)
    added=[];written=0;hero_written=0;skipped=0;records=[];previous_time=None;hero_previous={}
    for number,frame in enumerate(project['frames'],1):
        image=directory/frame['image'];source_time=float(frame['source_time_s'])
        dt=max(.001,source_time-previous_time) if previous_time is not None else .3
        unit_rows=_detect(unit_model,image,confidence=.10,device=device,tracker=tracker)
        bar_rows=_detect(bar_model,image,confidence=.10,device=device)
        hero_rows=_detect(hero_model,image,confidence=.25,device=device)
        heroes=_select_hero_detections(hero_rows,hero_previous)
        for hero in heroes:hero_previous[hero['side']]=hero['center']
        paired=associate_units_with_bars(unit_rows,bar_rows)
        paired,rejected=constrain_siege_candidates(paired)
        tracked=identity_tracker.update(paired,dt)
        current=annotations['frames'].setdefault(frame['id'],{}).setdefault('units',{})
        for hero in heroes:
            uid=hero['side']+'_hero';item=current.setdefault(uid,{})
            if item.get('center') not in (None,''):
                skipped+=1;continue
            item['center']=hero['center'];item['reviewed']=False
            item['coordinate_method']='yolo_hero_bar_center_unreviewed'
            item.setdefault('ai_evidence',{})['center']={'confidence':hero['confidence'],
                'provider':'ultralytics_hero_detector','image':frame['image'],
                'observed_center':hero['center'],'hero_bbox':hero['bbox_xyxy'],
                'class_name':hero['class_name']}
            written+=1;hero_written+=1
        for row in tracked:
            uid=row['unit_id']
            if row['new_unit'] and not any(u['id']==uid for u in project['units']):
                project['units'].append({'id':uid,'side':row['side'],'kind':row['kind'],'wave':0,
                                         'first_seen_s':source_time,'roster_reviewed':False})
                added.append(uid)
            item=current.setdefault(uid,{})
            if item.get('center') not in (None,''):
                skipped+=1;continue
            # Kalman coordinates decide identity only. The annotation itself
            # must remain the measured center of the complete visible bar.
            item['center']=row['observed_center'];item['reviewed']=False
            item['coordinate_method']='yolo_bar_center_kalman_unreviewed'
            item.setdefault('ai_evidence',{})['center']={'confidence':round(float(row['confidence']),4),
                'provider':'ultralytics','image':frame['image'],'tracking':row['tracking'],
                'observed_center':row['observed_center'],'filtered_track_center':row['center'],
                'detector_track_id':row.get('detector_track_id'),
                'matched_bar_bbox':row['matched_bar_bbox']}
            written+=1
        records.append({'frame_id':frame['id'],'source_time_s':source_time,'detections':len(unit_rows),
                        'bar_matches':len(paired),'hero_bar_matches':len(heroes),
                        'hero_sides':[hero['side'] for hero in heroes],
                        'tracked':len(tracked),'siege_rejected':rejected})
        previous_time=source_time
        if progress:progress({'stage':'auto_annotation','frame_count':number,'total_frames':len(project['frames'])})
    write_json(directory/'project.json',project);write_json(directory/'annotations.json',annotations)
    export_warning=None
    try:export_tables(directory)
    except ValueError as error:
        # Distance-object selection is a player review concern and must not
        # invalidate otherwise valid coordinate detection.
        export_warning=str(error)
    review_summary={'frames_without_bar_matches':sum(r['bar_matches']==0 for r in records),
                    'unmatched_unit_detections':sum(r['detections']-r['bar_matches'] for r in records),
                    'frames_without_blue_hero':sum('blue' not in r['hero_sides'] for r in records),
                    'frames_without_red_hero':sum('red' not in r['hero_sides'] for r in records),
                    'new_unit_ids':len(added)}
    result={'schema_version':1,'status':'complete','completed_at_ns':time.time_ns(),'signature':signature,
            'device':str(device),'written_centers':written,'skipped_existing_centers':skipped,
            'hero_written_centers':hero_written,'added_unit_ids':added,'review_summary':review_summary,
            'export_warning':export_warning,'records':records,'requires_review':True,
            'notes':'Centers are full visible health-bar centers. Primary identity uses side/kind-constrained Kalman minimum displacement; BoT-SORT IDs are used only as a validated fallback.'}
    write_json(stamp,result);return result
