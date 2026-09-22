# Pre-registration — B17-R1's prohibition branch on live input

**This scenario is engineered to reach the branch.** `gen_house_style_prohibition`
was written for one purpose: to put a prohibition-shaped success criterion in
front of the coverage check on live planner output, by naming a banned word list
in the objective explicitly enough that the planner restates it as a criterion.
**A pass is therefore evidence that the branch works on live input, and is not
evidence that a content corpus naturally produces such criteria.** Those are two
different claims and this run can only speak to the first. B14's two
demonstrations are the measurement of the second, and **neither of them emitted a
prohibition criterion at all** — which is precisely why this scenario exists.

Committed **before any spend**, per protocol. The commit that carries this file is
the evidence that the predictions preceded the result. **Spend: NOT YET
AUTHORISED.** `ARCH-20260922-027` proposes the run at a **$0.25** cap; the owner's
word is a separate act and this file does not assume it.

---

## Why the branch has never been reached

B17-R1 (§29) ruled that **shape selects the test**:

| shape | test |
|---|---|
| `presence` | term overlap, unchanged — at least 50% of the criterion's significant terms appear in the work |
| `prohibition` | **inverts** — the criterion's own forbidden tokens become the test, and it passes iff none appear |
| `form` | **abstains** — never fails the fold, and never silently |

The form branch is **demonstrated live, twice** (§34: a citation-fields criterion
abstained in both units and did not fail the fold, where its `-010` equivalent
scored 0.37 and killed the run).

**The prohibition branch — the headline repair — has survived two paid runs
without ever being exercised.** Neither regenerated plan emitted a criterion of
that shape, so the inversion had nothing to act on and remains proved by fixtures
alone. B16 is the reason: plan criteria are rewritten from scratch on every run,
so a third draw from `gen_marketing_claims` does not reliably reach it.

## The exact wording, so it can be checked against what the planner emits

The scenario's objective names the prohibition as:

> The house style bans four words and phrases outright, and the finished copy
> must not contain any of them: "leverage", "seamless", "robust", and "in
> today's fast-paced world".

The criterion this is **predicted** to produce, stated now so `-027` can compare
it against what actually appeared:

> *avoids the banned words ('leverage', 'seamless', 'robust', 'in today's
> fast-paced world')*

**Provenance of that wording.** It is taken verbatim from B17's own row in
`HANDOVER.md` §4.2 — it is the criterion that opened the bug, recorded in the
ledger on 2026-09-21. **It was quoted from the record, not reverse-engineered
from the classifier.** See "Disclosure" below, which is the part of this that is
not clean.

## Registered predictions

Four, numbered. `-027` reports each held or refuted with its observed value, and
**no prediction is added, dropped or reworded after a result is seen.**

**(a) The planner emits at least one prohibition-shaped success criterion.**
Observable in `plan.success_criteria` in the unit record. Refuted if no criterion
quotes a forbidden token list. If (a) is refuted, B17 stays OPEN and the finding
is about the planner, not the check.

**(b) Coverage classifies that criterion as `prohibition` — not `presence`, not
`form`.** Observable in the per-criterion shape table `ARCH-20260922-008` writes
into the unit record. **A classifier that reaches the right shape while extracting
the wrong tokens is not a pass**, so `-027` quotes the extracted tokens as well as
the criterion.

**(c) On a compliant draft, coverage passes that criterion.** This is the
headline: the inversion is what turns a compliant draft's 40% into a pass. This is
the prediction the run is bought to test.

**(d) A draft containing a banned token fails that criterion — NOT REACHABLE BY
THIS SCENARIO, and not promised.** Stated now rather than after the fact, as
`ARCH-20260922-026` requires. The scenario instructs the implementer to produce
compliant copy, so the draft it yields should contain no banned token; reaching
(d) would require a draft that violates its own brief, which cannot be ordered
reliably and would jeopardise (c) in the same unit. **(d) is exercised by fixtures
only and remains so after this run.** The consequence is stated plainly in
`-027`'s closing condition: **if the fail direction is not reached, B17 is not
fully closed**, and the honest outcome is a second scenario proposed rather than
victory declared.

## What would make this run worthless

Recorded in advance so it cannot be rationalised afterwards:

- **(a) refuted.** No prohibition criterion emitted despite an objective that
  names one explicitly. That is a finding about plan generation — and given B16,
  a single refutation is an anecdote, not a rate.
- **The run never reaches coverage.** A bound hit before the first coverage
  evaluation leaves every prediction unscorable. Both B14 units exhausted; this
  is the likeliest way to get nothing, and it is why `max_calls: 40` in the
  scenario is labelled a carried-over bound rather than a prediction of fit.
- **Coverage passes for the wrong reason.** If the criterion is classified
  `presence` and happens to score above 0.50 on term overlap, (c) would read as
  held while (b) is refuted. (b) is therefore reported before (c), and a pass on
  (c) without (b) is **not** a demonstration of the branch.

## Disclosure — the part of this that is not clean

`ARCH-20260922-026`'s second precondition says of `criteria_addressed`:
*"Do not read it to design around it — record the line only."* Its second question
asks whether reverse-engineering a scenario from a check's implementation violates
a standing rule in spirit.

**The executor had already read the classifier's structure before this command
existed.** During session orientation on 2026-09-22 it read the names and
locations of `_forbidden_tokens`, `_classify` and `_forbidden_present`
(`autornd/graph/checks.py:325,346,365`) as part of a general survey of the module.
The bodies of those functions were not read, and the banned list above comes from
the ledger rather than from the code. **But the constraint's own standard is
*"if you discover the answer first, the prediction is theatre"*, and a partial
prior read is disclosed here rather than left for someone to find.**

The owner should decide whether that disqualifies this executor from authoring
this registration. It is recorded in
`.orchestration/responses/ARCH-20260922-026.response.json` as an open question.

## Scope of the claim, restated

This run, if every prediction holds, licenses exactly one sentence:

> **On an objective engineered to produce one, the planner emitted a
> prohibition-shaped criterion, the coverage check classified it correctly,
> extracted the right forbidden tokens, and passed a compliant draft — n=1.**

It does not license *"B17 is fixed"*, *"the corpus produces prohibition
criteria"*, or any rate. Convention 23's n rules are about sweeps and this is a
branch demonstration; **n=1 is sufficient to show a branch fires and is
insufficient to show it fires reliably**, and it is labelled an anecdote in the
response.
