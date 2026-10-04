# Golden timing probe, rerun — pre-registration (2026-10-04)

The PR #152 review's item 4 add-on: rerun golden_q1, golden_q2
and golden_q3 through the pipeline on the owner's CORRECTED
lineup, with the spend guard repaired (PR #153, merged). This
document is committed before the first paid call; the measured
record is appended after the run, in the same file, and
committed again.

## The configuration (fixed before the run)

- Branch `arch/20261004-golden-timing-rerun`, cut from main
  at 7908985 — both review PRs merged (#152 at d311654,
  #153 at 7908985).
- Scenarios: golden_q1, golden_q2, golden_q3 — byte-copies of
  `evals/scenarios/golden/`, held in `/tmp/golden-q123/` so the
  sweep loads exactly the three (the loader does not recurse).
- Workflow `engineering-rnd` (the golden scenarios name no
  workflow of their own).
- Repeat 1, timeout 600 s (the scenarios' own timeout),
  max_calls 40 (the scenarios' own bound).
- Caps: `--max-spend 0.50` (one scenario-run),
  `--max-spend-sweep 1.50` (the invocation — 3 × $0.50, exact).
- Pins: the standing `.env` — the corrected lineup: triage and
  research google/gemini-3.8-flash, engineering
  thinkingmachines/inkling-small (the owner removed the
  `:exacto` suffix after the first reading), architecture
  xiaomi/mimo-v2.6-pro:exacto, escalation
  moonshotai/kimi-k3:exacto, judge
  qwen/qwen3-235b-a22b-2507:exacto, search perplexity/sonar,
  ranker qwen/qwen3-reranker-8b, premium unset; the
  owner-directed caps (plan 14000, escalation 13000, validate
  16000, judge 16000, search 8000/16000); provider order
  engineering:deepinfra/fp8, judge:deepinfra/fp8, fallbacks
  off.
- **Measurement fidelity (a departure from the first probe's
  invocation, recorded):** the shell still exports the OLD
  lineup (engineering qwen/qwen3-235b-a22b-2507, judge
  moonshotai/kimi-k2.5:exacto, premium
  openai/gpt-6.1-sol-pro:exacto, plan 78000, the old provider
  order), and the harness reads environment variables OVER
  `.env`. The invocation therefore removes the stale exports
  for its own process (`env -u ...`), so the `.env` is the
  source of truth. The owner's own runs need a fresh shell for
  the same reason.
- Preflight: run free, not skipped, BEFORE the paid run —
  measured **29 ok, 1 failing**: the engineering endpoint
  (DeepInfra | thinkingmachines/inkling-small-20260730, the
  catalogue's ONLY endpoint for the model) does not list
  `response_format`, which the harness sends on engineering
  calls. The pin serves (that check passed); removing the
  `:exacto` suffix changed nothing (same single endpoint). The
  sweep itself runs with `--skip-preflight` — the owner's
  recorded override — so the results header records
  `{ran: false, override: true}`. Runtime safety net, already
  shipped and tested: a 400 with `response_format` is logged,
  the parameter is dropped, and the call retried
  (`autornd/routing/openrouter.py:694-699`).
- The repaired spend guard (PR #153): on this lineup the
  worst-case table bounds every tier — triage/research
  google/gemini-3.8-flash $0.0766/call (per-request $0.0140),
  search perplexity/sonar $0.0226 ($0.0050), architecture
  $0.0129, engineering $0.0175, judge $0.0057, escalation
  $0.1832 — so the pre-call guard enforces the $0.50 per-run
  ceiling on bounded worst cases, not only on booked costs.
  (The first probe ran under the unrepaired guard, whose
  worst-case table printed "unknown (no rate)" for every tier.)

## The prediction (registered before the first paid call)

1. The results header records `{ran: false, override: true}`;
   the free preflight's findings (29 ok, 1 failing — the
   engineering endpoint's `response_format` declaration) are
   recorded in this document, not in the header.
2. Engineering calls may log the 400-with-response_format
   warning and retry without it; a retried call is not a
   failure. An engineering call that fails after the retry is
   a falsifier.
3. Every unit is bounded: 600 s, 40 calls, max_iterations 5,
   and the deliberation watchdog (Ruling D38) ends a hung run
   by its own terminal.
4. Total spend lands under the $1.50 sweep cap. The first
   probe (the old lineup) spent $0.1064 of $1.50; the
   corrected lineup's tiers are catalogue-priced and bounded
   by the repaired guard.
5. Pace: the plan node (architecture, mimo-v2.6-pro:exacto —
   unchanged since the first probe) is expected at the first
   probe's pace (126–293 s per plan iteration); the
   engineering tier (inkling-small, a small model) is expected
   faster than the old engineering pin; the judge
   (qwen3-235b-a22b-2507:exacto) is new and unmeasured — its
   validating-call pace is the open question. Whether one
   iteration plus one judging round fits the 600 s deadline is
   the measurement the probe exists to make.
6. `PLAN_MAX_TOKENS=14000` binds: the first probe's Q3 plan
   recorded 18,069 completion tokens; under the standing cap a
   Q3-scale plan is truncated at 14,000 tokens.
7. What this probe does NOT predict: whether units ship. The
   first probe shipped 0/3 on pace; the corrected lineup's
   pace is the measurement.

Falsifiers: a second preflight finding (beyond the known
declaration gap); a unit past its 600 s bound or its 40 calls;
a sweep spend above $1.50; a spend-guard refusal; an
engineering call that fails after the 400-retry.

## Caveats carried from the first probe

- The probe runs with an empty knowledge store (no ingested
  collection exists in this environment), so the context node
  takes its no-documentation scoping path and **no search-tier
  call is made** — the 0/3-or-better result reflects pace and
  the pipeline's own bounds, not answer quality.
- The timing figures are unaffected by the store: the plan and
  judge nodes' pace is a property of the servings.

## The measured record (2026-10-04, after the run)

The results file is `evals/results/probe-20261004-golden-q123-rerun.jsonl`
(gitignored, like every local run output). The header records
the corrected lineup exactly — engineering
`thinkingmachines/inkling-small`, judge
`qwen/qwen3-235b-a22b-2507:exacto`, premium absent, the
`.env` provider order, and `"preflight": {"ran": false,
"override": true}` — prediction 1 **HELD**.

The sweep, derived from the results file: **0/3 units passed,
0/3 shipped; 13 calls; 1111.3 s; $0.0720 booked of the
$1.5000 sweep cap** (the terminal's sweep-budget line
printed `sweep budget: $0.0720 of $1.5000`). `score_trace`'s
reading of the same file, verbatim:

```
Q1   FAIL (no answer)   blocked    no answer              items[] 164.083s/300s $0.0163/0.5 risk=low sprawl=None scope_out=None
Q2   FAIL (no answer)   blocked    no answer              items[] 347.592s/300s $0.0224/0.5 risk=critical sprawl=None scope_out=None
Q3   FAIL (no answer)   blocked    no answer              items[] 599.606s/300s $0.0333/0.5 risk=medium sprawl=None scope_out=None

0/3 PASS · 0/3 shipped · median sprawl None · total $0.072 · key v1
```

Booked spend by tier: architecture $0.0380, research $0.0189,
triage $0.0151, engineering $0.00, judge $0.00. No search-tier
call was made — the empty-knowledge-store caveat held.

### Per-unit records

- **golden_q1** — blocked, 164.083 s, 4 calls, $0.0163 booked.
  The plan node (architecture, `mimo-v2.6-pro:exacto`) took
  144.464 s / 6,497 completion tokens in one call. The
  feasibility node's engineering call was dispatched and failed
  with a 429 (`error_status`); its worst-case reservation
  $0.024359 was booked as unreconciled liability.
- **golden_q2** — blocked, 347.592 s, 4 calls, $0.0224 booked.
  Plan node 328.301 s / 13,678 completion tokens, one call.
  Engineering call dispatched, 429, liability $0.026227.
- **golden_q3** — blocked, 599.606 s, 5 calls, $0.0333 booked.
  Plan node 444.382 s / **21,377 completion tokens across TWO
  architecture calls**: the first call ran past the 14,000-token
  cap and was truncated mid-JSON — the client logged `JSON parse
  failed (attempt 1/3) for architecture: Unterminated string
  starting at: line 3 column 11 (char 29)` and retried. The
  feasibility node's engineering call was cancelled by the
  deliberation watchdog at 599.6048 s (`fired: true`,
  `rule: cancelled`, `node: feasibility`, `tier: engineering` —
  the 429 retries burned the remaining budget); liability
  $0.023837 (`kind: cancelled`). The watchdog's own billing
  note, verbatim: *"unknown — the watchdog stopped the wait;
  whether the provider stops billing an abandoned call is not
  observable from the harness."*

Every engineering failure carried the provider's own sentence:
*"thinkingmachines/inkling-small is temporarily rate-limited
upstream. Please retry shortly, or add your own key to
accumulate your rate limits:
https://openrouter.ai/settings/integrations"*

### Predictions vs measured

1. **HELD** — the header records `{ran: false, override: true}`.
2. **NOT EXERCISED** — no 400 occurred. Every engineering call
   failed on an upstream 429 before parameter acceptance was
   tested, so the 400-retry safety net was never needed.
3. **HELD** — 164.083 / 347.592 / 599.606 s (all ≤ 600),
   4 / 4 / 5 calls (≤ 40), and the watchdog ended Q3 by its
   own terminal at 599.6048 s.
4. **HELD** — $0.0720 booked of $1.50; $0.1464 including the
   three failed dispatches' liability ($0.024359 + $0.026227 +
   $0.023837 = $0.074423).
5. **PARTIALLY MEASURED** — the plan node (architecture, the
   unchanged serving) ran 144.5 / 328.3 / 444.4 s, slower than
   the first probe's 126.0 / 293.1 / 282.5 s because the
   14,000 cap now truncates a Q3-scale plan mid-JSON and forces
   a second call (see 6). The engineering and judge tiers are
   **NOT MEASURED** — no engineering call completed, so no
   implementation was produced and the judge never ran. The
   pace question the probe exists to make is still open.
6. **CONFIRMED — stronger than predicted.** `PLAN_MAX_TOKENS=14000`
   binds per call, measurably: Q3's plan call was truncated at
   the cap mid-JSON (unterminated-string parse failure, client
   retried), and the plan node finished across two calls
   totalling 21,377 completion tokens in 444.4 s, against the
   first probe's single-call 18,069 tokens / 282.5 s under the
   old 78,000 cap. A Q3-scale plan wants ~1.5–2× the standing
   cap.
7. **MEASURED 0/3** — every unit blocked: Q1 and Q2 stopped on
   the engineering 429, Q3 on the watchdog waiting on the same
   429.

Falsifiers: none fired — no second preflight finding, no unit
past its 600 s or 40-call bound, sweep spend $0.0720 < $1.50,
no spend-guard refusal, and no engineering call failed after the
400-retry (no 400 occurred at all).

### Findings (owner-visible)

- **F1 — the corrected engineering pin is upstream-rate-limited
  under the shared key.** Every engineering call (the feasibility
  node of all three units) was dispatched and failed with a 429.
  The client retried per its backoff; Q3's feasibility call
  spent the remaining budget in retries until the watchdog
  cancelled it. The engineering tier's pace — and with it the
  judge's — is still unmeasured, and the response_format
  question is still unanswered live: no engineering call got
  past the 429 to test the parameter path.
- **F2 — `PLAN_MAX_TOKENS=14000` binds per call and truncates a
  Q3-scale plan mid-JSON** (see 6). The plan node survives via
  the client's parse-retry, but pays a second call and ~160 s.
  The cap is ~2× too small for Q3-scale plans — the owner's
  line (G-3).
- **F3 — the repaired spend guard proved itself live on a paid
  run.** The worst-case line printed bounded for every tier
  (`triage $0.0614, research $0.0614, search $0.0160,
  architecture $0.0122, engineering $0.0168, judge $0.0056,
  escalation $0.1820`) where the first probe printed "unknown
  (no rate)" for every tier; and the three failed-after-dispatch
  engineering calls booked their reservations as unreconciled
  liability ($0.0744) — the D45 liability path, exercised for
  the first time on a live run.
- **F4 — the stale-exports discovery** (in the
  pre-registration): the shell exports the old lineup over the
  owner's `.env`; the owner's own runs need a fresh shell.

### Departures

- **D1** — the pre-registration commit (4c837ea) passed its
  message double-quoted through the shell, so the dollar figures
  were shell-expanded: `$0.50` read as `bash.50` and `$1.50` as
  `.50` — convention 26's exact warned failure. The document
  itself carries the correct figures; the mangling is recorded
  here rather than rewritten (no history rewrite). Every other
  commit on the branch used `git commit -F /tmp/msg*.txt`.
- **D2** — the invocation removed the shell's stale exports
  (`env -u ...`) so the `.env` is the source of truth — recorded
  in the pre-registration as a measurement-fidelity departure
  from the first probe's invocation.
- **D3** — the probe did not answer the engineering/judge pace
  question (the 429s) — the measurement it existed to make is
  still open.
- **D4** — the sweep's worst-case line and the pre-registration's
  free table print different figures for the same tiers
  (triage/research $0.0614 vs $0.0766, architecture $0.0122 vs
  $0.0129, engineering $0.0168 vs $0.0175, judge $0.0056 vs
  $0.0057, escalation $0.1820 vs $0.1832, search $0.0160 vs
  $0.0226): the two instruments measure different sides of the
  same call. The sweep CLI's line is completion-side only
  (`max_tokens × completion rate` — its own docstring says so);
  the tier-3 preflight's arm-E table is the full guard formula
  (the largest prompt's bytes plus the chat-template allowance at
  the prompt rate, the cap at the completion rate, and the
  per-request charge). Both bounded every tier, which is the
  property the repair exists for; each figure is quoted where it
  was printed.

### Where this leaves the owner

The re-measurement's other parts are done: the guard bounds
every tier (F3), the 14,000 cap is confirmed binding (F2), and
the liability path is proven live. The open question is the
engineering tier itself. Options: **(a)** retry the probe later
— the 429 is "temporary" per the provider; **(b)** add the
owner's own key (G-1: through the terminal into `.env` only) to
accumulate rate limits; **(c)** pick a different engineering
model/endpoint (G-2 pin ratification / G-3 `.env`); **(d)**
accept — the pace question waits. The same 429 would hit any
paid tier-3 arm-E unit, so the tier-3 experiment's gate 1 (the
five `TIER3_ARM_*` pins plus `TIER3_SERVINGS_RATIFIED` at
fingerprint `2d48223a86e0`) stays pending the owner until the
engineering tier clears or the owner acts.

## The re-run — pre-registration (2026-10-04, second sample)

The owner's directive: "try again with new env i just
updated". The owner edited `.env` (G-3 — the edit is the
owner's; its secret contents are neither printed nor
inspected). Two edits this window, both measured before any
paid call:

1. The first edit raised the caps (the harness read plan
   500000, escalation 50000, judge 55000, validate 32000,
   search 55000/56000 — was 14000/13000/16000/16000/8000/
   16000). Measured effect: the guard's worst case per
   engineering call rose to $0.6000 and escalation to
   $0.7000 — both above the probe's registered $0.50
   per-run cap, so the guard would have refused every
   engineering call before dispatch. The conflict was put to
   the owner as a blocking question before any paid call
   (free checks first).
2. The owner's second edit set the plan cap to 125000 ("I
   changed to 125k this lineup is prime now"). Measured:
   plan 125000, escalation 50000, judge 55000, validate
   32000, search 55000/56000; worst cases triage/research
   $0.0614, search $0.0560, architecture $0.1087,
   engineering $0.1500, judge $0.0192, escalation $0.7000.
   Every call this probe makes now fits the $0.50 per-run
   cap. The escalation tier's worst case ($0.7000) still
   exceeds it — the CLI prints its standing warning — but
   this probe makes no escalation call (both prior runs'
   units blocked at the feasibility node), so no refusal
   occurs on it.

The lineup is unchanged: fingerprint `2d48223a86e0`, the
same arm-E map, the same provider order, and the same one
genuine harness-preflight finding (the engineering
endpoint's `response_format` declaration). If the owner's
edit rotated the key — the provider's own advice for the
429 — the re-run measures whether the 429 clears; the key
is the owner's and is neither printed nor inspected.

Configuration (identical to the first run except where
named): this branch; scenarios `/tmp/golden-q123/`
(byte-copies); workflow `engineering-rnd`; repeat 1;
timeout 600 s; max_calls 40; `--max-spend 0.50`,
`--max-spend-sweep 1.50`; `--skip-preflight` (the same
known finding — the owner's recorded override; the header
records `{ran: false, override: true}`); the same `env -u`
invocation (the shell's stale exports still stand over
`.env`); a NEW results file,
`evals/results/probe-20261004-golden-q123-rerun2.jsonl`.
This is a second sample, never a confirmation (convention
27): the plan node regenerates its plan between runs, so
this run measures a different contract.

### The prediction (registered before the first paid call of the re-run)

1. The results header records `{ran: false, override:
   true}`.
2. The 14,000-cap truncation does NOT repeat: Q3's plan
   needed 21,377 tokens and the plan cap is now 125,000,
   so Q3's plan completes in one call — no mid-JSON
   truncation, no parse-retry.
3. The engineering 429 either clears (the owner's edit
   rotated the key — then the feasibility node completes,
   an implementation ships, the judge's validating-call
   pace is measured, and the pace question the probe exists
   for is answered) or repeats (then the record repeats the
   first run's shape: 0/3 blocked on the upstream 429 — a
   measurement of the serving, not of the harness).
4. Every unit is bounded: 600 s, 40 calls, the watchdog's
   own terminal.
5. Total spend lands under the $1.50 sweep cap, and no call
   the probe makes is refused by the guard (the largest
   worst case it can make is engineering at $0.1500, under
   the $0.50 per-run cap).
6. What this run does NOT predict: whether units ship. The
   pace is the measurement.

Falsifiers: a second preflight finding beyond the known
declaration gap; a unit past its 600 s or 40-call bound;
sweep spend above $1.50; a spend-guard refusal on a call
the probe makes; an engineering call that fails for a
reason other than the upstream 429 (e.g., a 400 the retry
does not clear).

Caveat: the same empty knowledge store — no search-tier
call; the timing figures are unaffected by the store. The
re-run's measured record is appended below after the run,
in this same file, and committed again.

### The re-run — measured record (2026-10-04, after the run)

The results file (gitignored, like every local run
output): `evals/results/probe-20261004-golden-q123-rerun2.jsonl`.
The header records the same lineup and
`"preflight": {"ran": false, "override": true}` —
prediction 1 **HELD**. The sweep: **0/3 units passed,
0/3 shipped; 15 calls; 1546.7 s; $0.0945 booked of
the $1.5000 sweep cap** (the terminal's sweep-budget
line printed `sweep budget: $0.0945 of $1.5000`; the
sweep CLI exited 1 — units ended blocked, not a
crash). `score_trace`'s reading, verbatim:

```
Q1   FAIL (no answer)   blocked    no answer              items[] 599.604s/300s $0.023/0.5 risk=medium sprawl=None scope_out=None
Q2   FAIL (no answer)   blocked    no answer              items[] 539.651s/300s $0.0354/0.5 risk=critical sprawl=None scope_out=None
Q3   FAIL (no answer)   blocked    no answer              items[] 407.399s/300s $0.0361/0.5 risk=medium sprawl=None scope_out=None

0/3 PASS · 0/3 shipped · median sprawl None · total $0.0945 · key v1
```

Booked spend by tier: architecture $0.0438, research
$0.0190, triage $0.0175, engineering $0.0142. No
search-tier call (the empty-store caveat held); no
judge call (no implementation was agreed in any run).

Per-unit records:

- **golden_q1** — blocked, 599.604 s, 4 calls, $0.0230
  booked. The plan node completed in ONE architecture
  call: 312.8 s, 15,444 completion tokens — above the
  old 14,000 cap, so it would have truncated under the
  first run's cap; at 125,000 it completed untruncated.
  The feasibility node's engineering call was dispatched
  and burned 275.563 s in 429 retries until the
  watchdog cancelled it at 599.6033 s (`fired: true`,
  `rule: cancelled`, `node: feasibility`, `tier:
  engineering`); liability $0.024182 (`kind:
  cancelled`).
- **golden_q2** — blocked, 539.651 s, 6 calls, $0.0354
  booked, **no failed dispatch**. The plan node
  completed in one call: 365.464 s, 16,100 completion
  tokens. The feasibility node's engineering calls
  **COMPLETED** — 161.435 s, 2 calls, 5,420 completion
  tokens, $0.0103 booked — the first completed
  engineering calls in any run; the pipeline advanced
  to the implement node, where the watchdog ended the
  run by its own terminal (`fired: true`, `rule:
  not_started`, `node: implement`, `tier:
  engineering`): *"this run's engineering pace is
  161.435s and only 59.949s of the 600s budget
  remain"* — the pace cannot fit the remaining budget.
- **golden_q3** — blocked, 407.399 s, 5 calls, $0.0361
  booked. The plan node completed in one call: 320.066
  s, 16,759 completion tokens. The feasibility node's
  engineering call completed (60.434 s, 1 call, 1,843
  completion tokens, $0.0039); the implement node's
  engineering call was dispatched and failed with the
  429 after the client's 3 retries (`error_status`;
  its worst-case reservation $0.156963 booked as
  liability — the reservation is larger now because the
  125,000 cap raised the worst case).

Every engineering failure carried the provider's own
sentence: *"thinkingmachines/inkling-small is
temporarily rate-limited upstream. Please retry shortly,
or add your own key to accumulate your rate limits:
https://openrouter.ai/settings/integrations"*

Predictions vs measured:

1. **HELD** — the header records `{ran: false,
   override: true}`.
2. **HELD** — the truncation does not repeat: every
   plan completed in ONE architecture call (15,444 /
   16,100 / 16,759 completion tokens — all above the
   old 14,000 cap, all under the 125,000 cap; no
   mid-JSON truncation, no parse-retry).
3. **MEASURED — the 429 REPEATS, but intermittently.**
   The owner's edit did not clear it (the same upstream
   sentence on every failure). It is not absolute: Q2's
   feasibility engineering calls completed (161.435 s,
   $0.0103) and Q3's feasibility completed (60.434 s,
   $0.0039), while Q1's feasibility burned 275.6 s in
   retries and Q3's implement failed after the 3
   retries. The provider's upstream capacity on
   inkling-small fluctuates; the shared key's
   engineering serving is unreliable call-to-call.
4. **HELD** — 599.604 / 539.651 / 407.399 s (all
   ≤ 600), 4 / 6 / 5 calls (≤ 40), and the watchdog
   ended Q1 and Q2 by its own terminal.
5. **HELD** — $0.0945 booked of $1.50; no spend-guard
   refusal (the largest worst case the probe made was
   engineering at $0.1500, under the $0.50 per-run
   cap); total liability $0.181145 (Q1 $0.024182 + Q3
   $0.156963), total exposure $0.2757.
6. **MEASURED 0/3** — but the pipeline advanced further
   than either prior run: Q2 completed the feasibility
   node (the first completed engineering calls in any
   run) and reached implement before the watchdog's pace
   arithmetic ended the run.

Findings (owner-visible):

- **F1 — the engineering pace is measured for the
  first time, and it answers the first probe's open
  question: no.** The feasibility node completed in
  161.435 s (2 calls, ~80 s each, 5,420 completion
  tokens, $0.0103). At that pace the 600 s deadline
  cannot fit: the plan node alone ran 312.8–365.5 s,
  and the watchdog's arithmetic (pace 161.435 s vs
  59.949 s remaining) ended Q2 at implement. Even with
  perfect availability, plan + feasibility + implement
  alone exceed the 600 s deadline on this lineup before
  any judging round.
