# Site concept

The design brief behind the web front door, kept so later changes stay in the same voice.

- **Concept:** the registry presents itself as an instrument. Every number on the page is
  counted from the registry, and the front page runs real calls against the APIs it lists.
- **Carrier:** the console, dark in both themes. It is the hero, and the same component carries
  the quick start and the captured answer on each API page and the terminal band.
- **Direction:** Specimen (mono labels, numbered sections, corner brackets, status lights, one
  signal red on warm paper), Composed motion, designed for desktop first with a full phone layout.
- **Signature:** the console replays five captured calls: the command types, the wait is the
  response time measured at capture, the answer prints line by line (ADR-0003).

Rules that keep it honest: no invented numbers (counts come from `registry.json`, answers from
`samples.json` with their capture date), no fade-ups on scroll, nothing that moves without a
pause, and a static version under reduced motion.

Tokens live in `site/assets/tokens.css`; the stylesheet header in `style.css` repeats the brief.
Type: Geist and Geist Mono, self-hosted (SIL OFL, `site/assets/fonts/OFL.txt`).
