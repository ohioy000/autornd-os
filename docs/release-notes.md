# Release notes: the first public release (draft, to be tagged on the owner's word)

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
- **Against a frontier model asked directly** (22 of the same questions, web search on): level on
  accuracy, the harness about six times cheaper and about seven times slower
  (`docs/reviews/2026-11-17-frontier-direct.md`, `docs/MODELS.md`). The harness is **not** shown to
  be more accurate than a frontier model.

These sets are the ones the harness was shaped against. They are not a hold-out, and the figures
are not a forecast for a question nobody has seen.

## Known limits

These are in the README's Limitations too. The first three came from the last run.

1. **A right figure can come with a wrong claim beside it.** Roughly 30 of the 264 answers carried
   a wrong or doubtful claim outside what was asked, by a rough count of the readers' notes.
2. **A pointing caution is raised on about a fifth of right answers** (58 of 259), usually because
   an older edition of the rule sits among the pages found.
3. **A confirmation is about words on a page.** It cannot see what a figure means: a right count
   of business days with the day misdefined was confirmed.
4. **A source that is wrong with nothing in its text to show it is not caught,** such as a stale
   official page that looks current.
5. **Answers written in words are not checked the way figures are.**
6. **The answer-step prompt can trip a safety filter on some frontier models.** Tried once, the
   model returned no text; what trips it was not looked for.
7. **Some sites refuse to be read,** and a scanned PDF stays unread. The delivery says so.
8. **The recompute vote cannot see an omission,** or an error every sample shares.
9. **The provider rate-limits.** Six of 270 units were blocked by an upstream 429 in the last run
   and made again; a caller should expect the odd blocked run.
10. **No code execution, no streaming, no roles.** Runs are kept apart per user; there are no
    admin or team permissions.

## What was checked by hand

- The test suite on three Python versions in CI, an editable install, a built wheel, and a Docker
  build that boots and asserts `/api/health` reports `degraded` honestly.
- The Docker image built and run on 2026-11-17 on a Linux machine, with the page driven in a real
  browser at desktop and phone width (`docs/reviews/2026-11-16-browser-check.md`).
- Not seen: a signed-in caller in a browser, and a completed run in the container (it needs a
  provider key and a spend).

## How to run it

See the README's quick start. In short: `pip install -e ".[dev]"`, fill the six required tiers
and `OPENROUTER_API_KEY` in `.env`, then `uvicorn autornd.main:app --port 8100`; or build the
Dockerfile and pass the same as environment variables, with `API_KEY` set if anything other than
that machine will call it.

## Before tagging

- The owner chooses the version number. `pyproject.toml` still says 0.1.0.
- The owner may add the reasons for the 2026-11-12 and 13 re-tiering to `docs/MODELS.md`.
- A second human reading of the acceptance answers is the owner's to ask for.
