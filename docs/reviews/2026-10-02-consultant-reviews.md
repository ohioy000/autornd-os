# Outside review, 2026-10-02

On 2026-10-02 the owner pasted two outside reviews of the third architect's
status report into the architect's session. The report was the published doc
"AutoRnD-OS: status and results report", written after run 107. The owner asked
the architect to take the reviews in, commit them to memory, and build a new
plan from them. The architect checked every code claim against main at
`4fda54f`. That verification comes first below, then the plan the owner
approved, then both reviews verbatim.

The paste names the second reviewer as GPT-6.1 Sol Pro. It does not name the
first. Between the two reviews it shows a cost line ("$0.059 · 24,647 tok") and
the second reviewer's tool log. That block is reproduced as pasted, because it
records which files the second reviewer could read.

## The architect's verification, against main at 4fda54f

| Claim | Verdict | Evidence |
|---|---|---|
| Async submit returns a row that never updates; the run lands on a second row with no owner | Confirmed | `autornd/api/routes.py:152` creates and commits a row; `autornd/engine/workflow.py:73` creates another |
| The Docker quick start is an open endpoint that spends money | Confirmed | `README.md:578` publishes on every interface; `autornd/api/auth.py:86` admits every request when no key or secret is set, which is the default |
| PUT /settings changes global settings, with unbounded ceilings | Confirmed | `autornd/api/routes.py:424` (setattr); SettingsUpdate sets no bound |
| /episodes shows every run, whoever asks | Confirmed | `autornd/api/routes.py:493` |
| API runs have no wall-clock or spend bound by default | Confirmed | `run_time_budget_seconds=None`; the spend ceiling is never set on the API path |
| An empty validation verdict passes | Confirmed | `autornd/models/verdicts.py:351` derives green from the absence of a red cause |
| The independent check's ship verdict has no consumer | Confirmed | No gate reads it |
| Phases are written only after the run, and live status never advances | Confirmed | `pending_saves` (`autornd/engine/workflow.py:78`); `_NODE_STATUS` is unused |
| Rerank has no pre-call guard, and concurrent calls share one balance check | Confirmed | `autornd/routing/openrouter.py:569`; the guard reads spend that updates only after a response |
| There is no retrieval: "citations" are provider annotations | Confirmed | No outbound HTTP exists outside the provider client |
| One bundled lookup; stored answers reused with no TTL; five answers filed under one URL | Confirmed | `autornd/knowledge/research.py:76, 83, 269`; the distance comment says squared L2, but the collection is cosine |
| Lookups are gated on risk, not on question type | Confirmed | `autornd/knowledge/context.py:191` |
| The README's research economics are stale | Confirmed | `README.md:112-156` describes per-sector lookups the code no longer runs |
| One shared collection; editing a document does not replace its chunks | Confirmed | `autornd/knowledge/store.py:17, 60` |
| The revision loop pastes the whole prior artifact at a 32k ceiling | Confirmed | `autornd/engine/phases.py:744`; `plan_max_tokens` 32768 |
| Feasibility cannot gate, yet tells implement to "address these" | Confirmed | `autornd/engine/phases.py:397, 768` |
| A consistency-only failure loops without telling the model why | Confirmed | `autornd/graph/adapter.py:583` logs only a red validate or implement |
| The number check passes if any value in a unit bucket agrees | Confirmed | `autornd/graph/checks.py:775` |
| Profile, settings and counters are process-global | Confirmed | `autornd/profiles.py:210`, `autornd/knowledge/research.py:43`, `autornd/knowledge/context.py:148` |
| Silent context truncation, duplicated rerank constants, a status cast outside the try | Confirmed | `autornd/knowledge/context.py:95`, `autornd/knowledge/context.py:104/156`, `autornd/engine/workflow.py:116` |
| The guard is bypassed on a 429 retry, causing the $0.012 overshoot | Wrong attribution | That overshoot was in 102, before the guard existed; a 429 retry re-posts an unbilled request. The real gaps are concurrency and failed calls left unaccounted |
| Calls past 120 s die as ReadTimeout | Unverified | Live calls have run to about 590 s without one; failed-call accounting is still missing |
| "Four CI jobs" against five required checks | Wrong | 3 jobs, one a 3-version matrix, give 5 checks |
| `enforce_triage_composition` is defined twice | Wrong | One definition, `autornd/engine/phases.py:96` |

## What the architect accepts

**Accepted:**

- Freeze the keys and version them.
- Build a hard tier, run at n≥3, before deciding anything about the pipeline. Six textbook questions cannot test the project's bet.
- Withdraw the report's success criterion, "6 of 6 through the fast path": a single call meets it.
- Do not escalate into the pipeline that already fails.
- Drop "the golden set's wrong answers as the check's test suite": it overfits.
- Checks report passed, not checked or unavailable, never "no issue found" as if verified.
- A judge is not a check.
- Retrieval means fetch, a versioned source, span verification and applicability.
- Add a stronger single model as the economic reference arm.
- Shrink the governance relative to the product.

**Overstated:**

