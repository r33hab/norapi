# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com), newest first, grouped by date.

## 2026-11-17
### Added
- `behaviour` and `owner_terms` fields on a registry entry: what the endpoint does in practice (for example, answers anonymously) and the owner's own stated terms (for example, asks for an app id, or points to a documented feed for redistribution), shown on the API page under "Oppførsel" and "Eierens vilkår". Set first on the entries where the two diverge: the Arbeidsplassen job search, Linticket events, Grünerløkkas kartkatalog and the Smilefjes inspection file.
- `registry/retained.yaml` and the build step behind it: entries Felles datakatalog has dropped but whose service still answers are re-added to the registry, tagged `no-longer-in-catalogue` with a caveat, and dropped again automatically once the catalogue lists them or the service stops answering. Brought back 123 live services the last harvest had removed.
- About 40 more curated APIs: private software (Visma Net, Severa and Business NXT, Conta, Sendregning, Pureservice, Fotoware, Strex, Pexip, Unleash), media (Tidal, Viaplay Norge, regional newsroom feeds), finance and property (Oslo Børs NewsWeb, Ambita eiendom, Gjeldsregisteret, Finansportalens bankfeed), research and culture (UniMus samlinger, UiB CHC and Samla, UiS open journals, NDLA frontpage), transport (Ruter trafikkstatus, Kystverket referanseruter) and energy, environment and marine (Gassco UMM, the NVE, Miljødirektoratet and Fiskeridirektoratet ArcGIS REST servers, NGU naturstein).
- Eleven more municipal map catalogs (Halden, Sola, Askøy, Volda, Hemsedal, Løten, Jevnaker, Søndre Land, Vestre Toten, Sortland, Karlsøy), each verified against one benign layer. Servers that exposed sensitive-looking layers were left out by design.
- `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), linked from `CONTRIBUTING.md`. First tagged release, `v0.1.0`, matching the version in `pyproject.toml`.
### Changed
- Registry total 1 445 to 1 616: 48 newly curated entries (eleven of them municipal map catalogs) and 123 retained delisted-but-alive ones.
- OpenAPI index: 249 specifications and 6 475 operations (was 239 and 4 905).
- Smilefjes inspection file (`mattilsynet-smilefjes-tilsyn`) recategorised from arbeid-og-velferd to offentlig-forvaltning.

## 2026-11-16
### Added
- 340 more curated APIs, taking the curated set from 177 to 517 and the registry to 1 445. Each was probed live before it went in: open ones with a quick start that was run, restricted ones with the documentation and the stated access method confirmed and, where one exists, a documented path that answers 401 without credentials.
- Public sector suites: 30 Nav APIs (the pension APIs with their Maskinporten scopes, Aa-registeret, sykepenger, dagpenger, oppfølgingsplan, barnehagelister, the Arbeidsplassen job search), KS Fiks (14), ten Norsk helsenett services, three Helfo APIs, Altinn 3 (correspondence, broker, notifications, events, resource registry), BarentsWatch (8), twelve more Entur APIs including the partner sales APIs and the journey planner MCP server, and more from Brreg, Digdir, Tolletaten, Mattilsynet, Finanstilsynet, Statens vegvesen and MET.
- Local and regional: public ArcGIS map directories for more than 70 municipalities and inter-municipal bodies, seven county municipalities, Statens vegvesen, NVE and Avinor, each with a layer query that returned data; waste collection calendars (Avfall Sør, GLØR, Innherred Renovasjon, Remiks); Stavanger's bike counters, rain sensors, bathing temperatures and parking; Bergen parking availability; Trondheim's GeoServer; Oslo's plan register services.
- Private Norwegian services with public documentation: Bring (12 APIs), Vipps MobilePay (7 more), Fiken, Tripletex, PowerOffice, Unimicro, 24SevenOffice, Xledger, Dintero, Two, Proff, Enin, Signicat, FINN, Norkart (4), SuperOffice, Link Mobility, Sveve, Telenor, Tibber, Elvia, Easee, Zaptec, Airthings, Disruptive Technologies, Nordic Semiconductor, Cognite, Sanity, Catenda, Ardoq, Xeneta and more, plus Firi and Bare Bitcoin, which answer without a key.
- Research, culture and media: UiO, NTNU, OsloMet and Novus endpoints, five more Nasjonalbiblioteket APIs (IIIF, metadata, vocabularies), NVA publication channels, Feide, NLB, NTB, THREDDS servers at NIVA and NILU, Havforskningsinstituttet's ERDDAP, GBIF Norway, and RSS feeds from eleven newsrooms (tagged `feed`).
- Open but unadvertised endpoints behind public sites, each tagged `undocumented` and only where robots.txt allows the path: Norsk Tipping results, site search at FHI, Finanstilsynet and Sjøfartsdirektoratet, Finanstilsynet's market warnings, and the content APIs of eight public bodies.
### Changed
- OpenAPI index: 239 specifications and 4 905 operations (was 143 and 2 224), from the specifications the new entries point to.
- The harvest on this date returned 956 data services from Felles datakatalog against 1 093 a week earlier: the catalogue dropped 140 entries across many agencies (Miljødirektoratet, Fredrikstad, NGU, NVE, DiBK). 125 of them still answered when probed; they return if the catalogue lists them again.

## 2026-11-10
### Added
- Bank and payment APIs, each marked with who can get access and what it takes: the SpareBank 1 personal API (own accounts, BankID, no licence), Enable Banking, Neonomics and Tink as open banking aggregators, the PSD2 and partner portals of DNB, Nordea and Danske Bank (licence from Finanstilsynet and an eIDAS certificate, or an agreement), Vipps MobilePay ePayment, Login and Report (merchant or accounting partner agreement), BankID OpenID Connect (through a BankID partner), and Norges Bank's payment statistics file. Caveats spell out the licence and agreement requirements; PSD2 entries carry the `psd2` tag.
- Front page console: five real calls (Enhetsregisteret, Kommuneinfo, grunnbeløpet, luftkvalitet, magasinfylling) replayed with the answer each API gave, captured by the new `norapi samples` command into `registry/samples.json` and refreshed by the weekly harvest. The same answer shows under the quick start on the API's own page. See ADR-0003.
- Twenty more curated APIs from counties, municipalities and smaller institutions, each probed live: NDLA's open APIs (search, articles, images, audio, concepts, learning paths, subject taxonomy, oEmbed) with their OpenAPI specs, Nasjonalmuseet's collection API (Linked Art and IIIF without a key), Norid RDAP for .no domains, the BIBSYS authority file (SRU), Nord Pool's day-ahead prices for NO1 to NO5, ReMidt's waste collection calendar (also Fosen), and the ArcGIS map servers of Bergen, Fredrikstad, IKT Agder (Arendal, Grimstad, Froland) and the Vestland, Trøndelag, Troms and Agder county municipalities.
- `registry/retired.yaml`: harvested entries whose service a manual check found gone are left out of the registry, with the reason; the catalogue still lists them, so the weekly harvest would otherwise bring them back. Starts with Oslo's two HC-plasser WFS entries, whose host no longer resolves.
### Changed
- Site redesign: warm paper and near-black ink with one signal red, Geist and Geist Mono self-hosted (no Google Fonts request), a light and dark theme that follows the system with a toggle, numbered sections, the registry in numbers as a readout strip, provider and category counts as bars, and API pages with a framed fact sheet and the link check as status lights. Code, quick starts and answers share one dark console look. Passes axe (WCAG 2.2 AA), 24 px touch targets and no overflow down to 320 px.
- The six NDLA APIs that Felles datakatalog lists under Vestland fylkeskommune (NDLA's host county) are curated under "NDLA (Vestland fylkeskommune)" with real endpoints and content licences instead of the catalogue's GPL code licence.
- `sikt-bibsys-sru` also lists the catalogue's OAI-PMH endpoint.
- `norges-bank-open-data` names the lending survey, liquidity, money market and settlement datasets and lists `/api/dataflow`; `ssb-statbank-api` names the bank deposit and interest rate tables.
### Fixed
- Harvested entries carried placeholder links from the catalogue (`http://example.com/` as endpoint for NDLA, NVE HydAPI and a Kartverket test service); URLs on the RFC 2606 example domains and localhost are now dropped at harvest.

