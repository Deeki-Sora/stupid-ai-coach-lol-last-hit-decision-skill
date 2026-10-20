"""Loopback-only annotation UI. Coordinates are accepted only through explicit annotation."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import secrets
import threading
import urllib.parse
import webbrowser
import os
import subprocess
import socket
from .core import read_json, write_json, validate_annotations, calibration, export_assessment, export_tables


def make_server(directory=None, port=0):
    directory = Path(directory).resolve() if directory else None
    nonce = secrets.token_urlsafe(24)
    lock = threading.Lock()
    jobs = {}
    job_lock = threading.Lock()
    auto_job = {'status':'idle'}

    def start_auto_annotation(target):
        if target is None or auto_job.get('status') == 'running':
            return
        auto_job.clear();auto_job.update(status='running',stage='loading_models',frame_count=0)
        def progress(values):auto_job.update(values)
        def run():
            try:
                from .auto_annotation import run_selected_automation
                project=read_json(Path(target)/'project.json')
                enabled=project.get('automation',{}).get('use_yolo_auto_annotation') is True
                result=run_selected_automation(target,use_yolo=enabled,progress=progress)
                auto_job.clear();auto_job.update(result)
            except Exception as error:
                auto_job.clear();auto_job.update(status='failed',error=str(error))
        threading.Thread(target=run,name='lol-auto-annotation',daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, data, mime='application/json; charset=utf-8', status=200):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError):pass

        def authorized(self):
            from http.cookies import SimpleCookie
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            return (urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('token') == [nonce]
                    or cookie.get('workbench_session') is not None and cookie['workbench_session'].value == nonce)

        def do_GET(self):
            asset = urllib.parse.urlsplit(self.path).path
            if asset == '/' and not self.authorized():
                self.send_response(302)
                self.send_header('Location', '/?token='+nonce)
                self.end_headers()
                return
            if asset in {'/assets/i18n.js', '/assets/loadouts.js', '/assets/assistant.js','/assets/unit_management.js'}:
                return self.respond((Path(__file__).parent / asset.split('/')[-1]).read_bytes(), 'text/javascript; charset=utf-8')
            if not self.authorized():
                return self.respond({'error':'invalid session token'},status=403)
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            if path == '/':
                return self.respond((Path(__file__).parent/('review.html' if directory else 'setup.html')).read_bytes(),'text/html; charset=utf-8')
            if path == '/setup':
                return self.respond((Path(__file__).parent/'setup.html').read_bytes(),'text/html; charset=utf-8')
            if path == '/api/setup':
                import shutil
                from .auto_annotation import auto_annotation_availability
                return self.respond({'ffmpeg':bool(shutil.which('ffmpeg')), 'ffprobe':bool(shutil.which('ffprobe')),
                                     'output_root':'','vision':auto_annotation_availability()})
            if path == '/api/request-context':
                from .assistance import status
                return self.respond({'workspace':str(directory) if directory else None,
                                     'request':status(directory) if directory else {'status':'idle'}})
            if path == '/api/state':
                with lock:
                    state = {k:read_json(directory/f'{k}.json') for k in ['project','annotations']}
                    state['proposals'] = read_json(directory/'proposals.json') if (directory/'proposals.json').exists() else {}
                    state['auto_tracking'] = dict(auto_job)
                return self.respond(state)
            if path == '/api/game-tools':
                from .game_tools import availability
                return self.respond(availability())
            if path == '/api/name-aliases':
                from .name_aliases import CHAMPION_ALIASES
                return self.respond(CHAMPION_ALIASES)
            if path == '/api/mechanics-template':
                from .mechanic_observations import template
                return self.respond(b'\xef\xbb\xbf'+template().encode('utf-8'),'text/csv; charset=utf-8')
            if path == '/api/mechanics-adapters':
                return self.respond(read_json(Path(__file__).resolve().parents[1]/'templates/mechanic_adapters.json'))
            if path == '/api/frame-summary':
                from .state_summary import frame_summary
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                frame_id = (query.get('frame_id') or [None])[0]
                return self.respond(frame_summary(directory, frame_id))
            if path == '/api/analysis-report':
                query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                language='en' if query.get('language')==['en'] else 'zh'
                report=directory/'assessment'/f'analysis_report_{language}.md'
                return self.respond({'markdown':report.read_text(encoding='utf-8') if report.exists() else '',
                                     'revision':report.stat().st_mtime_ns if report.exists() else None})
            if path == '/api/planning-state':
                from .planning_commands import saved_state
                return self.respond(saved_state(directory))
            if path == '/api/strategy-result':
                query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                language='en' if query.get('language')==['en'] else 'zh'
                result=directory/'assistant'/f'strategy_result_{language}.json'
                return self.respond(read_json(result) if result.exists() else {'language':language,'text':''})
            if path == '/api/matchup-prior':
                result=directory/'matchup_prior.json'
                return self.respond(read_json(result) if result.exists() else {})
            target = (directory/path.lstrip('/')).resolve()
            if not target.is_relative_to(directory) or not target.is_file() or target.suffix.lower() not in {'.jpg','.csv','.zip','.json','.md'}:
                return self.respond({'error':'not found'},status=404)
            mime = {'.jpg':'image/jpeg','.csv':'text/csv; charset=utf-8','.zip':'application/zip','.json':'application/json; charset=utf-8','.md':'text/markdown; charset=utf-8'}[target.suffix.lower()]
            return self.respond(target.read_bytes(),mime)

        def do_POST(self):
            nonlocal directory
            if not self.authorized() or self.headers.get('X-Session-Token') != nonce:
                return self.respond({'error':'invalid session token'},status=403)
            try:
                length = int(self.headers.get('Content-Length','0'))
                path = urllib.parse.urlsplit(self.path).path
                if path == '/api/upload-video':
                    from .video_setup import receive_video
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    return self.respond(receive_video(self.rfile, length, (query.get('name') or [''])[0]))
                if not 0 < length <= 32*1024*1024:
                    raise ValueError('invalid request size')
                body = json.loads(self.rfile.read(length))
                path = urllib.parse.urlsplit(self.path).path
                # Never hold the annotation lock while a chooser or FFmpeg waits.
                if path == '/api/browse':
                    from .video_setup import browse_paths
                    return self.respond(browse_paths(body.get('path')))
                if path == '/api/strategy-search':
                    from .strategy_search import search_strategy
                    return self.respond(search_strategy(directory, version=body['version'], blue=body['blue'],
                        red=body['red'], level=body.get('level'), language=body.get('language', 'en'),
                        max_results=body.get('max_results', 5)))
                if path == '/api/catalog':
                    from .catalog import load_catalog
                    return self.respond(load_catalog(directory, body['version']))
                if path == '/api/matchup-prior':
                    from .matchup_data import fetch_matchup_prior
                    # A webpage timeout must not block saves or assistance status polling.
                    return self.respond(fetch_matchup_prior(directory, version=body['version'], blue=body['blue'],
                        red=body['red'], level=None, lane=body.get('lane','middle'),
                        tier=body.get('tier','emerald_plus'),provider='lolalytics_web',
                        allow_aggregate=True))
                if path == '/api/video-info':
                    from .core import probe, VIDEO_SUFFIXES
                    video = Path(body['video']).expanduser().resolve()
                    if not video.is_file() or video.suffix.lower() not in VIDEO_SUFFIXES:
                        raise ValueError('Select a supported video file')
                    return self.respond(dict(probe(video), path=str(video), parent=str(video.parent)))
                if path == '/api/select-video':
                    from .video_setup import choose_path
                    return self.respond({'path':choose_path(body.get('kind','file'))})
                if path == '/api/sample-status':
                    with job_lock:
                        status = dict(jobs[body['job']])
                    return self.respond(status)
                if path == '/api/sample-start':
                    from .video_setup import create_workspace
                    job = secrets.token_hex(12)
                    with job_lock:
                        if any(j.get('status') == 'running' for j in jobs.values()):
                            raise ValueError('A sampling job is already running')
                        jobs[job] = {'status':'running','stage':'queued','frame_count':0}
                    def progress(values):
                        with job_lock:
                            jobs[job].update(values)
                    def run():
                        nonlocal directory
                        try:
                            result = create_workspace(body, progress=progress)
                            with lock:
                                directory = Path(result['workspace'])
                            progress(dict(result,status='running',stage='auto_annotation'))
                            from .auto_annotation import run_selected_automation
                            auto_result=run_selected_automation(directory,
                                use_yolo=body.get('use_yolo_auto_annotation') is True,progress=progress)
                            auto_job.clear();auto_job.update(auto_result)
                            progress(dict(result,status='complete',stage='complete',auto_tracking=auto_result))
                        except Exception as error:
                            progress({'status':'failed','error':str(error)})
                    threading.Thread(target=run,daemon=True).start()
                    return self.respond({'job':job})
                if path == '/api/sample-video':
                    from .video_setup import create_workspace
                    created = create_workspace(body)
                    with lock:
                        directory = Path(created['workspace'])
                    return self.respond(created)
                with lock:
                    if path in ('/api/save','/api/configuration-save','/api/unit-update'):
                        from .assistance import batch_active, status as assistance_status
                        if batch_active(assistance_status(directory)):
                            raise ValueError('All-frame assistance is active; edits resume after completion or cancellation')
                    if path == '/api/request-analysis':
                        from .analysis_task import prepare_skill_analysis
                        self.respond(prepare_skill_analysis(directory,body['frame_id'],body.get('language','zh')))
                    elif path == '/api/unit-update':
                        from .unit_management import update_unit
                        self.respond(update_unit(directory,body['unit_id'],body['frame_id'],body['operation']))
                    elif path == '/api/run-analysis':
                        from .analysis_task import run_analysis
                        self.respond(run_analysis(directory,body.get('language','zh')))
                    elif path == '/api/assistant-request':
                        from .assistance import request_assistance
                        self.respond(request_assistance(directory,body['frame_id'],body.get('kind','annotation'),body.get('scope','current'),body.get('language','zh'),body.get('context')))
                    elif path == '/api/assistant-status':
                        from .assistance import status
                        self.respond(status(directory))
                    elif path == '/api/assistant-cancel':
                        from .assistance import cancel
                        self.respond(cancel(directory))
                    elif path == '/api/assistant-import':
                        from .assistance import import_drafts
                        self.respond(import_drafts(directory,body))
                    elif path == '/api/mechanics-workspace':
                        from .assistance import ensure_mechanics
                        self.respond(ensure_mechanics(directory))
                    elif path == '/api/list-videos':
                        from .video_setup import list_videos
                        self.respond({'videos':list_videos(body['path'])})
                    elif path == '/api/save':
                        original = read_json(directory/'project.json')
                        # Keep source/frame paths immutable; only editable project fields cross the API.
                        for key in ['units','hero_data','strategy_text','calibration']:
                            if key in body['project']:
                                original[key] = body['project'][key]
                        value = original.get('calibration')
                        original['calibration'] = calibration(f"{value['pixels']}={value['game_units']}") if value else None
                        validate_annotations(original,body['annotations'])
                        for snap in original.get('configuration',{}).get('snapshots',[]):
                            frame=next((f for f in original['frames'] if abs(f['source_time_s']-snap['source_time_s'])<1e-6),None)
                            if frame:
                                snap['frame_id']=frame['id']
                                clock=body['annotations']['frames'].get(frame['id'],{}).get('game_time_s')
                                if clock is not None:snap['game_time_s']=clock
                        write_json(directory/'project.json',original)
                        write_json(directory/'annotations.json',body['annotations'])
                        # Keep the CSV event/distance/action tables in sync
                        # with every accepted frame edit.
                        export_tables(directory)
                        self.respond({'saved':True})
                    elif path == '/api/champion-details':
                        from .catalog import champion_details
                        self.respond(champion_details(directory, body['version'], body['champion']))
                    elif path == '/api/codex-reference':
                        from .reference_profiles import fetch_riot_codex
                        self.respond(fetch_riot_codex(directory,body['version'],body['champion']))
                    elif path == '/api/aramonly-preview':
                        from .external_selectors import aramonly_preview
                        self.respond(aramonly_preview(directory,body['url'],body['version']))
                    elif path == '/api/configuration-save':
                        from .loadouts import save_configuration
                        self.respond(save_configuration(directory, body))
                    elif path == '/api/matchup-prior-manual':
                        from .matchup_data import save_manual_matchup_prior
                        self.respond(save_manual_matchup_prior(directory, version=body['version'], blue=body['blue'],
                            red=body['red'], level=body['level'], blue_win_rate=body.get('blue_win_rate'),
                            red_win_rate=body.get('red_win_rate'), tier=body.get('tier', 'unknown'),
                            lane=body.get('lane', 'unknown'), source=body.get('source'),
                            level_specific=body.get('level_specific', False), notes=body.get('notes', '')))
                    elif path == '/api/frame-summary':
                        from .state_summary import frame_summary
                        self.respond(frame_summary(directory, body['frame_id']))
                    elif path == '/api/configuration-at':
                        from .loadouts import configuration_at, number
                        time = number(body['source_time_s'], 'source time')
                        self.respond(configuration_at(directory, read_json(directory/'project.json'), time))
                    elif path == '/api/parameters':
                        from .parameters import evaluate_project
                        from .loadouts import number
                        self.respond(evaluate_project(directory,read_json(directory/'project.json'),number(body['source_time_s'],'source time'),fetch_native=body.get('fetch_native') is True))
                    elif path == '/api/range-reference':
                        from .parameters import evaluate_project,direct_range_reference
                        from .loadouts import number
                        parameters=evaluate_project(directory,read_json(directory/'project.json'),number(body['source_time_s'],'source time'))
                        self.respond(direct_range_reference(parameters,body['actor'],body['skill'],body['distance_game_units']))
                    elif path == '/api/export':
                        self.respond(export_assessment(directory))
                    elif path == '/api/game-draft':
                        from .planning_commands import perform
                        self.respond(perform(directory,'draft',frame_id=body['frame_id'])['task'])
                    elif path == '/api/game-run':
                        from .planning_commands import perform
                        saved=perform(directory,'run',task=body['task'])
                        self.respond({key:value for key,value in saved.items() if key not in ('workspace','action')})
                    elif path == '/api/plan-window':
                        from .planning_commands import perform
                        self.respond(perform(directory,'plan',frame_id=body.get('frame_id'),source_time_s=body.get('source_time_s'),side=body['side'],horizon=body.get('horizon_s',3.0))['result'])
                    elif path == '/api/apply-observations':
                        from .planning_commands import perform
                        self.respond(perform(directory,'apply-observations',task=body['task']))
                    elif path == '/api/estimate-probabilities':
                        from .mechanic_observations import estimate
                        result=estimate(body['csv'])
                        folder=directory/'mechanics';folder.mkdir(exist_ok=True)
                        (folder/'observations.csv').write_text(body['csv'],encoding='utf-8-sig')
                        write_json(folder/'estimated_models.json',result)
                        self.respond(result)
                    else:
                        self.respond({'error':'not found'},status=404)
            except (ValueError,KeyError,TypeError,OSError,ImportError,RuntimeError,subprocess.SubprocessError) as error:
                self.respond({'error':str(error)},status=400)

    class WorkbenchHTTPServer(ThreadingHTTPServer):
        # Windows SO_REUSEADDR can bind two independent sessions to one port.
        # Reject that case so sequential fallback ports really are isolated.
        allow_reuse_address = False

        def server_bind(self):
            if os.name == 'nt':
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    server = WorkbenchHTTPServer(('127.0.0.1',port),Handler)
    server.session_url = f'http://127.0.0.1:{server.server_port}/?token={nonce}'
    if directory is not None:
        start_auto_annotation(directory)
    return server


def _open_browser(url):
    """Open a loopback workbench URL and return whether a launcher accepted it."""
    # On Windows, os.startfile delegates to the user's registered default
    # browser without relying on webbrowser's sometimes stale registry list.
    if os.name == 'nt':
        try:
            os.startfile(url)
            return True
        except OSError:
            pass
    try:
        return bool(webbrowser.open_new_tab(url))
    except (OSError, webbrowser.Error):
        return False


def review(directory=None, open_browser=True, port=58392):
    # Keep the historical local port when available; fall back to an ephemeral
    # port if another local session or a reserved port prevents binding.
    for candidate in range(port, min(port+100, 65536)) if port else [0]:
        try:
            server = make_server(directory, port=candidate)
            break
        except OSError:
            continue
    else:
        raise OSError('No available workbench port in the requested range')
    # Start serving before opening the browser. Opening first creates a race in
    # which the browser can receive a connection-refused response.
    serving = threading.Thread(target=server.serve_forever, name='lol-workbench-http', daemon=True)
    serving.start()
    print('Annotation workspace:',server.session_url,flush=True)
    print('Open this address in the default browser; keep this terminal open. Ctrl+C stops the local server.',flush=True)
    if open_browser:
        opened = _open_browser(server.session_url)
        print('Browser launch requested: '+('yes' if opened else 'no; copy the address above'),flush=True)
    try:
        while serving.is_alive():
            serving.join(.5)
    except KeyboardInterrupt:
        server.shutdown()
    finally:
        server.server_close()
