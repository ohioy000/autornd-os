# Week 1's removals and repairs (2026-11-16)

The owner ruled on thirteen items on 2026-11-16 ("yes to all"): eight things to take out and
five open items on the user's path. This is what was done. No paid call was made.

## The point

- **There is one lookup now, one workflow of its kind, and four switches, all live.** Nothing
  ships in shadow and no lookup setting is switched off waiting.
- **About 2,400 lines came out and about 500 went in.** The suite is 1993 tests in 90 files
  (1992 passed, 1 skipped), network guard 0. It was 2075 in 91.
- **No answer changes.** Everything removed was either switched off, recorded only, or never
  reached. The three repairs change what the server reports, not what a run concludes.
- **One correction to what the owner was told.** See "A correction" below.

## Taken out

| | What | Why, as ruled |
|---|---|---|
| A | The second request for documents (`lookup_documents_ask_again`) | Fired in 13 of 144 lookups and gained nothing |
| B | The lookup that asked the search model for an answer and its quotes, its second round, and `lookup_reads_documents` | 141 of 144 against 144 of 144, read blind; one lookup is easier to trust |
| C | `lookup_withhold_unverified` and its caution | An unverified answer was right three times in four |
| D | `workflows/answer-and-recompute-claims.yaml`, its five nodes' code and its 26 tests | Measured twice; it cannot supply a sentence the lookup never found |
| E–H | The switches `chunk_helps`, `finding_answers`, `hard_request`, `ask_covered`, and the code only they used | In shadow; nothing acted on them |
| I | Episodic memory: the module, the `/api/episodes` endpoint, the save at the end of a run | No episode was ever saved, and no phase read one |

The tests of the old lookup that were really tests of the fetch, the quote check, the store and
the list of refusing sites were kept and moved onto the documents lookup. The tests of the old
lookup's own behaviour went with it.

## Repaired

| | What a user met | The repair |
|---|---|---|
| J | A run in flight when the server stopped read as running for ever | At start, each such run ends `blocked` with "The server stopped while this run was in flight… Submit it again." Right for one server process on its database; the README says to run one |
| L | Thirteen settings were named as changeable at runtime and the endpoint took five | The list is the five. A call naming another gets 400 with the five named. A test holds the two lists together |
| M | Health did not list the recompute and decision tiers | Both are listed when set, so a wrong model there shows as `degraded` at start |
| K | Sites learned as refusing are shared by every run in the process | Left as it is, by the ruling, and said in the README |

Found while doing this, and repaired: **an `.env` that still names one of the three removed
lookup settings would have stopped the server from starting,** as any unknown name does. Those
three names are now dropped with a warning that says to delete them. Any other unknown name is
still refused.

## A correction

The list put to the owner said `finding_answers` "depends on saved episodes, and none is ever
saved". That was wrong. It read passages kept in the knowledge store by earlier lookups, which
are saved. The switch was still in shadow and nothing acted on it, which is the ground the other
three shadow switches were removed on, so the removal stands on that. The plain reuse of a
stored passage that restates the question (`REUSE_DISTANCE`) is untouched.

## What a reader of the record should know

- **A run's `sources` record no longer has `round` or `withheld`.** Each document's `request`
  is always 1. Traces from before this change keep their old shape.
- **The `episodes` table is no longer created.** An existing database keeps its empty table;
  nothing reads it. There is no migration tool, so it is left.
- **`tier_when`, the workflow feature `hard_request` was meant for, is still in the graph
  code.** No shipped workflow uses it. It is a general feature with its own tests and was not
  on the list.
- **`quote_found` still carries the loosenings written for a model's quotes** (tables, marks,
  closing punctuation). With pages' own words they rarely matter. Not on the list; left.
- **`CLAUDE.md` had one stale fact fixed in place:** the API entry point no longer owns
  episodic memory.

## Proof

Each new guard was broken once and its test failed: the sweep's filter, the sweep's status,
the settings list, the refusal's wording, the two health tiers, the retired names, the fetch
bound, the refusing-site skip, and the request switch's list. The full suite was run before
and after.
