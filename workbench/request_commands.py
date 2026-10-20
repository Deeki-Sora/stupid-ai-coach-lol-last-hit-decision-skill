"""Discover workbench requests and hand them to an explicitly invoked AI Skill."""
from pathlib import Path
import time
import urllib.parse
import urllib.request

from .core import ROOT, read_json, write_json


ACTIVE = {'pending', 'running', 'partial'}


def remember_workspace(directory):
    """Keep machine-local discovery data outside the portable Skill package."""
    index = ROOT / 'runs/workbench_requests.json'
    try:
        index.parent.mkdir(parents=True, exist_ok=True)
        paths = read_json(index).get('workspaces', []) if index.is_file() else []
        current = str(Path(directory).resolve())
        paths = [p for p in paths if p != current and (Path(p)/'assistant/request.json').is_file()]
        write_json(index, {'schema_version': 1, 'workspaces': [current, *paths[:99]]})
    except (OSError, ValueError, TypeError):
        # An explicit --workspace still works with a read-only checkout.
        pass


def _live_workspace():
    from .service_control import _read_state
    state = _read_state() or {}
    address = state.get('url', '')
    parsed = urllib.parse.urlsplit(address)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1':
        return None
    endpoint = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, '/api/request-context', parsed.query, ''))
    try:
        import json
        with urllib.request.urlopen(endpoint, timeout=3) as response:
            value = json.load(response)
        return value.get('workspace')
    except (OSError, ValueError, TypeError):
        return None


def resolve_workspace(workspace=None):
    if workspace:
        selected = Path(workspace).expanduser().resolve()
    else:
        live = _live_workspace()
        if live:
            selected = Path(live).resolve()
        else:
            index = ROOT / 'runs/workbench_requests.json'
            paths = read_json(index).get('workspaces', []) if index.is_file() else []
            candidates = []
            from .assistance import status
            for path in paths:
                directory = Path(path).expanduser().resolve()
                if (directory/'project.json').is_file() and status(directory).get('status') in ACTIVE:
                    if directory not in candidates:
                        candidates.append(directory)
            if not candidates:
                raise ValueError('No pending workbench request found. Press a request button, or pass --workspace.')
            if len(candidates) != 1:
                raise ValueError('Multiple workspaces have pending requests; pass --workspace: ' + ', '.join(map(str, candidates)))
            selected = candidates[0]
    if not (selected/'project.json').is_file() or not (selected/'annotations.json').is_file():
        raise ValueError('Workspace must contain project.json and annotations.json')
    return selected


def request_status(workspace=None):
    from .assistance import status
    directory = resolve_workspace(workspace)
    return {'workspace': str(directory), 'request': status(directory)}


def read_request(workspace=None, *, kind=None, scope=None, start=False):
    from .assistance import status, validate_request_frames
    directory = resolve_workspace(workspace)
    request = status(directory)
    if request.get('status') not in ACTIVE:
        raise ValueError('No active request: it is missing, completed or cancelled')
    if kind and request.get('kind') != kind or scope and request.get('scope') != scope:
        raise ValueError('The pending request has a different kind or scope; use its matching chat command')
    evidence = validate_request_frames(directory,request,
        require_images=request['kind'] in ('annotation','configuration') and request['scope']=='current')
    if start:
        request.setdefault('request_revision', request['revision'])
        request.update(status='running', revision=time.time_ns())
        write_json(directory/'assistant/request.json', request)
    return {'workspace': str(directory), 'request_revision': request.get('request_revision', request['revision']),
            'request': request, 'frame_context':request.get('frame_context'), 'evidence': evidence,
            'result_file': str(directory/'assistant/skill_response.json')}


def finish_request(workspace, payload):
    from .assistance import import_drafts, status
    directory = resolve_workspace(workspace)
    request = status(directory)
    if request.get('status') not in ACTIVE:
        raise ValueError('The request is no longer active; no result was written')
    expected = request.get('request_revision', request.get('revision'))
    if payload.get('request_revision') != expected:
        raise ValueError('Result revision does not match the active request; no result was written')
    if request['kind'] == 'strategy' and not payload.get('strategy_result') and not payload.get('unknown_items'):
        raise ValueError('Provide strategy_result or explain unknown_items')
    if request['kind'] == 'analysis' and not payload.get('analysis_report'):
        raise ValueError('Provide the evidence-based analysis_report Markdown')
    if request['kind'] == 'mechanics' and 'mechanics_observations' not in payload and not payload.get('unknown_items'):
        raise ValueError('Provide mechanics_observations or explain unknown_items')
    result = import_drafts(directory, dict(payload, proposals=payload.get('proposals', [])))
    return {'workspace': str(directory), 'status': result['status'],
            'filled_fields': result.get('filled_fields', 0),
            'inspected_frames': result.get('inspected_frames', []),
            'remaining_frames': result.get('remaining_frames', []),
            'unknown_items': result.get('unknown_items', []),
            'review_items': result.get('review_items', []),
            'mechanics_coverage': result.get('mechanics_coverage'), 'refresh_workbench': result['status'] == 'filled'}


def cancel_request(workspace=None):
    from .assistance import cancel
    directory = resolve_workspace(workspace)
    return {'workspace': str(directory), 'request': cancel(directory)}
