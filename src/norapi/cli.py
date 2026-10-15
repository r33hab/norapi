"""norapi: harvest, build, check, search."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from norapi.build import REGISTRY_DIR, REGISTRY_JSON, write_registry
from norapi.curated import load_curated, merge
from norapi.harvest import fdk
from norapi.model import ApiEntry
from norapi.search import Registry

DEFAULT_RAW_DIR = Path("data/raw/fdk")
CURATED_DIR = REGISTRY_DIR / "curated"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="norapi", description="Registry of Norwegian public APIs."
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    harvest = commands.add_parser("harvest", help="pull the catalogue(s) into data/raw/")
    harvest.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)

    build = commands.add_parser(
        "build", help="merge curated + harvested into registry/registry.json"
    )
    build.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    build.add_argument("--curated-only", action="store_true", help="skip harvested entries")

    check = commands.add_parser(
        "check", help="probe docs, spec and endpoint URLs, store the status"
    )
    check.add_argument("--curated-only", action="store_true")
    check.add_argument("--limit", type=int)
    check.add_argument("--timeout", type=float, default=15.0)

    search = commands.add_parser("search", help="full-text search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--access", choices=("open", "restricted", "non-public", "unknown"))
    search.add_argument("--auth")
    search.add_argument("--provider")
    search.add_argument("--format", dest="fmt")
    search.add_argument("--category")
    search.add_argument("--json", action="store_true")

    show = commands.add_parser("show", help="print one entry")
    show.add_argument("id")

    commands.add_parser("providers", help="providers with API counts")
    commands.add_parser("categories", help="categories with API counts")
    commands.add_parser("stats", help="registry summary")
    return parser


def cmd_harvest(args: argparse.Namespace) -> int:
    snapshot = fdk.harvest(fdk.FdkClient(), args.raw_dir)
    print(f"fdk: {len(snapshot['hits'])} data services -> {args.raw_dir / 'fdk.json'}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    curated = load_curated(CURATED_DIR)
    harvested: list[ApiEntry] = []
    if not args.curated_only:
        snapshot_file = args.raw_dir / "fdk.json"
        if snapshot_file.exists():
            harvested = fdk.to_entries(fdk.load_snapshot(args.raw_dir))
        else:
            print(
                f"no snapshot at {snapshot_file}; building from curated entries only",
                file=sys.stderr,
            )
    entries = merge(curated, harvested)
    document = write_registry(entries)
    print(f"registry: {document['count']} APIs ({document['sources']}) -> {REGISTRY_JSON}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from norapi.check import check_entries

    document = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    entries = [ApiEntry.from_dict(a) for a in document["apis"]]
    targets = [
        e
        for e in entries
        if not args.curated_only or e.source.get("kind", "").startswith("curated")
    ]
    checked = check_entries(targets, timeout=args.timeout, limit=args.limit)
    write_registry(entries)
    missing = [
        (e.id, name, probe.get("status") or probe.get("error"))
        for e in targets
        if e.checks
        for name, probe in e.checks.items()
        if isinstance(probe, dict) and probe.get("verdict") == "missing"
    ]
    print(
        f"checked {checked} entries; {len(missing)} links look missing (404, 410, 5xx, no answer)"
    )
    for api_id, name, status in missing:
        print(f"  {api_id}: {name} -> {status}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    registry = Registry.open()
    results = registry.search(
        args.query,
        limit=args.limit,
        access=args.access,
        provider=args.provider,
        fmt=args.fmt,
        category=args.category,
        auth=args.auth,
    )
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return 0
    if not results:
        print("no matches")
        return 1
    for api in results:
        badges = [api["access"]]
        if api["auth"] != "unknown":
            badges.append(f"auth: {api['auth']}")
        if api.get("formats"):
            badges.append(", ".join(api["formats"][:3]))
        print(f"{api['id']}")
        print(f"  {api['title']}  [{api['provider']['name']}]  ({'; '.join(badges)})")
        if api.get("summary"):
            print(f"  {api['summary']}")
        link = api.get("docs_url") or api.get("spec_url") or (api.get("endpoints") or [None])[0]
        if link:
            print(f"  {link}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    api = Registry.open().get(args.id)
    if api is None:
        print(f"no entry with id {args.id}", file=sys.stderr)
        return 1
    print(json.dumps(api, ensure_ascii=False, indent=1))
    return 0


def cmd_providers(args: argparse.Namespace) -> int:
    for row in Registry.open().providers():
        print(f"{row['apis']:5d}  {row['name']}")
    return 0


def cmd_categories(args: argparse.Namespace) -> int:
    for row in Registry.open().categories():
        print(f"{row['apis']:5d}  {row['id']:28s} {row['label']}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    print(json.dumps(Registry.open().stats(), ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if not args.verbose:  # one line per request is noise outside debugging
        logging.getLogger("httpx").setLevel(logging.WARNING)
    handlers = {
        "harvest": cmd_harvest,
        "build": cmd_build,
        "check": cmd_check,
        "search": cmd_search,
        "show": cmd_show,
        "providers": cmd_providers,
        "categories": cmd_categories,
        "stats": cmd_stats,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
