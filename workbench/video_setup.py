"""Local video selection and FFmpeg workspace creation for the browser."""
from pathlib import Path
from datetime import datetime
import subprocess
import sys

from .core import ROOT, VIDEO_SUFFIXES, sample, seconds, default_calibration, write_json, export_tables


def receive_video(stream, length, name):
    """Copy one browser-selected video to a unique local staging directory."""
    if not 0 < length <= 20*1024**3:
        raise ValueError('Video size must be between 1 byte and 20 GB')
    filename = name.replace('\\', '/').split('/')[-1]
    if not filename or Path(filename).suffix.lower() not in VIDEO_SUFFIXES or ':' in filename:
        raise ValueError('Select a supported video file')
    import uuid
    folder = ROOT/'runs'/'imports'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    target = folder/filename
    try:
        with target.open('xb') as handle:
            remaining = length
            while remaining:
                block = stream.read(min(1024*1024, remaining))
                if not block:
                    raise ValueError('Video transfer interrupted')
                handle.write(block)
                remaining -= len(block)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {'path':str(target), 'size':length}


def choose_path(kind):
    if kind not in ('file', 'folder'):
        raise ValueError('Select file or folder')
    # Tk runs on the main thread of a short-lived helper, not the HTTP thread.
    code = ("from tkinter import Tk,filedialog; r=Tk();r.withdraw();r.attributes('-topmost',True);r.update();"
            + ("p=filedialog.askdirectory(parent=r,title='Select folder',mustexist=True);" if kind == 'folder' else
               "p=filedialog.askopenfilename(parent=r,title='Select video',filetypes=[('Video','*.mp4 *.mkv *.webm *.mov *.avi *.m4v')]);")
            + "r.destroy();print(p)")
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, encoding='utf-8',
                            env=dict(__import__('os').environ, PYTHONIOENCODING='utf-8'), timeout=60)
    if result.returncode:
        raise ValueError('File dialog unavailable; enter the path instead')
    return result.stdout.strip()


def list_videos(path):
    selected = Path(path).expanduser().resolve()
    files = [selected] if selected.is_file() else sorted(selected.iterdir())
    return [{'name':p.name, 'path':str(p)} for p in files if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES]


def browse_paths(path=None):
    """Local disk browser, rendered as a web dialog; no desktop UI required."""
    import os
    if os.name == 'nt':
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        drives = [f'{chr(65+i)}:/' for i in range(26) if mask & (1 << i)]
    else:
        drives = ['/']
    if not path:
        return {'path':'','parent':None,'drives':drives,'entries':[]}
    current = Path(path).expanduser().resolve()
    if not current.is_dir():
        raise ValueError('Not a directory: '+str(current))
    entries = []
    for child in current.iterdir():
        try:
            folder = child.is_dir()
            if folder or child.is_file() and child.suffix.lower() in VIDEO_SUFFIXES:
                entries.append({'name':child.name,'path':str(child),'directory':folder})
        except OSError:
            continue
    return {'path':str(current),'parent':str(current.parent) if current.parent != current else None,
            'drives':drives,'entries':sorted(entries,key=lambda e:(not e['directory'],e['name'].casefold()))}


def create_workspace(body, progress=None):
    video = Path(body['video']).expanduser().resolve()
    if not video.is_file() or video.suffix.lower() not in VIDEO_SUFFIXES:
        raise ValueError('Select a supported video file')
    start, end, step = seconds(str(body.get('start',0))), seconds(str(body['end'])), float(body.get('step',.3))
    parent = Path(body.get('output_root') or video.parent).expanduser().resolve()
    output = parent/('session_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))/'clip_01'
    if progress:
        progress({'stage':'probing','workspace':str(output),'frames_directory':str(output/'frames')})
    project = sample(video, output, start, end, step, body.get('first_wave_template') is True, progress=progress)
    project['calibration'] = default_calibration()
    project['automation'] = {
        'use_yolo_auto_annotation': body.get('use_yolo_auto_annotation') is True,
        'fallback_when_unavailable': 'track',
    }
    write_json(output/'project.json', project)
    export_tables(output)
    from .assistance import ensure_mechanics
    ensure_mechanics(output)
    return {'workspace':str(output), 'frames_directory':str(output/'frames'), 'frame_count':len(project['frames']), 'url':'/'}
