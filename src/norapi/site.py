"""Static site generator: one page per API, provider and category, plus index, bidra, personvern, 404.

Everything is pre-rendered HTML so crawlers and language models see content without JavaScript;
the search on the index page and the ⌘K palette are progressive enhancements over
`search-index.json` and `ops-index.json`. Design decisions live in site/assets/style.css
(Hallmark stamp at the top).
"""

from __future__ import annotations

import html
import json
import shutil
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from norapi import __version__
from norapi.model import CATEGORIES, slugify

ASSETS = Path(__file__).resolve().parents[2] / "site" / "assets"
REPO = "https://github.com/r33hAB/norapi"
ISSUES = f"{REPO}/issues/new"

ACCESS_LABEL = {
    "open": "Åpen",
    "restricted": "Begrenset",
    "non-public": "Ikke offentlig",
    "unknown": "Tilgang ukjent",
}
AUTH_LABEL = {
    "none": "Ingen autentisering",
    "api-key": "API-nøkkel",
    "maskinporten": "Maskinporten",
    "id-porten": "ID-porten",
    "oauth2": "OAuth2",
    "unknown": "Autentisering ukjent",
}
SECTOR_LABEL = {
    "stat": "Statlig",
    "kommune": "Kommunal",
    "fylke": "Fylkeskommunal",
    "statlig-selskap": "Statlig selskap",
    "privat": "Privat",
}
FONTS = (
    "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600"
    "&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500;600&display=swap"
)
SEARCH_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/>'
    '<path d="m20 20-3.5-3.5"/></svg>'
)


def e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def nb_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


