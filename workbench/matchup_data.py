"""Fetch a patch-scoped champion matchup prior for the workbench.

Riot's static data identifies the patch and champion IDs but does not publish
public lane matchup win rates.  The default community provider is a
patch-labelled Lolalytics matchup page.  Its aggregate result is explicitly
marked as all-level data; it is never silently promoted to a level-specific
prior.  A future provider may return a ``levels`` map and will then be marked
level-specific after validation.
"""

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import html
import json
import re
import ssl
import urllib.parse
import urllib.request

from .catalog import load_catalog
from .name_aliases import CHAMPION_ALIASES
from .core import write_json
from algorithms.matchup_prior import validate_prior, _share


DEFAULT_PROVIDER = "lolalytics_web"
DEFAULT_URL = "https://lolalytics.com/lol/{blue}/vs/{red}/build/?lane={lane}&tier={tier}"
ALLOWED_HOSTS = {"lolalytics.com", "www.lolalytics.com"}


def _download(url):
    context = ssl.create_default_context()
    try:
        import certifi
        context.load_verify_locations(certifi.where())
    except ImportError:
        pass
    request = urllib.request.Request(url, headers={
        "User-Agent": "LOL-Short-Window-Workbench/0.91 (matchup-prior)",
        "Accept": "text/html,application/json",
    })
    with urllib.request.urlopen(request, timeout=25, context=context) as response:
        host = urllib.parse.urlsplit(response.geturl()).hostname
        if host not in ALLOWED_HOSTS:
            raise ValueError("unexpected matchup provider redirect")
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("matchup provider response is too large")
        return raw, response.geturl()


def _slug(value):
    value = re.sub(r"[^a-z0-9]+", "", str(value).lower())
    if not value:
        raise ValueError("champion slug is empty")
    return value


def _resolve_champion(value, catalog):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("champion name or ID is required")
    target = value.strip().lower()
    candidates = []
    for ident, row in catalog.get("champions", {}).items():
        names = list(row.get("names", {}).values())
        aliases = CHAMPION_ALIASES.get(ident, [])
        if target == str(ident).lower() or any(target == str(name).lower() for name in names + aliases):
            candidates.append(ident)
    if len(candidates) != 1:
        raise ValueError("cannot resolve champion name or ID: " + value)
    return candidates[0]


def _public_patch(version):
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.\d+)?", str(version))
    if not match:
        return str(version)
    major, minor = map(int, match.groups())
    return f"26.{minor}" if major == 16 else f"{major}.{minor}"


def _float(text):
    return float(str(text).replace(",", "").strip())


def _parse_lolalytics(raw, blue_slug, red_slug):
    """Parse the visible aggregate matchup summary and its game count."""
    source = html.unescape(raw.decode("utf-8", errors="replace"))
    patch_match = re.search(r"(?i)Patch\s+(\d+\.\d+)", source)
    data_patch = patch_match.group(1) if patch_match else None
    blue_anchor = re.escape(blue_slug)
    red_anchor = re.escape(red_slug)
    pattern = (r"(?is)/lol/" + blue_anchor + r"/build/.*?wins\s+against.*?/lol/" +
               red_anchor + r"/build/.*?([0-9]+(?:\.[0-9]+)?)%\s+of\s+the\s+time")
    match = re.search(pattern, source)
    if not match:
        # The page may omit the exact link in a localized render; use the
        # visible phrase but still require the two champion names nearby.
        fallback = re.search(r"(?is)wins\s+against.*?([0-9]+(?:\.[0-9]+)?)%\s+of\s+the\s+time", source)
        match = fallback
    if not match:
        raise ValueError("matchup provider returned no readable win-rate summary")
    win_rate = _float(match.group(1))
    if not 0.0 < win_rate < 100.0:
        raise ValueError("provider returned an invalid win rate")
    window = source[match.start():match.end() + 1200]
    games_match = re.search(r"([0-9][0-9,]*)\s*</div>\s*<div[^>]*>Games</div>", window, re.I)
    games = int(games_match.group(1).replace(",", "")) if games_match else None
    if games is None or games <= 0:
        # The same value is present in the serialized page when the visible
        # number is not in the short block.
        serialized = re.search(r"(?:\"n\"|Games).{0,80}?([0-9][0-9,]{2,})", window, re.I)
        games = int(serialized.group(1).replace(",", "")) if serialized else None
    return {"blue_win_rate": win_rate / 100.0, "red_win_rate": 1.0 - win_rate / 100.0,
            "sample_size": games, "data_patch": data_patch, "level_specific": False,
            "level_scope": "all_levels", "raw_summary": source[match.start():match.end()]}


