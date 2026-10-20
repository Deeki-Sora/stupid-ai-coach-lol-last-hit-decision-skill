"""Explicit roster corrections and frame-local visibility; absence is not death."""
from pathlib import Path
import time
from .core import read_json, write_json, validate_annotations, export_tables


def update_unit(directory, unit_id, frame_id, operation):
    directory=Path(directory)
    project=read_json(directory/'project.json')
    annotations=read_json(directory/'annotations.json')
    unit=next((u for u in project['units'] if u['id']==unit_id),None)
    if unit is None or frame_id not in {f['id'] for f in project['frames']}:
        raise ValueError('Unknown unit or frame')
    if operation not in ('hide','restore','death','delete'):
        raise ValueError('Unknown unit operation')
    if operation=='delete' and unit['kind']=='hero':
        raise ValueError('Keep both champion roster entries; correct their configuration instead')
    backup=directory/'backups'/f'unit_edit_{time.time_ns()}'
    backup.mkdir(parents=True)
    write_json(backup/'project.json',project)
    write_json(backup/'annotations.json',annotations)
    if operation=='delete':
        project['units']=[u for u in project['units'] if u['id']!=unit_id]
        for frame in annotations['frames'].values():
            frame.get('units',{}).pop(unit_id,None)
            if 'distance_minions' in frame:
                frame['distance_minions']=[uid for uid in frame['distance_minions'] if uid!=unit_id]
            for data in frame.get('units',{}).values():
                if data.get('target')==unit_id:data['target']=''
    else:
        data=annotations['frames'].setdefault(frame_id,{}).setdefault('units',{}).setdefault(unit_id,{})
        if operation=='death':data.update(alive=False,reviewed=True)
        else:data['visible']=operation=='restore'
    validate_annotations(project,annotations)
    write_json(directory/'project.json',project)
    write_json(directory/'annotations.json',annotations)
    export_tables(directory)
    return {'project':project,'annotations':annotations,'backup':str(backup.relative_to(directory))}
