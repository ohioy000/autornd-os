# Pre-registration: escalation shootout Kimi-K3 vs Gemini-3.8-Flash (2026-09-26, owner-ruled, no command file)

## Primary question

Which serving holds the escalation tier — the never-fired, hungriest,
8x-price-gap slot — judged on autopsy quality per dollar?

## Shape

3 autopsy questions x 2 servings = 6 direct chat calls (NOT the
workflow — the escalation prompt with committed failure logs, same
system prompt both sides, same max_tokens, temperature 0.3).
Contenders: `moonshotai/kimi-k3` via Moonshot AI ($3.00/$15.00) vs
`google/gemini-3.8-flash` via Google ($0.38/$1.88 base).

Q1 (073's shape — ceiling vs model vs loop): full green build in hand
(validate 7/7, fold 4-0), two rework reviewers truncate at 16384
mid-JSON, spend trips $1.00 at $1.27. Diagnose and name the
least-blast-radius fix.

Q2 (074/075/076's shape — model vs serving vs router): same id empty
6x at 16k across Baidu + Relace, then 404s 3x at 112k across Relace +
Alibaba despite 131072 listings. Which readings indict which layer?
What single experiment separates the remaining confound?

Q3 (the actual job — resolution directive): given Q1, write the
recovery directive — what to change, what to explicitly NOT change
(verdicts, gates, loop), predicted next terminal. Executable without
re-diagnosing.

## Rubric (1-5 each, rated from committed traces, blind to serving)

1. Correct attribution (apparatus, not loop). 2. Least-blast-radius
fix (wiring, not semantics). 3. Executability (acts without asking
back). 4. Honesty (unobserved vs proven named). Per-answer + per-model
means reported; price per answer from trace-billed actuals.

## Registered prediction (verbatim)

GEMINI MATCHES KIMI ON ATTRIBUTION (Q1/Q2 within 1 point), WINS ON
PRICE (~8x), LOSES ON DIRECTIVE SPECIFICITY (Q3: Kimi +1 or more).
Rationale: attribution is pattern-matching over a quoted log (both
flagships do this); directives need judgment about what NOT to touch
(Kimi's reasoning depth earns there); price is catalogue fact. If
Gemini matches or beats Kimi on Q3, refuted favourably and the slot
reprices immediately. If Kimi misattributes any question, refuted
against the incumbent and both servings stay suspect.

## Second bird (owner: kill two)

While running, watch every tier's replies for tweaks/weak points:
prompt waste (tokens paid for no signal), ceiling slack (headroom
never used), retry patterns, serving quirks. Findings recorded in
the report, fixed only if free and behaviour-neutral; anything else
proposed, not done.

## Budget + record

Envelope: $1.00 owner-approved (6 calls; Kimi dear, Gemini cheap).
Probe script committed with this pre-registration; raw replies +
ratings committed after as the trace. No workflow, no git ops
mid-run, suites untouched.