- F1's verdict that the comparison is meaningless. The pipeline scores did not move under any key repair, and two readers confirmed the direct answers by hand.
- F11's "drop the command channel". The agent-built record is part of the owner's stated mission. The owner ruled on 2026-10-02 that the system setup stays the same.

## The plan the owner approved, 2026-10-02

The owner answered:

- **"give the command to start phase 0-1"**: Phases 0 and 1 go ahead.
- **"2 yes"**: default API bounds, and the end of the open quick start.
- **"3 general"**: the tier-2 questions are general engineering.
- **"4 when it arises"**: the Phase 2 budget is authorised at its spend gate.
- **"5 the system setup stays the same"**: the advisor and executor roles are unchanged.

The phases:

- **Phase 0:** record this review and freeze the scoreboard (ARCH-20261002-108, Ruling D44).
- **Phase 1:** stop the live bleeding.
    - Workflow identity (109).
    - No open, unbounded spend (110, Ruling D45).
    - An approval means something was checked (111, Ruling D46).
- **Phase 2:** a general-engineering tier of 20-30 verifiable, decomposable questions where one call is expected to fail. Five arms run at n=3: one cheap model; that model with evidence and recomputation tools; complementary models; one stronger model; and the current pipeline.
- **Phase 3:** fetch and span verification, with eCFR as the first adapter. A deterministic test of whether the request names a source decides which questions go through it.
- **Phase 4:** the narrow fast path, as a workflow file with task-specific checks and an honest "unresolved".
- **Phase 5:** the pipeline's fate, decided on tier-2 data.
- **Phase 6:** proportionate process.

## Review A, verbatim

