# Recommended tier roster — 2026-09-26 (Option B dated record)

Drawn from run 084 (`docs/traces/084-sane-ceilings.jsonl`: COMPLETED 1/1,
9 calls) — every tier below names the serving that actually answered it
in that trace. This is a snapshot, not a default: run 071's serving
consumed its whole token budget and emitted nothing, and nothing
guarantees today's good roster is good next month. Re-verify with
`.venv/bin/python3 -m autornd.preflight` before trusting it; rates come
from the provider catalogue, never from this file (no price appears here).

| tier | function | serving that answered (084) |
|---|---|---|
| triage | classification and routing | triage pin, run 084 |
| engineering | implement, validate, review, feasibility | engineering pin, run 084 |
| architecture | planning and critical review | architecture pin, run 084 |
| research | documentation grounding | research pin, run 084 |
| search | outward lookup with sources | search pin, run 084 |
| escalation | failure autopsy and recovery | UNPINNED — never fired in 084 (clean completion exercises no autopsy); last live reading predates this roster |
| ranker (optional) | documentation ranking | UNPINNED — no live evidence in 084 |
| premium (optional) | independent Double Check | UNPINNED — never fired (no unrecallable triage on record) |

Concretely (model via provider, as recorded in the 084 header and
`providers_by_function`): planning via DeepInfra, building via
StreamLake, classification via Alibaba, grounding via Google, lookup
via Perplexity. Copy `.env.example` to `.env` and set each `MODEL_*`
to the serving above; set each pin in `OPENROUTER_PROVIDER_ORDER` to
the provider above. The owner holds `.env` (G-3) — this file
recommends, it does not configure.