def fetch_matchup_prior(directory, *, version, blue, red, level=None, lane="middle",
                        tier="emerald_plus", provider=DEFAULT_PROVIDER,
                        allow_aggregate=True, url_template=None):
    """Fetch and persist a validated prior for the selected matchup.

    ``allow_aggregate`` controls whether an all-level public matchup may be
    used when the requested level has no public level-specific data.  The
    returned object always records that limitation.
    """
    if level is not None and (isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 18):
        raise ValueError("level must be an integer from 1 to 18")
    catalog = load_catalog(directory, version)
    resolved_blue = _resolve_champion(blue, catalog)
    resolved_red = _resolve_champion(red, catalog)
    if resolved_blue == resolved_red:
        raise ValueError("blue and red champions must differ")
    public_patch = catalog.get("public_patch") or _public_patch(catalog["version"])
    if provider != DEFAULT_PROVIDER:
        raise ValueError("unsupported matchup provider: " + str(provider))
    blue_slug, red_slug = _slug(resolved_blue), _slug(resolved_red)
    url = (url_template or DEFAULT_URL).format(
        blue=blue_slug, red=red_slug, lane=urllib.parse.quote(lane), tier=urllib.parse.quote(tier))
    raw, final_url = _download(url)
    parsed = _parse_lolalytics(raw, blue_slug, red_slug)
    if not parsed.get("data_patch"):
        raise ValueError("provider page did not identify its data patch; ask the Skill to verify it")
    if parsed.get("data_patch") and _public_patch(parsed["data_patch"]) != public_patch:
        raise ValueError(f"provider patch {parsed['data_patch']} does not match selected patch {public_patch}")
    if not parsed.get("level_specific") and not allow_aggregate:
        raise ValueError("provider exposes aggregate all-level data, not the requested level")
    if not parsed.get("sample_size"):
        raise ValueError("provider did not expose a positive matchup sample size")
    now = datetime.now(timezone.utc).isoformat()
    prior = {
        "schema_version": 1,
        "patch": public_patch,
        "data_patch": parsed.get("data_patch") or public_patch,
        "tier": tier,
        "lane": lane,
        "level": level if level is not None else "all",
        "level_specific": bool(parsed.get("level_specific")),
        "level_scope": parsed.get("level_scope", "all_levels"),
        "sample_size": parsed["sample_size"],
        "source": final_url,
        "source_kind": "community_aggregate",
        "retrieved_at": now,
        "provider": provider,
        "blue_champion_id": resolved_blue,
        "red_champion_id": resolved_red,
        "blue_win_rate": parsed["blue_win_rate"],
        "red_win_rate": parsed["red_win_rate"],
        "notes": "Aggregate matchup prior; not a level-specific estimate." if not parsed.get("level_specific") else "Level-specific matchup prior.",
    }
    # Save provenance alongside the prior so it enters the normal workspace
    # audit and is available offline on subsequent evaluations.
    payload = json.dumps(prior, ensure_ascii=False, sort_keys=True).encode("utf-8")
    prior["response_sha256"] = hashlib.sha256(payload).hexdigest()
    write_json(Path(directory) / "matchup_prior.json", prior)
    return prior


