# Verdicts and schemas

Load when changing a verdict schema, a required field, or how model output is coerced.
Source: `autornd/models/verdicts.py`.

## The principle

Every phase outputs a typed Pydantic model, not prose. The engine checks
`plan.ready`, `validate.green`, `review.ship` directly. **No English is parsed for
control flow, ever.**

## Two schema rules, both bought by traces that died

**1. Required fields are informationally independent fields.** A field the
verdict's own contract derives from another is normalized loudly and counted,
never demanded.

`green` on `ImplementVerdict` and `ValidateVerdict` is `Optional[bool] = None`,
resolved after construction (`verdicts.py:257,423`):

| input | result |
|---|---|
| absent + a `red_cause` | `False` |
| absent + no cause | `True` |
| `True` *with* a cause | coerced `False` — a false red costs an iteration, a false green ships unchecked work |
| `False` with no cause | **raise** — the one case that loses information |

`done` stays required, because nothing else in the verdict implies it.

Why: every prompt defines green and red_cause in the same breath, and models
reliably supply the cause and omit the flag. Measured twice, four blueprints
apart — in the second, two of four convergence traces died *after all three
retries were spent*, each attempt carrying the rejection text, each coming back
without the field. The wiring worked; the model did not comply.

**2. Shape variance that preserves information is coerced; variance that loses it
is rejected.** `evidence` on `ValidateVerdict` accepts a `{criterion: finding}`
object and folds it to `"key: value"` lines, **natural-sorted** so `criterion_2`
precedes `criterion_10` and a retry cannot change the answer
(`verdicts.py:346,358,388`). Non-text keys or values, or a part-string list, are
refused **with the accepted shapes named**.

`ReviewFinding` is the older instance: a bare string becomes a `detail`, and eight
aliases are accepted for that field (`verdicts.py:430,444`), after a reviewer
writing `issue` lost three entire reviews at the last phase with the findings in hand.

**Exhibits precede leniency.** No field is made tolerant on speculation — point at
the trace that died.

## A claim only a proof may allow

`ImplementVerdict.not_stated` (owner's ruling of 2026-11-21, option C) is the one way an answer may say
a document states none for an ask. It is typed like `blocked_on` and never read from the summary's
English, and it works only where the grounding holds a proof of absence for that ask
(`knowledge/absence.py`: code searched the full text of a page read in full for the words an answer
would be printed with, and found none of them). `blocked_on_unmet` takes the claims and the numbers of
the proven asks: a claim with no proof ends the run blocked, as a blocked ask does, and is counted
(`NOT_STATED_NO_PROOF`); a claim that names no ask is a note (`NOT_STATED_NO_ASK`). **Never accept
"none stated" on the model's word, and never widen what a proof says:** it is about one page as
fetched, and only as wide as the words listed for it.

## Every normalization is counted

`_normalisations` / `normalisations()` / `normalisations_by_kind()` /
`reset_normalisations()` (`verdicts.py:298-318`). A fix that hides its own trigger
stops anyone noticing when it is no longer needed. If you add a coercion, count it
and surface it in `normalised_by_kind`.

## Open vocabularies

`Domain` and `SpecialistRole` (`verdicts.py:56,72`) are **default vocabularies,
not limits**. Both subclass `str`, so legacy comparisons keep working, and
everything downstream keys on the normalised string from `normalise_key()` /
`domain_key()` / `role_key()` (`verdicts.py:24,34,44`).

This is a measurement, not a preference. With `Domain` enforced as a closed enum,
**nine of twelve subjects had no fitting value and eight came back "hardware"** —
civil engineering as hardware, buffer chemistry as documentation, a latency budget
as firmware. A closed list does not make a model refuse honestly; it makes it pick
the least-wrong label and sound certain. Staffing had the same defect: asked to
review a records retention schedule, a closed roster returned seven engineers.

Profiles declare their own `domains:` and `roles:`; an undeclared role resolves to
a **synthesized generalist** rather than raising.

**Never widen an enum to fix a classification problem.** Add it to a profile.
