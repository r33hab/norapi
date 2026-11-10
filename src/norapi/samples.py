"""Captured first calls: run a few curated quick starts and keep what the live API answered.

The front page shows real requests next to the responses they got. `norapi samples` runs the
first `curl` command in each chosen entry's quick_start through the same public-only client as
the link checker, and stores status, timing, content type and a trimmed body in
`registry/samples.json`. The site only reads that file; generating the site never touches the
network.
"""

from __future__ import annotations

import json
import logging
import shlex
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from norapi.model import ApiEntry
from norapi.netguard import get_capped, public_client

log = logging.getLogger(__name__)

# Small, readable answers from five different providers, every one open and without a key,
# each with a label for what the call asks.
SAMPLES = (
    ("brreg-enhetsregisteret", "Søk i Enhetsregisteret"),
    ("geonorge-kommuneinfo", "Kommune for et punkt"),
    ("nav-grunnbelop", "Grunnbeløpet"),
    ("miljodir-luftkvalitet", "Luftkvalitet i Oslo"),
    ("nve-magasinstatistikk", "Fyllingsgrad i magasinene"),
)
SAMPLE_IDS = tuple(api_id for api_id, _ in SAMPLES)
USER_AGENT = "norapi-samples/0.1 (+https://github.com/r33hAB/norapi)"
MAX_LINES = 15
MAX_KEYS = 12
MAX_ITEMS = 1
MAX_STRING = 96
MAX_DEPTH = 4


def first_get(quick_start: str) -> tuple[str, str, dict[str, str]] | None:
    """The first curl command in a quick start, if it is a plain GET: (command, url, headers).

    Comment lines are skipped and backslash continuations joined. Anything that posts, uploads,
    or saves to a file is not a call the front page can replay, so it gives None.
    """
    lines = quick_start.strip().splitlines()
    command = ""
    for line in lines:
        stripped = line.strip()
        if not command and (not stripped or stripped.startswith("#")):
            continue
        if not command and not stripped.startswith("curl "):
            return None
        command += stripped.removesuffix("\\").strip() + " "
        if not stripped.endswith("\\"):
            break
    command = command.strip()
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens or tokens[0] != "curl":
        return None
    url = None
    headers: dict[str, str] = {}
    args = iter(tokens[1:])
    for token in args:
        if token in ("-H", "--header"):
            name, _, value = next(args, "").partition(":")
            if name.strip():
                headers[name.strip()] = value.strip()
        elif token in ("-A", "--user-agent"):
            headers["User-Agent"] = next(args, "")
        elif token in ("-X", "--request"):
            if next(args, "").upper() != "GET":
                return None
        elif token in ("-d", "--data", "--data-raw", "--data-binary", "-F", "--form", "-O", "-o"):
            return None
        elif token.startswith(("http://", "https://")) and url is None:
            url = token
    if url is None:
        return None
    return command, url, headers