def save_manual_matchup_prior(directory, *, version, blue, red, level,
                              blue_win_rate=None, red_win_rate=None,
                              tier="unknown", lane="unknown", source=None,
                              level_specific=False, notes=""):
    """Save a user-entered matchup prior without requiring a sample count.

    The workbench asks for only the patch, event level and (optionally) the
    two rates.  Empty rates mean an uninformative 50:50 prior; a single empty
    side is completed by the other side.  Unknown sample size is represented
    as zero plus ``sample_size_unknown`` rather than fabricated data.
    """
    if level is None or isinstance(level, bool):
        raise ValueError("level must be an integer from 1 to 18")
    try:
        level = int(level)
    except (TypeError, ValueError) as error:
        raise ValueError("level must be an integer from 1 to 18") from error
    if not 1 <= level <= 18:
        raise ValueError("level must be an integer from 1 to 18")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("version is required")
    if not isinstance(blue, str) or not blue.strip() or not isinstance(red, str) or not red.strip():
        raise ValueError("both champion names or IDs are required")

    # Resolve IDs when the patch catalog is already available.  Manual entry
    # remains usable offline: unresolved labels are preserved as supplied.
    resolved_blue, resolved_red = blue.strip(), red.strip()
    try:
        # Manual entry is intentionally offline-first.  Only inspect a
        # catalog already present in the workspace; never force a download
        # merely to save two user-entered rates.
        exact = re.fullmatch(r"\d+\.\d+\.\d+", str(version))
        cached_catalog = Path(directory) / "catalogs" / str(version) / "catalog.json" if exact else None
        if cached_catalog and cached_catalog.exists():
            catalog = load_catalog(directory, version)
            resolved_blue = _resolve_champion(resolved_blue, catalog)
            resolved_red = _resolve_champion(resolved_red, catalog)
            public_patch = catalog.get("public_patch") or _public_patch(catalog["version"])
        else:
            public_patch = _public_patch(version)
    except (OSError, ValueError, KeyError):
        public_patch = _public_patch(version)
    if resolved_blue == resolved_red:
        raise ValueError("blue and red champions must differ")

    def supplied(value):
        return value is not None and str(value).strip() != ""

    def manual_share(value, label):
        try:
            return _share(float(str(value).strip()), label)
        except (TypeError, ValueError) as error:
            raise ValueError(label + " must be a number") from error

    if not supplied(blue_win_rate) and not supplied(red_win_rate):
        blue_rate = red_rate = 0.5
    elif not supplied(blue_win_rate):
        red_rate = manual_share(red_win_rate, "red_win_rate")
        blue_rate = 1.0 - red_rate
    elif not supplied(red_win_rate):
        blue_rate = manual_share(blue_win_rate, "blue_win_rate")
        red_rate = 1.0 - blue_rate
    else:
        blue_rate = manual_share(blue_win_rate, "blue_win_rate")
        red_rate = manual_share(red_win_rate, "red_win_rate")
        if abs(blue_rate + red_rate - 1.0) > 1e-6:
            raise ValueError("blue and red win rates must sum to 1 or 100 percent")

    prior = {
        "schema_version": 1,
        "patch": public_patch,
        "tier": str(tier or "unknown"),
        "lane": str(lane or "unknown"),
        "level": level,
        "level_specific": bool(level_specific),
        "level_scope": "level" if level_specific else "manual_or_all_levels",
        "sample_size": 0,
        "sample_size_unknown": True,
        "source": str(source or "manual user entry"),
        "source_kind": "manual_entry",
        "provider": "manual",
        "entered_at": datetime.now(timezone.utc).isoformat(),
        "blue_champion_id": resolved_blue,
        "red_champion_id": resolved_red,
        "blue_win_rate": blue_rate,
        "red_win_rate": red_rate,
        "notes": str(notes or "") or "Rates entered by the user; sample size was not supplied.",
    }
    prior = validate_prior(prior)
    payload = json.dumps(prior, ensure_ascii=False, sort_keys=True).encode("utf-8")
    prior["response_sha256"] = hashlib.sha256(payload).hexdigest()
    write_json(Path(directory) / "matchup_prior.json", prior)
    return prior