class Site:
    def __init__(self, registry: dict[str, Any], operations: list[dict[str, Any]], base_url: str):
        self.base = base_url if base_url.endswith("/") else base_url + "/"
        self.registry = registry
        self.apis: list[dict[str, Any]] = registry["apis"]
        self.by_id = {a["id"]: a for a in self.apis}
        self.generated = registry["generated_at"][:10]
        self.ops_by_api: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for op in operations:
            self.ops_by_api[op["api_id"]].append(op)
        self.providers: dict[str, dict[str, Any]] = {}
        for api in self.apis:
            slug = slugify(api["provider"]["name"], 50)
            api["_provider_slug"] = slug
            bucket = self.providers.setdefault(
                slug,
                {
                    "slug": slug,
                    "name": api["provider"]["name"],
                    "orgnr": None,
                    "sector": None,
                    "apis": [],
                },
            )
            bucket["apis"].append(api)
            bucket["orgnr"] = bucket["orgnr"] or api["provider"].get("orgnr")
            bucket["sector"] = bucket["sector"] or api["provider"].get("sector")
        self.curated = [a for a in self.apis if a["source"]["kind"] != "fdk"]
        self.op_count = len(operations)

    # ----- shared chrome -----
    def url(self, path: str = "") -> str:
        return self.base + path.lstrip("/")

    def layout(
        self,
        *,
        title: str,
        description: str,
        path: str,
        body: str,
        jsonld: list[dict[str, Any]] | None = None,
        current: str | None = None,
        og_type: str = "website",
    ) -> str:
        canonical = self.url(path)
        full_title = (
            f"{title} · norapi" if title != "norapi" else "norapi: norske offentlige API-er"
        )
        ld = "".join(
            f'<script type="application/ld+json">{_jsonld(d)}</script>' for d in jsonld or []
        )

        def nav_link(href: str, label: str, key: str, secondary: bool = False) -> str:
            current_attr = ' aria-current="page"' if current == key else ""
            secondary_attr = " data-secondary" if secondary else ""
            return f'<a href="{self.url(href)}"{current_attr}{secondary_attr}>{label}</a>'

        return f"""<!doctype html>
<html lang="nb" data-root="{e(self.base)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(full_title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="norapi">
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:image" content="{self.url("assets/og.png")}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="norapi: søkbart register over norske offentlige API-er">
<meta property="og:locale" content="nb_NO">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{self.url("assets/favicon.svg")}" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{self.url("assets/style.css")}">
{ld}
</head>
<body>
<header class="nav"><div class="wrap nav__inner">
  <a class="nav__brand" href="{self.url()}">nor<b>api</b></a>
  <nav class="nav__links" aria-label="Hovedmeny">
    {nav_link("", "API-er", "index")}
    {nav_link("leverandorer/", "Leverandører", "providers", True)}
    {nav_link("bidra/", "Bidra", "bidra")}
  </nav>
  <button class="searchpill" type="button" data-cmdk-open aria-label="Søk i registeret, snarvei ⌘K">
    {SEARCH_ICON}<span class="searchpill__text">Søk etter API …</span>
    <span class="searchpill__kbd"><kbd>⌘</kbd><kbd>K</kbd></span>
  </button>
  <a class="btn nav__github" href="{REPO}">GitHub</a>
</div></header>
<dialog class="cmdk" id="cmdk" aria-label="Søk i registeret">
  <div class="cmdk__field">{SEARCH_ICON}<label class="visually-hidden" for="cmdk-input">Søk</label>
    <input id="cmdk-input" type="search" placeholder="API, endepunkt eller leverandør …" autocomplete="off"><kbd>esc</kbd></div>
  <div class="cmdk__results" id="cmdk-results" role="listbox"></div>
  <div class="cmdk__foot"><span><kbd>↑</kbd><kbd>↓</kbd> velg</span><span><kbd>↵</kbd> åpne</span><span><kbd>esc</kbd> lukk</span></div>
</dialog>
{body}
<footer class="wrap foot-line"><p>
  <span>norapi {e(__version__)}</span><span>·</span><span>generert {e(self.generated)}</span><span>·</span>
  <a href="{self.url("registry.json")}">registry.json</a><span>·</span>
  <a href="{self.url("llms.txt")}">llms.txt</a><span>·</span>
  <a href="{self.url("operations.json")}">operations.json</a><span>·</span>
  <a href="{REPO}">kildekode (MIT)</a><span>·</span>
  <a href="{self.url("personvern/")}">personvern</a><span>·</span>
  <span>metadata fra <a href="https://data.norge.no/data-services">data.norge.no</a>, hvert API har egne vilkår</span>
</p></footer>
<script src="{self.url("assets/app.js")}" defer></script>
</body>
</html>
"""

    # ----- fragments -----
    def badges_html(self, api: dict[str, Any], limit_formats: int = 3) -> str:
        parts = [
            f'<span class="badge badge--{e(api["access"])}">{e(ACCESS_LABEL[api["access"]])}</span>'
        ]
        if api.get("caveats"):
            parts.append('<span class="badge badge--caveat">Forbehold</span>')
        if api["auth"] != "unknown":
            parts.append(f'<span class="badge badge--plain">{e(AUTH_LABEL[api["auth"]])}</span>')
        for fmt in (api.get("formats") or [])[:limit_formats]:
            parts.append(f'<span class="badge badge--plain">{e(fmt)}</span>')
        ops = len(self.ops_by_api.get(api["id"], []))
        if ops:
            parts.append(
                f'<span class="badge badge--plain">{ops} endepunkt{"" if ops == 1 else "er"}</span>'
            )
        return "".join(parts)

    def row_html(self, api: dict[str, Any], note: str | None = None) -> str:
        tail = (
            f" · {e(note)}"
            if note
            else (" · håndplukket" if api["source"]["kind"] != "fdk" else "")
        )
        return (
            '<li class="row">'
            f'<h3 class="row__title"><a href="{self.url("api/" + api["id"] + "/")}">{e(api["title"])}</a></h3>'
            f'<p class="row__provider">{e(api["provider"]["name"])}{tail}</p>'
            f'<p class="row__summary">{e(api.get("summary") or "")}</p>'
            f'<div class="row__meta">{self.badges_html(api)}</div>'
            "</li>"
        )

    def card_html(self, api: dict[str, Any]) -> str:
        return (
            '<article class="card">'
            f'<h3 class="card__title"><a href="{self.url("api/" + api["id"] + "/")}">{e(api["title"])}</a></h3>'
            f'<p class="card__provider">{e(api["provider"]["name"])}</p>'
            f'<div class="card__badges">{self.badges_html(api, 2)}</div>'
            f'<p class="card__summary">{e(api.get("summary") or "")}</p>'
            "</article>"
        )

    def code_figure(
        self, label: str, code_html: str, *, light: bool = False, copy_id: str | None = None
    ) -> str:
        klass = "code code--light" if light else "code"
        button = (
            f'<button class="copy" type="button" data-copy="#{copy_id}">Kopier</button>'
            if copy_id
            else ""
        )
        pre_id = f' id="{copy_id}"' if copy_id else ""
        return (
            f'<figure class="{klass}"><figcaption><span>{e(label)}</span>{button}</figcaption>'
            f"<pre{pre_id}>{code_html}</pre></figure>"
        )

    def breadcrumbs(self, trail: list[tuple[str, str | None]]) -> tuple[str, dict[str, Any]]:
        items = []
        ld_items = []
        for position, (label, href) in enumerate(trail, start=1):
            if href is None:
                items.append(f'<li aria-current="page">{e(label)}</li>')
            else:
                items.append(f'<li><a href="{self.url(href)}">{e(label)}</a></li>')
            entry: dict[str, Any] = {"@type": "ListItem", "position": position, "name": label}
            if href is not None:
                entry["item"] = self.url(href)
            ld_items.append(entry)
        nav = f'<nav class="crumbs" aria-label="Brødsmuler"><ol>{"".join(items)}</ol></nav>'
        return nav, {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": ld_items,
        }

    # ----- pages -----
    def page_index(self) -> str:
        providers_sorted = sorted(
            self.providers.values(), key=lambda p: (-len(p["apis"]), p["name"])
        )
        category_counts: dict[str, int] = defaultdict(int)
        for api in self.apis:
            if api.get("category"):
                category_counts[api["category"]] += 1
        latest = sorted(
            (a for a in self.apis if a["source"]["kind"] == "fdk" and a.get("modified")),
            key=lambda a: a["modified"],
            reverse=True,
        )[:8]
        featured = sorted(self.curated, key=lambda a: (not a.get("quick_start"), a["title"]))[:12]
        tries = ["kjøretøy", "adresse", "værvarsel", "selskap", "stillinger", "kollektiv"]

        facet = lambda key, value, label: (  # noqa: E731
            f'<button class="chip" type="button" data-facet="{key}" data-value="{value}" aria-pressed="false">{label}</button>'
        )
        terminal = self.code_figure(
            "terminal",
            '<span class="cmt">$</span> uv run norapi search <span class="tok">"kjøretøy"</span> --access open\n'
            '<span class="cmt">$</span> uv run norapi ops <span class="tok">"enheter orgnr"</span>\n'
            '<span class="cmt">$</span> claude mcp add norapi -- uv run --directory norapi norapi-mcp\n'
            '<span class="cmt">$</span> curl -s ' + e(self.url("llms.txt")) + " | head\n"
            '<span class="ok">200 OK</span> <span class="cmt">· '
            + nb_int(len(self.apis))
            + " API-er, én linje hver</span>",
        )
        body = f"""
<main>
<section class="wrap top">
  <div class="top__lead">
    <h1>Norske offentlige API-er, samlet og søkbare.</h1>
    <p class="lede">{nb_int(len(self.apis))} API-er fra Felles datakatalog og {
            len(self.curated)
        } håndplukkede med
      eksempler som kan kjøres. For utviklere i nettleseren, for KI-agenter gjennom MCP og <code>llms.txt</code>.</p>
    <form class="search" id="search-form" role="search" action="{self.url()}">
      <label for="q">Søk etter API</label>
      <div class="search__row"><input id="q" name="q" type="search" placeholder="kjøretøy, adresse, værvarsel …" autocomplete="off" spellcheck="false">
      <button class="btn btn--primary" type="submit">Søk</button></div>
      <p class="search__status" id="search-status" aria-live="polite"></p>
    </form>
    <p class="try">Prøv {
            " · ".join(
                f'<a href="{self.url()}?q={e(t)}" data-try="{e(t)}">{e(t)}</a>' for t in tries
            )
        }. Trykk <kbd>/</kbd> for å søke.</p>
  </div>
  <aside class="readout" aria-label="Registeret i tall">
    <p class="readout__title">Registeret i tall</p>
    <dl>
      <div><dt>API-er</dt><dd>{nb_int(len(self.apis))}</dd></div>
      <div><dt>Håndplukket med eksempler</dt><dd>{len(self.curated)}</dd></div>
      <div><dt>Leverandører</dt><dd>{nb_int(len(self.providers))}</dd></div>
      <div><dt>Endepunkter indeksert</dt><dd>{nb_int(self.op_count)}</dd></div>
      <div><dt>Åpne uten avtale</dt><dd>{
            nb_int(sum(1 for a in self.apis if a["access"] == "open"))
        }</dd></div>
      <div><dt>Generert</dt><dd>{e(self.generated)}</dd></div>
    </dl>
    <p class="readout__links"><a href="{self.url("registry.json")}">registry.json</a> · <a href="{
            self.url("llms.txt")
        }">llms.txt</a> · <a href="{self.url("operations.json")}">operations.json</a></p>
  </aside>
</section>

<section class="wrap results" id="results" hidden>
  <div class="facets" aria-label="Filtre">
    {facet("access", "open", "Åpen")}{facet("access", "restricted", "Begrenset")}{
            facet("access", "unknown", "Tilgang ukjent")
        }
    {facet("auth", "none", "Ingen auth")}{facet("auth", "api-key", "API-nøkkel")}{
            facet("auth", "maskinporten", "Maskinporten")
        }
    {facet("source", "curated", "Håndplukket")}
  </div>
  <ol class="list" id="result-list"></ol>
  <p class="empty" id="empty" hidden>Ingen API-er matcher. Prøv et kortere ord, et engelsk ord, eller
    <a class="link" href="{self.url("bidra/")}">foreslå et API som mangler →</a></p>
  <button class="btn more" id="more" type="button" hidden>Vis flere</button>
  <div class="ops-hits" id="op-results"></div>
</section>

<div id="rails">
<section class="wrap rail">
  <header class="rail__head"><h2>Håndplukket</h2><a class="link" href="{
            self.url()
        }?source=curated" data-source-link>Alle {len(self.curated)} håndplukkede →</a></header>
  <div class="grid">{"".join(self.card_html(a) for a in featured)}</div>
</section>

<section class="wrap rail rail--split">
  <div>
    <header class="rail__head"><h2>Etter kategori</h2><p>håndplukkede oppføringer</p></header>
    <ul class="keyval">{
            "".join(
                f'<li><a href="{self.url("kategori/" + key + "/")}">{e(label)}</a><span class="n">{category_counts.get(key, 0)}</span></li>'
                for key, label in CATEGORIES.items()
                if category_counts.get(key)
            )
        }</ul>
  </div>
  <div>
    <header class="rail__head"><h2>Flest API-er</h2><a class="link" href="{
            self.url("leverandorer/")
        }">Alle leverandører →</a></header>
    <ul class="keyval">{
            "".join(
                f'<li><a href="{self.url("leverandor/" + p["slug"] + "/")}">{e(p["name"])}</a><span class="n">{len(p["apis"])}</span></li>'
                for p in providers_sorted[:12]
            )
        }</ul>
  </div>
</section>

<section class="band"><div class="wrap band__inner">
  <div>
    <h2>For terminalen og for agenter</h2>
    <p>Samme register, tre innganger: en CLI som søker lokalt, en MCP-server som gir en KI-assistent
      verktøyene <code>search_apis</code> og <code>search_operations</code>, og en tekstfil som kan limes rett inn i en prompt.</p>
    <p><a class="link" href="{
            REPO
        }#for-ai-assistants">Oppsett for Claude Code og andre MCP-klienter →</a></p>
  </div>
  {terminal}
</div></section>

<section class="wrap rail">
  <header class="rail__head"><h2>Sist endret i Felles datakatalog</h2><p>etatenes egne oppdateringer</p></header>
  <ol class="list">{
            "".join(self.row_html(a, note=f"endret {a['modified'][:10]}") for a in latest)
        }</ol>
</section>
</div>
</main>
"""
        jsonld = [
            {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": "norapi",
                "url": self.base,
                "description": "Søkbart register over norske offentlige API-er, for utviklere og KI-agenter.",
                "inLanguage": "nb",
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": {
                        "@type": "EntryPoint",
                        "urlTemplate": f"{self.base}?q={{search_term_string}}",
                    },
                    "query-input": "required name=search_term_string",
                },
            },
            {
                "@context": "https://schema.org",
                "@type": "Dataset",
                "name": "norapi registry",
                "description": "Metadata om norske offentlige API-er: tilgang, autentisering, formater, dokumentasjon og endepunkter.",
                "url": self.base,
                "license": "https://opensource.org/licenses/MIT",
                "isAccessibleForFree": True,
                "distribution": [
                    {
                        "@type": "DataDownload",
                        "encodingFormat": "application/json",
                        "contentUrl": self.url("registry.json"),
                    },
                    {
                        "@type": "DataDownload",
                        "encodingFormat": "text/markdown",
                        "contentUrl": self.url("llms.txt"),
                    },
                ],
            },
        ]
        return self.layout(
            title="norapi",
            description=f"Søkbart register over {nb_int(len(self.apis))} norske offentlige API-er med tilgang, autentisering, dokumentasjon og eksempler. For utviklere og KI-agenter.",
            path="",
            body=body,
            jsonld=jsonld,
            current="index",
        )

    def page_api(self, api: dict[str, Any]) -> str:
        provider = api["provider"]
        pslug = api["_provider_slug"]
        crumbs, crumbs_ld = self.breadcrumbs(
            [("norapi", ""), (provider["name"], f"leverandor/{pslug}/"), (api["title"], None)]
        )
        source = api["source"]
        access_from = {
            "geonorge": "fra Geonorge",
            "fdk-dataset": "fra datasettene tjenesten leverer",
            "conflict": "Geonorge og datasettene er uenige; den strengeste verdien er brukt",
            "review": f"sjekket for hånd {source.get('access_checked', '')}: {source.get('access_note', '')}",
        }.get(source.get("access_from") or "")
        facts: list[tuple[str, str]] = [
            (
                "Tilgang",
                e(ACCESS_LABEL[api["access"]])
                + (f'<br><span class="meta">{e(access_from)}</span>' if access_from else ""),
            ),
            ("Autentisering", e(AUTH_LABEL[api["auth"]])),
        ]
        if api.get("formats"):
            facts.append(("Formater", e(", ".join(api["formats"]))))
        if api.get("category"):
            facts.append(
                (
                    "Kategori",
                    f'<a href="{self.url("kategori/" + api["category"] + "/")}">{e(CATEGORIES[api["category"]])}</a>',
                )
            )
        if api.get("license"):
            lic = api["license"]
            facts.append(
                (
                    "Lisens",
                    f'<a href="{e(lic)}">{e(_short_url(lic))}</a>'
                    if lic.startswith("http")
                    else e(lic),
                )
            )
        if api.get("docs_url"):
            facts.append(
                (
                    "Dokumentasjon",
                    f'<a href="{safe_href(api["docs_url"])}" title="{e(api["docs_url"])}">{e(_link_label(api["docs_url"]))} →</a>',
                )
            )
        if api.get("spec_url"):
            facts.append(
                (
                    "Spesifikasjon",
                    f'<a href="{safe_href(api["spec_url"])}" title="{e(api["spec_url"])}">{e(_link_label(api["spec_url"]))} →</a>',
                )
            )
        for endpoint in (api.get("endpoints") or [])[:3]:
            facts.append(("Endepunkt", f"<code>{e(endpoint)}</code>"))
        if len(api.get("endpoints") or []) > 3:
            facts.append(
                (
                    "",
                    f'<span class="meta">+ {len(api["endpoints"]) - 3} endepunkter til i registry.json</span>',
                )
            )
        if api.get("spec"):
            spec = api["spec"]
            facts.append(
                ("OpenAPI", e(f"{spec.get('format', '')}, {spec.get('operations', 0)} operasjoner"))
            )
        if api.get("status"):
            facts.append(("Status", e(_short_url(api["status"]))))
        if api.get("modified"):
            facts.append(("Sist endret", e(api["modified"][:10])))
        if api["source"].get("catalogue_url"):
            facts.append(
                (
                    "Kilde",
                    f'<a href="{safe_href(api["source"]["catalogue_url"])}">data.norge.no →</a>',
                )
            )
        facts.append(
            (
                "Oppføring",
                e(
                    "håndplukket"
                    if api["source"]["kind"] == "curated"
                    else "håndplukket, utfylt fra Felles datakatalog"
                    if api["source"]["kind"] == "curated+fdk"
                    else "høstet fra Felles datakatalog"
                ),
            )
        )
        facts_html = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in facts)

        check_note = ""
        if api.get("checks"):
            checks = api["checks"]
            bits = []
            for key, label in (
                ("docs_url", "dok"),
                ("spec_url", "spec"),
                ("endpoint", "endepunkt"),
            ):
                probe = checks.get(key)
                if isinstance(probe, dict):
                    verdict = {"ok": "ok", "answers": "svarer", "missing": "mangler"}.get(
                        probe.get("verdict"), ""
                    )
                    bits.append(
                        f"{label} {probe.get('status') or probe.get('error')} {verdict}".strip()
                    )
            if bits:
                check_note = f'<p class="facts__note">Lenkesjekk {e(checks.get("checked_at", "")[:10])}: {e(" · ".join(bits))}</p>'

        issue_title = f"Rettelse: {api['title']} ({api['id']})"
        edit_link = ""
        if api["source"].get("file"):
            edit_link = f'<a class="link" href="{REPO}/blob/main/registry/curated/{e(api["source"]["file"])}">Rediger kilden på GitHub →</a>'
        actions = (
            f'<div class="facts__actions">'
            f'<a class="link" href="{ISSUES}?template=feil-i-oppforing.yml&title={e(issue_title)}">Meld en feil i oppføringen →</a>'
            f"{edit_link}</div>"
        )

        sections: list[str] = []
        if api.get("caveats"):
            sections.append(
                '<section class="caveats" aria-labelledby="caveats-h"><h2 id="caveats-h">Forbehold</h2><ul>'
                + "".join(f"<li>{e(c)}</li>" for c in api["caveats"])
                + "</ul></section>"
            )
        description = (api.get("description") or "").strip()
        long_description = len(description) > 420
        lede_text = (
            description if description and not long_description else (api.get("summary") or "")
        )
        if description and long_description:
            paragraphs = "".join(
                f"<p>{e(p.strip())}</p>" for p in api["description"].split("\n") if p.strip()
            )
            sections.append(f'<section class="prose"><h2>Om API-et</h2>{paragraphs}</section>')
        if api.get("quick_start"):
            sections.append(
                "<section><h2>Kom i gang</h2>"
                + self.code_figure(
                    "kjør dette", e(api["quick_start"].strip()), light=True, copy_id="quickstart"
                )
                + "</section>"
            )
        ops = self.ops_by_api.get(api["id"], [])
        if ops:
            sections.append(self.operations_section(ops))
        siblings = [a for a in self.providers[pslug]["apis"] if a["id"] != api["id"]][:8]
        if siblings:
            sections.append(
                f'<section><h2>Flere fra {e(provider["name"])} <span class="count">({len(self.providers[pslug]["apis"]) - 1})</span></h2>'
                '<ul class="related">'
                + "".join(
                    f'<li><a href="{self.url("api/" + s["id"] + "/")}">{e(s["title"])}</a><span class="n">{e(ACCESS_LABEL[s["access"]])}</span></li>'
                    for s in siblings
                )
                + f'</ul><p style="margin-top:var(--space-sm)"><a class="link" href="{self.url("leverandor/" + pslug + "/")}">Alle fra {e(provider["name"])} →</a></p></section>'
            )

        body = f"""
<main class="wrap page">
{crumbs}
<header class="api-head">
  <h1>{e(api["title"])}</h1>
  <p class="api-head__provider">Levert av <a href="{self.url("leverandor/" + pslug + "/")}">{e(provider["name"])}</a>{f' <span class="mono">· org.nr. {e(provider["orgnr"])}</span>' if provider.get("orgnr") else ""}</p>
  <div class="badges">{self.badges_html(api, 4)}</div>
  <p class="lede">{e(lede_text)}</p>
</header>
<div class="api-body">
  <aside class="api-facts"><h2 class="visually-hidden">Fakta</h2><dl class="facts">{facts_html}</dl>{check_note}{actions}</aside>
  <div class="api-main">{"".join(sections)}</div>
</div>
</main>
"""
        webapi: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "WebAPI",
            "name": api["title"],
            "description": api.get("summary") or api["title"],
            "url": self.url(f"api/{api['id']}/"),
            "provider": {"@type": "Organization", "name": provider["name"]},
            "isAccessibleForFree": api["access"] == "open",
            "inLanguage": "nb",
        }
        if provider.get("orgnr"):
            webapi["provider"]["identifier"] = provider["orgnr"]
        if api.get("docs_url"):
            webapi["documentation"] = api["docs_url"]
        if api.get("license") and api["license"].startswith("http"):
            webapi["license"] = api["license"]
        description = api.get("summary") or f"{api['title']} fra {provider['name']}"
        return self.layout(
            title=f"{api['title']} ({provider['name']})",
            description=description[:300],
            path=f"api/{api['id']}/",
            body=body,
            jsonld=[webapi, crumbs_ld],
            og_type="article",
        )

    def operations_section(self, ops: list[dict[str, Any]]) -> str:
        by_tag: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for op in ops:
            by_tag[(op.get("tags") or ["(uten tag)"])[0]].append(op)
        groups = []
        for tag, items in sorted(by_tag.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            rows = "".join(
                f'<li><span class="method method--{op["method"].lower()}">{e(op["method"])}</span>'
                f"<code>{e(op['path'])}</code>"
                + (
                    f'<span class="op__summary">{e(op.get("summary") or op.get("description") or "")}</span>'
                    if op.get("summary") or op.get("description")
                    else ""
                )
                + "</li>"
                for op in sorted(items, key=lambda o: (o["path"], o["method"]))
            )
            heading = f'<p class="ops-tag">{e(tag)} · {len(items)}</p>' if len(by_tag) > 1 else ""
            groups.append(f'{heading}<ul class="ops">{rows}</ul>')
        body = "".join(groups[:6])
        if len(groups) > 6:
            body += f'<details class="ops-more"><summary>Vis {len(groups) - 6} grupper til</summary>{"".join(groups[6:])}</details>'
        return (
            f'<section><h2>Endepunkter <span class="count">({len(ops)})</span></h2>{body}</section>'
        )

    def page_provider(self, provider: dict[str, Any]) -> str:
        apis = sorted(provider["apis"], key=lambda a: (a["source"]["kind"] == "fdk", a["title"]))
        crumbs, crumbs_ld = self.breadcrumbs(
            [("norapi", ""), ("Leverandører", "leverandorer/"), (provider["name"], None)]
        )
        meta = [f"{len(apis)} API-er"]
        if provider.get("sector"):
            meta.append(SECTOR_LABEL.get(provider["sector"], provider["sector"]))
        if provider.get("orgnr"):
            meta.append(f"org.nr. {provider['orgnr']}")
        body = f"""
<main class="wrap page">
{crumbs}
<header class="head-hang"><h1>{e(provider["name"])}</h1><p class="meta">{e(" · ".join(meta))}</p></header>
<ol class="list">{"".join(self.row_html(a) for a in apis)}</ol>
</main>
"""
        ld: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": provider["name"],
            "url": self.url(f"leverandor/{provider['slug']}/"),
        }
        if provider.get("orgnr"):
            ld["identifier"] = provider["orgnr"]
        return self.layout(
            title=f"{provider['name']}: {len(apis)} API-er",
            description=f"API-er fra {provider['name']} i norapi-registeret: {', '.join(a['title'] for a in apis[:5])}.",
            path=f"leverandor/{provider['slug']}/",
            body=body,
            jsonld=[ld, crumbs_ld],
            current="providers",
        )

    def page_providers(self) -> str:
        providers = sorted(self.providers.values(), key=lambda p: (-len(p["apis"]), p["name"]))
        crumbs, crumbs_ld = self.breadcrumbs([("norapi", ""), ("Leverandører", None)])
        half = (len(providers) + 1) // 2

        def col(items: list[dict[str, Any]]) -> str:
            return (
                '<ul class="keyval">'
                + "".join(
                    f'<li><a href="{self.url("leverandor/" + p["slug"] + "/")}">{e(p["name"])}</a><span class="n">{len(p["apis"])}</span></li>'
                    for p in items
                )
                + "</ul>"
            )

        body = f"""
<main class="wrap page">
{crumbs}
<header class="head-hang"><h1>Leverandører</h1><p class="meta">{len(providers)} organisasjoner · sortert etter antall API-er</p></header>
<div class="columns">{col(providers[:half])}{col(providers[half:])}</div>
</main>
"""
        return self.layout(
            title="Leverandører",
            description=f"{len(providers)} norske organisasjoner som tilbyr API-er, med antall API-er per leverandør.",
            path="leverandorer/",
            body=body,
            jsonld=[crumbs_ld],
            current="providers",
        )

    def page_category(self, key: str, label: str, apis: list[dict[str, Any]]) -> str:
        crumbs, crumbs_ld = self.breadcrumbs([("norapi", ""), (label, None)])
        body = f"""
<main class="wrap page">
{crumbs}
<header class="head-hang"><h1>{e(label)}</h1><p class="meta">{len(apis)} håndplukkede API-er i kategorien</p></header>
<ol class="list">{"".join(self.row_html(a) for a in sorted(apis, key=lambda a: a["title"]))}</ol>
</main>
"""
        return self.layout(
            title=label,
            description=f"Norske API-er innen {label.lower()}: {', '.join(a['title'] for a in apis[:5])}.",
            path=f"kategori/{key}/",
            body=body,
            jsonld=[crumbs_ld],
        )

    def page_bidra(self) -> str:
        crumbs, crumbs_ld = self.breadcrumbs([("norapi", ""), ("Bidra", None)])
        example = e(
            "updated: 2026-10-15\n"
            'provider:\n  name: Eksempeletaten\n  orgnr: "123456789"\n  sector: stat\n'
            "apis:\n  - id: eksempeletaten-saker\n    title: Saksoppslag API\n"
            "    description: >-\n      Oppslag i saker per saksnummer, med status og dokumentliste.\n"
            "    category: offentlig-forvaltning\n    access: open\n    auth: none\n    formats: [JSON]\n"
            "    endpoints:\n      - https://api.eksempeletaten.no/saker/v1\n"
            "    docs_url: https://eksempeletaten.no/api\n    license: NLOD 2.0\n"
            "    keywords: [saker, saksnummer, innsyn]\n"
            '    quick_start: |\n      curl "https://api.eksempeletaten.no/saker/v1/2026-001"\n'
        )
        body = f"""
<main class="wrap page">
{crumbs}
<header class="head-hang"><h1>Bidra til registeret</h1>
<p class="lede">Felles datakatalog dekker mye, men ikke alt, og etatenes egne beskrivelser er ofte tynne.
Det som gjør registeret nyttig er håndplukkede oppføringer: hva API-et faktisk gir deg, hvordan du får tilgang,
og ett kall som virker. Kjenner du et API som mangler, eller ser en feil, er det tre måter å bidra på.</p></header>
<div class="text">
<h2>1. Foreslå et API i et skjema</h2>
<p>Det raskeste. Fyll ut <a href="{ISSUES}?template=nytt-api.yml">skjemaet for nytt API</a> på GitHub med navn, leverandør,
dokumentasjonslenke og hva det krever av tilgang. Vi legger det inn og krediterer deg i commit-meldingen.</p>
<h2>2. Meld en feil</h2>
<p>Hver API-side har lenken «Meld en feil i oppføringen». Den åpner et <a href="{ISSUES}?template=feil-i-oppforing.yml">utfylt skjema</a>
med API-ets id, så du bare trenger å skrive hva som er galt: død lenke, feil tilgangsnivå, utdatert beskrivelse.</p>
<h2>3. Send en pull request</h2>
<p>Håndplukkede oppføringer er én YAML-fil per leverandør i <code>registry/curated/</code>. Legg til et API slik,
kjør <code>uv run norapi build</code> og <code>uv run norapi check --curated-only</code>, og åpne en pull request.</p>
<pre>{example}</pre>
<p>Feltene <code>access</code> (open, restricted, non-public, unknown) og <code>auth</code> (none, api-key, maskinporten,
id-porten, oauth2, unknown) er faste verdier. <code>quick_start</code> skal være et kall som svarer uten avtale,
eller tydelig si hva som trengs. Finnes API-et allerede i Felles datakatalog, matcher vi på endepunkt eller
<code>merge_with</code>, og dine felter vinner over katalogens. Har API-et forbehold, som udokumentert grensesnitt,
begrensende vilkår eller innlogging for deler av det, skriv dem som korte punkter i <code>caveats</code>; de vises som
«Forbehold» på API-siden, i llms.txt og i MCP-svarene.</p>
<h2>Hva som hører hjemme her</h2>
<ul>
<li>API-er fra stat, kommune, fylke og statlige selskaper. Private tjenester tas med når de er åpne og brukes mye av norske utviklere.</li>
<li>Metadata og lenker, aldri dataene selv. Hvert API har egne vilkår, og registeret gjengir bare det leverandøren eller bidragsyteren skrev.</li>
<li>Ingen scraping av nettsider. Kildene er Felles datakatalog og håndskrevne oppføringer, se <a href="{REPO}/blob/main/docs/adr/0001-catalogues-and-curation-not-scraping.md">ADR-0001</a>.</li>
</ul>
<h2>Se også</h2>
<ul>
<li><a href="https://data.norge.no/data-services">data.norge.no</a>, den nasjonale katalogen registeret høster fra. Registrer API-et ditt der også, det er kilden alle andre bruker.</li>
<li><a href="https://github.com/iamkm1/Norway-Open-Data">Norway-Open-Data</a>, en TypeScript-SDK som pakker inn flere av de samme API-ene.</li>
<li><a href="https://datalandsbyen.norge.no/">Datalandsbyen</a>, Digdirs forum for folk som jobber med offentlige data.</li>
</ul>
</div>
</main>
"""
        return self.layout(
            title="Bidra",
            description="Foreslå et norsk API som mangler, meld en feil, eller send en pull request med en håndplukket oppføring.",
            path="bidra/",
            body=body,
            jsonld=[crumbs_ld],
            current="bidra",
        )

    def page_personvern(self) -> str:
        crumbs, crumbs_ld = self.breadcrumbs([("norapi", ""), ("Personvern", None)])
        body = f"""
<main class="wrap page">
{crumbs}
<header class="head-hang"><h1>Personvern</h1><p class="meta">sist oppdatert {e(self.generated)}</p></header>
<div class="text">
<p>norapi er en statisk nettside uten innlogging, skjemaer som sender data, informasjonskapsler eller sporing.
Søket kjører i nettleseren din mot en nedlastet indeksfil, så søkeordene dine forlater ikke maskinen.</p>
<h2>Det som likevel registreres</h2>
<ul>
<li>Siden ligger på GitHub Pages. GitHub logger IP-adresse og forespørsler for drift, etter
<a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHubs personvernerklæring</a>.</li>
<li>Skrifttypene hentes fra Google Fonts. Google ser forespørselen om skriftfilen, ikke hva du søker på.</li>
<li>Lenker til dokumentasjon og endepunkter går til leverandørenes egne nettsteder, med deres vilkår.</li>
</ul>
<h2>Innhold om personer</h2>
<p>Registeret inneholder metadata om API-er, ikke personopplysninger. Kontaktpersoner fra Felles datakatalog tas ikke med.
Bidrag via GitHub følger GitHubs regler, og navnet ditt vises der du selv har valgt å vise det.</p>
<p>Spørsmål? <a href="{REPO}/issues">Åpne en sak på GitHub</a>.</p>
</div>
</main>
"""
        return self.layout(
            title="Personvern",
            description="Hvordan norapi behandler data: ingen sporing, ingen informasjonskapsler, søk som kjører i nettleseren.",
            path="personvern/",
            body=body,
            jsonld=[crumbs_ld],
        )

    def page_404(self) -> str:
        body = f"""
<main class="wrap page">
<header class="head-hang"><h1>Fant ikke siden</h1>
<p class="lede">Adressen finnes ikke i registeret. API-sider ligger under <code>/api/&lt;id&gt;/</code>, og id-er kan ha endret seg siden en lenke ble delt.</p></header>
<p><a class="btn btn--primary" href="{self.url()}">Til søket</a>  <a class="link" href="{self.url("leverandorer/")}" style="margin-left:var(--space-md)">Se alle leverandører →</a></p>
</main>
"""
        return self.layout(
            title="Fant ikke siden", description="Siden finnes ikke.", path="404.html", body=body
        )

    # ----- machine-readable -----
    def search_index(self) -> list[dict[str, Any]]:
        rows = []
        for api in self.apis:
            row: dict[str, Any] = {
                "id": api["id"],
                "t": api["title"],
                "s": api.get("summary"),
                "p": api["provider"]["name"],
                "ps": api["_provider_slug"],
                "a": api["access"],
                "u": api["auth"],
                "f": (api.get("formats") or [])[:4],
                "src": api["source"]["kind"],
            }
            if api.get("title_en"):
                row["e"] = api["title_en"]
            keywords = list(api.get("keywords") or []) + list(api.get("tags") or [])
            if keywords:
                row["k"] = keywords[:20]
            if api.get("category"):
                row["c"] = api["category"]
            if api.get("endpoints"):
                row["n"] = api["endpoints"][0]
            if api.get("quick_start"):
                row["q"] = 1
            if api.get("caveats"):
                row["w"] = 1
            ops = len(self.ops_by_api.get(api["id"], []))
            if ops:
                row["o"] = ops
            rows.append(row)
        return rows

    def ops_index(self) -> list[dict[str, Any]]:
        return [
            {
                "a": op["api_id"],
                "m": op["method"],
                "p": op["path"],
                "s": op.get("summary"),
                "n": self.by_id[op["api_id"]]["title"],
            }
            for api_id, ops in self.ops_by_api.items()
            if api_id in self.by_id
            for op in ops
        ]

    def sitemap(self, paths: list[tuple[str, str | None]]) -> str:
        entries = "".join(
            f"<url><loc>{e(self.url(p))}</loc>"
            + (f"<lastmod>{e(m)}</lastmod>" if m else "")
            + "</url>"
            for p, m in paths
        )
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>\n'


