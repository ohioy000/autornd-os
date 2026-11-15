# Where the answer's passage is lost: the lookup test (2026-11-14)

Preregistered in `docs/preregistration-20261114-lookup-asks-request.md`, pushed before the run. The
figures re-derive with `docs/probes/lookup_asks_request_analysis.py`.

## The point

- **The directive tested did not earn its place.** Looking up the request's own question first
  found the answer's passage in 9 of 15 runs. The code as it is found it in 8. The bar was 12, and
  4 more than now. It is not proposed.
- **The test did find where the passage is lost, and it is mostly after the search.** The search
  returned the passage in 24 of the 30 runs. The quote check then kept it in only 17.
- **There are three separate losses, each tied to a kind of source or question:**
  1. **Tables.** The search quotes a table as a grid of cells. The quote check looks for the same
     words in a row on the page and does not find them. Q12 lost its passage in 6 of 6 runs this
     way.
  2. **A site that refuses us.** osha.gov answers every fetch with "HTTP 403". All 13 quotes from
     it that held the answer could not be checked.
  3. **A vague request.** For the inspection-authorization question the search itself brought the
     wrong section in 5 of 6 runs. Asking the request first helped once in three.
- **Cost:** '$0.346' for 30 grounding runs, against '$0.30' expected. About '$2.44' of the owner's
  '$7' is now spent.

## What was run

- The grounding step alone, through the real engine (`workflows/triage-only.yaml`), two arms, five
  requests, three repeats: 30 runs. No answer was written.
- **Code:** main at `4c1a87d`, with the owner's `.env` of the date. Arm `request_first` wrapped one
  function inside the probe. Started 00:23 UTC on 2026-11-15.
- **Trace,** copied byte-identical:
  `docs/traces/20261115T002323Z-lookup-asks-request-runs.jsonl`, sha256 `60204e2d1723…`.

## Run by run

Runs out of 3 in which the passage was among the found quotes; in brackets, runs in which the
search returned it at all.

| Request | `now` | `request_first` | Where it was lost |
|---|---|---|---|
| IA, eligibility conditions | 0 (0) | 1 (1) | The search brought 65.95 and 43.7, not 65.91 |
| Q2, oxygen limits | 3 (3) | 3 (3) | Not lost |
| Q12, water limits (a table) | 0 (2) | 0 (3) | The table quoted as a grid; not matched on the page |
| Q17, tagout strength | 3 (3) | 3 (3) | Not lost. The osha.gov copies were refused; eCFR's were found |
| Q22, audiograms | 2 (3) | 2 (3) | In one run each, every copy quoted was from osha.gov |
| **All** | **8 (11)** | **9 (13)** | |

One reader, the architect, read the matched passages: each one states the answer it was counted
for. D50 asks for two readers; a stated departure.

## The 52 quotes that held the answer

| Site | Kind | Found | Not found on the page | Not fetched |
|---|---|---|---|---|
| ecfr.gov | page | 15 | 11 | 0 |
| govinfo.gov | PDF | 8 | 3 | 0 |
| govinfo.gov | XML | 2 | 0 | 0 |
| osha.gov | page | 0 | 0 | 13, each "HTTP 403" |

- **The 11 on ecfr.gov** are mostly the Q12 table, written by the search model with bars between
  the cells ("|(1) Fluoride|4.0|").
- **The 3 govinfo PDFs:** one is a table row with dot leaders and a line break before the figure
  ("(16) Arsenic ......" then "0.010"). The other two are plain sentences the PDF's text did not
  match; not traced.

## The bars and the predictions

| | Stated | Result |
|---|---|---|
| Bar 1 | `request_first` finds the passage in at least 12 of 15 | **Missed.** 9 |
| Bar 2 | and in at least 4 more runs than `now` | **Missed.** 1 more |
| Prediction 1 | `now` finds it in fewer than 10 of 15 | **Held.** 8 |
| Prediction 2 | `request_first` finds it in at least 12 | **Wrong.** 9 |
| Prediction 3 | Q12 is the hardest | **Held.** 0 of 6, level with IA under `now` |
| Prediction 4 | `request_first` costs within 20 percent of `now` | **Wrong, narrowly.** '$0.189' against '$0.157', 20.4 percent more |

## What this means for a directive

The owner asked whether the flaw can be met with a directive used only where it is needed. The test
says the flaw is three flaws, and each has its own narrow remedy. None is built; each changes what
counts as checked or what is fetched, so each is the owner's ruling.

1. **Tables: read a quoted table cell by cell.** When a quote is a grid, the check would look for
   each cell's words on the page instead of the whole grid in a row. Free code, applies only to a
   quote that is a table. It would have recovered Q12 in 5 of 6 runs here.
2. **A refused site: say so, and prefer a copy that can be read.** osha.gov refuses every fetch. The
   same rules are on ecfr.gov and govinfo.gov, which do not. The narrow remedy is to tell the
   search step which sites cannot be read, so it quotes a readable copy. Applies only to the sites
   on that list.
3. **A vague request: not solved.** Asking the request first is not enough. This one needs its own
   test, and it is the only one of the three that touches the inspection-authorization errors.

The architect's order: 1 first (free, largest measured gain), then 2, then a test for 3.

## A caution on the reading

"Found" is the quote check's word. A passage it did not find can still reach the answer through
the search model's own summary, which is why Q12's answers were right in 8 of 8 recorded runs with
no table found. What is lost is the check, not always the fact: the delivery says the quote is
unverified when the page in fact holds it.
