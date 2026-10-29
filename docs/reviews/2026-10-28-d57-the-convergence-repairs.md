# D57: the convergence repairs (advisor, 2026-10-28)

**Status: ruled by the advisor on 2026-10-28.** Command ARCH-20261028-129 carries it, with an amendment to D56. It is free work: no paid call, no `.env` change, and no DB schema change.

This is step 5 of the generality-first order the owner approved on 2026-10-21: finish the convergence repairs. Four properties were named that day, each to be shown by tests that call no provider:

- a correct draft ships;
- a block without evidence cannot stop it;
- a run that does not settle returns its best draft;
- a revision is not forced to grow.

D51 (2026-10-10) named the causes: a yardstick the run wrote itself, vetoes without evidence, a terminal that threw the work away, and a revision ratchet. Its repairs and the fix plan of 2026-10-15 (#176 to #185) closed most of them. This ruling closes what they missed. Each gap below was shown by a provider-free probe on main at 2705e4d.

## 1. What is still wrong

| | where | what the probe showed |
|---|---|---|
| 1 | `graph/adapter.py` `_phase_implement` | **A revision is told to fix notes.** Coverage's misses reach the next attempt under "THE PREVIOUS ATTEMPT LEFT THESE SUCCESS CRITERIA UNMET — satisfy each one", and in the cause line, though coverage has been a note since R1. In a rework, every review finding reaches the revision under "resolve each one": the anchored one, the one demoted from critical for having no anchor, and a low one. All three come again as a Python object's repr under the UNMET heading. D51 (3) rules that a revision "receives only the anchored dissents". The two channels are D21's read of `coverage.missed` and D24's `rework_extra`. Both are older than R1 and D51 and were never brought in line. |
| 2 | `engine/phases.py` `run_doublecheck` | **The independent check can veto with no anchor.** Its `ship: false` ends an unrecallable run blocked, and its `critical_issues` are free text. Every other judge that can block has been held to an anchor since D51 (3); this one was missed. |
| 3 | `engine/workflow.py` | **The API drops the candidate.** The executor keeps the last answer of a run that ends blocked or escalated (D51 (7)), but the API path never saves it. A caller sees the status and the error, never the answer the run wrote. |
| 4 | `graph/executor.py` `_approved_pointer` | **The record undercounts agreement.** D38's pointer finds "the last implementation the build judges agreed on" by looking for an empty dissent list. That list still names coverage and consistency, which are notes. So an answer the judges agreed on beside a coverage note reads as never agreed. |

Found while reviewing command 128: D56 left a gap on purpose (its §3). A fetch checks a name's addresses, and then the connection resolves the name again. So a name that answers one way to the check and another to the connection gets through. D56 deferred this "if the harness is ever served to others". The repo is public, and its Dockerfile serves on all interfaces. That condition already holds, and the fix turned out small.

## 2. The ruling

> **Ruling D57 (advisor, 2026-10-28): the convergence repairs.**
>
> **(1) A revision receives the anchored dissents and nothing else.** The implement phase no longer reads `coverage.missed`, and D24's `rework_extra` is removed. What a revision is told comes from the failure log alone. The log's writers keep the notes apart:
> - validate's entry puts coverage and consistency under `notes`, so its `red_cause` names only the fold's own judges;
> - validate's evidence lines are logged only when validate dissents;
> - review's entry keeps, under `review_findings`, only the findings still at critical or high after `run_review` has demoted the unanchored ones; the rest go under `review_notes`;
> - review's cause is stated from typed fields: "Review blocked on N anchored finding(s)", or, when the review did not complete, how many reviewers did.
>
> The notes stay in the log for the escalation's autopsy and for the record. D21's channel and D24's second copy are superseded.
>
> **(2) The independent check vetoes only on an anchored issue.** An issue is a `ReviewFinding` and carries its anchor in the same fields: an ask, a quote of the request, a hazard with the answer's own words, or a wrong fact with its source. `run_doublecheck` applies `dissent_anchored`, the test review applies. An anchored issue is kept and marked critical. An unanchored one moves to `notes` and is counted, as `unanchored_dissent` or, for a wrong fact with no source, `unverified_dissent`. The check's `ship` is computed: true exactly when no issue is anchored. Its own `ship: false` with no anchored issue is a note, as a reviewer's is. The prompt states the anchor rule in review's words. A bare-string issue still loads, and anchors nothing.
>
> **(3) The candidate reaches the caller.** When a run ends without a delivered answer after an answer exists, the API path records the executor's candidate as a zero-cost phase record, `candidate`, as D55's `workflow` record is written. The record carries the last answer, unendorsed, and its open dissents with their anchors. It also carries D38's pointer, and the answer the pointer names when that answer is not the last. `GET /api/workflows/{id}` returns the record as `candidate`. A completed run has none.
>
> **(4) The record says whether the judges agreed, and how long each answer was.** Each judged iteration records `agreed` (implement and validate both green, which is every workflow's build fold; a test guards that) and `answer_chars`. A partial iteration records `agreed: false`. D38's pointer reads `agreed`. The dissent list is unchanged: it still names every judge that was red, notes included.
>
> **D56, amended.** A fetch connects to the address its check approved: the request goes to that address, with the page's name in the Host header and as the TLS server name. The name is resolved once per hop, by the check. The client takes nothing from the environment (`trust_env=False`): no proxy, which would resolve the name itself, and no `.netrc` credentials sent to a quoted page.
>
> **Rationale:** the probes in §1. D51 (3) and R1 already say what a revision receives and what blocks. D51 (7) already says what an unfinished run keeps. This ruling makes the code do it in the places it did not.

## 3. What proves it, provider-free

`tests/test_convergence.py`, 17 tests, through the real graph and the API path's engine, behind the recording double of `tests/test_d51_acceptance.py`:

- **(1)** A revision after an anchored validate dissent carries the dissent and no coverage miss. A rework after review carries the anchored finding and neither note, and no repr. A revision after an anchored domain concern carries the concern and not validate's passing lines. The notes are in the log.
- **(2)** Seven cases on `run_doublecheck`: an unanchored issue, no issue, an issue naming its ask, one quoting the request, a wrong fact without its source, and a hazard with and without the answer's words.
- **A correct draft ships.** A correct first answer on unrecallable work meets an unanchored objection from every judge. It ships with no revision.
- **(3)** A blocked run's caller reads the last answer and its open dissent. When review blocks an agreed answer and validate dissents from every revision, the caller also gets the agreed answer. A completed run has no candidate.
- **(4)** An answer agreed beside a coverage note is recorded as agreed, and the pointer finds it. Each iteration records its length. Every workflow's build fold is implement and validate.

`tests/test_source_check.py` gains two tests: the request goes to the checked address, with the name in the Host header and as the TLS server name; and the client trusts nothing from the environment.

Every test has a break-proof in the command's Task 7. Four existing tests change because each enshrined the old rule (convention 17):

- two in `tests/test_iteration_dissent.py`, which asserted that coverage and consistency are a cause;
- one in `tests/test_engine.py`, whose veto used a bare-string issue;
- one in `tests/test_failure_path_terminal.py`, which read `_phase_implement`'s source for the word `rework_extra`. A comment naming the retired channel would pass that check.

The independent check's prompt fixture is re-captured; its anchor block and issue fields are the only change. The no-break space that command 128's delivery dropped from a quote-check test is restored, written as ` `.

## 4. Budgets (convention 18)

No call is added. The independent check's prompt grows by 1,417 bytes. A revision's prompt shrinks by whatever notes it used to carry. Every call reserves its worst case from its own prompt's bytes, so the spend bound covers the growth unchanged. The time budget and the spend ceiling stand, re-derived as unchanged.

## 5. Not ruled here

| left out | why |
|---|---|
| **The plan gate** | A plan that says it is not ready ends the run blocked before any answer exists, with no anchor needed. D51's logic would let the build go on and leave the honest refusal to the implementer, who can block only by naming an ask (D51 (5)). But that this gate blocks is the last clause of D37, which the owner supplied. **The owner's call; see §6.** |
| A review that does not complete | Below D42's quorum, review sends a correct answer back for a revision with nothing to fix. A re-review, not a revision, may be the right response. That is D42's ruling to revisit, on the measurement's data. |
| The default workflow, and choosing one from the request | After the measurement of record (D55 §2 (8)). |
| The doublecheck endpoint's asks | `POST /api/workflows/{id}/doublecheck` runs the check without the run's asks, so an issue there anchors only by the request's words or a hazard. |

## 6. For the owner

- **Nothing to sign for D57.** It applies rulings already made (D51 (3) and (7), R1) where the code missed them, and it holds the independent check to the same rule.
- **One question, yours under D37: may a plan that says "not ready" stop the run?** Today it does, before any answer is written. If you say no, the plan's blockers go to the implementer as open points, and only an implementer naming an ask can stop the run. That would be command 130. If you say yes, nothing changes.
- **After command 129, the next step is the measurement of record (step 6), on your word.** It is a paid run.
