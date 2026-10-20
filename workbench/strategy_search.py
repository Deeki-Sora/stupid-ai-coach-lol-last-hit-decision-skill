"""Small, auditable web search for champion mechanics and lane guidance.

The workbench stores links and snippets as optional references.  It never
converts a search result into a verified game rule or a scoring number.
"""

from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import html
import json
import ssl
import urllib.parse
import urllib.error
import urllib.request

from .core import write_json


class _Results(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._current, self._text, self._snippet = [], None, [], False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._current = {"title": "", "url": attrs.get("href", ""), "snippet": ""}
            self._text = []
        elif tag == "a" and "result__snippet" in classes and self.rows:
            self._snippet = True
            self._text = []

    def handle_data(self, data):
        if self._current is not None or self._snippet:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._snippet and self.rows:
            self.rows[-1]["snippet"] = " ".join("".join(self._text).split())
            self._snippet, self._text = False, []
            return
        if tag == "a" and self._current and not self._current["title"]:
            self._current["title"] = " ".join("".join(self._text).split())
            self.rows.append(self._current)
            self._current, self._text = None, []


def _download(url):
    context = ssl.create_default_context()
    try:
        import certifi
        context.load_verify_locations(certifi.where())
    except ImportError:
        pass
    request = urllib.request.Request(url, headers={
        "User-Agent": "LOL-Short-Window-Workbench/0.91 (strategy-reference)",
        "Accept": "text/html",
    })
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("strategy search response is too large")
        return raw, response.geturl()


def parse_duckduckgo(raw):
    parser = _Results()
    parser.feed(html.unescape(raw.decode("utf-8", errors="replace")))
    rows = []
    for row in parser.rows:
        target = row.get("url", "")
        if target.startswith("//"):
            target = "https:" + target
        parsed = urllib.parse.urlsplit(target)
        if parsed.path.startswith("/l/") and parsed.query:
            target = urllib.parse.parse_qs(parsed.query).get("uddg", [target])[0]
        if not target.startswith("http"):
            continue
        rows.append({"title": row.get("title", ""), "url": target,
                     "snippet": row.get("snippet", "")})
    return rows


def _champion_label(value, catalog):
    if catalog:
        row = catalog.get("champions", {}).get(value)
        if row:
            return row.get("names", {}).get("en_US") or value
    return str(value)


def search_strategy(directory, *, version, blue, red, level=None,
                    language="en", max_results=5):
    """Search general champion mechanics and matchup guidance.

    Search failures are recorded per query and do not prevent the workspace
    from being evaluated.  The returned document is reference material only.
    """
    directory = Path(directory)
    catalog = None
    try:
        from .catalog import load_catalog
        catalog = load_catalog(directory, version)
    except (OSError, ValueError, KeyError):
        pass
    blue_label, red_label = _champion_label(blue, catalog), _champion_label(red, catalog)
    suffix = f"League of Legends patch {version} mechanics lane guide"
    queries = [f"{blue_label} champion abilities passive guide {suffix}",
               f"{red_label} champion abilities passive guide {suffix}",
               f"{blue_label} vs {red_label} mid matchup lane guide {suffix}"]
    if level:
        queries[-1] += f" level {int(level)}"
    results, errors = [], []
    for query in queries:
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
        try:
            raw, final_url = _download(url)
            parsed = parse_duckduckgo(raw)[:max_results]
            results.append({"query": query, "search_url": final_url, "items": parsed})
        except (OSError, ValueError, urllib.error.URLError) as error:
            errors.append({"query": query, "error": str(error)})
    codex = [f"https://riotcodex.net/champions/{urllib.parse.quote(x)}" for x in (blue, red)]
    document = {
        "schema_version": 1, "patch": str(version), "level": level,
        "blue": {"id": blue, "label": blue_label},
        "red": {"id": red, "label": red_label},
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "queries": queries, "results": results, "errors": errors,
        "mechanics_reference_urls": codex,
        "notes": "Search results are optional references. Verify patch, rank, level and applicability before scoring.",
    }
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")
    document["content_sha256"] = hashlib.sha256(payload).hexdigest()
    target = directory / "references" / "strategy_search.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json(target, document)
    return document