def render_json(value: Any) -> tuple[list[str], bool]:
    """Pretty-print a JSON value for display, trimmed: long arrays keep their first item, wide
    objects twelve keys (plain values first, in the API's order), long strings their start.
    Every cut is marked with `…` and a count, so the reader can see what was left out.
    Returns (lines, trimmed)."""
    trimmed = False

    def scalar(v: Any) -> str:
        nonlocal trimmed
        if isinstance(v, str) and len(v) > MAX_STRING:
            trimmed = True
            v = v[:MAX_STRING].rstrip() + "…"
        return json.dumps(v, ensure_ascii=False)

    def walk(v: Any, indent: int, prefix: str, comma: str) -> list[str]:
        nonlocal trimmed
        pad = "  " * indent
        if isinstance(v, dict):
            if not v:
                return [f"{pad}{prefix}{{}}{comma}"]
            if indent >= MAX_DEPTH:
                trimmed = True
                return [f"{pad}{prefix}{{…}}{comma}"]
            keys = list(v)
            # plain values say more than nested ones in a short excerpt: pick those first,
            # then show the picked keys in the order the API sent them
            ranked = sorted(
                range(len(keys)), key=lambda i: (isinstance(v[keys[i]], (dict, list)), i)
            )
            shown = [keys[i] for i in sorted(ranked[:MAX_KEYS])]
            out = [f"{pad}{prefix}{{"]
            for i, key in enumerate(shown):
                last = i == len(shown) - 1 and len(keys) <= MAX_KEYS
                out += walk(
                    v[key],
                    indent + 1,
                    json.dumps(key, ensure_ascii=False) + ": ",
                    "" if last else ",",
                )
            if len(keys) > MAX_KEYS:
                trimmed = True
                out.append(f"{pad}  … {len(keys) - MAX_KEYS} felt til")
            out.append(f"{pad}}}{comma}")
            return out
        if isinstance(v, list):
            if not v:
                return [f"{pad}{prefix}[]{comma}"]
            if indent >= MAX_DEPTH:
                trimmed = True
                return [f"{pad}{prefix}[…]{comma}"]
            if all(not isinstance(x, (dict, list)) for x in v) and len(v) <= 4:
                inline = f"{pad}{prefix}[{', '.join(scalar(x) for x in v)}]{comma}"
                if len(inline) <= 80:
                    return [inline]
            shown = v[:MAX_ITEMS]
            out = [f"{pad}{prefix}["]
            for i, item in enumerate(shown):
                last = i == len(shown) - 1 and len(v) <= MAX_ITEMS
                out += walk(item, indent + 1, "", "" if last else ",")
            if len(v) > MAX_ITEMS:
                trimmed = True
                out.append(f"{pad}  … {len(v) - MAX_ITEMS} til")
            out.append(f"{pad}]{comma}")
            return out
        return [f"{pad}{prefix}{scalar(v)}{comma}"]

    lines = walk(value, 0, "", "")
    if len(lines) > MAX_LINES:
        trimmed = True
        lines = lines[: MAX_LINES - 1] + ["…"]
    return lines, trimmed


def render_body(body: bytes, content_type: str) -> tuple[list[str], bool]:
    text = body.decode("utf-8", errors="replace")
    if "json" in content_type or text.lstrip().startswith(("{", "[")):
        try:
            return render_json(json.loads(text))
        except ValueError:
            pass
    lines = [line[:MAX_STRING] for line in text.strip().splitlines()]
    if len(lines) > MAX_LINES:
        return lines[: MAX_LINES - 1] + ["…"], True
    return lines, False


def capture(entry: ApiEntry, client: httpx.Client, label: str = "") -> dict[str, Any] | None:
    call = first_get(entry.quick_start or "")
    if call is None:
        log.warning("%s: no plain GET in quick_start, skipped", entry.id)
        return None
    command, url, headers = call
    started = time.perf_counter()
    try:
        fetched = get_capped(client, url, headers=headers, limit=512 * 1024)
    except httpx.HTTPError as exc:
        log.warning("%s: %s", entry.id, type(exc).__name__)
        return None
    elapsed = round((time.perf_counter() - started) * 1000)
    if fetched is None or fetched[1] is None:
        log.warning("%s: blocked or body over the cap", entry.id)
        return None
    response, body, _ = fetched
    if not 200 <= response.status_code < 300:
        log.warning("%s: answered %s", entry.id, response.status_code)
        return None
    content_type = response.headers.get("content-type", "").split(";")[0].strip()
    lines, trimmed = render_body(body, content_type)
    return {
        "id": entry.id,
        "label": label,
        "command": command,
        "url": url,
        "status": response.status_code,
        "reason": response.reason_phrase,
        "ms": elapsed,
        "content_type": content_type,
        "bytes": len(body),
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "lines": lines,
        "trimmed": trimmed,
    }


def capture_samples(entries: list[ApiEntry], out: Path, timeout: float = 15.0) -> int:
    """Capture every SAMPLE_IDS entry; keep the previous capture for one that fails this time."""
    by_id = {e.id: e for e in entries}
    previous: dict[str, Any] = {}
    if out.exists():
        previous = {s["id"]: s for s in json.loads(out.read_text(encoding="utf-8"))["samples"]}
    samples = []
    with public_client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        for api_id, label in SAMPLES:
            entry = by_id.get(api_id)
            sample = capture(entry, client, label) if entry else None
            if sample is None and api_id in previous:
                sample = previous[api_id]
            if sample is not None:
                samples.append(sample)
    out.write_text(
        json.dumps({"count": len(samples), "samples": samples}, ensure_ascii=False, indent=1)
        + "\n",
        encoding="utf-8",
    )
    return len(samples)
