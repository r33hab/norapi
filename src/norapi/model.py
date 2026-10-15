"""The registry entry and the normalisation helpers every source goes through."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

ACCESS_VALUES = ("open", "restricted", "non-public", "unknown")
AUTH_VALUES = ("none", "api-key", "maskinporten", "id-porten", "oauth2", "unknown")

CATEGORIES: dict[str, str] = {
    "bedrift-og-organisasjon": "Bedrifter, organisasjoner og registre",
    "statistikk": "Statistikk og analyse",
    "transport-og-samferdsel": "Transport, vei og kollektiv",
    "vaer-og-klima": "Vær, klima og hav",
    "kart-og-geodata": "Kart, adresser og geodata",
    "arbeid-og-velferd": "Arbeid, velferd og helse",
    "skatt-og-avgift": "Skatt, avgift og økonomi",
    "offentlig-forvaltning": "Offentlig forvaltning og innsyn",
    "natur-og-miljo": "Natur, miljø og energi",
    "kultur-og-kunnskap": "Kultur, bibliotek og kunnskap",
    "finans": "Finans og valuta",
    "politikk-og-valg": "Politikk og valg",
    "identitet-og-tilgang": "Identitet, innlogging og tilgang",
    "annet": "Annet",
}

_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,118}[a-z0-9]|[a-z0-9]")
_SPEC_HINTS = ("openapi", "swagger", "api-docs", "apidocs", ".json", ".yaml", ".yml", "wsdl")
_FORMAT_ALIASES = {
    "application/json": "JSON",
    "application/ld+json": "JSON-LD",
    "application/xml": "XML",
    "text/xml": "XML",
    "application/rdf+xml": "RDF/XML",
    "text/turtle": "Turtle",
    "text/csv": "CSV",
    "text/html": "HTML",
    "application/geo+json": "GeoJSON",
    "application/vnd.ogc.wms_xml": "WMS",
    "application/octet-stream": "Binary",
}


@dataclass
class Provider:
    name: str
    orgnr: str | None = None
    org_path: str | None = None
    sector: str | None = None  # stat, kommune, fylke, statlig-selskap, privat


@dataclass
class ApiEntry:
    id: str
    title: str
    provider: Provider
    description: str | None = None
    summary: str | None = None
    title_en: str | None = None
    access: str = "unknown"
    auth: str = "unknown"
    formats: list[str] = field(default_factory=list)
    endpoints: list[str] = field(default_factory=list)
    spec_url: str | None = None
    docs_url: str | None = None
    probe_url: str | None = None  # a call that answers anonymously, for `norapi check`
    spec: dict[str, Any] | None = None  # OpenAPI summary from `norapi enrich`
    license: str | None = None
    keywords: list[str] = field(default_factory=list)
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    quick_start: str | None = None
    status: str | None = None
    modified: str | None = None
    source: dict[str, Any] = field(default_factory=dict)
    checks: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.id):
            raise ValueError(f"{self.id!r}: id must be a slug (a-z, 0-9, hyphens)")
        if self.access not in ACCESS_VALUES:
            raise ValueError(
                f"{self.id}: access must be one of {ACCESS_VALUES}, got {self.access!r}"
            )
        if self.auth not in AUTH_VALUES:
            raise ValueError(f"{self.id}: auth must be one of {AUTH_VALUES}, got {self.auth!r}")
        if self.category is not None and self.category not in CATEGORIES:
            raise ValueError(f"{self.id}: unknown category {self.category!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApiEntry:
        data = dict(data)
        data["provider"] = Provider(**data["provider"])
        return cls(**data)


def slugify(text: str, max_length: int = 60) -> str:
    """ASCII slug: 'Enhetsregisteret API (v2)' -> 'enhetsregisteret-api-v2'. Keeps æøå readable."""
    text = text.lower().replace("æ", "ae").replace("ø", "o").replace("å", "a")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_length].rstrip("-") or "x"


def stable_suffix(value: str, length: int = 6) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def looks_like_spec(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in _SPEC_HINTS)


def normalise_format(value: str) -> str | None:
    """Map catalogue format values (media types, EU file-type URIs, 'WMS') to short names."""
    value = value.strip()
    if not value:
        return None
    for prefix in ("MEDIA_TYPE ", "FILE_TYPE "):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    if value.startswith("http"):
        value = value.rstrip("/").rsplit("/", 1)[-1]
    lowered = value.lower()
    if lowered in _FORMAT_ALIASES:
        return _FORMAT_ALIASES[lowered]
    if "/" in lowered:  # an unmapped media type: keep the subtype
        return lowered.split("/", 1)[1].split("+")[0].upper()
    return value.upper() if len(value) <= 12 else value


def infer_auth(*texts: str | None) -> str:
    blob = " ".join(t for t in texts if t).lower()
    if "maskinporten" in blob:
        return "maskinporten"
    if "id-porten" in blob or "idporten" in blob:
        return "id-porten"
    if "oauth" in blob or "openid" in blob:
        return "oauth2"
    if "api-nøkkel" in blob or "api nøkkel" in blob or "api key" in blob or "apikey" in blob:
        return "api-key"
    return "unknown"


def make_summary(description: str | None, title: str, limit: int = 240) -> str:
    """A one-liner for search results and language models: first sentence(s), cut at a word."""
    text = re.sub(r"\s+", " ", (description or "").strip())
    if not text:
        return title
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"
