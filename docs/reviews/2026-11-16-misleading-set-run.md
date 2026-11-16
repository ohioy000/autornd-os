# The three-arm run on the set where a summary misleads (2026-11-16)

Preregistered in `docs/preregistration-20261115-misleading-set-run.md` (#274), pushed before the
spend. Set `professional-misleading-1`, 12 questions with keys the owner signed, 12 answers a
question in each of three arms: `now` (the lookup that asks for an answer), `documents` (the
lookup that reads the documents, the default since #271) and `again` (the same, with the second
request for documents switched on).

## The point

- **Every arm was right almost every time.** `now` 141 of 144, `documents` 144 of 144, `again`
  141 of 144. The set built to separate the lookups did not.
- **Bar 1 missed, bar 2 met:** by the preregistered rule the default stands on cost and on
  quotes found, not on this set.
- **No wrong answer carried a "verified" line** (bar 3 met).
- **The second request does not earn its call** (bar 5 missed). It fired in 13 of 144 lookups
  and `again` was 3 answers behind `documents`. It stays off.
- **The two stale-page answers carried no caution.** Both are `now`, both gave the pre-2024
  BasicMed limits from the FAA's own advisory circular. Nothing in the text handed on shows the
  page is stale. This is the known limit, seen as predicted.
- **Cost:** '$5.03' in all against about '$5.60' planned. An answer cost '$0.0120' (`now`),
  '$0.0111' (`documents`), '$0.0118' (`again`).

## How it was read

Every delivered answer was read blind against its key by a Sonnet reader, one reader a question,
in packets without the arm (`docs/probes/blind_reading_packets.py`, seeds `misleading-wave1`
for shard 0 and `misleading-wave2` for shard 1). The codes were kept from the readers. The
architect read every answer not marked right, and spot-checked the rest against the key's
figure with a free check: every answer of wave 2 states its key figure. The verdicts were then
matched to their arms (`docs/probes/blind_reading_verdicts.py`).

Traces, byte-identical: `docs/traces/20261115T-misleading-{now,documents,again}-*`, the
results files and the phase rows of each shard database (`phases-shard-N.jsonl`, each citing
its database's sha256).

## The answers

| | `now` | `documents` | `again` |
|---|---|---|---|
| Right | **141** | **144** | **141** |
| Wrong | 2 (M1, M1) | 0 | 1 (M5) |
| Unclear | 0 | 0 | 1 (M11, no conclusion) |
| Ended blocked, no answer | 1 (M9) | 0 | 1 (M4) |
| Right answers with no caution | 120 of 141 | 77 of 144 | 75 of 141 |

The four answers that are not right:

| Arm | Question | What it said | "Verified" lines | Cautions |
|---|---|---|---|---|
| `now` | M1 BasicMed | 6,000 lb, 6 occupants, 5 passengers: the rule before 2024 | 0 | none |
| `now` | M1 BasicMed | the same, from AC 68-1A | 0 | none |
| `again` | M5 Part 135 rest | 12 hours, from the tier for duty over 14 hours | 0 | "12 hours is in none of the passages": **points at it** |
| `again` | M11 | no conclusion for either key item | 0 | two "two pages differ" |

## The bars

| Bar | Result |
|---|---|
| 1. `documents` right in at least 10 more of 144 than `now` | **Missed.** 3 more |
| 2. On no question `documents` worse than `now` by more than 2 of 12 | **Met.** It is worse on none |
| 3. No wrong answer carries a "verified" line | **Met.** 0 of 4 |
| 4. Half the wrong answers of `documents` carry a pointing caution; half its right ones carry none | **First half not testable:** `documents` had no wrong answer. **Second half met:** 77 of 144 carry none, 53 percent |
| 5. `again` right in at least 4 more than `documents`, at no more than 15 percent more an answer | **Missed.** 3 fewer |

By the preregistered rules: the default of step 2 stands on cost and quotes found; the
"verified" line stays; the second request stays off.

## The predictions

| Prediction | Result |
|---|---|
| 1. `now` right in 95 to 115, `documents` in 115 to 135; bar 1 met | **Wrong.** 141 and 144. The architect expected the misleading pages to catch the asking lookup far more often |
| 2. Bar 2 met | **Held** |
| 3. Bar 3 met | **Held** |
| 4. Bar 4's first half missed | **Not testable** on `documents`. In `now` both wrong answers carried no caution, as the prediction's reason said |
| 5. Bar 5 missed; the second request fires in fewer than one lookup in ten; `again` within 3 of `documents` | **Held.** 13 of 144, 9 percent; 3 behind |
| 6. M5 and M1 the questions most often wrong in `now` | **Half held.** M1 twice; M5 never in `now` |
| 7. M9 and M10 right at least 10 times of 12 in every arm | **Held.** M9 in `now` is 11 of 11 delivered |

## Read free off the record

- **First request for documents a miss:** 17 of 144 lookups in `documents`, 13 in `again`. All
  were the kind where pages were read and none held the pointer; never "no page read".
- **The second request's 3 fewer** are one wrong M5 paragraph, one answer with no conclusion
  and one run that ended blocked. None is shown to come from the second request itself.
- **Cautions are commoner with the documents lookup:** about half its right answers carry one,
  against one in seven for `now`. Most are the "two pages differ" check on long regulatory
  pages; its false cases on PDF line wraps and on one section fetched by two addresses are
  repaired in this pull request (see `docs/reviews/2026-11-16-user-path-audit.md`).

## What follows

- **The set is at the ceiling for every arm.** A further lookup change cannot show on it. With
  the other three professional sets near the ceiling too, that is the case for finishing rather
  than building.
- **`lookup_documents_ask_again`:** recommended for removal in week 1 of the handover's plan.
- **The stale page is the open limit.** Two answers in 432 went wrong on it, both in the arm
  that is no longer the default, and no check flagged them.

## Limits

- One blind reader a question; the architect re-read the four not-right answers and checked
  every other against its key figure for free, not by a second full reading.
- 12 questions. A difference of 3 in 144 is noise.
