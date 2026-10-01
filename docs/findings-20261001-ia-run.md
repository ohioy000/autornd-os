# Findings for the advisor: the IA ad-hoc run (2026-10-01)

The owner's question about FAA Inspection Authorization qualifications for
major alterations, put to the harness once at a $0.50 cap. The full
execution record is notebook section 93, and the trace is
`docs/traces/adhoc-20261001-ia-major-alterations.jsonl`.

**Outcome:** blocked by the watchdog after 1,126 s, 4 calls and $0.0545,
with no implementation.

## Why it failed, in four links

1. **Grounding came back empty, and the record does not say why.** The
   knowledge store was empty, so the context node fell back to scoping the
   request on the research tier. That tier's pinned provider was
   rate-limited upstream: two retries, both 429, then the call failed. The
   failure was caught and logged to stderr only. The unit record shows 0
   characters of grounding, no lookup, and `retries: 0`.
2. **The plan ran blind for 18 minutes.** Triage read critical risk. D36
   says an unknown is a blocker, and the executor's prompt asked that
   everything be verified against eCFR. One plan call took 1,097 s (61% of
   the 1,800 s budget) and 43,485 tokens. It produced a 28-row matrix with
   every row unverified, and none of the key figures (3 years, 2 years, 90
   days, 8 hours, March). It ended not ready, with five blockers, the first
   "no eCFR access". That is accurate: ecfr.gov redirects automated fetches
   to a bot block.
3. **D37 fired live for the first time.** One bundled lookup sent the five
   blockers as paragraphs, not questions, and one finding came back. What
   that finding said is not recorded.
4. **The watchdog refused the second plan pass,** correctly under D38/D40:
   the node's own pace was 1,096.651 s, and 673.898 s remained.

## The executor's error

The clause "say which items you could not verify against that text" was
the executor's addition, not the owner's question. It is the 094 pattern:
it invites the planner to block on verification.

## Questions for the advisor

1. **A failed scoping call is invisible in the run record.** Should the
   context record carry the scoping call's failure, and should retries and
   failed attempts be counted? Instrument repair, or a ruling?
2. **The re-grounding lookup's findings are not recorded.** R6 covered only
   the first grounding. Extend it to `reground_lookup`?
3. **One plan pass can take more than half the budget,** after which D40's
   node pace makes D37's second pass unaffordable by construction. Is that
   the intended interaction, or should the budget or the plan be bounded?
4. **The context record's `asked` is still rewritten in place** by the
   re-grounding lookup (093 note 2). When is it fixed?
5. **A killed process writes no unit record and no spend.** The companion
   logic run was lost this way. Should the record survive a killed process?
6. **Re-pinning the rate-limited research tier** is G-2, the owner's. Is
   evidence needed first?

## Suggested next test

Rerun with the owner's question verbatim (no verification clause), after
the research tier is healthy. Or give the harness the regulation text as a
profile corpus, as 094 did with cupline, so the test is closed-world. The
logic-circuit question also needs a rerun.
