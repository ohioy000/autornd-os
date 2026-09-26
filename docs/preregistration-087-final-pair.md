# Pre-registration: final paired probe — pool sizing + backfill migration (2026-09-26, owner-ruled, no command file)

## Primary question

Does the loop hold on two harder convergence shapes — backend capacity
sizing with a word cap and ≥3 derivations, and a phased migration with
a word band, a prohibition, and a required verification query — for an
owner-side price comparison against a frontier harness?

## What changed since 085 (scenarios only)

- 085 (cup-line sensor): COMPLETED 1/1, 11 calls, $0.07 — loop
  generalizes to machine wiring. 2-for-2 completions, different
  domains. Committed, pushed.
- New scenarios (no code changes): conv_pool_sizing (900-word cap,
  ≥3 derivations, must name pool timeout + pooler) and
  conv_backfill_migration (1,000–1,350 words, no vendor names,
  must contain verification query). Both convergence-tagged,
  engineering-rnd, same roster.
- Roster unchanged (preflight 15/15): Flash triage/Alibaba,
  Inkling-small plan/DeepInfra, GLM-5 build/StreamLake-first,
  failover open. Suite 1018 green at main.

## Budget arithmetic (Ruling D25: sized, not defaulted)

085 spent $0.07 in 11 calls; backfill's 1,000+ word deliverable is
~3x the output volume — budget ~$0.25 for the pair against $2.00
caps each. Envelope: $2.00 per run owner-approved; caps --max-spend
2.00 --max-spend-sweep 2.00. Timeout 1800 each, sequential (no git
ops mid-run either way; second pre-registered here to avoid a second
commit round-trip).

## Registered prediction (verbatim)

BOTH RUNS COMPLETE with validate green. Rationale: the loop is
3-for-3 on terminals (079 probe, 084, 085) across three domains;
word caps/bands are output-shape constraints the plan phase has
already honored (085's deliverable held its sections); the
prohibition (no vendor names) is a vocabulary constraint of the
same class as the honesty firewall (name assumptions, not sources).
The risk is the backfill length (1,000+ words through implement +
review at 112k ceilings — fits, but the longest deliverable yet).
If either run drifts a figure across sections or breaks its word
band, refuted in the informative direction with the section named.

## Run shape

- Scenarios: conv_pool_sizing.yaml + conv_backfill_migration.yaml
  (NEW — first outings; workflow + roster are the replication).
- Workflow: engineering-rnd. Repeat: 1. Timeout: 1800. Sequential.
- Isolation: knowledge store isolated. Tree clean at commit
  (scenario files included).
- Departure (owner-authorized): no command file; owner ruled alone
  with full go-ahead. Pre-registration commit is the precedence
  evidence for BOTH runs.

## What will be reported

Per run: terminal verbatim; word count vs band; derivation count;
figure agreement; served_by; trace + mirror; n=1 and the $2.00
envelope. Pair total spend for the owner-side comparison.
