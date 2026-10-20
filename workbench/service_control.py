"""Start, inspect, stop, or restart one background workbench service."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from .core import ROOT


STATE=ROOT/'runs'/'workbench_service.json'
LOG=ROOT/'runs'/'workbench_service.log'


def _read_state():
    try:
        return json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError,ValueError,TypeError):
        return None


def _healthy(state):
    if not state or not state.get('url'):
        return False
    try:
        endpoint=state['url'].replace('/?','/api/setup?')
        with urllib.request.urlopen(endpoint,timeout=1.5) as response:
            return response.status==200
    except (OSError,ValueError):
        return False


def status():
    state=_read_state()
    if _healthy(state):
        return dict(state,status='running')
    return {'status':'stopped','stale_state':bool(state)}


def start(*,workspace=None,port=58392,timeout=20):
    current=_read_state()
    if _healthy(current):
        return dict(current,status='running',already_running=True)
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.unlink(missing_ok=True)
    command=[sys.executable,str(ROOT/'main.py'),'start','--no-browser','--port',str(int(port))]
    if workspace:command.extend(['--workspace',str(Path(workspace).resolve())])
    log=LOG.open('w',encoding='utf-8')
    options={'cwd':str(ROOT),'stdout':log,'stderr':subprocess.STDOUT,'stdin':subprocess.DEVNULL}
    if os.name=='nt':
        options['creationflags']=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW
    else:
        options['start_new_session']=True
    process=subprocess.Popen(command,**options)
    log.close()
    deadline=time.monotonic()+float(timeout);url=None
    pattern=re.compile(r'Annotation workspace:\s*(http://127\.0\.0\.1:\d+/\?token=\S+)')
    while time.monotonic()<deadline:
        if process.poll() is not None:
            tail=LOG.read_text(encoding='utf-8',errors='replace')[-2000:] if LOG.exists() else ''
            raise RuntimeError('Workbench service exited during startup: '+tail.strip())
        if LOG.exists():
            match=pattern.search(LOG.read_text(encoding='utf-8',errors='replace'))
            if match:
                url=match.group(1);break
        time.sleep(.1)
    if not url:
        process.terminate()
        raise RuntimeError('Timed out waiting for the workbench address')
    value={'schema_version':1,'pid':process.pid,'url':url,
           'workspace':str(Path(workspace).resolve()) if workspace else None,
           'port':int(urllib.parse.urlsplit(url).port),
           'started_at':datetime.now(timezone.utc).isoformat(),'log':str(LOG)}
    STATE.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return dict(value,status='running',already_running=False)


def stop(*,timeout=8):
    state=_read_state()
    if not _healthy(state):
        STATE.unlink(missing_ok=True)
        return {'status':'stopped','already_stopped':True}
    try:
        os.kill(int(state['pid']),signal.SIGTERM)
    except (OSError,ValueError,TypeError):
        pass
    deadline=time.monotonic()+float(timeout)
    while time.monotonic()<deadline and _healthy(state):time.sleep(.1)
    STATE.unlink(missing_ok=True)
    return {'status':'stopped','already_stopped':False,'previous_url':state['url']}


def restart(*,workspace=None,port=58392):
    previous=_read_state()
    if workspace is None and previous:workspace=previous.get('workspace')
    stop()
    result=start(workspace=workspace,port=port)
    result['restarted']=True
    return result