```text
Findings, severity-ordered
F1. The scoreboard was repaired against the answers it scored
Observation. evals/golden/SOURCE.md lists five key repairs. Four of them were triggered by correct answers that failed the key (107's Q3/Q4 LaTeX, Q5.8 ordering ×2, Q5.6 wording), and one by a fabricated quotation passing a false positive. All repairs were then applied retroactively to runs 102, 106 and 107. score.py::item_holds is a conjunction of regex all patterns and negated none patterns over normalized text — "holds every item" means "contains these strings," not "is correct." One run per question.

Why it matters. The headline claim — 6/6 direct vs 3/6 and 2/6 pipeline — is computed under an acceptance region that was widened until the direct answers passed it. That is not a measurement of the pipeline; it is a measurement of the key's drift. The report discloses this (three paragraphs down, admirably), but disclosure does not un-contaminate the number, and the executive summary leads with it. Everything proposed downstream — D44, the cascade, the "escalate on check failure" trigger — is derived from this comparison.

Opinion. This is the finding that blocks the others. No pipeline decision should be made on it.

Option. Freeze the keys now, in writing, and treat any further key change as a new key version scored against all runs including the new one. Then rebuild the comparison on the harder tier before touching the graph. Trade: you delay the redesign by the time it takes to write 20–30 real questions, which is the time you were going to spend debugging pipeline changes anyway.

F2. The redesign optimizes a benchmark that does not test the hypothesis
Observation. The stated bet: "non-frontier models, organised well, can answer expert-level questions." All six golden questions are textbook-level and were answered 6/6 by one direct call at $0.003 each. The proposed success criterion is "the golden set passes 6 of 6 through the fast path."

Why it matters. A harness that ships a single call to one model and discards every other component satisfies that criterion exactly. The success test is satisfied by the architecture the report argues against. More subtly: the corpus was selected without regard to whether the direct model can answer it, so "the direct call wins 6/6" is a statement about this corpus, not about the pipeline. The conclusion may be right — I think it probably is — but it does not license deleting the multi-model machinery, because it was never tested on a question the machinery could win.

Option. Invert the sequence. Build the harder tier first (multi-step derivation with a checkable key, conflicting constraints, a lookup where the primary source contradicts the model's prior, a design where two defensible answers exist and the key names the trade-off). Measure direct-vs-pipeline on it at n≥3. Only then decide what the pipeline is for. Trade: the redesign slips by a week, and the architect will have to hold a position without data for a week. That is the correct trade.

F3. There is no retrieval in this codebase. Not weak retrieval — none.
Observation. knowledge/research.py::research_gaps makes one client.chat(function="search") call. ModelResponse.citations is populated from choice["message"]["annotations"][*].url_citation.url in routing/openrouter.py. There is no HTTP fetch primitive anywhere — the only outbound request in the codebase is to the model provider's /chat/completions, /models, /rerank. The knowledge store (store.py) is ChromaDB over local files and previously-ingested research blobs, character-chunked at 1000. No store ships empty.

So "citations" are whatever annotations the upstream provider chose to attach. When it attaches none — the normal case for a non-search-serving model — Finding.grounded is False, _remember declines to store, and the answer renders as "Sources: none found — treat as unverified." The 106 IA run's fabricated "direct quotes" are the predicted behaviour of this design, not a prompt defect.

Three aggravating details:

MAX_LOOKUPS = 1 bundles every blocking gap into one question, so a five-part lookup is one model call with one answer. The README's research economics ("7/8 figures at ~4800 tokens, $0.72 across eight sectors," "roughly one sector per 800 tokens") describe a per-sector lookup design the code no longer implements. That is stale measurement presented as current fact, which the repo's own Convention 24 exists to prevent.
_recall reuses any stored finding at cosine ≤ 0.35 with no TTL, no source-date check, and no revalidation. _remember stores a multi-part answer under source=citations[0] — one URL for five answers. One wrong lookup becomes a permanent wrong answer for every future run, and the "cheapest lookup is the one already answered" optimisation becomes an error-amplification mechanism.
worth_a_lookup() gates on risk, not on question type. A pure lookup question ("what does 29 CFR 1910.146 require") is precisely the case where sourcing matters most and is classified low or medium.
Why it matters. The report calls this "lookups without real retrieval" and proposes eCFR. That proposal is right in direction and understated in scope: it is not a config change, it is a new capability — fetch, chunk, span, verify — and it is the single highest-value thing in the redesign.

Option. Build fetch(url) -> text and make the lookup path: resolve to a source → fetch → extract the relevant section → require the answer to quote spans → verify each span by exact substring match against the fetched text. Store only verified spans, with the source date, and TTL them. Do not gate this on triage risk; gate it on "does the request name a standard, part number or document," which is a deterministic string test, not a model classification — triage is the least reliable component in the system (they measured Q6 as low in one run and critical in the next) and putting a retrieval decision on it reproduces the same instability. Trade: you need one fetch adapter per corpus and a chunker that preserves section identity. eCFR alone does not generalise; treat it as the first adapter, not the design.

F4. The revision loop is an artifact ratchet
Observation. D33 instructs implement on every iteration after the first: "you are editing your previous implementation… Preserve every part that the success criteria judged correct; change ONLY what the diagnosis and the unmet criteria require." The full previous artifact is pasted into the prompt. Criteria accumulate across plan → feasibility blockers → validate evidence → review findings → coverage.missed. The implement prompt has a max_tokens of 32,768 and grows every iteration.

Why it matters. This mechanically explains the sprawl measurement (22–32× the key answer) and it explains why the pipeline gets worse the more it iterates — each iteration costs more tokens, takes longer, and surfaces more surface area for a reviewer to object to. The report observes that "review found real errors, mostly in content nobody asked for." That is the ratchet's downstream symptom, not an independent defect. It also predicts that fixing the judges without fixing this will reproduce the same failure at a higher iteration count.

Option. Bound the artifact, not the iteration count: a hard character ceiling on summary enforced as a schema constraint, and on the third iteration discard prior_summary and rebuild from the plan with the accumulated findings. Trade: you lose the "the fixer must see the artifact containing the bug" property D33 was bought for — so keep the revision path for iterations 1–2 only, which is where the measured failures were.

F5. Feasibility review cannot gate, and it re-imports the sprawl D43 was written to remove
Observation. run_plan_feasibility runs after plan_ready has already tested plan.ready == true. It appends to plan.blockers, and nothing in the graph reads those as a gate — confirmed by the report's own note and by the YAML, where feasibility has no downstream gate. Its only effect is that plan.blockers is rendered into the implement prompt as "FEASIBILITY CONCERNS (from domain specialist review — address these)." Up to seven specialists run in parallel (DOMAIN_LEAD_MAP/roster at critical risk).

Why it matters. D43 (scope: "the request sets the scope") constrains the plan's criteria. Feasibility runs after that constraint exists and injects fresh work items the request never asked for, as instructions. It is a second, uncontrolled criteria channel that opens after the scope rule was closed, and it is paid at up to 7 calls per run for zero control power.

Option. Delete it, or demote it to non-instructional text ("considerations a reviewer raised; not requirements"). Trade: you lose a genuine independent pre-build check on plans. Given that it cannot stop anything, the check's value is currently only in what it tells the implementer, and that is precisely the harmful part.

F6. The documented quick start is an unauthenticated, unbounded, money-spending endpoint
Observation.

README.md: docker run -p 8100:8100 --env-file .env autornd. -p 8100:8100 binds 0.0.0.0 on the host.
config.py: api_key="", jwt_secret="", registration_enabled=True. README's own auth-priority rule: "with no auth configured, any caller can see every workflow and spend your credits."
routes.py: no route on the router carries an auth dependency. _get_user_id(request) reads request.state.user_id if a middleware set it, and that is the entire enforcement. POST /api/workflows (202, spends money), POST /api/workflows/sync, PUT /api/settings, POST /api/profiles/{name}, GET /api/knowledge/stats are all open.
PUT /api/settings writes the process-global settings object. escalation_max_tokens is an unbounded integer — an unauthenticated caller can raise a token ceiling process-wide. max_iterations is capped at 20; the rest are not.
GET /api/episodes does not filter by user_id, unlike /api/workflows. It returns every workflow's request, verdict and cost to any caller, authenticated or not.
run_time_budget_seconds defaults to None, so GraphExecutor is constructed with time_budget=None and the D38 watchdog never arms. The default configuration has no wall-clock bound.
No rate limiting, no queue depth cap, no dedupe on POST /api/workflows.
Why it matters. This is the only finding that is exploitable by someone who did not choose to attack you. Everything else in this review is about correctness of answers; this is about someone else spending your money, reading your requests, and raising your ceilings.

Option. (a) Refuse to start on a non-loopback bind without api_key or jwt_secret set, with an explicit ALLOW_UNAUTHENTICATED_REMOTE=1 override — roughly ten lines, no architecture change. (b) Ship a non-None run_time_budget_seconds default. (c) Add Depends(auth) to the mutating routes. (d) Filter /api/episodes by owner. (e) Bound PUT /api/settings to loopback. Trade: the zero-config quick start stops working, and the README's "designed for private-network use" has to become an enforced statement rather than a plea.

F7. POST /api/workflows returns an id that will never update
Observation. submit_workflow inserts a Workflow row, commits it, and returns its id. It then hands off to _run_workflow_bg, which loads that row and calls engine.execute(workflow.request). WorkflowEngine.execute begins with workflow = Workflow(request=request, status=PENDING); self.session.add(workflow); await self.session.flush(). Two rows are created; the one the caller holds stays PENDING forever.

Why it matters. The async path — the one the README offers for long runs, and the only one that could survive a 600-second call — hands back a dead handle. Callers poll /api/workflows/{id} and watch "pending" indefinitely while a second, invisible run bills the account. Combined with _NODE_STATUS in workflow.py being unused on this path (phase saves are buffered in pending_saves until the run ends), a caller has no way to observe or attach to a run in flight.

Option. Pass the row into execute instead of letting it create one, and flush pending_saves on a timer or per node so status advances. Trade: none. This is a bug, not a trade.

F8. Process-global mutable state is shared across concurrent runs
Observation. Module-level mutable state that changes the answer: settings (mutated by PUT /api/settings), the active profile and specialist registry (set_profile/reload_specialists, called by POST /api/profiles/{name}), _rerank_mode in context.py, _refused_lookups in research.py, and one on-disk ChromaDB path. BackgroundTasks runs workflows concurrently in the same event loop.

Why it matters. One unauthenticated POST /api/profiles/{name} changes the grounding for every run in flight. _refused_lookups is a process counter, so a failed lookup under one user's run is attributed to another user's record — which is precisely the misattribution Convention 26 forbids. The knowledge store means one user's looked-up fact becomes another user's grounding. The per-user workflow isolation the README advertises covers the record, not the answer.

Option. Scope profile/settings to a run context object; give each profile its own Chroma collection name; make _refused_lookups and the rerank probe per-run. Trade: a real refactor through adapter.py — the one file I could not read in full.

F9. The spend guard does not hold under retry, and transport failures are unclassified
Observation. _guard_spend() bounds one call's worst case. The 429 handler re-posts the identical payload up to _RATE_LIMIT_ATTEMPTS=3 with 2s/4s backoff, with no re-guard. _account() runs only after a response arrives. httpx.AsyncClient(timeout=120.0) is fixed and unparameterised, and a read timeout is not one of the three counted retry classes.

Why it matters. The F3 guard's guarantee ("a call whose worst case could not fit is not made") is violated on the exact path the guard was written for — which is the likely origin of the documented $0.012 overshoot. And a reasoning model that runs past 120 s produces a raw httpx.ReadTimeout that ends the run as an infrastructure fault, is not counted in retries_by_kind, and records none of what was billed. This is the same defect class as the meter-epoch bug that AGENTS.md flags: cost recorded at one site, spent at another. The codebase has now rediscovered it three times in three different places.

Option. _account on failure paths too; classify transport errors as a fourth retry class; re-run _guard_spend before every retry. Trade: none.

F10. Loop bounds and the latency target are mutually exclusive by construction
Observation. One question can traverse: build_loop (5 iterations) → escalation → recovery_loop (3) → escalation → review_rework_loop (2) → escalation. Each iteration re-runs implement + domain_review + coverage + consistency + validate. The golden scorer marks a question failed if it misses 300 s or 600 s.

Why it matters. At six to eight calls per body, that path is 40–60 calls. It cannot finish inside 600 s, so the scoreboard penalises the pipeline for a property of its loop bounds, not of its answers. 102's 740 s and 094's 3,600 s are this arithmetic, not model slowness.

Option. Make escalation a separate workflow file with its own small budget, invoked by the fast path, not a branch inside the same graph. The "workflows are data" design already supports this and it makes the cost of escalation a visible number instead of a surprise. It also directly implements the report's D44 with no code change — the cascade is a two-node graph. Trade: the loop wiring exists twice.

F11. The governance layer is roughly an order of magnitude larger than the thing it governs, and that is measurable
Observation. 708 commits, 122 PRs, 64 command files, 43 rulings, 1,167 tests, 20 days, for a system with about six measured live runs — of which 0/7 shipped after the 09-29 lineup change. The report's own count: about 8 of 10 commands were instrument and record work. ci.yml uses fetch-depth: 0 so that one test can assert a sha named in a document is an ancestor of the commit under test; the other three jobs are test matrix, packaging, container.

Why it matters. The cost is not aesthetic. The one measurement that settled the architecture — the direct-call baseline — arrived last, after the instrument work it did not need. And the advisor/executor split is not free: the report records merging two PRs out of order, once merging without re-reading HEAD, carrying an unreviewed implementation. That is the predictable failure of a two-role protocol with a file-based handshake and no shared state, and it happened twice.

Opinion. The conventions that encode epistemics — 22, 26, 28, "an instrument's test simulates the condition it watches," "no evidence must never be reported as no problem" — are genuinely good and they are why this report exists. The conventions that encode document hygiene are not, and they are the majority.

Option. Keep: pre-registration of paid runs, the golden set, hand-reading, and the instrument/behaviour boundary. Drop: the command channel, the document-count guards, the conventions about doc formatting. Collapse to one agent role with a reviewer. Trade: you lose the audit trail this report is built on — but git history is the audit trail, and it is better than the one being reconstructed.

F12. Smaller items worth naming
Report accuracy. "Five required CI checks" — ci.yml has four jobs. If branch protection requires five, the fifth lives outside the repo, which is itself worth knowing. The executive summary's "6 of 6 in $0.019" carries no adjacent note that the key was repaired against those answers; the caveat is two pages down.
MAX_CONTEXT_CHARS = 32000 silently truncates concatenated project documentation in manifest order. Grounding is described as "the single biggest lever on output quality," and the lever silently drops the tail of the document list. Rank, then truncate, then record what was cut.
Three sources of truth for token caps. settings.plan_max_tokens (32,768), judge_max_tokens (8,000), and max_tokens: in the workflow YAML. run_review's parameter default is settings.plan_max_tokens — a review verdict budgeted at the plan ceiling on any path that does not thread the node value. I could not read adapter.py in full to confirm which path threads it; this needs checking, not assuming.
RERANK_PROMPT and RERANK_CANDIDATES are each defined twice in context.py, ~120 lines apart, with drifted wording. Harmless today; a merge hazard tomorrow.
enforce_triage_composition exists twice — once in phases.py (called), once as an unused @staticmethod on WorkflowEngine. The live one is correct.
WorkflowStatus(state.status) runs outside the try/except in execute(). Any workflow whose terminal string is not an enum member raises after the run and before the commit, losing the result.
The planner defect is narrower than the report says. The report frames D36 as "plan rules written for design work." The actual defect is that plan rule 2 — "UNKNOWN IS A BLOCKER, NOT AN ASSUMPTION" — is unconditional. Making it conditional on question type is one prompt edit, not a redesign.
What I would actually do
Not a redesign. The graph engine, the typed verdicts, the free-check discipline, the spend accounting and the watchdog are sound and worth keeping. What is wrong is that the default path is the full pipeline, and that the measurement apparatus cannot tell you whether anything works.

In order:

Fix F6 (security), F7 (dead handle), F9 (accounting on failure). Hours.
Freeze the golden keys. Write the hard tier — 25 questions where a direct call is expected to fail. Score it by hand. n=3. This is the gate on everything else.
Build fetch + span verification. One adapter (eCFR). No risk-based gating.
Ship the cascade as a workflow file: answer → check → escalate, where check is arithmetic recomputation and span matching only. No judge in the fast path — one judge is what failed on Q3 in both runs.
Bound the artifact (F4) and delete or demote feasibility (F5).
Only then decide the pipeline's fate, on tier-2 data.
What I could not judge, and what it would cost to judge
autornd/graph/adapter.py and spec.py — the fetch tool truncated both mid-file. How max_tokens is threaded from YAML to phases, and the exact execution_order semantics, are unverified. Missing piece: those two files, untruncated.
The traces (docs/traces/102|106|107*.jsonl) are too large to read here. Every number I cite comes from the report's own tables, cross-checked against SOURCE.md, score.py and baseline.py for internal consistency — not against the raw records. Missing piece: the traces.
_extract_json in routing/openrouter.py renders as re.sub(r".*? ", ...) in what I fetched, which would break nearly every JSON reply. I believe this is an artifact of HTML tag stripping in my fetch tool (the intended pattern is almost certainly a reasoning-block regex) and I am not reporting it as a defect. Missing piece: the raw bytes of that file.
I do not know your actual domain. If it is firmware/hardware compliance rather than general engineering, F3's retrieval adapters and F2's hard tier should be scoped to it, and the whole question of whether a pipeline earns its cost looks different than it does for general technical QA.
On your four probing questions
Which hard questions would show the pipeline winning? Questions where correctness decomposes into parts with independently checkable answers and the composition is where models fail: a five-constraint sizing problem where each constraint is separately derivable; a standards question where the primary source contradicts the model's prior; a design where two defensible architectures exist and the key names the trade-off. Not "harder trivia" — decomposable questions with a checkable composition.
Which cheap check? Recomputation and span matching. Those are the only two that can fail for a reason you can point at. Self-consistency measures variance, not error — a confidently wrong model is perfectly self-consistent. A single judge is a coin flip that costs money, and you have already measured it refusing correct work twice.
Regulatory retrieval? Fetch and span-match. But do not build the check around the golden set's "known wrong answers become the test suite" idea — that trains a classifier on the observed error distribution of six textbook questions and will report ~100% accuracy and near-zero real recall. That is the same overfitting you already did to the answer keys, one level up.
Is the governance proportionate? No. See F11.
```

