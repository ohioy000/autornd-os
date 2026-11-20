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
- The hold-out run is done and written up: `docs/reviews/2026-11-17-holdout-run.md`. 42 questions
  nobody shaped the harness against, 113 of 126 right on the key (97 on a stricter reading),
  '$1.355'. **Bar 2 was missed: one confirmation stood beside a wrong year. The preregistration
  holds the release for the owner.** Bar 4 was missed again.
- The database has numbered migrations and a refusal of a newer database; the rate-limit retry is
  five attempts; the Docker image has been run with a real key and a signed-in browser; an agent
  started the project from the README alone and found one real risk (the image carried `.env`),
  now fixed.
- **0.2.0 is released** (tag `v0.2.0`, 2026-11-17), on the owner's word "Release 0.2.0, limit
  stated". The notes are `docs/release-notes.md`.
- **Added 2026-11-18: a frontier model asked directly was right on all 42 hold-out questions,**
  against the harness's 113 of 126, at about nine times the cost an answer ('$0.0986' against
  '$0.0108') and a tenth of the time. `docs/reviews/2026-11-18-frontier-direct-holdout.md`,
  '$4.14' of '$5.00'. Bar 1 was missed. The 0.2.0 claim of equivalent accuracy holds only for the
  questions the harness was shaped against, and `docs/MODELS.md` and the release notes now say so.

## Open, in the order that matters

1. **1.0.** The hold-out run missed its bar 2 (`docs/reviews/2026-11-17-holdout-run.md`), so
   the owner released 0.2.0 with the limit stated. **On 2026-11-17 the owner took the advice to
   leave that limit stated and build no guard:** judges and second models were tried and caught
   nothing (`docs/MODELS.md`), and a free check on years and names would fix one symptom. 1.0 now
   waits for **a person other than the builder starting the project from the README** (an agent
   did it, which is not the same), using `docs/first-try-note.md`, and for the owner's word to
   lift the held bar. The container run, the migrations and the retry are done. The frontier
   comparison of 2026-11-18 (item 10) bears on how 1.0 is described, since the harness is less
   accurate than a frontier model on new questions.
   Also the owner's: `CLAUDE.md` rule 12 says there is no migration tool, and the database now
   has numbered migrations.
2. **A second human reading** of the acceptance answers was offered and declined on 2026-11-17; the release went out on the two-reader reading. Verdicts are in
   `docs/traces/20261117T-acceptance-reading-*`. The hold-out answers were read the same way.
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

10. **The accuracy gap on new questions.** The harness missed 13 answers on 11 questions that a
    frontier model asked directly answered right, but it was right on each of the 11 in at least
    one draw: the misses scatter. A lookup that read 3 pages or fewer was not right in 6 of 13
    units, against 7 of 113 for 4 or more; most unread pages gave "no answer within 25 s"
    (`docs/reviews/2026-11-19-holdout-misses-classified.md`). The rerun of the 11 questions
    (`docs/reviews/2026-11-19-eleven-rerun.md`, '$3.0122' spent of '$4.50') gave the harness 24 right
    of 28 answers made against the frontier model's 27 of 27 at low effort: bar 1 met on rate,
    bar 3 (within five points) missed, cost bar met. The first run's misses were draws on 8 of the
    11 questions and repeat on X12, X31 and X41. **11 draws were never made (provider 402 on
    credit while the two arms ran together); redoing them costs about '$0.65' and needs the
    owner's word and a runner option to pick exact units.** **2026-11-20, owner's ruling:
    the fetch limits went to 60 s (from 25) and 37.5 MB (from 15); the downloads take 0.5-2 s
    and the time is the PDF text read, so a faster read would pay more (not done); effect on
    answers unmeasured.** **Also 2026-11-20, owner's ruling: a reader tier (`MODEL_READER`, set in
    the owner's `.env`, serving unpinned: G-2 open) reads a lookup's long pages in parallel and
    copies back verbatim passages, each checked against the page. Built, tested, never run live;
    not measured.** What to do
    about the gap is a design question and needs a ruling (a longer fetch limit, a retry of a
    cut-off answer, saying "none stated", reading more pages). **Any lookup change makes the 42
    hold-out questions a used set;** a second hold-out set is needed to judge it.

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
