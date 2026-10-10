# D51 — the request is the yardstick (advisor, 2026-10-10)

The design record for Ruling D51: the theory of why the pipeline scored 0 of 21, the ruling, the pathways that could make AutoRnD-OS succeed, and the predictions, committed before command 120 is built. The owner gave the go on 2026-10-10. Command `ARCH-20261010-120` carries the ruling to the executor.

## 1. The decision

In tier 3 stage 1, every arm that answered the question directly held 17–18 of 21 answers under the frozen key. The full pipeline held none. Its plans carried the right numbers, so the failure was not knowledge. The pipeline judged its answers against a test it had written itself, and that test drifted away from the question. D51 removes the self-written test:

- The request's own words become the only yardstick.
- Every judgment that fails an answer must point at those words.
- Nothing may demand what the run cannot do.
- A run that cannot finish keeps its best candidate, instead of returning nothing.
- A second, much smaller workflow, verify-first, answers once and checks against the request. It is measured beside the repaired pipeline.

## 2. What success means

Five bars, each measurable on the record. The project's purpose is non-frontier models answering expert questions through structure (`HANDOVER.md` §0), so the bars compare structure against the same class of model called once.

| bar | meaning | measured by |
|---|---|---|
| **S1 — no harm** | On questions a single call already answers, the harness holds at least as many. | Key-held answers against arm A, paired by question. |
| **S2 — value** | On questions a single call misses, the harness recovers some. | Questions where A fails and the harness holds. Tier 4 is built for this. |
| **S3 — honesty** | When the harness cannot verify an answer, it says "unresolved" instead of shipping it. Unresolved answers are wrong more often than delivered ones. | Read the unendorsed candidates beside the delivered answers. |
| **S4 — economy** | Cost and time stay within a stated multiple of the single call. | Cost per key-held answer; median seconds per unit. |
| **S5 — record** | Every number reproduces from the repository alone. | The traces, the reading sheets, and the commands with their responses. |

Stage 1 failed S1 completely: 0 of 21 against 18. It never reached S2–S4. On S5, the record was complete except for the pipeline's internals; R1 (#165) repairs that.

## 3. Why the pipeline scored 0 of 21

### 3.1 The facts

From `docs/reviews/2026-10-06-tier3-stage1-report.md` and the trace `docs/traces/20261005T215237Z-tier3-run.jsonl`:

- **Delivery.** 20 of arm E's 21 units ended with no answer: 16 escalated and 4 blocked. All 20 took the same kind of route: draft, judge, redraft, escalate, nothing.
- **Cost and time.** Median $0.371, 911 s and 30 calls per unit. Arm A's median was $0.0064, 8 s and 1 call.
- **Not knowledge.** The Q23 plan's five numbers were exact. The pipeline failed an XOR truth table 3 of 3.
- **The plan wrote the exam (F4).** Four of the Q23 plan's six criteria demanded what the question never asked:
  - every arithmetic step inline;
  - two independent routes to each stress;
  - a presentation format;
  - kill triggers on yielding and eccentricity, which the key's `scope_out` excludes;
  - a measured 60 s "falsifier" for a hand calculation. No answer can satisfy that one.
- **The reviewers graded the invented exam (F5).** Of the 12 review findings visible in the log:
  - 9 targeted plan-invented content;
  - 3 targeted scope the reviewer invented;
  - 0 found a wrong value.
  On Q17, two findings contradicted each other.
- **Lookups blocked (F3).** All three Q17 units blocked on a check against the regulation's text, which the pipeline has no tool to fetch. Arms A–D answered Q17 from knowledge, 10 of 12 correctly.
- **Where the money went (F2).** 53% to drafts and redrafts, 31% to escalation, 8.5% to judges, 3.5% to planning.
- **Sprawl (F11).** The one delivered answer ran 7,960 characters, against about 2,000 for arm A's median.

**A gap in the record.** D38's approved pointer is computed only at a watchdog cut (`autornd/graph/executor.py`, in `_cut`). No stage-1 unit was cut, so the record cannot say whether any of the 20 had a build-approved draft that review or escalation later lost. The report's "the build loop runs to its bound" is inferred from call counts, not recorded. R1 records the route from now on, and D51 (7) computes the pointer at every unfinished terminal.

