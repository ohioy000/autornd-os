# Release notes: the first public release (draft, held: see "Before tagging")

AutoRnD-OS answers expert and professional questions with inexpensive models, and says honestly
what it checked. A prose question goes in. A typed answer comes out, with the passages it read,
the checks it ran, and cautions where something did not hold up.

## What this release is

- **One default workflow, `answer-and-recompute`.** Triage, the asks, one lookup that finds
  where the answer is written, fetches those pages itself and hands on their own words, one
  answer with typed values, free checks, and an optional recompute vote kept for calculations.
- **A record of what was read.** Each passage is stored as found or not found, with a sha256.
  The delivery lists cautions (pages that differ, a figure on no page, nothing readable) and,
  where it can, a confirmation that the answer's figures stand in a passage found on its page.
- **Models by job, not by name.** Tiers ship empty and the owner fills them in `.env`; rates come
  from the provider catalogue at startup. `docs/MODELS.md` says what was tried and why.
- **Spend is bounded.** Every call reserves its worst case and releases exactly its own; a run
  that fails after dispatch keeps its liability. Nothing runs without a key, and the server
  serves loopback only until `API_KEY` or `JWT_SECRET` is set.

## What was measured, on the final configuration

One run of 2026-11-17, preregistered before the spend, on the three frozen professional sets:
44 questions, six answers each, 264 answers, read blind by two readers against signed keys
(`docs/reviews/2026-11-17-acceptance-run.md`).

- **259 of 264 right on the key** by the rule the preregistration states, **248** on the blind
  readers' stricter marks.
- **No confirmation stood beside a wrong figure.**
- **About '$0.009' an answer, '$2.32' for the run, about 82 seconds an answer.**
- **One of six bars missed:** of the five wrong answers only one, a wrong figure, carried a
  caution that pointed at it. The other four were an omission, a missing form, and a term
  defined wrongly beside a right figure; the checks read figures, not prose.
- **Against a frontier model asked directly** (22 of the same questions, web search on): **equivalent
  accuracy**, the harness about six times cheaper and about seven times slower
  (`docs/reviews/2026-11-17-frontier-direct.md`, `docs/MODELS.md`). The frontier model was right
  22 of 22 at medium effort and 14 of 14 at high effort. The harness, in the acceptance run, was
  right on 131 of its 132 answers to those same 22 questions (129 on the stricter marks). Neither
  is shown to be more accurate than the other: the samples are too small to separate a miss rate
  of one or two in a hundred from none.

These sets are the ones the harness was shaped against, so the figures above are not a forecast
for a question nobody has seen. A second run, also preregistered, did that.

**The hold-out run, 2026-11-17.** 42 questions written after the harness was fixed, by authors
that never saw its answers, in fields the other sets leave out; checked against the live pages by
two other agents; keys signed by the owner. Three answers each, 126 answers, read blind by three
readers and again by the executor (`docs/reviews/2026-11-17-holdout-run.md`).

- **113 of 126 right on the key** (about 90 percent), **97 on a stricter reading** where a wrong
  claim outside the key counts. On the 26 questions whose cited page the harness's own fetch
  can read, 74 of 78; on the 16 it cannot, 39 of 48. On the five traps, where the right answer
  is "the document states no such figure", 10 of 15.
- **'$1.355' for the run, about '$0.011' an answer, about 107 seconds an answer.**
- **None blocked by a rate limit** in 126; the retry was raised to five attempts.
- **Two of seven bars missed.** One confirmation stood beside a wrong figure (a year taken from
  a superseded licence whose page is still served), and of nine wrong answers three carried a
  caution that pointed at them. Four answers ended blocked by the harness's own checks: two
  cut off, two that named an ask it could not satisfy, one of them a trap.

## Known limits

These are in the README's Limitations too. The first three came from the last run, and the proxy line from a check made afterwards.