## 2026-10-21
### Fixed
- 969 of the 1048 harvested APIs showed "tilgang ukjent" because Felles datakatalog leaves access rights blank for most map services. Access now falls back to Geonorge's kartkatalog record for the service (760), then to the access rights of the datasets the service serves (151), with the strictest value when the two disagree (10). The remaining 48 were checked by hand (an anonymous call and the owner's docs) and recorded with the reason in `registry/access-review.yaml`; 5 stay unknown, each with a caveat saying why (dead address, 403, no endpoint). Every harvested entry now says where its access value came from, and the API page shows it.
### Added
- Forty more curated APIs, each probed live and with a quick start that was run, many of them open but unadvertised: Kystverket's Kystdatahuset and navigation warnings, Politiloggen, Vegvesen's ferry, traffic message, road weather and webcam, rest area and search services, Kartverket port data (OGC API), Bergen, Trondheim and Lillestrøm city bikes, Bring's postal code file, Store norske leksikon, Lokalhistoriewiki, DataverseNO, Divvun Sámi language tools, NRK's programme catalogue, BIBSYS SRU, NBIM fund holdings and live value, Brreg's municipal reporting and form registers, Oslo's statistics bank, the Stavanger region CKAN portal, Forskningsrådet open data and Prosjektbanken, Hjorteviltregisteret road kill, NIBIO agrometeorology, Sokkeldirektoratet FactMaps DataService, NVE hydro and wind power plant databases, electricity certificates and ChartServer, UiB seismology (FDSN), Forbrukerrådet's electricity price reference data, Helsenorge waiting times, the helsedata.no catalogue, Yr's bathing temperatures and Sildelaget vessel quotas.
- Eleven more that answer but come with strings attached, each with its caveats: IMDi statistics, Rovbase code lists, Getaround, Dott and Zeus GBFS feeds, Nkom's telecom statistics files, NILU (login), MET's Havvarsel-Frost (expired certificate), NAAF's pollen forecast (token), DFØ's data catalogue API and Hjorteviltregisteret's hunting data API (login).
- `caveats` on curated entries: short, plain restrictions to respect before relying on an API (restrictive terms, undocumented or unstable interface, test server, login for parts of it, personal data, expired certificate). They show as «Forbehold» in a warning box on the API page and as a badge in every listing and in search, in `llms.txt` after the summary, in `registry.json`, and in MCP results, whose instructions tell the assistant to pass them on. 45 entries carry them. Undocumented APIs also keep the `undocumented` tag.
### Changed
- A caveat that YAML would read as a mapping (an unquoted `Accept: x`) now fails the build with the entry id instead of crashing while writing `llms.txt`.

