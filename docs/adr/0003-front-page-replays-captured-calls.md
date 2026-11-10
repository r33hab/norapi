# ADR-0003: The front page replays captured calls, never live ones

Date: 2026-11-10. Status: accepted.

## Context

The site's front page should show that the registry works, not only that it lists things: a
real request to an API it lists, and the answer that came back. The site is static on GitHub
Pages, and most of the APIs do not send CORS headers, ask for a client header, or rate-limit
anonymous callers. A visitor's browser cannot be relied on to call them, and a page that fires
requests at public-sector APIs on every view would be a poor neighbour.

## Decision

- `norapi samples` runs the first `curl` command in the quick start of five chosen entries
  (`SAMPLES` in `src/norapi/samples.py`), through the same public-only client as the link
  checker, and writes status, measured time, content type, size and a trimmed rendering of the
  body to `registry/samples.json`. The weekly harvest runs it after the link check.
- The trimmed rendering keeps the API's key order, shows plain values before nested ones when it
  has to cut, and marks every cut with `…` and a count. The page says the answer was captured,
  and on which date.
- A call that fails keeps its previous capture. A call whose entry has left the registry, or that
  did not answer 2xx, is not shown.
- The site generator only reads the file. It never touches the network, so builds and tests stay
  offline and deterministic.
- The console replays the calls in the browser (the command types, the wait is the measured
  time, the answer prints), pauses on hover, keyboard focus, a hidden tab or when scrolled away,
  and stops for good when the visitor picks a call. With reduced motion it is a static switcher.

## Consequences

- The answers on the page can be up to a week old; the date is printed next to them.
- `samples.json` changes on every weekly run (timings, dates), so the harvest commit always
  touches it.
- Picking other calls is a one-line change to `SAMPLES`; the call must be a plain GET in the
  entry's quick start that answers anonymously.
