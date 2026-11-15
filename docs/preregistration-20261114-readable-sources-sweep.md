# Preregistration: the readable-sources sweep (2026-11-14)

Written and pushed before the run. The owner's direction of 2026-11-14: when a lookup's page
cannot be read, flag the site and find one that can be, or stop if nothing can be found, so an
unchecked answer does not reach the next step; and test it in a wider sweep of about '$1.75'.

## What was built, switched off

Two settings in `autornd/config.py`, both off by default, so main behaves as before until the
owner has read this sweep:

- `lookup_avoid_unreadable`: a site that refuses a fetch ("HTTP 401, 403, 429, 451" or a
  challenge page) is remembered for the life of the process. Every later lookup, the second
  round of the same question included, is told the sites by name and told to quote the passage
  from a site that can be read.
- `lookup_withhold_unverified`: a lookup answer with no passage found on its page is kept in the
  run's record and is not shown to the phases. The delivery says how many were withheld.

"Stop if nothing can be found" is read here as the second setting: nothing unchecked is passed
on. Whether the whole run should also end without an answer is **not** built. This sweep counts
how often every lookup answer of a run is withheld and whether those runs' answers were right,
which is the evidence that decision needs.

## What is run

Full answers through the default workflow (`answer-and-recompute`), by
`docs/probes/short_workflows_measurement.py` unchanged; the arms differ only in two environment
settings.

- **Three arms:** `now` (both off), `avoid` (the first on), `avoid_withhold` (both on).
- **Six questions, four repeats each, in every arm: 72 answers.** They are the six recorded
  questions whose answers use a lookup: tier-2 Q2, Q7, Q12, Q17, Q22 and the owner's
  inspection-authorization request. The other 20 tier-2 questions are calculations that look
  nothing up, so they would test nothing here.
- **Cost.** About '$1.45' expected. Stops: '$0.22' on each of six tier-2 shards and '$0.14' on
  each of three inspection-authorization runs, '$1.74' in all. About '$3.41' of the owner's
  '$7' is spent before it.

## What is measured

1. The share of quoted passages on pages that could not be read.
2. The share of answers with at least one passage found on its page.
3. How often the second round, told the site, quoted a readable one.
4. Answers passing the screen (the tier-2 scorer and the golden scorer). The screen is not the
   result (D50): every answer on which the arms' screens differ is read by hand.
5. In `avoid_withhold`: runs in which every lookup answer was withheld, and their screens.
6. Cost for each arm.

## The bars

1. **Fewer unread quotes.** In `avoid` the share of quotes on unread pages is at most half of
   `now`'s.
2. **No harm from avoiding.** `avoid` passes the screen in at most 1 fewer of 24 answers than
   `now`.
3. **No harm from withholding.** `avoid_withhold` passes the screen in at most 1 fewer of 24
   than `now`.
4. **Cost.** Neither arm costs more than 25 percent above `now`.

All met for an arm: the architect advises switching that setting on. Bar 3 missed: withholding
is not advised, and stopping a run even less so.

## Predictions

1. `now` has 25 to 40 percent of its quotes on unread pages, nearly all osha.gov.
2. Bar 1 is met: the search can find eCFR copies when told.
3. Bar 2 is met.
4. Bar 3 is missed or met narrowly: Q12's answers were right 8 times of 8 with no passage found,
   so withholding takes away something the answer used.
5. Each shard's first question is not helped in its first round, because nothing is flagged yet.

## Limits, stated beforehand

- Six questions. Four are OSHA rules, which is where the refusing site is.
- The memory of refusing sites lasts one process. A shard here is one process answering ten
  questions, so later questions benefit from earlier ones, as they would on a server and would
  not on a single command-line run.
- One reader; D50 asks for two, a stated departure.
