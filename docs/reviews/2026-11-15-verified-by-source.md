# What was verified, said beside the answer: three of the owner's rulings (2026-11-15)

The professional baseline (`docs/reviews/2026-11-15-professional-baseline.md`) found 45 of 45
answers right and a caution on 38 of them. The owner ruled on 2026-11-15 to build all three
remedies. All three are in this change, each proven on recorded runs before it shipped.

## 1. Say what was verified

- **What changed.** The delivery has a new list, `confirmations`. When every number an ask's
  answer states stands in a passage found on its page, the delivery says: "The figures this
  answer gives for ask 1 stand in a passage found on its page." The dashboard shows it with a
  tick, above the cautions.
- **The vote's cautions for such an ask are dropped:** that it compared nothing, reached no
  majority, could not compare, or worded the ask differently. A found passage has already
  settled what those say was left open.
- **The rule, strict on purpose** (`_backed` in `autornd/api/routes.py`). It reads the answer's
  typed results and the quoted text, never the answer's prose. A number must be in a found
  passage as a whole number, not as part of a longer one. A single digit counts only with its
  word beside it ("1" with "year"), because "5" is on every page. An answer that states no
  number is not backed. A passage `quote_answers` judged beside the point backs nothing.
- **What stays.** An ask that is not backed keeps every caution. The cautions about quotes are
  not changed. The stored rows are not changed; this is the delivery only.

## 2. A found passage outranks the vote

- **What changed.** When the vote disagrees on an ask that is backed, the delivery no longer
  flags the answer. The ask is listed in the vote's `overruled_by_source`, and a confirmation
  says the passage was taken over the vote. What the vote itself found stays in
  `flagged_by_vote` and `disagreements`.
- **An honest note.** The false alarm that prompted this (the radiation question, two samples
  saying 2 rems against the rule's 15) is **not** cleared by it on the record: in that run the
  one found passage had been judged beside the point, so nothing backed the ask. The rule is
  right and tested; it did not fire on the 133 recorded answers replayed.

## 3. Three more of the search model's marks

The quote check now also drops the tildes of a subscript ("O~3~"), a backslash before a mark,
and a list mark at the start of a line ("1. ", "- "). Words are still compared one for one.

## What proves it

| Replay, free | Before | Now |
|---|---|---|
| Professional baseline, 45 right answers: cautions | 57 | 48 |
| …answers with no caution | 7 | 15 |
| …answers that now carry a confirmation | – | 34 |
| Yesterday's 68 rule-question answers: cautions | 112 | 110 |
| Yesterday's 20 inspection-authorization answers, 5 of them wrong: asks backed | – | 0 |
| All recorded quotes against their live pages: found before, still found | 485 | 485 |
| …not found before, found now | 26 | 29 |

- **No wrong figure was backed.** Of the recorded answers that were wrong or failed their
  screen, none has the wrong ask backed. One failed its screen with ask 1 backed; read by hand,
  that answer's figures are the rule's, and the screen misread it.
- `docs/probes/verified_by_source_replay.py` re-derives the first five rows from the traces.
- **Tests:** 16 new, with seven cases of what must not back an ask. Five lines break-proved.
  2016 passed, 1 skipped; 2017 tests in 90 files.

## What it does not do

- **It is a smaller gain than hoped.** 30 of the 45 right answers still carry a caution, mostly
  about quotes: some passage not found, a page not read, a passage beside the point. Those are
  true statements about the lookup and say little about the answer. They are the next thing to
  look at, and they need the owner's ruling.
- Answers whose values are words, not numbers, cannot be backed this way.
