# Bidra til norapi

Takk for at du vil hjelpe. Registeret blir bedre av hver håndplukkede oppføring: hva API-et
faktisk gir, hvordan du får tilgang, og ett kall som virker.

## Tre måter å bidra på

1. **Foreslå et API** uten å skrive kode: [skjema for nytt API](https://github.com/r33hAB/norapi/issues/new?template=nytt-api.yml).
2. **Meld en feil** i en oppføring: [skjema for feil](https://github.com/r33hAB/norapi/issues/new?template=feil-i-oppforing.yml).
   Hver side på nettstedet har en lenke som fyller ut skjemaet med riktig id.
3. **Send en pull request** med en oppføring i `registry/curated/`. Resten av dette dokumentet handler om det.

## Legge til et API

Én YAML-fil per leverandør. Finnes leverandøren fra før, legg API-et til i den filen.

```yaml
updated: 2026-10-15
provider:
  name: Eksempeletaten
  orgnr: "123456789"      # valgfritt, men fint
  sector: stat            # stat | kommune | fylke | statlig-selskap | privat
apis:
  - id: eksempeletaten-saker          # stabil slug: leverandør-tittel
    title: Saksoppslag API
    description: >-
      To til fire setninger: hva du får, hvordan du får tilgang, og det som overrasker.
    category: offentlig-forvaltning   # se CATEGORIES i src/norapi/model.py
    access: open                      # open | restricted | non-public | unknown
    auth: none                        # none | api-key | maskinporten | id-porten | oauth2 | unknown
    formats: [JSON]
    endpoints:
      - https://api.eksempeletaten.no/saker/v1
    docs_url: https://eksempeletaten.no/api
    spec_url: https://api.eksempeletaten.no/saker/v1/openapi.json   # valgfritt; gir endepunktsøk
    probe_url: https://api.eksempeletaten.no/saker/v1/health        # valgfritt; et kall som svarer anonymt
    license: NLOD 2.0
    keywords: [saker, saksnummer, innsyn]
    tags: [no-auth]
    caveats:                                                         # valgfritt; forbehold brukeren må kjenne til
      - Ikke dokumentert av etaten, og kan endres uten forvarsel.
    quick_start: |
      curl "https://api.eksempeletaten.no/saker/v1/2026-001"
```

Regler som holder kvaliteten oppe:

- **Skriv det du har verifisert.** Kjør `quick_start` selv. Står det `auth: none`, skal kallet svare uten nøkkel.
- **Beskrivelsen er for en utvikler som skal velge.** Hva får du, hva krever det, hva mangler. Ingen markedsføring.
- **Finnes API-et i Felles datakatalog**, matcher vi automatisk på identisk endepunkt-URL, eller eksplisitt med
  `merge_with: <katalogens data service-URI>`. Dine felter vinner, katalogens fyller tomrom.
- **Metadata, aldri data.** Ingen uttrekk fra API-ene, ingen personopplysninger, ingen kontaktpersoner.
- **Private tjenester** tas med når de er åpne og brukes mye av norske utviklere, med `sector: privat`.
- **Åpne, men uannonserte API-er** (JSON bak en offentlig nettside, en Swagger ingen lenker til) tas med når de
  svarer uten innlogging, med taggen `undocumented`.
- **Forbehold står i `caveats`**, ett kort punkt per forbehold: udokumentert eller ustabilt grensesnitt, vilkår som
  begrenser bruken, testserver, innlogging for deler av API-et, personopplysninger, utløpt sertifikat. De vises som
  «Forbehold» på API-siden, i `llms.txt` og i MCP-svarene, så både folk og KI-agenter ser dem før de tar API-et i bruk.

## Før du åpner pull requesten

```sh
uv sync
uv run norapi build                    # regenererer registry/registry.json og llms.txt
uv run norapi check --curated-only     # lenkesjekk; se at ingenting "mangler"
uv run pytest -q
uv run ruff check src tests
```

Commit både YAML-filen og de regenererte filene i `registry/`. Hvis du la til en `spec_url`, kjør gjerne
`uv run norapi enrich` også, så får oppføringen endepunkter med en gang.

## Kodebidrag

Harvester, søk, MCP-server og nettside ligger i `src/norapi/`. Les `docs/adr/` først; de to beslutningene der
(katalog og kuratering, aldri scraping; `registry.json` som produkt med FTS5 som indeks) styrer det meste.
Tester kjører på innspilte fixtures og skal ikke trenge nett.