1. **A right figure can come with a wrong claim beside it.** Roughly 30 of the 264 answers carried
   a wrong or doubtful claim outside what was asked, by a rough count of the readers' notes.
2. **A pointing caution is raised on about a fifth of right answers** (58 of 259), usually because
   an older edition of the rule sits among the pages found.
3. **A confirmation is about words on a page.** It cannot see what a figure means: a right count
   of business days with the day misdefined was confirmed.
4. **A source that is wrong with nothing in its text to show it is not caught,** such as a stale
   official page that looks current. In the hold-out run one such answer, a year taken from a
   superseded licence, carried a confirmation, because the figure did stand on a page that was
   found. A confirmation is about words on a page, not about which page is current.
5. **Answers written in words are not checked the way figures are.**
6. **The answer-step prompt can trip a safety filter on some frontier models.** Tried once, the
   model returned no text; what trips it was not looked for.
7. **With no key set, a same-host proxy that does not pass `X-Forwarded-For` serves everyone.**
   Measured 2026-11-17: with the header the request is refused, without it accepted. Set `API_KEY`
   or `JWT_SECRET` whenever anything other than that machine can reach the server.
8. **Some sites refuse to be read,** and a scanned PDF stays unread. The delivery says so.
9. **The recompute vote cannot see an omission,** or an error every sample shares.
10. **The provider rate-limits.** Six of 270 units were blocked by an upstream 429 in the acceptance
   run, before the retry was raised from three attempts to five. None of 126 was blocked in the
   hold-out run. A caller should still expect the odd blocked run.
11. **No code execution, no streaming, no roles.** Runs are kept apart per user; there are no
    admin or team permissions.
12. **The harness blocks rather than say "none stated".** On a datasheet that gives no thermal
    resistance, one answer was blocked on an ask it could not satisfy and one invented a figure
    (with cautions saying it was on no page). Two of 126 answers were cut off and blocked.
13. **Wrong words and missing items get no caution.** Of nine wrong answers in the hold-out run,
    six carried none: a missing item, a wrong status, a comparator. The checks read figures.
14. **`/api/profiles` reports the profile's display name** ("AutoRnD" for the default), which is
    not in its own list of names. The names in the list are the ones to use.

## What was checked by hand

- The test suite on three Python versions in CI, an editable install, a built wheel, and a Docker
  build that boots and asserts `/api/health` reports `degraded` honestly.
- The Docker image built and run on 2026-11-17 on a Linux machine, with the page driven in a real
  browser at desktop and phone width, and a completed run through the image with a real key from
  a signed-in browser: 68 seconds, a correct answer with a confirmation, '$0.0080'
  (`docs/reviews/2026-11-16-browser-check.md`).
- A cold start: an agent with only the README cloned, installed and started the project in
  about five minutes, and built the image. It found that the image carried the working `.env`;
  that is fixed. It was an agent, not a person, and it had no browser.
- A database from before the version stamp, and one from a newer release, were migrated and
  refused as the tests say.

## How to run it

See the README's quick start. In short: `pip install -e ".[dev]"`, fill the six required tiers
and `OPENROUTER_API_KEY` in `.env`, then `uvicorn autornd.main:app --port 8100`; or build the
Dockerfile and pass the same as environment variables, with `API_KEY` set if anything other than
that machine will call it.

## Before tagging

- **The release is held.** The hold-out run missed its bar 2, and the preregistration says the
  release is held and the case goes to the owner. The owner decides: release with the limit
  stated, or take a ruling on a guard first.
- The owner chooses the version number. `pyproject.toml` still says 0.1.0. The recommendation
  was 0.2.0, with 1.0 only after a hold-out run that met its bars and a person starting the
  project from the README.
- The owner may add the reasons for the 2026-11-12 and 13 re-tiering to `docs/MODELS.md`.
- A second human reading of the acceptance and hold-out answers is the owner's to ask for.
- `CLAUDE.md` rule 12 still says there is no migration tool; the database now has numbered
  migrations. Changing the rule is the owner's.
