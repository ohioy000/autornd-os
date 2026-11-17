# A frontier model asked directly, beside the harness (2026-11-17)

Preregistered in `docs/preregistration-20261117-frontier-direct.md` (#285), pushed before the
spend. The owner asked for it: 22 of the 44 professional questions, once each, to
`anthropic/claude-fable-5.2` with web search on and reasoning effort medium, no harness in the
path. '$1.57' was spent of a '$6.00' limit.

## The point

- **The frontier model was right on all 22.** So is the harness, on every recorded answer to
  the same 22 questions. On correctness this is a tie, and both are at the ceiling.
- **The frontier model is about seven times faster:** 8.5 seconds an answer against about 60.
- **The harness is about six times cheaper:** about '$0.011' an answer against '$0.071'. The
  executor predicted 15 to 30 times. **That was wrong, and bar 2 is missed.**
- **They differ in what they show for the answer.** Six of the frontier model's 22 answers
  named no page, and six told the reader the figures were unchecked or should be verified. The
  harness's delivery carries the passages it read, each with whether it was found on its page.
- **`docs/MODELS.md` is corrected in this pull request.** Its price argument overstated the
  gap, and it had no measurement of a frontier model. It has one now.

## What was run

`docs/probes/frontier_direct_probe.py`: each question as the only message, no system prompt,
the provider's web plugin with up to 5 results, reasoning effort medium. The 22 questions were
drawn by a fixed seed before any result. Trace, byte-identical:
`docs/traces/20261117T-frontier-direct-answers.jsonl` (`9db601954a26…`).

**Reading.** A Sonnet reader graded all 22 against the signed keys: 22 right. The executor
screened every answer for its key's figures and read the two the screen stopped on. H13 states
the key's frequency in other notation. H4 gives 5.6 weeks capped at 28 days and does not split
it into the key's four weeks and 1.6; one of the harness's own four recorded H4 answers does
the same and was read right on 2026-11-15, so the same standard is applied here.

## Side by side, the same 22 questions

| | The frontier model, asked directly | The harness as shipped |
|---|---|---|
| Answers | 22, one a question | every recorded answer with the lookup that reads the documents: 3 or 4 a question on the first two sets, 12 a question on the third |
| Right | **22 of 22** | **all of them** (`2026-11-15-lookup-reads-documents.md`, `2026-11-16-misleading-set-run.md`) |
| Cost an answer | **'$0.071'** (from '$0.032' to '$0.141') | **'$0.011'** to '$0.012' |
| Seconds an answer | **8.5** | about 60 |
| Answers naming a page | 16 of 22 | every answer that ran a lookup, with the passage and its checksum |
| Answers saying their figures were unchecked or to be verified | 6 of 22 | said by a caution when a figure stands on no page read |

**What the frontier model's cost is made of.** On average 5,500 tokens read and 530 written a
call. The reading is most of it: the search results are put in front of the model at its input
price. Seven calls read about 13,000 tokens and cost '$0.13' to '$0.14'. It reasoned on 7 of
the 22 and wrote little reasoning when it did.

## The bars

| Bar | Result |
|---|---|
| 1. The harness is right on at least as many as the frontier model, within one | **Met.** Level |
| 2. The harness costs no more than a tenth as much an answer | **Missed.** About a sixth |

## The predictions

| Prediction | Result |
|---|---|
| 1. The frontier model is right on 19 to 22 | **Held.** 22 |
| 2. Any miss is on the set where a summary misleads | **Nothing to test.** No miss |
| 3. Its cost is 15 to 30 times the harness's | **Wrong.** About 6 times |
| 4. It is faster than the harness | **Held.** About 7 times |
| 5. Both bars are met | **Wrong.** Bar 2 is missed |

## What it means

- **The honest case for the harness is not "a frontier model would get these wrong".** It gets
  them right, quickly, for seven cents.
- **The case that stands is narrower, and real:**
  - **Cost at volume.** A cent against seven. At a thousand questions that is '$11' against
    '$71'.
  - **A record of what was read.** Every passage, its page, its checksum, and whether it was
    found, and "verified" lines only beside figures that stand in a found passage. Six of the
    frontier model's 22 answers gave the reader nothing to check, and four of those said so.
  - **No dependence on one model.** The harness reached the same answers with inexpensive
    models that can be swapped and pinned.
- **The case against it, as plainly:** it is seven times slower, it is a system to run and
  keep, and for a person with a handful of questions the frontier model is the simpler buy.
- **Neither side was tested where it is weak.** The draw left out H1, the one question the
  harness has answered wrong. Every set is at the ceiling for both.

## Limits

- 22 questions, one answer each for the frontier model. One answer says nothing about how
  steady it is; the harness's side has several answers a question.
- The harness's figures are from earlier days, through a probe script. The acceptance run will
  give fresh ones through the API.
- The readers are models of the same maker as the model read. The keys are figures and
  identifiers.
- One model, one effort setting, one search setting, one day's prices.
- A stated departure: after the one-question smoke the probe was changed to record the
  provider's own usage figures for each call. Nothing it sends was changed.
