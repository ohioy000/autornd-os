# Per-profile model pins and per-profile prompt words (2026-11-21)

**Status.** Owner-directed in conversation, 2026-11-21. The pin is **proposed, not ratified**: a serving pin is the owner's
(G-2), and no `.env` carries it. The tuned prompt text is **held for four profiles** by the pre-registered rules of the
sweep (below); the owner rules on what ships. Spend was authorised before each paid step: up to '$3.00' for the pin smoke
and up to '$1.00' for the prompt sweep. Spent: '$0.1521' and '$0.2251'. Branch `feat/20261121-profile-model-pins`;
no pull request until the owner says.

## What was asked, and what it became

The owner asked how the profiles differ and whether they run on different models. Reading the tree: a profile supplied a
team, a vocabulary, framing words and a corpus, and no model; tier to model was one global table built from `.env`. The
owner directed (1) a per-profile pin, a legal model on a legal profile as the example; (2) four field profiles, `legal`,
`finance`, `medical`, `science`; (3) prompts written in each profile's words, `general` universal, engineering left exactly
as it was; (4) the README to treat the choice of models as half the harness; (5) the stale items found on the way fixed
or removed; (6) the `.env` line done by me, because the owner cannot reach the file from where they are.

## Classification (CLAUDE.md, "the permission boundary")

| Change | Class |
|---|---|
| `PROFILE_MODELS` setting, the pure-overlay resolver (`autornd/routing/pins.py`), a pin carrying its own serving | owner-directed behaviour change (which model answers) |
| Four field profiles; framing words 19 to 35 keys; risk guide examples, hazard sentence, three switch questions, citation phrases and escalation prompt in the profile's words; `general` universal | owner-directed behaviour change (prompt text that steers judgment) |
| `reader` added to preflight's optional tiers and call functions, its endpoint and parameters now checked | instrument repair: a tier the harness calls was never checked |
| `models_by_function` in a unit record, and the eval header's effective model map and pins | instrument repair: a record that would have reported the global map while a pin served |
| `check_models` rating every profile's pin | instrument repair: a runtime profile switch must never be `spend_guard_blind` |
| A typo'd or unconfigured tier still falls back to the engineering model, now with a warning | the owner's ruling: warning only |
| README, `.env.example`, `HANDOVER.md` stale lines | owner-directed removals; each was checked stale before it was changed |

Where the design was silent: whether preflight should refuse a reader endpoint that lacks `reasoning` (the reader sends it)
is **recorded, not decided**.

## Engineering is byte-identical

`tests/prompt_capture.capture_all` renders every prompt site under a profile, with the default and with the neutral seats.
It was run on `origin/main` before any edit and on this branch after the last prompt change: `engineering`, `example`,
`cupline` and `tier4` are equal under both seats, for every site including the escalation prompt (engineering family hash
`fdf81156…6955`, equal on both). `general` and `studio` differ, as meant. The four golden fixtures
(`tests/fixtures/prompts/`) pass unchanged, and a fixture of the five switches' rendered question and answers, captured from
main before the first edit, is byte-equal under the four. The owner's `.env` says `AUTORND_PROFILE=engineering`, so their
runs send what they sent. **A checkout with the variable unset changes**: it ran a hybrid (neutral team words,
engineering examples) and now runs the universal `general`.

## The pin smoke (`docs/preregistration-per-profile-pins-smoke.md`, with two amendments)

Seven runs, one per cell, '$0.1521' in all. Under `legal` the answer call was served by the pinned model through Z.AI in
all three runs, and by nothing else. Traces, sha256:

| Trace | sha256 |
|---|---|
| `pin-smoke-legal-gen_contract_threshold.jsonl` | `60949fb3f12839edf50cd1573b3db118b901a8aaec7440111ca8d253e4637d6d` |
| `pin-smoke-legal-pin_legal_termination_clause.jsonl` | `12277f0a30a2eafd87a774507cf120973bd5942af6ef4cb824fa36f40a002873` |
| `pin-smoke-legal-pin_legal_delay_damages.jsonl` | `232684a670783483aa4e2c17c471a7a116712374f1529eaeb9e2cf28b5cd36ad` |
| `pin-smoke-general-gen_contract_threshold.jsonl` | `5b303bd9c326698c187c9e343297971c403b7ac20ee15972f6ac68ff36b9b295` |
| `pin-smoke-general-pin_legal_termination_clause.jsonl` | `fac69a15dc7d54c43cbe35fb0be1370e3f8111893d1320cf17bee0c429e23aa2` |
| `pin-smoke-general-pin_legal_delay_damages.jsonl` | `e664fbef6a3fa048d18f151dff9078d60d571375488a9d0a0e9af3a33c7ae817` |
| `pin-smoke-engineering-pin_engineering_leak_check.jsonl` | `a26422759bbe8423ca9c6ef9f71fa8e3daf563a802286ee976667c3d0de5e7fd` |