def _link_label(url: str) -> str:
    """A label that reads: the host, plus the path only while the whole thing stays short."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.netloc or url
    path = parsed.path.rstrip("/")
    return host + path if path and len(host + path) <= 40 else host


def _jsonld(data: dict[str, Any]) -> str:
    """JSON for a <script> block: angle brackets and ampersands escaped so data cannot close the tag."""
    text = json.dumps(data, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def safe_href(url: str | None) -> str:
    """Only http(s) links are rendered as links; anything else becomes a dead anchor."""
    if url and url.startswith(("https://", "http://")):
        return e(url)
    return "#"


def _short_url(url: str) -> str:
    text = url.replace("https://", "").replace("http://", "").rstrip("/")
    return text if len(text) <= 48 else text[:45] + "…"


def generate_site(registry_dir: Path, out_dir: Path, base_url: str) -> int:
    registry = json.loads((registry_dir / "registry.json").read_text(encoding="utf-8"))
    operations_file = registry_dir / "operations.json"
    operations = (
        json.loads(operations_file.read_text(encoding="utf-8")).get("operations", [])
        if operations_file.exists()
        else []
    )
    site = Site(registry, operations, base_url)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    written = 0

    def put(path: str, content: str) -> None:
        nonlocal written
        target = out_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written += 1

    paths: list[tuple[str, str | None]] = [("", site.generated)]
    put("index.html", site.page_index())
    for api in site.apis:
        put(f"api/{api['id']}/index.html", site.page_api(api))
        paths.append((f"api/{api['id']}/", (api.get("modified") or site.generated)[:10]))
    for provider in site.providers.values():
        put(f"leverandor/{provider['slug']}/index.html", site.page_provider(provider))
        paths.append((f"leverandor/{provider['slug']}/", site.generated))
    put("leverandorer/index.html", site.page_providers())
    paths.append(("leverandorer/", site.generated))
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for api in site.apis:
        if api.get("category"):
            by_category[api["category"]].append(api)
    for key, apis in by_category.items():
        put(f"kategori/{key}/index.html", site.page_category(key, CATEGORIES[key], apis))
        paths.append((f"kategori/{key}/", site.generated))
    put("bidra/index.html", site.page_bidra())
    paths.append(("bidra/", site.generated))
    put("personvern/index.html", site.page_personvern())
    paths.append(("personvern/", site.generated))
    put("404.html", site.page_404())
    put("sitemap.xml", site.sitemap(paths))
    put("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {site.url('sitemap.xml')}\n")
    put(
        "search-index.json",
        json.dumps(site.search_index(), ensure_ascii=False, separators=(",", ":")),
    )
    put("ops-index.json", json.dumps(site.ops_index(), ensure_ascii=False, separators=(",", ":")))
    put(".nojekyll", "")

    for name in ("registry.json", "llms.txt", "operations.json", "specs.json"):
        source = registry_dir / name
        if source.exists():
            shutil.copy(source, out_dir / name)
            written += 1
    assets_out = out_dir / "assets"
    shutil.copytree(ASSETS, assets_out)
    written += len(list(assets_out.iterdir()))
    (out_dir / "generated.json").write_text(
        json.dumps(
            {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "pages": len(paths)}
        ),
        encoding="utf-8",
    )
    return written
