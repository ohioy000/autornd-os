# Cost, accounting and budgets

Load for anything that makes, prices, retries or bounds a provider call.
Source: `autornd/routing/openrouter.py`, `autornd/config.py`.

## Accounting lives on the client, and nothing can escape it

`OpenRouterClient` holds `spend`, `calls`, `spend_by_function`,
`calls_by_function`, `providers_by_function`, `tokens_by_function`, plus optional
`call_ceiling` / `spend_ceiling` enforced **inside `_account()`**
(`openrouter.py:210-251`). Budgets are enforced there rather than by the caller so
a ceiling covers research lookups and reranking too. `PhaseRunner.total_cost` is a
*property* reading `client.spend` (`graph/adapter.py:83`).

**Rule: every request calls `_account()`. No exceptions, including test doubles.**
A free double once hid a real accounting bug — and hid it from the very tests meant
to prove one workflow was cheaper than another.

`BudgetExceeded` messages name the bound *and* the per-tier breakdown
(`openrouter.py:242,248`). Keep that: an instrument's report states what it
measured, and a reading that can be mistaken for a weaker claim is a defect in the
instrument.

**Do not swallow `BudgetExceeded`.** Six handlers on the research and rerank paths
once caught it, so an abort did not stop the run.

## No hardcoded prices or model names

Rates are learned from the provider catalogue at startup
(`openrouter.py:590,609,644`). Tiers ship empty (`config.py:26-40`) — AutoRnD is a
harness, not a model recommendation. `tests/test_docs.py` fails any PR that names
a model in code, config defaults, profiles, workflows or user-facing docs.

## Token budgets are settings, and each carries its measurement

Read the comment before changing the number (`config.py:57-80`):

- `plan_max_tokens` = 32768. The plan node ran at `Specialist.run`'s 16,384 default
  while every serving advertised a ceiling above 262,000; on hard requests it burned
  seven full-budget retries returning nothing. A ceiling is billed only when used,
  so headroom costs nothing on the runs that were already fine.
- `escalation_max_tokens` = 16384.
- The validator's cap: unbounded, it produced 15k output tokens for a green/red
  verdict, costing more than the implementation it checked. 3000 was too tight in
  the worst way — a reasoning model spent the whole budget thinking and emitted
  nothing, three times.
- `review_rework_attempts` = 2. Three of four traces ended blocked at review with
  the findings unread; exhaustion routes to the escalation autopsy rather than
  looping.

## Search is the expensive tier — the policy is deliberate

Search was **61% of a full workflow** and **98% of a grounding run**. The gate:

```
risk == low                  → 0 lookups, $0
no blocking gap marked       → 0 lookups, $0
otherwise                    → EXACTLY 1 bundled request carrying every gap
  medium                     → SEARCH_MAX_TOKENS (1500)
  high / critical            → SEARCH_MAX_TOKENS_CONSEQUENTIAL
store already answers a gap  → free (recall before search, distance ≤ 0.35)
MAX_LOOKUPS = 1
```

Measured effect: **$0.0999 → $0.0562 per workflow (−44%)** across 36 sectors.

One override: when the *plan's* success criteria demand verifiability, ONE bundled
lookup fires regardless of triage risk, at the medium-risk budget — detected free
and deterministically over the criteria text, after the plan exists.

## Three-state rerank probe

`_rerank_mode: None → "native" | "listwise" | "distance"`. Each strategy is probed
**at most once**, so a dead end stops costing calls forever after.

## Pinning the serving matters as much as the model

`openrouter_provider_order` (`config.py:41-47`). Empty means the provider decides,
which favours availability over reproducibility — and they are not the same: one
model id served by different providers produced shorter replies, a 30× price
difference and different risk classifications between two runs of one eval suite.
**A serving does not only run at a speed — it converges at a rate.** Pinning the
last unpinned tier is what closed this project's longest-running convergence bug,
moving iterations 8→2 and 4→1 while per-call latency barely moved.

Pins are the **owner's** to ratify. Propose with evidence; run experiments
env-prefixed. The executor never edits `.env`.

## ⚠️ Meter epoch

Cost accounting was broken before commit `b4cd89f`: research, context and rerank
calls bypassed it entirely. **Any cost figure predating it is understated
2.6×–295×. Never cite one — re-measure.**

## Changing per-run work re-derives the budgets

A change that alters how much work a run does re-derives the harness budgets **in
the same change**. And: an instrument reading is a reading, not a diagnosis — a
timeout, a zero score, a refused lookup and a 403 are facts about the apparatus
until something rules the apparatus out.
