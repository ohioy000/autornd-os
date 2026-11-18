# A frontier model asked directly on the hold-out questions, 2026-11-18

Preregistered in `docs/preregistration-20261118-frontier-direct-holdout.md` (#303), merged before
the spend. The owner approved '$5.00' ("5 dollars approved"). '$4.1419' was spent. The run asks the
question the earlier comparison could not: on the 42 questions nobody shaped the harness against,
how does a frontier model asked directly compare with the harness?

## The point

- **The frontier model was right on all 42.** The harness was right on 113 of its 126 answers
  (89.7 percent). **Bar 1 is missed:** the harness is 10.3 points behind, and the bar allowed 5.
- **So the claim of equivalent accuracy, made on the 22 questions the harness was shaped
  against, does not hold for new questions.** On those the frontier model was more accurate.
  `docs/MODELS.md`, the release notes and the history are corrected in this pull request.
- **The harness is about nine times cheaper an answer: '$0.0108' against '$0.0986'.** Bar 2 is
  met. The harness is also nearly ten times slower: 107 seconds against 11.2.
- **All 13 answers the harness did not get right fell on 11 questions, and the frontier model
  was right on all 11.** Among them: the year of the instrument in force (X31), the withdrawn
  status of an old revision (X20), and a datasheet that states no figure (X41).
- **What is left of the case for the harness is cost at volume and a record of what was read.**
  Not accuracy.

## What was run

`docs/probes/frontier_direct_probe.py` with `FRONTIER_SET=professional-holdout`, as preregistered:
`anthropic/claude-fable-5.2`, reasoning effort medium, the provider's web search with up to 5
results, the question as the only message, at most 8,000 tokens a call. The 42 questions of
`evals/professional/holdout-questions.json` (professional-holdout-1), once each, in order. The
smoke was X1: '$0.0934', 13.1 seconds, 2,235 characters, stop reason `stop`, 5 citations, under
the '$0.30' hold line. The other 41 followed in one run. No call failed, none was repeated, none
was cut off, and the probe never reached its '$4.60' stop.

## Side by side, the same 42 questions

| | The frontier model, asked directly | The harness as shipped (hold-out run, 2026-11-17) |
|---|---|---|
| Answers | 42, one a question | 126, three a question |
| Right on the key | **42 of 42** (100 percent) | **113 of 126** (89.7 percent); its three rounds 37, 37 and 39 of 42 |
| Right on the stricter reading | 42 of 42 | 97 of 126 (77.0 percent) |
| Cost an answer | **'$0.0986'** (median '$0.0728', from '$0.0293' to '$0.4485') | **'$0.0108'** |
| Seconds an answer | **11.2** (from 3.8 to 22.8) | **107** |
| Answers naming a page | 38 of 42 | every answer that ran a lookup, with the passage found |
| Answers saying a figure is unconfirmed, from memory or to be checked | 10 of 42, and 2 more say to check a current page | said by a caution when a figure stands on no page read |

| Cut | Frontier model | Harness |
|---|---|---|
| All 42 | 42 of 42 | 113 of 126 (89.7 percent) |
| The 26 the harness's own fetch can read | 26 of 26 | 74 of 78 (94.9 percent) |
| The 16 it cannot read | 16 of 16 | 39 of 48 (81.3 percent) |
| The 5 traps | 5 of 5 | 10 of 15 (66.7 percent) |
| The other 37 | 37 of 37 | 103 of 111 (92.8 percent) |
| X1 to X14 | 14 of 14 | 39 of 42 |
| X15 to X28 | 14 of 14 | 38 of 42 |
| X29 to X42 | 14 of 14 | 36 of 42 |

The gap is on every cut. It is smallest on the questions the harness can read (5 points) and
largest on the traps and on the sources it cannot read.

**Which questions.** The harness's 9 wrong answers were on X12, X13, X16, X19, X20, X31, X34, X38
and X41, and 4 more units ended blocked by its own checks (X3, X24, X31, X41): 13 answers on 11
questions. The frontier model was right on all 11. There is no question the harness answered
right and the frontier model wrong.

## The bars

| Bar | Result |
|---|---|
| 1. The harness's right rate is within 5 points of the frontier model's (met at 39 or fewer right of 42) | **Missed.** 42 of 42; the gap is 10.3 points |
| 2. The harness costs no more than a quarter as much an answer (met at '$0.043' or more) | **Met.** '$0.0108' is 0.11 of '$0.0986', about a ninth |

**How steady bar 1 is.** I tried the readings that favour the harness.

- The two answers that give the key's content only in hedged words (X20, X41) counted wrong: the
  frontier model is right on 40 of 42 (95.2 percent). Bar 1 is still missed, by 5.6 points.
- The three harness answers the 2026-11-17 reading called borderline (X13, X16, X34) counted
  right: the harness is right on 116 of 126 (92.1 percent). Bar 1 is still missed, by 7.9 points.
- **Both together:** 92.1 against 95.2 percent, a gap of 3.2 points, and bar 1 would be met. That
  takes a reading that goes the harness's way at five answers at once. It is not the
  preregistered reading and I do not take it.
- If the frontier model's true rate were the harness's 89.7 percent, 42 right in 42 would come
  about once in a hundred runs. That treats the harness's rate as the truth, which with 42
  questions it is not, and the questions share one author.

## The predictions

| Prediction | Result |
|---|---|
| 1. The frontier model is right on 37 to 41 of 42 | **Failed.** 42 |
| 2. At least half its wrong answers fall on the traps or X29 to X42 | **Not tested.** It had none wrong |
| 3. Its cost an answer is '$0.05' to '$0.09' | **Failed.** '$0.0986' |
| 4. 6 to 15 seconds an answer | **Held.** 11.2 |
| 5. Bar 2 is met, bar 1 about even | **Held on bar 2. Bar 1 missed** by more than even |
| 6. Fewer than half its wrong answers say their figures are unchecked | **Not tested.** None wrong |

**The cost.** The first comparison's '$0.071' was matched by this run's median, '$0.0728'. The mean
is higher because three calls cost '$1.20' together: X31 '$0.449', X41 '$0.443' and X9 '$0.304'.
They read 32,000 to 47,000 tokens of search results each, against 7,300 on average. The other 39
averaged '$0.0755'. Forty-two answers cost '$4.14', not the '$3.00' I expected, and inside the
'$5.00' limit.

## How it was read

The rule is the hold-out run's, as preregistered. Three blind Sonnet readers read the 42 answers
under codes (`docs/probes/blind_reading_packets.py`, 14 each) and marked **all 42 right**, with no
`outside_wrong` mark. Two of them flagged a judgement call: X20, whose status of Revision 2 is
headlined "superseded" with "withdrawn on 14 May 2024" given only from recollection, and X41,
where the answer says it could not find the figures and that the datasheet publishes none is from
memory.

**The executor read all 42 answers in full against the keys.** The preregistration asked for the
answers the readers did not mark right (none) and a random 12; because a result of 42 of 42 runs
against what I predicted, I read every one. I agree with the blind readers on all 42, and I
searched for a wrong claim outside the key as I read and found none I could show was wrong. X20
and X41 give the key's content in hedged words ("From memory", "I can't confirm", "there may be
no"). The rule says an item "None" is right only if the answer says so, and X41 says so; X20 gives
the withdrawn status and date. I count both right and report the sensitivity above.

I also read what each answer says about its own figures, by hand, because the keyword screen in
the analysis script found only 6 of the 10. Ten answers say a figure they give is unconfirmed,
from memory or to be checked against the text (X11, X12, X20, X21, X26, X27, X31, X36, X38, X41),
and two more say to check a current page for a later change (X30, X33). The two answers that give
their key content only as hedged memory (X20, X41) are two of the harness's worst misses. For
them the frontier model said it was unsure, and was right.

## What the numbers say

- **On new questions the frontier model, asked directly, was more accurate.** 42 of 42 against
  113 of 126. The earlier "equivalent accuracy" came from 22 questions the harness had been
  shaped against, where both were at the ceiling. The hold-out does what it was built to do: it
  shows the gap the shaping hid.
- **What the harness missed is mostly what is read, not how it is reasoned about.** X31: the harness
  took the year from a licence page still served; the frontier model's search found the 2025
  instrument and said its figures came from a consultation draft. X20: the harness said
  Revision 2 was superseded, not withdrawn, and that the PDF carries no banner; the cover says
  withdrawn. X12, X38 and X41: figures inside long PDF documents, and for X38 and X41 the
  harness's own fetch reports the file larger than its 15 MB limit. The harness's answers were
  not right 4 times in 78 on the 26 questions it can read, and 9 times in 48 on the 16 it
  cannot. Whether the frontier model's search reads pages the harness's fetch cannot is not
  shown here: on X41 it says its searches did not reach the datasheet, and its right answer
  rests on memory. These are pointers for the lookup, and none was tested as a cause.
- **The price argument stands and is wider than we said:** about nine times, not six. At 10,000
  answers, '$108' against '$986' at these rates. The record of what was read (passages and
  whether each was found on its page) remains a difference in what the two deliver. This run did
  not measure how much that record is worth.
- **The frontier model's answers are not better sourced for being right.** 38 of 42 cite a page,
  and several cite third-party sites for official text (X1, X27, X38). I did not check that each
  cited page prints the figure given. The key says the answer was right, not that it was well
  sourced.

## What follows

- **No change to the harness.** Anything that changes what the harness concludes needs a ruling.
  What the gap points at (the lookup's reach into long PDFs and its handling of a status stated on
  a cover page) is for the owner and the next architect to decide. It is a design question: the
  harness could use a different way of finding pages. It is not an instrument repair.
- **The documents are corrected,** in this pull request: `docs/MODELS.md` (the claim of
  equivalent accuracy, the thesis paragraph, and "the question sets are at the ceiling"), the
  release notes, `docs/HOW-WE-GOT-HERE.md`, the one-page handover and the changelog.
- **For the owner:** the hold-out run of 2026-11-17 missed two bars and this one misses a third.
  Together they say the harness is less reliable on new questions than on the ones it was shaped
  against, and a fix to one stale-page case would not close a gap of ten points. 1.0 still waits
  for a person starting from the README and for the owner's word.

## Limits

- 42 questions, one answer each for the frontier model, three for the harness. A difference of two
  or three questions is noise. A difference of ten points is not.
- **Authors, checkers, readers and the model are of one maker.** The questions and keys were
  written and checked by models of this maker and signed by the owner; the blind readers are of
  this maker, and so is the frontier model. That could favour either side.
- The harness ran on 2026-11-17 and the frontier model on 2026-11-18. Pages change.
- One model, one effort, one search setting. A cheaper frontier model, or this one with search
  off, is not measured. At high effort the first comparison found no gain on 14 questions.
- **The harness's side is the earlier run, not re-run,** including its four blocked answers, which
  count as not right.
- The cited pages were not opened to see whether each prints the figure given.

## Traces

Copied byte-identical from the run into `docs/traces/`, cited by sha256 (first 12 characters).
The codes file maps each answer to its question and was kept from the readers.

| File | sha256 |
|---|---|
| `20261118T-frontier-holdout-answers.jsonl` | 95303243bf17 |
| `20261118T-frontier-holdout-reading-codes.json` | 725386af3c5b |
| `20261118T-frontier-holdout-reading-blind-verdicts-1.json` | 34012e674fe8 |
| `20261118T-frontier-holdout-reading-blind-verdicts-2.json` | 158d58c2df84 |
| `20261118T-frontier-holdout-reading-blind-verdicts-3.json` | 0ea18b03f71a |
| `20261118T-frontier-holdout-reading-second-reading.json` | f12c59f554f3 |

To rebuild the figures:

    python -I docs/probes/frontier_holdout_analysis.py \
        docs/traces/20261118T-frontier-holdout-answers.jsonl \
        docs/traces/20261118T-frontier-holdout-reading-codes.json \
        "docs/traces/20261118T-frontier-holdout-reading-blind-verdicts-*.json" \
        docs/traces/20261118T-frontier-holdout-reading-second-reading.json
