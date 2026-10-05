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

## The third sample — pre-registration (2026-10-04)

The owner's directive: "rertry". The free checks
re-read before this registration: the configuration
is UNCHANGED from the second sample — the same
lineup (fingerprint `2d48223a86e0`, the same arm-E
map, the same provider order), plan cap 125000
(escalation 50000, judge 55000, validate 32000,
search 55000/56000), worst cases triage/research
$0.0614, search $0.0560, architecture $0.1087,
engineering $0.1500, judge $0.0192, escalation
$0.7000 (every call this probe makes fits the
$0.50 per-run cap; escalation's $0.7000 still
exceeds it but this probe makes no escalation
call), and the same one genuine harness-preflight
finding (the engineering endpoint's
`response_format` declaration). Configuration
identical to the second sample except the results
file: `evals/results/probe-20261004-golden-q123-rerun3.jsonl`.
A third sample, never a confirmation (convention
27).

What the second sample established (the prior
this one measures against): the 429 is
intermittent (Q2's and Q3's feasibility
engineering calls completed; Q1's feasibility and
Q3's implement did not), the engineering pace is
60.4–161.4 s per feasibility node (too slow for
the 600 s deadline against a 312.8–365.5 s plan
node), and the 125,000 cap lets every plan
complete in one call.

### The prediction (registered before the first paid call of the third sample)

1. The results header records `{ran: false,
   override: true}`.
2. Every plan completes in ONE architecture
   call (the 125,000 cap).
3. The 429 recurs on some engineering
   dispatches and clears on others (the
   intermittent pattern); whether any unit's full
   engineering sequence (feasibility + implement)
   completes is the measurement — the second
   sample's Q2 showed the sequence can start
   (feasibility completed) but the watchdog's
   pace arithmetic ended it at implement.
4. Every unit is bounded: 600 s, 40 calls, the
   watchdog's own terminal.
5. Total spend lands under the $1.50 sweep cap,
   and no call the probe makes is refused by the
   guard (the largest worst case is engineering
   at $0.1500, under the $0.50 per-run cap).
6. What this run does NOT predict: whether units
   ship. The pace finding (60.4–161.4 s per
   engineering node against a ~320–365 s plan
   node) says no unit can ship inside 600 s on
   this lineup; this sample measures the spread,
   not the verdict.

Falsifiers: a second preflight finding beyond
the known declaration gap; a unit past its 600 s
or 40-call bound; sweep spend above $1.50; a
spend-guard refusal on a call the probe makes;
an engineering call that fails for a reason other
than the upstream 429.

Caveat: the same empty knowledge store — no
search-tier call. The third sample's measured
record is appended below after the run, in this
same file, and committed again.

### The third sample — measured record (2026-10-04, after the run)

The results file (gitignored, like every local
run output): `evals/results/probe-20261004-golden-q123-rerun3.jsonl`.
The header records the same lineup and
`"preflight": {"ran": false, "override": true}`
— prediction 1 **HELD**. The sweep: **0/3 units
passed, 0/3 shipped; 12 calls; 1076.3 s;
$0.0884 booked of the $1.5000 sweep cap** (the
terminal's sweep-budget line printed `sweep
budget: $0.0884 of $1.5000`; the sweep CLI
exited 1 — units ended blocked, not a crash).
`score_trace`'s reading, verbatim:

```
Q1   FAIL (no answer)   blocked    no answer              items[] 260.945s/300s $0.0227/0.5 risk=low sprawl=None scope_out=None
Q2   FAIL (no answer)   blocked    no answer              items[] 458.911s/300s $0.0286/0.5 risk=critical sprawl=None scope_out=None
Q3   FAIL (no answer)   blocked    no answer              items[] 356.478s/300s $0.0371/0.5 risk=medium sprawl=None scope_out=None

0/3 PASS · 0/3 shipped · median sprawl None · total $0.0884 · key v1
```

Booked spend by tier: architecture $0.0525,
research $0.0204, triage $0.0155, engineering
$0.00 — **no engineering call completed in
this sample**. No search-tier call (the
empty-store caveat held); no judge call (no
implementation was agreed).

Per-unit records (the shape is identical
across the three units — the plan node
completes, the feasibility node's engineering
call is dispatched and fails with the 429
after the client's 3 retries, and the run
ends on the exception):

- **golden_q1** — blocked, 260.945 s, 4
  calls, $0.0227 booked. The plan node
  completed in ONE architecture call: 241.719
  s, 14,280 completion tokens. The feasibility
  node's engineering call was dispatched and
  failed with the 429 (`error_status`; its
  worst-case reservation $0.024885 booked as
  liability). The feasibility phase itself
  took 6.671 s (the retries' backoff is not
  in the phase seconds; the run ended on the
  exception).
- **golden_q2** — blocked, 458.911 s, 4
  calls, $0.0286 booked. The plan node
  completed in one call: 439.947 s, **20,909
  completion tokens** — the largest plan of
  the three samples, well under the 125,000
  cap. The feasibility node's engineering call
  dispatched, 429 after the 3 retries
  (liability $0.026702).
- **golden_q3** — blocked, 356.478 s, 4
  calls, $0.0371 booked. The plan node
  completed in one call: 330.477 s, **23,139
  completion tokens**. The feasibility node's
  engineering call dispatched, 429 after the
  3 retries (liability $0.026572).

Every engineering failure carried the
provider's own sentence: *"thinkingmachines/
inkling-small is temporarily rate-limited
upstream. Please retry shortly, or add your
own key to accumulate your rate limits:
https://openrouter.ai/settings/integrations"*

Predictions vs measured:

1. **HELD** — the header records `{ran:
   false, override: true}`.
2. **HELD** — every plan completed in ONE
   architecture call (14,280 / 20,909 /
   23,139 completion tokens — all above the
   old 14,000 cap, all under the 125,000
   cap; the cap now holds with headroom
   across three samples, the largest plan
   23,139 tokens).
3. **MEASURED — the 429 recurred on EVERY
   engineering dispatch this sample** (3 of
   3 units' feasibility calls failed after
   the client's 3 retries). The intermittence
   is run-correlated: the second sample was a
   good window (2 of 3 units' feasibility
   calls completed), the first and third
   samples bad windows (0 of 3). Across the
   three samples, 2 of 9 units' feasibility
   dispatches completed — both in one run.
4. **HELD** — 260.945 / 458.911 / 356.478 s
   (all ≤ 600), 4 / 4 / 4 calls (≤ 40); the
   429 failures ended the runs on the
   exception before the watchdog's budget
   arithmetic was needed (the watchdog did
   not fire).
5. **HELD** — $0.0884 booked of $1.50; no
   spend-guard refusal (the largest worst
   case the probe made was engineering at
   $0.1500, under the $0.50 per-run cap);
   total liability $0.078159 ($0.024885 +
   $0.026702 + $0.026572), total exposure
   $0.1666.
6. **MEASURED 0/3** — no unit shipped; no
   engineering call completed, so this sample
   adds no pace measurement. The pace verdict
   from the second sample stands (60.4–161.4 s
   per feasibility node against a
   312.8–365.5 s plan node: the 600 s
   deadline cannot fit plan + feasibility +
   implement before any judging round).

Falsifiers: none fired — no second preflight
finding, no unit past its 600 s or 40-call
bound, sweep spend $0.0884 < $1.50, no
spend-guard refusal, and no 400 (every
failure was a 429).

The three samples together ($0.0720 +
$0.0945 + $0.0884 = $0.2549 of the $4.50
total authorization across the three runs):
the plan node is measured (241.7–439.9 s,
14,280–23,139 completion tokens, always one
call at the 125,000 cap); the engineering
serving is intermittently unavailable
(2 of 9 units' feasibility dispatches
completed, both in one run) and, when it
serves, too slow for the 600 s deadline
(60.4–161.4 s per node); the judge's pace
remains unmeasured (no implementation was
agreed in any of the nine units). Where this
leaves the owner: the options are unchanged —
**(a)** keep retrying (the availability is a
window the provider controls; the pace
finding stands regardless), **(b)** pick a
different engineering model/endpoint (G-2 pin
ratification / G-3 `.env`) — the decisive
option, one whose per-call pace fits the
600 s deadline alongside the ~320–440 s plan
node, **(c)** raise the per-scenario timeout
(the owner's line — does not address the 429),
**(d)** accept. No paid tier-3 arm-E unit can
start until the engineering tier both serves
reliably and fits the deadline.

## The fourth sample — pre-registration (2026-10-05, before the first paid call)

The owner acted on options (b) and (c)
together: a different engineering serving
**and** a raised per-scenario timeout. The
owner's `.env` edits (G-3; contents never
printed): engineering is now plain
`thinkingmachines/inkling` (not
`inkling-small`) via **Together** (the
catalogue lists two providers for plain
inkling — DeepInfra and Together; the
`inkling-small` id is DeepInfra-only), the
judge provider is **google-vertex/us-south1**
(the judge model is unchanged,
`qwen/qwen3-235b-a22b-2507:exacto`), and
the plan ceiling is **55,000** (was 125,000).
The per-scenario timeout is raised 600 →
**1900 s** — the owner's stated trade-off:
sacrifice speed for performance and price
with mimo-pro.

The free checks re-verified the locked
configuration before any paid call:

- **The guard's geometry fits.** The worst-
  case table (completion side, max_tokens ×
  the catalogue rate): triage $0.0614,
  research $0.0614, search $0.0180,
  architecture $0.0479, **engineering
  $0.2228**, judge $0.0057, escalation
  $0.2520 — every tier under the $0.50
  per-run cap, no warning fired. The 55,000
  ceiling is what makes it fit: plain inkling
  completes at $4.05/M on both providers
  (3.375× inkling-small's $1.20/M), so at
  the old 125,000 ceiling the engineering
  worst case would have been $0.50625 —
  over the cap, and the guard would have
  refused every engineering call before
  dispatch (the 500000-cap conflict's
  geometry, now caused by the model switch).
  At 55,000 the largest measured plan
  (23,139 tokens) still holds with 58%
  headroom.
- **The engineering pin resolves**: Together
  serves `thinkingmachines/inkling` (the
  endpoints route lists both providers).
  Together's endpoint does not declare
  `response_format` (the same declaration
  gap DeepInfra's carried) — the client's
  shipped safety net (log, drop the
  parameter, retry on a 400) covers it; it
  has never been exercised live.
- **The judge pin check reports FAIL, and
  the record shows why that is an instrument
  false negative, not a configuration 404**:
  the check compares the pin against the
  endpoint's `provider_name` (`Google`,
  normalized `google`), but the client routes
  by **tag** — it passes the pin verbatim in
  `provider.order`, and the catalogue lists
  the judge model's `google-vertex/us-south1`
  endpoint (tag `google-vertex/us-south1`,
  declaring `response_format` and
  `max_tokens`, priced). The pin check's
  normalization was written before any
  tag-style pin whose prefix names a platform
  rather than its provider; every prior pin's
  tag prefix matched its provider name. The
  router's server-side resolution of the tag
  is provider behaviour — the first judge
  call of any unit that reaches judging is
  the live test, and a 404 there is a
  falsifier of this pre-registration.
- The sweep runs with `--skip-preflight`
  (the owner's standing override; the results
  header records `{ran: false, override:
  true}`), because the two free findings
  above would otherwise refuse the start.

Configuration: golden_q1–q3 through
`engineering-rnd`, repeat 1, timeout 1900 s,
`--max-spend 0.50` per scenario-run,
`--max-spend-sweep 1.50`, the same `env -u`
invocation (the shell's stale exports
removed so the owner's `.env` is the source
of truth), a new results file
(`evals/results/probe-20261004-golden-q123-rerun4.jsonl`,
gitignored like every local run output).

Predictions:

1. The header records the lineup above and
   `{ran: false, override: true}`.
2. Every plan completes in ONE architecture
   call — the 55,000 ceiling holds if plans
   stay under it (the largest plan of the
   three samples was 23,139 tokens, 42% of
   the ceiling); a plan past 55,000 would
   truncate mid-JSON (the sample-1 finding
   at 14,000) and the client's parse-retry
   would split it across calls.
3. The engineering dispatch via Together:
   the measurement. Whether Together's serving
   escapes the upstream 429 that hit
   DeepInfra's inkling-small is unknown — a
   different model id and a different provider
   route. The response_format gap means the
   first engineering call may 400 once before
   the client's safety net retries without
   the parameter.
4. Units stay within 1900 s and 40 calls.
   At the measured paces (plan 241.7–439.9 s;
   feasibility 60.4–161.4 s when it served;
   judge 271–291 s in the first probe), a
   full unit — plan + feasibility + implement
   + validate + one judging round — fits
   1900 s with room for a second judging
   round.
5. Booked spend under $1.50; no spend-guard
   refusal (every tier's worst case fits,
   engineering $0.2228 completion-side).
6. The outcome: units may now complete
   feasibility and implement and reach
   judging — the first judge calls in four
   samples, which would measure the judge's
   pace and live-test the google-vertex tag
   pin.

Falsifiers: a second preflight finding; a
unit past 1900 s or 40 calls; sweep spend
over $1.50; a spend-guard refusal; a
recurring 400 (the safety net failing); a
judge 404 (the tag pin not resolving
server-side); a plan past 55,000 tokens.

Caveats: the same empty knowledge store —
no search-tier call. The fourth sample's
measured record is appended below after the
run, in this same file, and committed with
the run's completion (the owner directed no
git actions until the test completes, so the
pre-registration rides uncommitted until
then — a recorded departure from
pre-register-and-commit-first; the
predictions precede the result in this
document either way).

### The fourth sample — measured record (2026-10-05, after the run)

The results file (gitignored, like every
local run output): `evals/results/
probe-20261004-golden-q123-rerun4.jsonl`.
The header records the locked lineup —
engineering `thinkingmachines/inkling:exacto`
via `together`, judge `qwen/qwen3-235b-a22b-
2507:exacto` via `google-vertex/us-south1` —
`"timeout": 1900.0` and `"preflight":
{"ran": false, "override": true}` —
prediction 1 **HELD**. The sweep: **0/3
units passed, 49 calls, 1413.8 s, $0.4239
booked of the $1.5000 sweep cap** (the
sweep CLI exited 1 — units ended blocked 2,
escalated 1, not a crash). Booked spend by
tier: engineering $0.2396, escalation
$0.0793, architecture $0.0356, judge
$0.0319, research $0.0198, triage $0.0177.
Served by: engineering via **Together**,
judge via **Google**, escalation via
InferenceNet, architecture via Xiaomi,
research and triage via Google AI Studio.

Per-unit records:

- **golden_q1** — blocked, 258.679 s, 13
  calls, $0.0743 booked. The plan node
  completed in ONE architecture call:
  147.867 s, 7,464 completion tokens. The
  feasibility node's engineering call
  **completed on Together in 10.58 s** —
  the 429 that ended the first three
  samples did not recur. The implement
  node completed (22.389 s and 32.221 s
  across two attempts; engineering 3 calls,
  $0.0500 booked), the deliverable was
  **implement_green and validate_green —
  all six success criteria PASS, the first
  golden unit in four samples to produce a
  validated deliverable** — and the review
  loop revised it green again. The unit
  then died on a **new failure class**:
  `SSLError: [SSL: SSLV3_ALERT_BAD_RECORD_
  MAC]` — a TLS transport alert, not
  upstream capacity — during the rework
  loop's third implement call (0.482 s in).
  The judge tier served 6 calls via Google
  (5.484 / 2.729 / 7.532 / 17.282 s —
  the tag pin resolved server-side and
  served, the first judge calls in four
  samples); two judge calls failed with the
  qwen3-235b upstream 429 after the
  client's retries (the same rate-limit
  phenomenon, now observed on a second
  model family). Liability $0.2641 (the
  SSL-killed engineering call's worst case
  $0.248866 + the two judge 429s $0.0152).
- **golden_q2** — blocked, 599.606 s, 6
  calls, $0.0577 booked. The plan node
  completed in ONE architecture call:
  **522.66 s, 24,107 completion tokens** —
  mimo-pro's pace on a large plan (~21.7 s
  per 1k tokens), 87% of the 600 s budget.
  The feasibility node completed on
  Together (17.949 s). The deliberation
  watchdog then cancelled the implement
  call at iteration 1: budget 600.0 s,
  pace 17.949 s (the observed engineering
  pace), 45.7984 s available, terminal at
  599.6052 s — the remaining pipeline
  (implement + validate + review + possible
  rework) could not fit 45.8 s. The
  cancelled dispatch's worst case $0.242959
  booked as liability.
- **golden_q3** — **escalated**, 555.501 s,
  30 calls, $0.2920 booked, zero liability
  (every call completed). The plan node
  completed in one call (139.753 s, 7,314
  tokens); feasibility completed on
  Together (10.56 s); the implement node
  ran 7 engineering calls across 3
  iterations (239.63 s) — **every iteration
  implement_green and validate_green**; the
  judge tier served 18 calls ($0.0239);
  the escalation tier served 1 call via
  InferenceNet (71.373 s, $0.0793) and its
  recovery loop ran 3 iterations without
  converging, "still red". The escalation's
  own assessment, verbatim in substance:
  all three attempts produced identical,
  numerically correct results (J = 6.14e-7
  m^4, tau_max = 20.4 MPa, theta = 0.0102
  rad); "the failures are purely
  presentational and self-inflicted... The
  block is now a prose artifact, not an
  engineering defect" — each attempt's
  added explanatory prose about rounding
  conventions became a new procedural
  finding surface.

Predictions vs measured:

1. **HELD** — the header records the locked
   lineup and `{ran: false, override: true}`.
2. **HELD** — every plan completed in ONE
   architecture call (7,464 / 24,107 /
   7,314 completion tokens — all under the
   55,000 ceiling, the largest 44% of it).
3. **MEASURED — Together's serving
   completed.** The 429 did not recur: all
   12 engineering dispatches across the
   three units completed (3 / 2 / 7 calls;
   feasibility in 10.58 / 17.95 / 10.56 s;
   engineering $0.2396 booked, the largest
   tier spend). The availability problem
   was DeepInfra's route (or the
   inkling-small id's upstream), not the
   model family. No 400 occurred —
   Together's route accepted response_format
   despite not declaring it; the client's
   400-retry safety net was never needed.
4. **MEASURED — and the 1900 s bound was
   never tested.** Q1 258.679 s / 13 calls,
   Q2 599.606 s / 6 calls (the watchdog
   cancelled it), Q3 555.501 s / 30 calls —
   all inside 600 s. The D38 watchdog's
   budget is `settings.run_time_budget_
   seconds` (autornd/engine/workflow.py:144),
   which the owner's `.env` pins at 600 (the
   config default is 1800); the CLI's
   `--timeout` is a separate, outer bound
   that does not move the watchdog. The
   owner's 1900 s raise reached the outer
   bound only — the watchdog still armed at
   600 s in all three units (each unit's
   record carries `budget_seconds: 600.0`).
   The raise the owner asked for is one
   `.env` line away: `RUN_TIME_BUDGET_
   SECONDS=1900` (G-3).
5. **HELD** — $0.4239 booked of $1.50; no
   spend-guard refusal (engineering's worst
   case $0.2228 fit the $0.50 per-run cap).
   Total liability $0.5071 (Q1 $0.2641 +
   Q2 $0.242959 + Q3 $0.00); total
   exposure $0.9310.
6. **MEASURED — units reached judging, and
   the judge's pace on the new serving is
   2.7–17.3 s per call** (24 judge calls
   across the sweep, $0.0319) — against
   271–291 s on the first probe's old judge
   serving. The pace problem the original
   probe raised is answered by the new
   lineup: the judge tier is no longer the
   bottleneck. The judge model itself
   429'd intermittently upstream (two calls
   lost in Q1; retries absorbed the rest) —
   the same phenomenon on a second family.

Falsifiers: none fired — no second preflight
finding, no unit past 600 s or 40 calls (the
1900 s bound was not the watchdog's), sweep
spend $0.4239 < $1.50, no spend-guard
refusal, no recurring 400, no judge 404 (the
tag pin resolved server-side and served), no
plan past 55,000 tokens. The SSL transport
error is a new failure class, not a
registered falsifier — one occurrence.

The four samples together ($0.0720 +
$0.0945 + $0.0884 + $0.4239 = $0.6788 of
the $6.00 total authorization across the
four runs): the engineering tier now serves
reliably (Together: 12 of 12 dispatches
completed in this sample, after 2 of 9 on
DeepInfra's inkling-small across three
samples) and the judge tier serves and is
fast (2.7–17.3 s per call). The pace
question is answered conditionally: a unit
whose plan node stays ~7–8k tokens fits
600 s with ~400 s to spare (Q1: 258.7 s to
a green deliverable; Q3: the full pipeline
including escalation in 555.5 s), but a
24k-token plan on mimo-pro (522.7 s) eats
the budget alone (Q2). Where this leaves
the owner: **(a)** set `RUN_TIME_BUDGET_
SECONDS=1900` in `.env` (G-3) if the
watchdog's budget should be 1900 s — the
`--timeout` raise alone does not reach it;
**(b)** the SSLError class — one occurrence,
transience unmeasured (a re-run would tell);
**(c)** the judge model's intermittent
upstream 429s — the provider's own-key
remedy (G-1) or acceptance (retries absorb
most); **(d)** Q3's prose-artifact block —
the escalation's recovery loop not
converging on numerically correct work is a
harness-behaviour finding (the review loop
generates finding surfaces from defensive
meta-prose), the advisor's to rule on, not
a serving change; **(e)** the plan node's
variance on mimo-pro (139.8–522.7 s by
plan size) is the measured cost of the
owner's "sacrifice speed for performance"
trade — under a 600 s bound, plans above
~10k tokens risk the watchdog; **(f)** the
tier-3 experiment's gate 1 is no longer
blocked by the engineering tier — it serves
and fits — and the arm-E worst-case table
under the new lineup (inkling at $4.05/M
completion) should be re-quoted free before
ratification (the tier-3 runner's
`worst-case` subcommand).