### 3.2 The mechanism is written in the prompts

None of this needs a model to misbehave. The pipeline does what its text tells it to:

- **The plan prompt** tells the architect its success criteria are what "every later phase is judged against … and nothing else" (`autornd/engine/phases.py`, the plan prompt).
- **The assessment contract** tells every validator that the criteria are fixed, and that "where the work and a criterion disagree, that criterion FAILS — whichever of the two looks more sensible to you" (`ASSESSMENT_CONTRACT`).
- **The review prompt** hands reviewers the plan, so they judge the answer against the plan as well as the request.
- **The consistency check** compares the answer's numbers with the plan's (`numbers_consistent(plan, implementation)` in `workflows/engineering-rnd.yaml`). An answer that corrects a plan error fails it.
- **The verification override** fires a lookup when the plan's criteria demand verification. The criteria the request never asked for decide that spend too.
- **The ready-plan validator** rejects a plan with no criteria (`PlanVerdict.ready_plans_need_criteria`), so the architect *must* write a test.

D43 (2026-10-01) said the request sets the scope. It said so in prompt text, inside the very prompt that told the architect its criteria were the only standard, and stage 1 shows it was not enforced.

### 3.3 Three causes that multiply

1. **A self-written exam.** The yardstick is a document the pipeline produced about the question, not the question. Every phase can add to it: the plan through criteria, the reviewers through findings, feasibility through considerations, escalation through directives. Nothing is ever removed.
2. **Vetoes without evidence.** The build loop exits only when every judge agrees (`judges_agree`). Any reviewer can block on anything, at critical or high severity. The burden is on the answer to satisfy every judge, not on a judge to show a defect.
3. **A terminal that discards the work.** A run that does not converge returns nothing. A single call always returns its answer; the pipeline returns one only on unanimous approval.

A fourth effect feeds them: **the revision ratchet.** Every red produces a revision (D33) that must also "address" the new findings. The answer grows and offers reviewers more to find. Stage 1 spent 53% of arm E's money on redrafts and produced a 4× longer answer.

### 3.4 A small model of convergence

Suppose a draft is correct, and each iteration must pass *m* independent judgments, each failing a correct answer with probability *f*. An iteration passes with probability (1 − *f*)^*m*, and *k* iterations converge with probability 1 − (1 − (1 − *f*)^*m*)^*k*.

| f, per judgment | m = 6 | m = 12 | m = 12, with one unsatisfiable criterion |
|---|---|---|---|
| 0.05 | 0.74 per iteration | 0.54 | **0** |
| 0.10 | 0.53 | 0.28 | **0** |
| 0.20 | 0.26 | 0.07 | **0** |

The last column is the stage-1 situation. One criterion no answer can meet sets convergence to zero, whatever the answer's quality, and the loop then spends its whole budget. Reviewers with unbounded scope push *f* up, and unanimity multiplies it across every judge. D51 attacks each term:

- it removes unsatisfiable criteria at the source;
- it lowers *f* by requiring a judge to point at the request;
- verify-first cuts *m* to a handful.

### 3.5 Why one call won

A single call has one author and one yardstick: the question. It cannot fail a test it wrote, because it writes none. Its errors are its own: an omitted step (Q15) and a precision convention (Q23). Those are exactly the errors a check anchored to the request can catch. Q15's request says, verbatim, "The fixture instruction requires zeroing the readout at zero displacement". Arm A omitted that step in 2 of 3 units.

### 3.6 The general law

