# D55: a workflow per request (advisor, 2026-10-21)

**Status: proposed. It awaits the owner's sign-off, and no command is issued until then.**

This is step 3 of the generality-first order the owner approved on 2026-10-21. A general harness serves many kinds of work, and different work needs different amounts of process. A one-line check and a multi-part design should not run the same 31 steps. The workflows are already files, but today a request cannot choose one.

## 1. The problem

| where | what |
|---|---|
| `autornd/engine/workflow.py` `workflow_path()` | The workflow is one server-wide setting, `AUTORND_WORKFLOW` (default `engineering-rnd`). Every run on the server uses it. |
| `autornd/api/routes.py` `WorkflowRequest` | The request body carries only `request`. A caller cannot name a workflow. |
| `workflows/` | It holds 8 files. Four produce a deliverable: `engineering-rnd`, `lean`, `verify-first`, `answer-and-recompute`. Four are instruments built to measure one stage: `triage-only`, `triage-classify`, `plan-probe`, `independent-check-probe`. Nothing marks which is which. |
| the run gate (`_admit_run`) | A duplicate is the same caller with the same request text. The same request run through two workflows, to compare them, would be refused as a duplicate. |
| the name `engineering-rnd` | Under D54 the code ships no team, but the default workflow's name says engineering. What it actually describes is the full team process: plan, feasibility, domain review, build loop, review, escalation. |

## 2. The ruling

1. **A request may name its workflow.** `WorkflowRequest` gains `workflow: str | None`, on both `POST /workflows` and `POST /workflows/sync`. If it is unset, the run uses the server's configured default, exactly as today.
2. **Only offered workflows can be named.** A workflow file declares `offered: true` at its top level. The four deliverable workflows declare it, and the four instruments do not. Instruments stay runnable through `AUTORND_WORKFLOW` and the eval runners, where they are used to measure, but a caller cannot pick one.
3. **A name, never a path.** The API accepts only a name that matches an offered file's stem. Anything else is refused with `HTTPException(422, …)` and a plain sentence that lists the offered names: a path, an unknown name, an instrument, or a file that fails to load. `AUTORND_WORKFLOW` keeps accepting a path, because that setting is the owner's (G-3).
4. **The offered list is visible.** `GET /workflows/offered` returns each offered workflow's name and description. It is declared before `GET /workflows/{workflow_id}`, so the run detail route is unchanged.
5. **Every run records which workflow ran.** At the run's start the engine writes one zero-cost phase record, `workflow`, carrying the workflow's name and the sha256 of its file. It goes through the same channel D53's vote uses. There is no DB schema change.
6. **The duplicate guard includes the workflow.** A duplicate is now the same caller, request and workflow. The concurrency cap and the spend ceiling are unchanged and bound every workflow alike, so naming the 31-step workflow cannot spend past the run's ceiling (D45).
7. **`engineering-rnd` is renamed `full-team`.**
   - The file, the setting's default, the docs that describe the current harness, the tests and the eval runners' references all change.
   - The file's contents do not change, so the tier-3 runner's arm E treatment is unchanged.
   - The old name is refused with a sentence giving the new one, in both the setting and the request. There is no alias.
   - Historical records (preregistrations, past reviews, traces, past commands) keep the name they were written with.
8. **The default stays the full team.** Which workflow should be the default is decided after the convergence repairs (step 5), on evidence. Not here.

## 3. What proves it, provider-free

1. **Choice.** A mocked API run naming `verify-first` runs that graph, and its `workflow` record says so. An unnamed run uses the configured default. Break-proof: ignore the field, and the named run's record shows the default.
2. **Refusals.** `../workflows/lean`, `/etc/passwd`, `triage-only`, `nonexistent` and `engineering-rnd` are each refused with 422 and a sentence naming the offered workflows. The old name's sentence also gives the new one. No refused request creates a row or holds a slot (D45 (6)). Each refusal has a break-proof.
3. **Offered.** `GET /workflows/offered` lists exactly the four, with their descriptions. Every file that declares `offered: true` loads. `GET /workflows/1` still returns a run.
4. **Duplicates.** The same request under two workflows is admitted twice. The same request under one workflow twice is refused, as today.
5. **The rename.** `full-team.yaml` is byte-identical to today's `engineering-rnd.yaml`. The tier-3 runner's message hashes and freeze tests pass unmodified. No current doc or code names `engineering-rnd`, except historical records and the refusal sentence. A test keeps that list.

## 4. What this costs, and what it does not settle

- **No paid call.** Nothing changes what an existing run does: an unnamed run under the default setting runs the same graph as today.
- **G-3.** The owner's `.env` sets no `AUTORND_WORKFLOW`, so nothing to edit. A setting that names `engineering-rnd` is refused at startup with the new name.
- **Not ruled here:**
  - **Choosing the workflow automatically from the request's shape.** For example, triage proposing a workflow from the offered list. That changes what the harness concludes on every unnamed run, so it needs evidence that the workflows behave as intended. It comes after the convergence repairs.
  - **A team per request.** The profile is process-wide, and `get_profile()` is read at every prompt site, so making it per-run is a larger change. It is its own ruling, after D54 lands.
  - **The dashboard's workflow selector.**

## 5. For the owner

**Sign off D55 as written,** or name what changes. The one choice in it that is yours is the rename: **`full-team` (recommended)**, another name, or keep `engineering-rnd`.
