import json

import httpx
import pytest
from test_site import _registry_dir

from norapi.model import ApiEntry, Provider
from norapi.samples import capture, first_get, render_body, render_json
from norapi.site import _highlight, generate_site


@pytest.mark.parametrize(
    ("quick_start", "expected"),
    [
        ('curl "https://x.no/a?b=1"', ("https://x.no/a?b=1", {})),
        (
            '# a comment first\ncurl -H "Accept: application/json" "https://x.no/a"\ncurl "https://x.no/b"',
            ("https://x.no/a", {"Accept": "application/json"}),
        ),
        ('curl -A "demo" \\\n  "https://x.no/a"', ("https://x.no/a", {"User-Agent": "demo"})),
    ],
)
def test_first_get_reads_the_first_plain_get(quick_start, expected):
    _, url, headers = first_get(quick_start)
    assert (url, headers) == expected


@pytest.mark.parametrize(
    "quick_start",
    [
        'curl -X POST "https://x.no/graphql" -d "{}"',
        'curl -O "https://x.no/file.xml"',
        "# only a comment",
        'wget "https://x.no/a"',
    ],
)
def test_first_get_refuses_what_the_console_cannot_replay(quick_start):
    assert first_get(quick_start) is None


def test_render_json_marks_every_cut():
    wide, trimmed = render_json({f"k{i}": i for i in range(14)})
    assert trimmed and "  … 2 felt til" in wide, "fourteen keys, twelve shown"
    long, trimmed = render_json([{"a": 1}, {"b": 2}, {"c": 3}])
    assert trimmed and "  … 2 til" in long, "three items, one shown"
    tall, trimmed = render_json({"x": [[[[1]]]] * 1, **{f"k{i}": "v" * 200 for i in range(11)}})
    assert trimmed and any(line.endswith('…",') or line.endswith('…"') for line in tall)


def test_render_json_prefers_plain_values_but_keeps_the_api_order():
    value = {f"nested{i}": [] for i in range(13)} | {"name": "Oslo"}
    lines, _ = render_json(value)
    keys = [line.strip().split(":")[0] for line in lines if line.startswith('  "')]
    assert '"name"' in keys, "the one plain value survives the cut"
    assert keys[-1] == '"name"', "and stays where the API put it"


def test_render_body_leaves_short_answers_whole():
    lines, trimmed = render_body(b'{"fylkesnavn": "Oslo"}', "application/json")
    assert lines == ["{", '  "fylkesnavn": "Oslo"', "}"] and not trimmed


def test_highlight_escapes_what_the_api_sent():
    html = _highlight('  "x": "<script>alert(1)</script>",')
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert '<span class="k">' in html and '<span class="s">' in html


def test_capture_records_status_timing_and_the_trimmed_answer():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "application/json"
        return httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"})

    entry = ApiEntry(
        id="x-api",
        title="X",
        provider=Provider(name="X"),
        quick_start='curl -H "Accept: application/json" "https://x.no/a"',
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    sample = capture(entry, client, "Et kall")
    assert sample["status"] == 200 and sample["label"] == "Et kall"
    assert sample["lines"] == ["{", '  "ok": true', "}"]
    assert sample["content_type"] == "application/json" and sample["ms"] >= 0


def _with_samples(tmp_path, fixtures, snapshot, samples):
    registry_dir = _registry_dir(tmp_path, fixtures, snapshot)
    (registry_dir / "samples.json").write_text(
        json.dumps({"count": len(samples), "samples": samples}), encoding="utf-8"
    )
    return registry_dir


SAMPLE = {
    "id": "geonorge-kommuneinfo",
    "label": "Kommune for et punkt",
    "command": 'curl "https://ws.geonorge.no/kommuneinfo/v1/kommuner"',
    "url": "https://ws.geonorge.no/kommuneinfo/v1/kommuner",
    "status": 200,
    "reason": "OK",
    "ms": 70,
    "content_type": "application/json",
    "bytes": 86,
    "captured_at": "2026-11-10T09:00:00+00:00",
    "lines": ["{", '  "kommunenavn": "<b>Oslo</b>"', "}"],
    "trimmed": False,
}


def test_index_shows_the_console_with_the_captured_call(tmp_path, fixtures, snapshot):
    stale = SAMPLE | {"id": "gone-from-the-registry"}
    registry_dir = _with_samples(tmp_path, fixtures, snapshot, [SAMPLE, stale])
    out = tmp_path / "_site"
    generate_site(registry_dir, out, base_url="https://example.invalid/norapi/")
    index = (out / "index.html").read_text()

    assert "data-console" in index and "Kommune for et punkt" in index
    assert "kommuneinfo/v1/kommuner" in index and "200 OK" in index
    assert "&lt;b&gt;Oslo&lt;/b&gt;" in index and "<b>Oslo</b>" not in index
    assert "gone-from-the-registry" not in index, "a call for a removed entry is dropped"
    api_page = (out / "api" / "geonorge-kommuneinfo" / "index.html").read_text()
    assert "hentet 2026-11-10" in api_page, "the API page shows the same captured answer"


def test_index_without_samples_has_no_console(tmp_path, fixtures, snapshot):
    registry_dir = _registry_dir(tmp_path, fixtures, snapshot)
    out = tmp_path / "_site"
    generate_site(registry_dir, out, base_url="https://example.invalid/norapi/")
    index = (out / "index.html").read_text()
    assert "data-console" not in index and 'id="q"' in index