## As pasted between the two reviews

```text
$0.059
24,647 tok
Favicon for openai
GPT-6.1 Sol Pro


shell
git clone --depth 1 https://github.com/ohioy000/autornd-os.git /tmp/autornd-os && cd /tmp/autornd-os && git rev-parse HEAD && ls -la
✗ exit 128
https://github.com/ohioy000/autornd-os
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/engine/phases.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/workflows/engineering-rnd.yaml
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/engine/workflow.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/graph/executor.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/graph/adapter.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/routing/openrouter.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/knowledge/research.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/knowledge/store.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/api/workflows.py
Error
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/api/auth.py
Auto
https://github.com/ohioy000/autornd-os/tree/main/autornd/api
Error
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/knowledge/context.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/graph/checks.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/models/verdicts.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/main.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/AGENTS.md
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/evals/golden/SOURCE.md
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/config.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/api/routes.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/api/dashboard.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/database.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/models/workflow.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/evals/golden/direct.py
Error
https://raw.githubusercontent.com/ohioy000/autornd-os/main/docs/preregistration-107-direct-baseline.md
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/pyproject.toml
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/tests/test_knowledge.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/api/templates/dashboard.html
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/evals/golden/baseline.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/docs/traces/107-direct-baseline.jsonl
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/graph/spec.py
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/Dockerfile
Auto
https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/profiles.py
Auto

shell
curl --connect-timeout 8 --max-time 15 -fsSL https://raw.githubusercontent.com/ohioy000/autornd-os/main/autornd/models/verdicts.py -o /tmp/autornd-verdicts.py && python - <<'PY' import importlib.util s=importlib.util.spec_from_file_location('verdicts','/tmp/autornd-verdicts.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m) print('ValidateVerdict({}):', m.ValidateVerdict(**{}).model_dump()) print('ImplementVerdict(done=False,summary=""): ',m.ImplementVerdict(done=False,summary='').model_dump()) PY
✗ exit 28
```