**A judge needs a yardstick that every phase reads and no phase writes.** Once a phase can write the yardstick, the system optimises its own proxy (Goodhart's law inside the loop), and the proxy drifts toward whatever the strongest writer cares about. In this pipeline that writer was the planner, governed by D36's rules for reasoning. Those rules are good rules for *reasoning*. Turned into *grading*, they demand derivation formats, falsifiers and kill triggers the question never asked for.

## 4. The ledger of structure

Structure can add accuracy only through a few channels, and can lose it through a few leaks. A design succeeds by opening the channels and closing the leaks.

**Where structure can add accuracy**

| channel | what structure does | stage-1 exhibit | lever |
|---|---|---|---|
| Information | supplies text the model lacks | Q17 answered from memory (10 of 12); arm B's fetch was used | fetch with span verification (P4) |
| Computation | recomputes what the model computed | arm B's `recompute` gave typed rejections the model adapted to | claim-level recompute (P3) |
| Attention | makes every ask visible and checks each one | Q15's zeroing step omitted by A twice | the asks and an anchored check (D51, P2) |
| Variance | treats disagreement among samples as the uncertainty signal | untested | self-consistency (P5) |
| Independent eyes | a different model catches a defect, with evidence | arm C's checker concurred 20 of 20; untested | anchored dissent (D51 (3)) |
| Abstention | says "unresolved" when checks disagree | none; the pipeline returned nothing | the unendorsed candidate (D51 (7)) |

**Where structure loses accuracy**

| leak | stage-1 exhibit | D51's closure |
|---|---|---|
| Yardstick drift | Q23's criteria; 9 of 12 findings on plan-invented content | the asks are the only criteria (1, 2, 4) |
| Vetoes without anchors | 3 of 12 findings on invented scope; Q17's contradictory findings | anchored dissent (3) |
| Impossible demands | Q17 blocked 3 of 3 | unavailable is not a fail (5) |
| Terminal loss | 20 of 21 no answer | the candidate is kept (7) |
| Revision ratchet | 53% of spend on redrafts; 7,960 against ~2,000 characters | a revision receives only anchored dissents (3); verify-first allows one revision (8) |
| Escalating sideways | 31% of spend; no recorded conversion | per-dissent rulings recorded (6); upward adjudication decided on data (P6) |

## 5. Ruling D51

> **Ruling D51 (advisor, 2026-10-10, on the owner's go of the same date) — the request is the yardstick. (1) The asks. Before any work is judged, the run extracts the request's asks: verbatim quotes of what the request asks the answer to give or satisfy, each with its kind — value, verdict, step, constraint or format. A model proposes them in an `asks` node on the triage tier, after triage; a free deterministic check keeps a quote only if it occurs in the request under the normalisation the checks already apply, and records every other quote as not anchored, counted. When nothing anchors, the whole request is the one ask. The anchored asks are the run's only success criteria. (2) Every judge judges against the asks and nothing else. Validate, the coverage check, domain review, review, rework review and escalation receive the asks and judge the answer against them. A judge may raise something the asks lack only by quoting the request verbatim, anchored by the same free check. (3) A dissent carries its anchor. A judgment that fails the work names its anchor — an ask, an anchored quote of the request, or a hazard — and what the answer states or omits against it, in typed fields. A hazard is something the answer states or instructs that would, followed as written, injure a person or damage equipment; an omission is never a hazard, and if the request asked for what is missing, it is an ask. Only an anchored dissent fails the work: validate is red only when it names a failed ask; a domain concern flips the implementation red, and a review finding blocks, only when it is critical or high and anchored; the implementer's own red counts only when it names an ask. Any other judgment is a note: recorded and counted, never blocking, and not sent to the next revision, which receives only the anchored dissents. (4) The plan is reasoning, not a yardstick. The plan no longer writes success criteria, and a ready plan no longer needs them. D36's four rules stay byte-identical and keep governing how the plan is reasoned; nothing the plan produces is judged against. Reviewers read the request, the asks and the answer, not the plan; the consistency check's reference is the request's stated figures, not the plan's; the assessment contract's "a contradiction with the plan" becomes "a contradiction with the request". D43's plan-prompt paragraph retires with the criteria it governed — its scope is now enforced by construction — and its deliverable sentence in the implement prompt stays. D46 (2) and D48 (2) are unchanged. (5) Nothing demands what the run cannot do. An ask whose verification needs what the run does not have — a source text the grounding does not hold, a measurement, an execution — is judged on what the answer states, and its verification is recorded as unavailable: neither pass nor fail, never blocking (D49 (3)'s distinction), and listed in the run's record. An implementer's blocked_on entry must name an ask; an entry that names none is a note, counted. (6) Escalation rules on each open dissent before it directs: upheld or not, against its anchor, typed and recorded; the directive addresses only the upheld dissents. Routing is unchanged. (7) An unfinished run keeps its candidate. A run that ends escalated or blocked after an implementation exists records its last answer, labelled unendorsed, with its open dissents and their anchors; D38's approved pointer is computed at every terminal that is not completed, not only at a watchdog cut. Neither counts as delivered; both are read and reported as what abstention cost. Terminal statuses do not change. (8) The verify-first workflow. A second workflow answers once and checks against the asks: triage, grounding, asks, one answer on the engineering tier from the request and the asks with no plan, the free checks, and one check on the judge tier under (3) and (5). No anchored dissent ends the run completed; otherwise one revision addresses only the anchored dissents, followed by the free checks and one more check, and a dissent that survives ends the run escalated and unresolved, with its candidate kept under (7). The standing workflow does not change; which requests take which workflow is ruled on the re-measurement's data. D36's text, the tiers, the pins, the budgets and the loop bounds are untouched. Rationale: tier 3 stage 1 (docs/reviews/2026-10-06-tier3-stage1-report.md): the pipeline held 0 of 21 answers where one call held 18; 20 of 21 units ended with no answer; the plans carried correct numbers but wrote the exam — four of the Q23 plan's six criteria demanded what the question never asked, one of them unsatisfiable by a hand calculation (a measured 60 s falsifier); 9 of the 12 review findings in the log targeted plan-invented content, 3 reviewer-invented scope and none a wrong value; all three Q17 units blocked on a verification the pipeline cannot perform; and the prompts made this the rule — the plan's criteria are what every later phase is judged against and nothing else, and a validator must fail work that disagrees with one. D43 said the request sets the scope, in prompt text, and was not enforced. The design, the theory and the pathways are in docs/reviews/2026-10-10-d51-the-request-is-the-yardstick.md. Falsifier: in the re-measurement, the repaired pipeline still trails the single call by 7 or more of 21 key-held answers on stage 1's seven questions; or a run record shows work failed, blocked or looped by a judgment with no anchor; or a delivered answer misses an item its request asked for, its asks contained it, and no judge dissented.**

### Notes on the clauses

- **(1) The model proposes and a free check verifies.** This is the house pattern. A cheap model is good at quoting; a substring check is incapable of inventing. Requiring quotes, not paraphrases, is what makes the yardstick incapable of drift. The triage tier costs a fraction of a cent per call.
- **(1) Granularity.** For Q15, the asks are:
  - the zeroing step;
  - the two reference steps;
  - the return-to-zero step "without re-zeroing";
  - the ±0.020 mm and 0.010 mm limits;
  - "Do not adjust the instrument between readings";
  - "State each signed error as reading minus reference";
  - "the overall verdict".

  That list matches the key's six items without anyone having read the key. The tier-2 questions were written decomposable, so their keys trace to their requests. That property is the reason this works, and it is also a warning: it must hold on requests outside the 25 as well. The executor never tunes the asks prompt against the keys.
- **(2) The open door.** A judge who sees an omission the extractor missed can still block, but only by quoting the request. The yardstick is closed under the request and open to every judge.
- **(3) The burden of proof flips.** An approval must still show what was checked (D46, D49). A rejection must now show where the answer gets the request wrong. The hazard carve-out keeps safety blocking. Omissions are excluded on purpose: "the answer does not mention PPE" is exactly the reviewer-invented scope stage 1 measured. If the request asked for it, it is an ask.
- **(3) Only anchored dissents reach the revision.** This stops the ratchet: the implementer is told what is wrong against the request and nothing else.
- **(4) Removing the plan from review** is the largest single change in reviewer behaviour, and the most important. The plan is the implementer's working method. The reviewers judge the deliverable.
- **(5)** extends D49 (3) from checks to asks. For Q17, the ask "what minimum unlocking strength is required" is answered from knowledge. Its source verification is recorded as unavailable instead of blocking the run.
- **(6) is a measurement, not yet a policy.** The strongest serving rules on every dissent. If it overrules most of them and the overruled answers read correct, the record will say so, and ship-on-adjudication (P6) gets ruled on that evidence.
- **(7) costs nothing and fixes the record's blind spot** (§3.1).
- **(8) is the smallest structure that could beat a single call:** one answer, the free checks, one check, at most one repair. It runs the same tiers and grounding as the pipeline, so the comparison isolates the plan and the loops.
- **(8) keeps one model check, against outside advice.** The 2026-10-02 reviews advised a fast path with no judge at all, only arithmetic recomputation and span matching, because "one judge is what failed on Q3 in both runs" (`docs/reviews/2026-10-02-consultant-reviews.md`).
  - **Why D51 keeps the check.** Neither recomputation nor span matching exists in the harness yet (P3, P4). Without them, the only check on the attention channel (did the answer give every ask, correctly?) is the coverage check's term overlap, which cannot tell a right value from a wrong one.
  - **Why it should behave differently this time.** The check D51 keeps is anchored: it can fail an answer only by pointing at the request.
  - **How the record answers the reviewers.** Verify-first keeps its first answer beside its final one. On every revised unit, the readers can say whether the check turned a wrong answer right or a right answer wrong.
  - **Prediction 9.** The check should help more than it hurts. If it does not, the reviewers were right, and the check comes out.

**What D51 does not do:**
- no routing between the workflows;
- no ship-on-adjudication;
- no tools in the pipeline;
- no change to tiers, pins, budgets, loop bounds or D36's text;
- no database change.

R8, the plan's hard-coded architecture tier, stays open.

## 6. Pathways to success

Ranked by expected value for the mission, each with its mechanism, its theory, its cost, what would show it failing, and when it is decided. P1 and P2 are D51. The rest are hypotheses, ordered for after the re-measurement.

### P1 — The yardstick repair (D51 (1)–(7))

- **Mechanism.** The pipeline's judges read the request's words, and every veto points at them.
- **Theory.** It removes the zero in §3.4 and lowers *f*.
- **Cost.** One cheap call per run, plus fewer iterations. The run should get *cheaper*.
- **Fails if** the repaired pipeline still trails the single call by 7 or more of 21.
- **When.** Command 120, then the re-measurement.

This is the floor, not the destination. On a set where one call already holds 18 of 21, the repaired pipeline can at best stop losing.

### P2 — Verify-first (D51 (8))

- **Mechanism.** Answer once, check against the asks, repair once, or say unresolved.
- **Theory.** It keeps the single call's strength (one author, one yardstick) and adds the attention channel. The Q15 omission is the exhibit.
- **Cost.** Four to six calls, about $0.02–0.05 per unit at the current lineup.
- **Fails if** it trails A by 2 or more on the 25 questions × 3. Structure that cannot beat one call on closed questions should not run on them.
- **When.** The re-measurement. If it holds S1 at a stated cost, it becomes the candidate default for closed questions.

### P3 — Claim-level computation

- **Mechanism.** The answer states each asked quantity as a typed claim: name, expression, value and unit. The harness evaluates the expression with a safe recompute, like arm B's tool. A mismatch is an anchored dissent carrying exact numbers.
- **Theory.** Generation is hard and verification is often easy. Non-frontier models slip on arithmetic and precision far more than on method, and a deterministic evaluator never slips. The harness can also report the exact value beside the rounded one, which dissolves K1-type disputes at the source.
- **Reach.** 15 of the 25 tier-2 questions are sanity, derivation or specification questions.
- **Cost.** Free at check time; one schema in the answer.
- **Fails if** recompute dissents mostly on correct answers, from misparsed expressions, at a rate above the slips it catches.
- **When.** After P2 is measured, as a check inside verify-first.

### P4 — Sourced lookups

- **Mechanism.** A closed-world fetch of the cited source (the eCFR adapter the 2026-10-02 reviews proposed), then span verification. A regulatory value in the answer must match a span of the fetched text; otherwise its verification is unavailable, and the answer says so.
- **Theory.** This is the only channel through which a small model can beat its own memory on regulations. A frontier model wins lookups by memorising more; a harness can win by reading.
- **Reach.** 5 of the 25 questions are lookups. On harder lookups, single-call accuracy should fall well below Q17's 10 of 12.
- **Cost.** One fetch (free) and one check.
- **Fails if** span verification fails correct answers from paraphrase or formatting more often than it catches wrong values.
- **When.** After P2, on lookup questions harder than the 25.

### P5 — Disagreement as the signal

- **Mechanism.** *n* independent cheap answers (*n* = 3–5 at under a cent each). Extract each ask's value. Agreement ships; disagreement goes to a check or adjudication, or ends unresolved.
- **Theory.** Independent samples err partly independently. Agreement filters slips, and disagreement is a free, model-agnostic uncertainty estimate, which is exactly what S3 needs. It is also the cheapest route to calibrated abstention.
- **Cost.** *n* single calls, still under $0.05.
- **Fails if** agreement does not predict correctness on the 25 × *n*, measured from the re-measurement's own repetitions before any build.
- **When.** The re-measurement already produces three samples per question per arm, so P5 can be evaluated on its data for free, before it is built.

### P6 — Escalate upward

- **Mechanism.** When dissents persist, the strongest serving rules on them against the asks and can ship the answer on adjudication, with the overrule recorded.
- **Theory.** Arm D, the escalation serving called once, held 18 of 21 (21 at 3 s.f.). Today escalation directs the weaker implementer to satisfy the same failing judges. The 2026-10-02 reviews named that move: "Routing to a pipeline that already fails is not a recovery strategy merely because it is called escalation."
- **Fails if** the recorded rulings (D51 (6)) uphold most dissents, or the overruled answers read wrong.
- **When.** Ruled on the re-measurement's escalation records.

### P7 — Route by shape, deterministically

- **Mechanism.** Features of the request choose the lane:
  - it cites a section or standard → the lookup lane;
  - it supplies numeric givens and asks for values → the compute lane;
  - it asks for a procedure → the procedure lane, with an ordered-steps check against the step asks;
  - it is an open design brief → the pipeline.
- **Theory.** Different shapes fail differently, so one lane cannot be the best for all of them. The route is decided by a free check, never by a model's opinion of itself.
- **Fails if** the lanes' measured results do not differ by shape.
- **When.** After P2–P4 have per-shape numbers.

### P8 — The pipeline's real test: open design (tier 4)

- **Mechanism.** Multi-constraint design briefs, where no single call sits at the ceiling. Scored by rubric by two readers. The plan is used as decomposition, and D51's asks come from the brief.
- **Theory.** Planning, feasibility review and heterogeneous judges are tools for problems too large to hold in one answer. On closed questions they only add places to fail. If the pipeline earns its place anywhere, it is here.
- **Fails if** verify-first or a single strong call matches it on tier 4 at lower cost. Then the pipeline is retired, and that is a legitimate, publishable result.
- **When.** Designed after the re-measurement.

### Further out

- **A verifier library per domain.** The profiles' `DOMAIN_CHECKS` questions, turned into deterministic checks where possible. A truth table for logic (Q6), unit balance, limit checks against stated constraints. Each one is a free check that replaces a model judgment.
- **Learned routing from the record.** Episodic memory of which lane resolved which shape. Only after hundreds of measured units, and only as a proposal a free check confirms.
- **The product is a frontier, not a pipeline.** Report accuracy against cost per key-held answer for every lane, and ship the Pareto set. For a question a cheap call answers, the right structure may be none.

## 7. The sequence

| when | step | owner of the step |
|---|---|---|
| now → about 10-13 | The repair round: #165, #167, #170 rebased; #160, #171 fixed | executor, then advisor review |
| about 10-13 → 10-18 | Command 120: D51 and verify-first, free work | executor, then advisor review by probe |
| about 10-19 → 10-20 | Command 121: the re-measurement's manifest, pre-registration and mocked dry run | advisor writes, executor builds |
| before the run | Spend authorisation; K1 key version or not; pins unchanged | **owner** |
| about 10-21 | The run, overnight | owner launches |
| about 10-22 → 10-24 | Two readings, resolution, verdict, the decision below | advisor and executor |

**After 120 merges, the harness is frozen** until the re-measurement finishes. Only fixes that stop the run from working go in.

**The decision the re-measurement makes:**

| outcome | what it means | next |
|---|---|---|
| Pipeline within 2 of A, verify-first at least A − 1 | The yardstick was the cause, and structure no longer harms. | Verify-first becomes the closed-question candidate default; P3/P4 go into it; the pipeline is tested on tier 4 (P8). |
| Pipeline trails A by 7 or more, verify-first at least A − 1 | The pipeline is not the closed-question lane. | Retire it from closed questions; verify-first is the product there; tier 4 decides the pipeline's fate. |
| Verify-first trails A by 2 or more | Structure still harms closed questions. | Read the anchored dissents; measure each judge's false-fail rate; decide P6 on the escalation rulings. |
| Verify-first beats A | The first evidence that structure adds accuracy here. | Build P3 and P5 into it, and test on harder sets. |

## 8. The re-measurement, proposed

This is for the owner's authorisation. Command 121 registers it.

| arm | treatment | questions | units | estimated cost |
|---|---|---|---|---|
| A | one cheap call (the triage serving) | all 25 × 3 | 75 | about $0.50 |
| D | one strong call (the escalation serving) | all 25 × 3 | 75 | about $1.60 |
| F | verify-first (D51 (8)) | all 25 × 3 | 75 | about $2.30 |
| E′ | the pipeline under D51 | stage 1's seven × 3 | 21 | about $3.20 |

- **Cost.** About $8 expected against a proposed $15 ceiling. The estimates come from stage 1's medians, with E′ assumed at about $0.15 per unit.
- **Keys.** Frozen v1 (key-strict), plus v2 side by side if the owner rules K1.
- **Readings.** Two readers under D50: every scorer FAIL and a seeded sample of passes per arm, blind to arm.
- **Single stage.** There is no stage rule.

## 9. Predictions

Committed before 120 is built. Each is reported as it reads, never adjusted afterwards (convention 7).

1. **E′ holds at least 14 of 21** key-strict answers on stage 1's seven questions (stage 1: 0). With 3 s.f. accepted (K1), at least 16. Its remaining losses will be mostly Q23 under the strict key, because the engineering serving rounds to 3 s.f. (arm C lost all three Q23 units that way). The rest will show in the record as anchored dissents that escalation overrules.
2. **E′'s median unit costs at most $0.15 and takes at most 400 s** (stage 1: $0.371 and 911 s).
3. **No E′ or F record shows a block, failure or loop iteration caused by a judgment with no anchor.** Any instance is an implementation defect, not a finding.
4. **F is at least A − 1 on the seven questions under both key versions, and at least A − 2 on all 25** (key-strict).
5. **F omits Q15's zeroing step in at most 1 of 3 units** (arm A: 2 of 3).
6. **F's median unit costs at most $0.05,** and at most 5× arm A's median.
7. **If F leaves 5 or more answers unresolved,** those candidates read wrong at a higher rate than F's delivered answers. Below 5, this is reported, not tested.
8. **Agreement predicts correctness (for P5).** On the 25 × 3, a question where all three of an arm's repetitions agree on every asked value is correct more often than one where they disagree.
9. **F's check helps more than it hurts.** Among F units whose check forced a revision, more go from a wrong first answer to a right final answer than from right to wrong. If fewer than 5 units are revised, this is reported, not tested.

## 10. How D51 could fail, and what we would see

| risk | what we would see | where it shows |
|---|---|---|
| The asks miss something asked | A delivered answer omits a requested item and no judge dissents. This is falsifier clause 3. | the asks in the record, beside the key's items |
| The asks over-reach, quoting givens as asks | Harmless dissents on restated inputs | the anchored dissents |
| Judges still fail correct answers against real asks | Unresolved runs whose candidates read correct; escalation overrules | D51 (6)'s rulings; prediction 7 |
| The hazard door is abused | Blocks marked hazard that are really omissions | every hazard block, read |
| The coverage check fails verbatim asks | Coverage dissents on answers that read correct | the per-judge dissent counts (R1) |
| The plan's approach still bloats the answer | Answers far longer than arm A's | answer length per arm |
| K1 confounds Q23 | Different key-strict and 3 s.f. rows | both key versions, side by side |
| Overfitting to the 25 | Gains vanish on new questions | tier 4, and any request outside the 25 |

## 11. Open questions for later rulings

- **R8.** `run_plan` always plans on the architecture tier, whatever `tier_when` says.
- **K1.** The Q23 force precision. This is the owner's key version.
- **Routing (P7).** Ruled on per-shape data.
- **Ship-on-adjudication (P6).** Ruled on D51 (6)'s records.
- **Tier 4's design (P8).**
