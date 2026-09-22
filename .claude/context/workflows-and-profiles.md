# Authoring workflows and profiles

Load when editing `workflows/*.yaml` or `profiles/*.yaml`.

## Workflows are data, not code

`workflows/*.yaml` is the pipeline. It is not compiled into the engine; it is a
file you copy and change. The hardcoded sequencer that once mirrored it is gone —
a reference that models less than the product is not confidence.

Shipped shapes:

| file | what it is |
|---|---|
| `engineering-rnd.yaml` | the flagship, 25 nodes |
| `lean.yaml` | cheapest shape that still checks its work — plan, build, verify, stop |
| `triage-classify.yaml` / `triage-only.yaml` | classification only |
| `plan-probe.yaml` | plan-phase probes |
| `independent-check-probe.yaml` | a minimal workflow built to reach `independent_check` live; kept as the regression shape |

A node (`autornd/graph/spec.py:76`, loader at `:292`):

```yaml
- id: plan
  kind: ai                 # ai | check | gate
  tier: architecture       # named by JOB, never by vendor
  specialist: systems_architect   # or a roster token
  prompt: plan             # dispatches to PhaseRunner._phase_plan
  schema: PlanVerdict
  max_tokens: plan_max_tokens     # may NAME a setting, resolved at run time
  depends_on: [context]

- id: plan_ready
  kind: gate
  condition: plan.ready == true
  depends_on: [plan]
  on_fail: blocked                # a terminal status OR a node id to route to
  on_fail_reason: "Plan not ready"
```

Rules that bite:

- **Every loop declares a bound at load time** (`max_iterations`, or
  `on_exhausted` / `on_exhausted_status`).
- **A loop owns its `body`** — see `.claude/context/architecture.md`. Adding an
  existing node to a body removes it from the main flow silently.
- **Conditions use the one grammar** in `graph/conditions.py`. No `eval`, no new
  operators, and a missing path raises.
- **`check:` names a registered free check** (`graph/checks.py:43`). The five in
  use: `criteria_addressed`, `numbers_consistent`, `totals_reconcile`,
  `judges_agree`, `blocked_on_unmet`.
- **No model ids in workflow files.** Tiers only.

## Profiles are the generalization mechanism

`profiles/example.yaml` is an engineering project; `profiles/studio.yaml`
deliberately is not. Selected with `AUTORND_PROFILE=<stem>`.

```yaml
name: "Meridian Studio"
stack:        # free context prepended to EVERY specialist prompt — keep it short
  - "..."     # and true; it is paid for on every call
constraints:
  - "..."
domains:      # domain -> lead specialist, or {lead, checks}
  copywriting:
    lead: copywriter
    checks: ["..."]     # the validation questions work in this domain is judged by
roles:        # the team this project actually has
structural_roles:       # who checks the work, who holds the system-level view
  checks_work: editor
  holds_system_view: strategist
```

- **Nothing in `studio.yaml` is a shipped domain or role**, and none of it needed a
  code change. `copywriting` is not in the `Domain` enum; `fact_checker` is not in
  `SpecialistRole`. That is the point.
- **`checks` matter more than they look.** The built-in lenses only cover the seven
  shipped domains, so before profiles could declare these, work in any other
  subject was judged by an engineering lens.
- **`structural_roles` are declared, not hardcoded.** Undeclared resolves to the
  shipped engineering roles, so every engineering project behaves byte-identically —
  4 regression guards pin that.
- **Private corpora never enter this repo.** `profiles/milkhouse.yaml` is
  gitignored. Doc corpora used for testing generalization live in `docs/<corpus>/`
  with a `manifest.json` and are guarded by `tests/test_doc_corpora.py`.

## Known sharp edge: prohibition-shaped criteria

`criteria_addressed` (`graph/checks.py:381`) is **term overlap, not comprehension**
— at least 50% of a criterion's significant terms must appear in the
implementation. It works on engineering criteria, where the compliant artifact
contains the words. It does **not** work when satisfaction is an *absence*:

> criterion: *"avoids the banned words ('leverage', 'seamless', 'robust')"*

Six of that criterion's seventeen significant terms are words it forbids the draft
to contain, and eight more are meta-vocabulary about the rule. **14 of 17 terms are
unreachable for a compliant draft — satisfying the criterion is what makes it fail
the check.**

The ruled fix is **shape selects the test** (`_classify`, `_forbidden_tokens`,
`_forbidden_present` — `checks.py:325,346,365`): `presence` keeps term overlap
unchanged; `prohibition` inverts, using the criterion's own forbidden tokens as the
test and passing iff none appear; `form` **abstains**, never failing the fold and
never silently. The fail-safe direction is `presence`, because abstention is
leniency and exhibits precede leniency.

Two things to know before touching this: a fourth shape is exhibited and not named
by the ruling — *property-of-the-prose* criteria like "a single sentence with no
subordinate clauses" or "independently defensible", satisfied by how the text
**reads**, not by what it contains. And the input is unstable: plan criteria are
regenerated from scratch on every run of the same request, and a rewording alone
has moved a criterion from 0.63 (pass) to 0.43 (fail) and decided the run.