- **F2 — the 429 is intermittent, not absolute** (see
  3): some calls get through, some don't. The owner's
  edit did not clear it (whether the owner rotated the
  key is the owner's; the failure sentence is the
  provider's upstream-capacity note, and it recurred).
- **F3 — the 125,000 cap fixed the truncation** (see
  2): every plan completed in one call, all three above
  the old 14,000 cap.
- **F4 — the guard's liability path booked both failure
  classes live**: a watchdog-cancelled dispatch (Q1,
  $0.024182) and a post-retry 429 dispatch (Q3,
  $0.156963 — the larger reservation the 125,000 cap
  now produces).

Falsifiers: none fired — no second preflight finding,
no unit past its 600 s or 40-call bound, sweep spend
$0.0945 < $1.50, no spend-guard refusal, and no 400
(every failure was a 429).

Where this leaves the owner: the re-run measured the
pace (F1) and the availability (F2). The engineering
serving is both intermittent AND slow (161 s per
feasibility node); the 600 s deadline is the binding
constraint even when the serving is available. The
judge's pace remains unmeasured (no implementation was
agreed in any run). Options: **(a)** wait and retry
later (the 429 is "temporary" per the provider, but
the pace finding F1 stands regardless); **(b)** pick a
different engineering model/endpoint (G-2 pin
ratification / G-3 `.env`) — one whose per-call pace
fits the 600 s deadline alongside the ~320–365 s plan
node; **(c)** raise the per-scenario timeout (the
owner's line — the scenarios' own bound is 600 s);
**(d)** accept. The tier-3 experiment's gate 1 stays
pending, and no paid tier-3 arm-E unit can start until
the engineering tier both serves reliably and fits the
deadline.