## Review B (GPT-6.1 Sol Pro, per the paste), verbatim

```text
1. Critical — The acceptance machinery can approve work without an actual assessment
Observation — source: In autornd/models/verdicts.py, ValidateVerdict defaults green and red_cause to None, and evidence to an empty list. _resolve_green() then derives green from the absence of a cause. Consequently, an empty JSON object becomes a passing validation.

ImplementVerdict also permits an empty summary and done=False; the workflow’s judges node reads implement.green, not implement.done.

Two further checks do not enforce what their names imply:

Feasibility appends hard blockers without changing plan.ready.
The automatic independent_check produces a ship verdict, but no subsequent gate reads it. The executor can finish completed after that reviewer says not to ship.
Why it matters: The harness confuses “no failure was reported” with “the required assessment was completed and passed.” This is more serious than excessive blocking: it undermines the meaning of approval.

Opinion — option I’d take: Define explicit acceptance invariants before changing the pipeline:

A deliverable must exist and be complete.
A checker must distinguish passed, failed, not_checked, and unavailable.
Each blocking verdict must have an actual consumer.
Validation must identify which required claims were assessed; an empty assessment cannot pass.
Trade-off/cost: Some previously accepted responses will become incomplete or unverified. That reduces apparent success rates, but makes those rates meaningful. Do not compensate with unlimited schema retries.

2. Critical — The asynchronous API runs a different workflow from the one it returns
Observation — source: In autornd/api/routes.py:

submit_workflow() creates and commits a user-owned pending workflow.
_run_workflow_bg() loads it.
WorkflowEngine.execute() creates another workflow rather than executing the existing one.
The new workflow receives no user_id. The synchronous endpoint also calls execute() without propagating ownership.

Why it matters:

The asynchronous caller polls an ID that the execution path never updates.
The actual result is attached to a second, unowned record.
Authenticated list/detail queries filter by ownership, so users can lose access to the results they paid for.
This is an application correctness defect independent of model quality.
Opinion — option I’d take: Make workflow creation and workflow execution separate operations. Execution must take an existing workflow identity and immutable owner identity. Both submission paths should use that same contract.

Trade-off/cost: A contained API/engine refactor and real endpoint integration tests. No new orchestration framework is needed.

3. High — Production execution is neither durably checkpointed nor reliably recoverable
Observation — source: autornd/engine/workflow.py collects completed phases in pending_saves and writes them after execution ends. The initial workflow insert is flushed, but the transaction is committed only at the end.

The asynchronous execution mechanism is FastAPI BackgroundTasks, not a durable queue. _NODE_STATUS exists, but the graph execution path does not use it to update live progress.

Why it matters:

A process crash can discard completed, paid-for work.
Restarting does not reconstruct the execution state.
The dashboard cannot observe genuine phase-by-phase progress.
With SQLite, the flushed insert can hold a write transaction across lengthy provider calls, delaying other database writers.
The eval runner’s incremental JSONL retention does not establish equivalent reliability in the application.
Opinion — option I’d take: Persist immutable node-completion events as they occur, with short transactions. Add a durable job record and a single worker with a lease. Initially, restart interrupted work from the last completed safe boundary—not an imagined exactly-once provider call.

Trade-off/cost: More persistence and recovery logic. A single SQLite-backed worker is sufficient initially; Redis, Celery, and a database migration to PostgreSQL are not prerequisites.

4. High — Spend limits are not hard limits, and the application does not arm them
Observation — source: In autornd/routing/openrouter.py:

API-created clients do not receive a spend or call ceiling.
_guard_spend() checks completed spend, without reserving funds for concurrent calls.
Reviewer fan-out uses asyncio.gather(), so several calls can each pass against the same remaining balance.
Prompt tokens are estimated from characters divided by four, which is not a worst-case bound.
Missing pricing permits the call and records blindness.
rerank() does not use the pre-call spend guard.
Call ceilings are checked after a response.
The production wall-clock budget also defaults to unset.

Why it matters: The report treats overspending largely as an apparatus repair already completed. The current design still cannot guarantee an authorization cap. Large token ceilings make this particularly damaging.

Opinion — option I’d take: Require application-level budgets and atomically reserve estimated maximum liabilities before dispatch, including parallel calls and retries. Release unused reservations after reconciliation. Unknown prices should require an explicit operator allowance, not silently defeat a hard cap.

Distinguish observed spend, estimated spend, and outstanding liability. Cancellation does not establish that provider billing stopped.

Trade-off/cost: Conservative reservations can refuse calls that would have been cheap. Smaller task-specific ceilings and explicit budget extensions improve utilization without pretending the cap is exact.

5. High — Retrieval currently promotes model-generated answers into reusable “facts”
Observation — source: In autornd/knowledge/research.py, a finding is grounded whenever its citations list is nonempty. The harness stores the search model’s answer, not a fetched and checked source passage.

_recall() reuses the nearest stored research chunk as the answer. There is no claim-to-passage verification, applicability check, or effective-date check. Its comment describes squared L2 distance, while store.py configures cosine distance.

Why it matters: A citation proves that a URL was attached—not that the URL supports the claim. One wrong cited answer can become persistent context and contaminate later runs.

The proposed quotation matcher fixes fabrication of quotation text, but does not establish that the quotation answers the question correctly. A genuine passage can still concern the wrong jurisdiction, date, component revision, exception, or applicability condition.

Opinion — option I’d take: Retrieve and retain primary-source text with document identity, version/date, retrieval timestamp, content hash, and exact passage locations. Keep generated interpretations separate from source evidence.

For regulatory answers, check:

Source identity and requested date.
Exact quotation correspondence.
Coverage of the requested requirements.
Applicability, exceptions, and cross-references.
Use official eCFR material for current regulatory text, and appropriate historical official sources when the requested date requires them.

Trade-off/cost: Source connectors, parsing, version management, and more explicit “not established” answers. This is work that can justify a harness; additional unsupported reviewers cannot.

6. High — Knowledge and configuration are not isolated by project or run
Observation — source: store.py uses one collection, with no project or user metadata filter. Research recall filters only on tag="research".

File ingestion uses IDs derived from a tag and chunk index, then skips existing IDs. Editing an already ingested document therefore does not replace its existing chunks.

Profiles and settings are process-global and runtime-mutable. Phase functions repeatedly consult those globals during execution.

Why it matters:

Project A can retrieve Project B’s documentation.
Corrected documentation can remain stale in the knowledge store.
A profile change during a run can change later specialist behavior and constraints.
The result cannot reliably be attributed to one configuration snapshot.
These defects matter even in a single-user installation with several projects.

Opinion — option I’d take: Give each run an immutable configuration/profile snapshot. Namespace retrieval by project, and by tenant if multi-user operation remains supported. Version or replace documents explicitly; do not treat ingestion as append-only knowledge.

Trade-off/cost: More metadata and cache invalidation. The alternative is simpler operationally but invalidates both grounding and reproducibility.

7. High — The report’s “shipping, not answering” diagnosis is too narrow for the actual project goal
Observation — report and trace: The direct baseline demonstrates that one selected engineering model answered six relatively elementary questions correctly in one recorded attempt each. 107-direct-baseline.jsonl supports the reported answers, timings, and costs.

It does not demonstrate expert-level performance or an advantage from combining cheaper models. The IA result already shows a substantive answering failure.

Why it matters: You could implement D44, pass the six golden questions, and still have made no progress on the original bet.

There are two unproven hypotheses:

A useful checker can distinguish correct from incorrect direct answers.
Escalation improves answers that the direct path gets wrong.
Routing to a pipeline that already fails is not a recovery strategy merely because it is called escalation.

Opinion — option I’d take: Stop treating the existing full pipeline as the destination of the redesign. Keep it as an experimental comparison arm.

Evaluate at least these alternatives on the same held-out tasks:

Arm    What it tests
One inexpensive model    Whether a harness is needed
That model plus evidence/tools    Value of external information and computation
Targeted complementary models    Value of model cooperation
A stronger single model    Whether the coalition is actually economical
A stronger baseline does not need to become the shipped product. It is necessary to test the economic claim.

Trade-off/cost: Less feature development and more evaluation spending. The cost buys evidence about the product, rather than evidence that its workflow terminates.

8. High — D44 needs a coverage-aware checking policy, not “one cheap check”
Observation — proposal: D44 describes a generic direct answer, deterministic checks, then at most one independent judge. Existing deterministic checks mainly inspect prose overlap and consistency with a generated plan.

Why it matters: A generic checker can cheaply confirm that an answer looks plausible while missing its decisive error. A judge that sees the proposed answer may reproduce its assumptions rather than independently test them.

Self-consistency also detects instability, not truth. Several inexpensive models can confidently agree on the same wrong rule.

Opinion — option I’d take: Route by verification need, not just risk or apparent difficulty:

Task    Check that can earn its cost
Numerical derivation    Recompute from independently extracted inputs; verify units and assumptions
Boolean/state logic    Enumerate cases or check explicit invariants
Regulatory lookup    Primary-source evidence, applicability, and requirement coverage
Constrained selection/design    Check stated constraints and challenge load-bearing assumptions
Open technical analysis    Targeted independent criticism, explicitly labeled as incomplete verification
A checker should report what it checked and what remains unchecked. “No issue found” must not mean “verified.”

Use multiple models where they contribute different evidence or capability: independent derivation, source interpretation, constraint checking, or a genuinely competing hypothesis—not several personas reading the same plan.

Trade-off/cost: You lose the simplicity of one universal green/red gate. You gain checks with defensible coverage. For arbitrary expert questions, complete cheap verification is not available.

9. High — The revision loop does not reliably receive the failure that caused another iteration
Observation — source: In autornd/graph/adapter.py, _phase_validate() appends to failure_log only when validation or implementation is red.

But judges also refuses convergence when coverage or consistency fails. A consistency-only failure can therefore trigger another implementation without placing that failure in the feedback log. Coverage misses have a separate feedback path; consistency conflicts do not have an equivalent one.

Escalation clears failure_log, while retaining other outputs and the prior implementation. Its architectural_correction is not applied as a revised plan.

Why it matters: The harness can spend iterations revising work without telling the model what actually failed. Clearing one log does not create a clean recovery context, and a corrected architecture expressed in prose does not repair the fixed criteria contract.

Opinion — option I’d take: Represent each failed check as a structured issue linked to an artifact version and requirement. Revision consumes the current unresolved issue set. If the plan or requirements must change, create an explicit new version and invalidate dependent assessments.

Bound retries by new evidence or a specific actionable correction, not merely by disagreement.

Trade-off/cost: More explicit state modeling; fewer opportunities for an unconstrained rewrite to accidentally solve the problem. It also prevents blind retries from masquerading as progress.

10. High — The “deterministic checks” are heuristic gates, not correctness checks
Observation — source: autornd/graph/checks.py compares numeric values by shared unit. A unit avoids a conflict when any plan value agrees with any implementation value.

For example, a plan containing a connection timeout of 60,s and retry delay of 5,s can share the value 5,s with an implementation while the timeout incorrectly becomes 600,s.

Coverage uses term overlap and cannot generally distinguish a requirement being implemented from being negated or discussed.

Also, failed free checks do not automatically prevent the paid validator from running: dependency ordering is not short-circuiting.

Why it matters: Determinism means repeatable behavior, not a reliable inference. These gates can both reject correct answers and miss contradictions—the exact failure pattern the report describes.

Opinion — option I’d take: Demote prose-overlap and unit-bucket checks to advisory lint. Use blocking deterministic checks only where operands and their semantic identities are explicit: named quantities, equations, limits, truth tables, or source spans.

Trade-off/cost: Less claimed coverage and some additional structured extraction. The reward is fewer false blockers and fewer false approvals.

Direction I would take
Opinion: This needs a partial architectural redesign, not a stack rewrite and not merely a fast-path patch.

Retain Python, FastAPI, typed artifacts, the provider boundary, and useful executor components. Replace the default operating model with:

Request contract → direct answer or required evidence acquisition → task-specific checks → one bounded targeted correction or explicit unresolved result.

Do not automatically escalate to the existing full pipeline. Make escalation earn its place experimentally.

Priorities:

Repair acceptance, workflow identity, ownership, persistence, and spending.
Establish real source acquisition and versioned evidence.
Ship the narrow direct path without claiming universal verification.
Test complementary-model cooperation against equal-budget alternatives.
Remove stages that do not improve held-out delivered correctness.
The project should be generalized at the execution and evidence layers, but specialized at the verification layer. A generalized committee is not a generalized expert.
```