The predictions, scored one at a time:

- **S1, served by the pin, n = 3: holds, 3 of 3.** One id, the pinned one, one provider.
- **S2, no leak, n = 3: the leak half holds; the positive half could not be observed.** The pinned id is in no `general`
  run. But under `general` the answer is not on the engineering tier at all: `general` declares no domains, so a named
  domain resolves to the profile's system-view role, the planner, which is on the architecture tier. The pin's tier was not
  called there. This is how `general` was built; it is not changed here and is listed below.
- **S3, only the engineering tier moved, n = 3 pairs: holds.** The paired headers differ in `models.engineering` only.
- **S4, typed verdicts held on the pin, n = 3: falsified.** One of the three `legal` runs
  (`pin_legal_termination_clause`) had one engineering reply rejected against the verdict's schema, served by Z.AI; the
  retry was accepted. `general` had none.
- **S5, nothing blind or refused, n = 6: falsified as written, holds as restated.** The `decision` tier's model is not in
  the public chat catalogue, so the spend guard cannot rate it and every unit of this workflow carries three
  `spend_guard_blind` entries for it ('$0.0002' in all). The owner ruled after run 1 to amend the stop rule to blind
  entries on the pinned tier and run the other five (Amendment 1). Restated, no blind entry on the engineering tier, no
  404 and every unit completed: holds, 6 of 6. That the decision model is unrated is a known property (README), not a
  finding of this run.
- **S6, the pin's cost is its catalogue rate, n = 3: holds.** Billed cost over the no-cache figure from the token counts:
  1.000, 1.000, 0.997.
- **S7, spend, n = 6: holds.** The three `legal` runs cost '$0.0402', '$0.0418' and '$0.0100'; the six together
  '$0.1455'; each under '$0.40'.
- **S8, the delay-damages figure, n = 2: holds.** 48,000 stated under both profiles.
- **S9, the engineering profile untouched by the legal pin, n = 1: holds.** The engineering tier was served by the global
  engineering model and the pinned id appears nowhere in the record ('$0.0066' brings the seven runs to '$0.1521').

**What this is evidence of:** serving, cost and typed output. **It is not evidence of quality.** No legal question set
with signed keys was answered; the three runs are for the owner to read by hand when ruling on the pin (G-2).

## The prompt sweep (`docs/preregistration-prompt-sweep-per-profile.md`, with one amendment)

The wide suite, 36 sectors, `triage-classify`, five repeats, 180 units an arm. The control is main's text under `general`
in a clean worktree at `origin/main`; the other six arms are this branch. No arm had an error or a timeout. Cost per arm
'$0.0304' to '$0.0344', '$0.2251' in all. The rules that decide were written before the spend and are applied as written.

| Arm | sha256 of the trace | Units below a risk floor | Meets every risk bound | C1 (floor, at most control + 3) | C2 |
|---|---|---|---|---|---|
| control | `1495b1a80a4e02bf1934d7137fd1c514c8b086382264e817b58a5c50893922ec` | 0 | 174 | | |
| general | `bd17123a2ec3f3bf8ec51ae474e2f43eac517f678230cfee4f6d93c28f0b57c4` | 0 | 169 | holds | **fails** (169 against at least 171) |
| studio | `e9621637f1cc30af5473ec1562859f0db94976e6ed822981ba8160eb5811b883` | 3 | 156 | holds, at the margin | |
| legal | `2885715eaa83e8283187ecae4c017afaeddf136bfb2e279bc4a6ef93e97f9503` | 10 | 154 | **fails** (10 against at most 3) | |
| finance | `f5ac74bd28eebb71d21139f712dad7700947bda53949b35183ac47fcf50cc812` | 24 | 150 | **fails** (24) | |
| medical | `11cf50bf86ab67b5b85ceeb87c039087ea416e740bda555f5616ca1f3f32a741` | 18 | 156 | **fails** (18) | |
| science | `8b8d944847c79e2278b4512b3259a2c6be69d471ef6a85c18578dd87986bcbe2` | 1 | 157 | holds | |

**What the rules say.** The tuned text of `legal`, `finance` and `medical` fails C1, and the tuned text of `general` fails
C2. By the pre-registration those are **held**: not shipped as measured, nothing tuned further to pass, no arm re-run to
pass. `studio` and `science` hold C1. Predictions P1 (every arm within the margin), P2 (`general` holds) and P3 (C4 is 0
for every arm) are **falsified** for the arms above; P4 (instrument) holds.

**What the failures are.** They are not noise: three of the four are under-calls of physical hazards.

- `finance` reads aquaculture `low` or `medium` on 5 of 5 (control: `high` on 5 of 5), dentistry `low` on 2, printing `low`
  on 3, rail signalling `low` on 2, space `medium` on 4, automotive `low` on 2 and veterinary `low` on 2.
