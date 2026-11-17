# One-page handover, 2026-11-17

For whoever opens this repository next. The long version is `HANDOVER.md`; the plan and the story
are `docs/carryover-2026-11-16.md` and `docs/HOW-WE-GOT-HERE.md`. Read `CLAUDE.md` and `AGENTS.md`
first for the rules. They stay as they are.

## State

- Main carries the finished harness: one lookup, one default workflow, live switches, the
  delivery's cautions and confirmations, and the removals of 2026-11-16.
- The suite is green and CI passes on 3.11, 3.12 and 3.13, with an editable install, a wheel and a
  Docker build.
- The acceptance run is done and written up: `docs/reviews/2026-11-17-acceptance-run.md`.
  259 of 264 right on the key, about '$0.009' an answer, one of six bars missed.
- The Docker image and the page have been run by hand.
- The release is drafted in `docs/release-notes.md`. It is not tagged.

## Open, in the order that matters

1. **Tag the release.** The owner picks the version; the recommendation is 0.2.0. The notes are written. 1.0 waits for a hold-out run of questions nobody shaped the harness against, a completed run through the container with a real key, a migration tool or an explicit no-upgrade promise, and a person other than the builder starting it from the README.
2. **A second human reading** of the acceptance answers was offered and declined on 2026-11-17; the release goes out on the two-reader reading. Verdicts are in
   `docs/traces/20261117T-acceptance-reading-*`.
3. **Why the answer-step prompt trips a content filter on one frontier model.** Not looked for.
   About '$0.10' a try. Only if someone wants a frontier model in that seat.
4. **Prose is not checked the way figures are.** The last run's five misses were omissions and a
   misdefined term. A check that reads conditions in words would be a new design and a ruling.
5. **The pointing cautions fire on about a fifth of right answers.** Narrowing them is a change to
   what the delivery says, so it needs a ruling.
6. **Owner-side:** reasons for the 2026-11-12 and 13 re-tiering, for `docs/MODELS.md`.
7. **`HANDOVER.md` is an archive,** marked so at its top on the owner's word of 2026-11-17. It stays
   where it is because tests and other files cite it by path.
8. **Sites learned as refusing are shared by every run in one process.** By design, not isolated
   (`docs/reviews/2026-11-16-user-path-audit.md`, left open 3).
9. **Not seen live:** whether the 1,800-second time budget cuts a node already in flight. The
   watchdog tests cancel calls mid-flight; no live run has been timed out on purpose.

## How to work here

- **Free work** (tests, documents, probes that call no provider) can go through a pull request on
  green. Never push to main.
- **A paid run** needs the owner's word and an amount, and a preregistration pushed first, with
  bars and predictions. Read the answers by hand, two readers; the scorer is a screen.
- **Do not run git in the tree a paid run writes into.** Work from a clone.
- **Keys:** never print one. `.env` is the owner's; if you edit it, mask values when you look.
- **Write simply.** Single-quote dollar figures. No model names or prices in the README or
  `.env.example`; they belong under `docs/`.
- **Records are the memory.** A session's scratch folder is wiped on restart. Keep traces in
  `docs/traces/` byte-identical and cite them by sha256.

## Where things are

| | |
|---|---|
| The rules and the protocol | `CLAUDE.md`, `AGENTS.md` |
| A map of the documents | `docs/README.md` |
| What was tried with models and why | `docs/MODELS.md` |
| Every run and audit, by date | `docs/reviews/` |
| Every plan before its spend | `docs/preregistration-*.md` |
| Recorded runs, byte-identical | `docs/traces/` |
| Probes and analysis scripts | `docs/probes/` |
| The frozen questions and keys | `evals/professional/`, `evals/tier2/` |
