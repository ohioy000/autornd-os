# D54: the team is the profile's (advisor, 2026-10-21)

**Status: proposed. It awaits the owner's sign-off, and no command is issued until then.**

This withdraws the D54 sketched in `Dunce-Arch-Self-Assesment.md` §5 (3), which would have retired the pipeline on the strength of closed-question scores. That sketch measured the wrong thing. The goal is a general harness, one that works for any team and is not tuned to be good at one thing (the owner, 2026-10-21). Cost and quality are measured once the harness's core problems are fixed. This ruling fixes the first of those problems.

## 1. The problem

Profiles already let a team declare its own subjects and roles without a code change (`profiles/studio.yaml`, `autornd/profiles.py`). But the team itself is still an engineering team, and it is written into the code:

| where | what is fixed in code |
|---|---|
| `autornd/engine/phases.py` | Nine places in its prompts name engineering. Triage says "Classify this engineering request" and "a triage classifier for an engineering team". The request analyst says "an engineering request analyst". The plan says "plan for this engineering request". The output contract says "Produce the actual engineering work … a competent engineer". Review says "Review this engineering work" and "an independent senior engineering reviewer". The recompute says "a careful senior engineer". |
| `autornd/knowledge/context.py` | Ten places in its grounding prompts. Two rankers say "help an engineer carry out"; query expansion says "An engineer is about to work on" and "search queries that retrieve engineering"; the briefing says "for an engineer" and "You brief engineers"; another says "engineering task"; request scoping says "An engineer is about to plan", "a competent engineer" and "You scope engineering requests". |
| `autornd/knowledge/research.py` | The lookup asks for "engineering questions" from "manufacturer datasheets"; its examples are a pasteuriser, a partition and an interlock, and ERP against EIRP. |
| `autornd/specialists/registry.py` | Every role's system prompt ends "Produce the engineering work itself". |
| `_domain_vocabulary`, `_role_vocabulary` (`phases.py`) | Triage is always offered the seven shipped engineering subjects and seven engineering roles, *plus* the profile's own. A studio's triage is offered `firmware` and `firmware_engineer`. |
| `phases.py` | The lens table (validation questions) exists only for the seven engineering subjects. The subject-to-lead map is engineering-only, and the fallback lead is `systems_architect`. The planner and the validator always speak as the shipped systems architect and test engineer, whatever the profile declares. |
| `autornd/graph/adapter.py:143`, `engine/workflow.py:287` | Code that decides who builds and who must be added compares against the shipped `TEST_ENGINEER` and `SYSTEMS_ARCHITECT` literals. It does not ask the profile, which B14 made the owner of those two roles. |

**The effect:** a team that isn't engineering gets its own words added on top of an engineering team. It never gets a team of its own.

## 2. The ruling

1. **The code ships no team.** Every word that names a kind of team, its work, its practitioners or the sources it trusts, every example a prompt gives, and every default subject, role, lens and lead come from the active profile. A shipped check or prompt carries no subject's vocabulary. (The ident ruling in the review of #208 §3 applies the same rule to checks.)
2. **A profile gains a `framing` block:**
   - `team`: who the harness works for;
   - `work`: what the deliverable is called;
   - `practitioner`: who could apply it;
   - `sources`: what counts as authoritative;
   - `deliverables`: the kinds of output, as listed in the output contract;
   - `examples`: the illustrations the research and assessment prompts give.

   Every prompt in §1 renders from these fields.
3. **The engineering team moves, unchanged, into `profiles/engineering.yaml`.** That covers:
   - the seven subjects, with their lenses and leads;
   - the seven role templates;
   - the structural roles (`test_engineer`, `systems_architect`);
   - framing that renders every prompt as it is today.

   **Under that profile every rendered prompt is byte-identical to main's.** That is how engineering behaviour is kept unchanged.
4. **`profiles/general.yaml` is the default when `AUTORND_PROFILE` is unset.** It carries:
   - neutral framing: team "a team", work "the work", practitioner "a competent practitioner in the field", sources "primary sources: the governing rules and standards, official specifications, and original publications";
   - no subject list, so triage names the subject itself, which the open vocabulary already supports;
   - three roles: a lead who does the work, a reviewer who checks it, and a lead architect who holds the whole view, named in plain words;
   - no examples.
5. **Triage is offered the active profile's subjects and roles only,** never the shipped ones added on top. An undeclared role still resolves as a generalist (B14), so nothing fails for lack of a role.
6. **A profile that declares no framing gets the general framing,** not engineering's. A profile that declares no structural roles gets the general profile's.
7. **The planner and the validator speak as the profile's structural roles.** That is the role that holds the system view and the role that checks the work. The builder filter and role injection compare against the profile's roles, not the shipped literals.

## 3. What proves it, provider-free

1. **Engineering is unchanged.** Under `AUTORND_PROFILE=engineering`, every prompt in §1 renders byte-identical to golden copies captured from main before the change. Every existing test passes with the engineering profile active.
2. **Nothing engineering leaks.** Under `general` and under `studio`, every prompt in §1 renders without any of: engineer, engineering, firmware, hardware, backend, frontend, datasheet, pasteuriser, EIRP. Break-proof: put "engineering" back into the triage prompt and the test fails.
3. **Triage is offered the profile's own list,** exactly. Under `studio` that is studio's subjects and roles and nothing else; under `general`, none.
4. **The structural roles are the profile's.** Under `studio`, high risk adds the editor, the planner speaks as the strategist, and the validator speaks as the editor, as studio declares them.
5. **The hard-coded sites stay gone.** A test lists every module that names a shipped engineering role or subject as a code literal, and expects that list to be empty outside the profile loader.

## 4. What this costs, and what it does not settle

- **No paid call.** The general framing is new prompt text that no run has seen. Its effect on answers is measured once, with the other core fixes, on the owner's word.
- **The default changes for anyone who sets no profile (G-3).** The owner's `.env` sets none today, so after this the owner's runs use `general`. To keep engineering, the owner adds `AUTORND_PROFILE=engineering` to `.env`.
- **Not ruled here:**
  - choosing a workflow per request (the next ruling);
  - retrieval;
  - the convergence repairs;
  - the workflow file name `engineering-rnd`, which the per-request workflow ruling will settle.

## 5. For the owner

**Sign off D54 as written,** or name what changes. The one choice in it that is yours is the default: **`general` (recommended)**, or keep engineering as the default and prove generality only through the guards in §3.