- `medical` reads textiles `low` on 4 of 5 and hvac `medium` on 4 of 5 (control: `critical` on 5 of 5).
- `legal` reads aquaculture `low` or `medium` on 4, printing `low` on 3.
- `general`'s C2 miss is on the other side: every one of its units meets the floor, and it fails the ceiling more often
  than the control did (broadcast 5 of 5, textiles 3 of 5), so it **over-calls** where the control sat lower. Two units past
  the margin.

The same sectors that the plan said would stress the non-engineering profiles on purpose did so. A field profile's examples
that contain no physical-hazard case teach the model to read a physical-hazard request as low-risk for that field; the
hazard sentence keeps injury and equipment damage, as the guard test requires, and the examples around it do not carry
enough weight alone.

**C3, the movers** (sectors whose modal risk differs from the control's): general 9 of 36, studio 5, legal 10, finance 11,
medical 8, science 7. Each is listed with both readings in the scoring output, reproducible with
`score_sweep.py evals/results` over the traces. Veterinary moves to a modal `critical` under five of the six arms (finance splits four ways).

**C4, sectors that read the same on all five repeats in both arms but differ** (predicted 0; reported as a finding, not a
hold): general 0 of 22, studio 1 of 22 (marketing, `low` to `medium`), legal 1 of 21 (semiconductor, `high` to `medium`),
finance 1 of 17 (semiconductor, `high` to `medium`), medical 0 of 15, science 1 of 22 (textiles, `medium` to `critical`).

**Not read.** The 13 sectors naming `test_engineer` fail `specialists_include` under every arm that is not engineering (65
of 180 units in each, as in the control); reported, not scored. The decision switches, citation phrases and escalation
prompt were not covered by the sweep, by design.

## Options, and a recommendation (the decision is the owner's)

A held profile's text is not mine to ship or revert. Three ways to go on, for each held profile:

1. **Revert the held profile's risk examples to engineering's text** (the control), keep everything else (team, vocabulary,
   switches, escalation, pins). The sweep's measurement is then true of what ships. For `general` this restores the control
   exactly; for `legal`, `finance` and `medical` it means a field profile whose risk guide teaches with physical-engineering
   examples again, which the leak test forbids today and would have to be relaxed by the owner's ruling.
2. **Write field examples that include a physical-hazard case and measure again.** This is a new pre-registration and a new
   spend; about '$0.23' for seven arms, '$0.78' of the '$1.00' remains.
3. **Ship as measured, with the limit stated.** The docs already say so; the cost is that a legal, finance or medical run
   may under-call a physical-hazard request.

My recommendation is option 2 for `legal`, `finance` and `medical`, because the under-call is the failure that matters and
reverting reintroduces the engineering words the owner asked to remove, and, for `general`, to ship it: its only miss is an
over-call by two units, which costs a lookup and not a missed hazard. `studio` and `science` held and need nothing. None of
this changes engineering.

## Found, not touched

- **A stale provider pin in `.env`**: `architecture:gmicloud/bf16` names a provider that no longer serves that model. Four
  providers do (the catalogue lists deepinfra, primalabs, streamlake, xiaomi). It makes every sweep's preflight refuse; the
  sweep ran with the order overridden in the process environment and the file untouched. A pin is the owner's (G-2).
- **The decision model is not in the public catalogue**, so its calls are `spend_guard_blind` ('$0.0002' a unit); and the
  global engineering and recompute models carry unbounded charge components in the catalogue, so they are blind too. Both
  are known and not changed.
- **`general` answers on the architecture tier**, because it declares no domains. Left as built.
- **Whether preflight should refuse a reader endpoint that lacks `reasoning`**: undecided, see above.
- **Two tests depend on order**: `test_non_security_fields_take_their_declared_defaults` fails when it runs after
  `test_settings`, and `tests/test_api.py::TestHealthEndpoint::test_health` leaks a `_model_status`. Found on the way, not
  introduced here, not fixed.
- **Residual engineering words in code paragraphs** ("setpoint band", "interlock") in `autornd/engine/phases.py`; four dead
  framing keys (`sources`, `questions`, `unit_examples`, `gap_examples`); the JSON field name `architectural_correction` is
  kept because it is the verdict's schema; the word `cite` also matches inside "excited". None changes what a model is sent
  under a field profile in a way the sweep measured.

## What waits on the owner

1. **G-2:** a "yes" on the pin `PROFILE_MODELS=legal:engineering=<id>@z-ai` after reading the three smoke runs. Nothing is
   written to `.env` before it, and not before this branch is merged and every checkout that reads `.env` has the code that
   declares the key (the settings refuse an unknown key).
2. **The ruling on the held text** above, and whether to spend on a new sweep.
3. **The stale architecture provider pin.**
4. A merge instruction.