## 2026-10-20
### Added
- Ten more curated APIs, each probed live and with a quick start that was run: the utdanning.no API (HK-dir), Arbeidstilsynet's register of approved occupational health services, Vegvesen's parking register, Udir Barnehagefakta, Udir's Grep SPARQL endpoint, Artsdatabanken Nortaxa, Mattilsynet's meat inspection code lists, Luftfartstilsynet's aircraft register, the Geonorge register API (SOSI code lists) and Geonorge coordinate transformation, which curates an entry that was only harvested before.
### Fixed
- `norapi enrich` skipped specifications served as YAML under an `application/json` content type (Vegvesen's parking register); a body that fails JSON parsing and does not start with `{` now gets the YAML check.

## 2026-10-19
### Added
- Thirty more curated APIs, each probed live and with a quick start that was run: Lovdata open datasets, eInnsyn, Elhub energy data, Nav grunnbeløp, Matvaretabellen, Varsom, Regobs, NVE GridTimeSeries and magasinstatistikk, Entur Mobility v2 and vehicle positions, SSB PxWebApi 2, Sikt NVA and Cristin, NB DH-lab, KulturNav, Tolletaten open data, Arbeidstilsynet renholdsregisteret, Udir school and kindergarten registers, Fiskeridirektoratet vessel and aquaculture registers, Miljødirektoratet air quality, Finanstilsynet registry, plus keyed or registration-only APIs: Doffin, NOBIL, Enova's data portal, Vegvesen DATEX II, Patentstyret and Kassalapp.
- Nine of them curate entries that were only harvested before (`merge_with` on the catalogue URI), so the raw Felles datakatalog rows get proper descriptions, docs and quick starts.
### Changed
- DigitaltMuseum moved from the Nasjonalbiblioteket file to a new KulturIT provider file, next to KulturNav; its id is unchanged.
### Fixed
- `norapi enrich` crashed with "Object of type date is not JSON serializable" on YAML specs with unquoted dates; YAML documents now go through a JSON round trip when parsed, which also turns integer status-code keys into strings like a JSON spec has.
- `norapi build` failed with "UNIQUE constraint failed: apis.id" when the Felles datakatalog search API returned one data service on two pages; the harvester now keeps one entry per catalogue URI.
### Security
- YAML specs can no longer exhaust memory through alias expansion or nested `<<` merge keys: the composed node graph is measured before the document is built and refused past two million expanded nodes, self-referencing aliases are rejected, and the JSON round trip also stops past four times the 8 MB fetch cap. A spec with a mapping key JSON cannot hold, such as an unquoted date, is skipped instead of crashing the run.

## 2026-10-15
### Added
- OpenAPI enrichment (`norapi enrich`): resolves specifications behind `spec_url` and Swagger UI pages, caches the documents, writes `registry/specs.json` and `registry/operations.json`, and indexes every operation so `norapi ops` and the MCP tool `search_operations` can land on a method and path.
- Static site generator (`norapi site`): one pre-rendered page per API, provider and category, index with client-side search and a ⌘K palette, contribute and privacy pages, custom 404, sitemap, robots.txt, canonical and Open Graph tags, JSON-LD (WebSite, Dataset, WebAPI, Organization, BreadcrumbList). Hallmark design (Cobalt theme, Ecosystem Index) with tokens in `site/assets/tokens.css`.
- Fourteen more curated APIs after a source review: Statnett driftsdata, Udir Grep, HK-dir DBH, FHI Statistikk, Helsedirektoratet HAPI, Vinmonopolet, Luftfartstilsynet dronesoner, Ordbøkene, DigitaltMuseum, Kartverket høydedata, WMTS and vannstand, Frivillighetsregisteret, Entur rutedata, Digdir KRR.
- Contribution path: CONTRIBUTING.md, issue forms for new APIs and corrections, a pull request template, and a "Bidra" page on the site.
- `probe_url` on curated entries so the link checker can call an endpoint that answers anonymously.
### Changed
- Pages workflow now generates the site with `norapi site`; the weekly harvest also runs `norapi enrich`.
- Link checker reports verdicts (ok / answers / missing) instead of raw status codes.
- README rewritten as a proper front page: banner, live badges from registry.json, screenshot, the four front doors, pipeline and entry shape.
### Security
- All outbound fetches (spec fetcher, link checker) go through `netguard`: http(s) only, hosts resolved and checked against private, loopback and link-local ranges, every redirect hop validated before it is requested, bodies read through a streamed cap.
- Address pinning happens in the TCP layer (`PinningBackend`), so the URL keeps its hostname and TLS verifies the certificate against it; a lying resolver now fails the handshake with a hostname mismatch instead of being trusted. An earlier variant put the address in the URL, which weakened that check.
- JSON-LD escapes angle brackets and ampersands; external links render only for http(s) URLs; operation methods from third-party specs are escaped in the client-side search; entry ids must be slugs before they become file paths.
### Fixed
- `norapi enrich --limit N` merges into the existing specs and operations instead of overwriting them with the subset.
- Harvester for Felles datakatalog (data.norge.no): search API for the list, SPARQL per predicate for endpoints, specs, docs, licences and keywords, joined on the data service URI.
- Curated entries for about 35 well-known APIs (BRREG, SSB, Entur, MET, Kartverket, Nav, Skatteetaten, Digdir, Altinn, Vegvesen, Norges Bank, Stortinget, NVE and more) with access, auth, formats, docs and quick-start calls.
- Merge rules: curated fields win, harvested fields fill gaps, matched by FDK URI or identical endpoint.
- Build: `registry/registry.json`, `registry/llms.txt` for language models, and an SQLite FTS5 index rebuilt on demand.
- CLI `norapi harvest|build|check|search|show|providers|categories|stats` and an MCP server (`norapi-mcp`) with `search_apis`, `get_api`, `list_providers`, `list_categories`.
- Link checker that records docs/spec/endpoint status per entry.
- Static search site in `site/` with a GitHub Pages workflow, CI, and a weekly harvest workflow.
