# The revised caution fix on 109 new answers (2026-11-23)

Preregistered alone before any spend (`docs/preregistration-20261123-caution-v2-test.md`, commit 7367a9d). The tree is the caution
branch at `957bc08` (the gap cautions of the frozen design plus two changes: the numbering-slip rule and thinking off for the
call that names the words of a proof of absence), with the reader tier restored in `.env`. Everything below is read as it stood;
**the revision was designed after reading the earlier fresh answers, so this test is the revision's own fresh test.**

## Short version

* The weakness is fixed at its root and the fix is measured: **words for a proof of absence are now named for 100 of 104 lookups that
  read a page (96 percent), against 9 of 193 (4.7 percent) in the tally's second hold-out answers.** The question that had failed in
  every run, X41 (a datasheet whose full text never states the figure), is now **right in 3 of 3** answers, each through the typed
  "not stated" channel with a proof.
* The "no result for ask N" false alarm is gone: it stands beside **2 of 98** right answers (one a real short record, one X36), and the
  six of the earlier test were all numbering slips.
* **The preregistered bars are not all met, and the revision is not called complete.** Gaps stand beside 6 of 63 right answers of
  A and the control (9.5 percent, bar 3), and beside 2 of 8 not-right answers (25 percent, bar 30), both pointing at the wrong part
  (2 of 2, bar 4 of 5). What is left is one thing, below.
* **What is left:** the "none stated" caution stands beside right "none stated" answers, and **proofs also made two wrong answers say
  "none stated"** on pages that were not the document (a 72-character page and a 1,770-character cover page). The caution is what
  catches both. A typed signal that may separate the good proofs from the bad (the size of the page searched) is a lead, not a rule.

## What ran

109 answers (the preregistered 69 + 40): group A 8 questions whose right answers had carried a false gap, 3 answers each (24);
group B 15 questions that had failed, 3 each (45); control: 40 questions, 1 each, a seeded sample of questions every one of whose tally
answers had been right. **106 delivered; 3 ended blocked on an ask they said they could not satisfy** (Y170, X20, X31; counted as
results). Cost **'$1.848'** of a ceiling of '$2.50' (expected '$1.5'). No 404, 402, 403 or blind guard. Read by five blind readers and
by the executor on every not-right answer (8) and a seeded sample of 20 right ones; **no verdict changed**. No answer or caution was
looked at before the readings were fixed.

Seats, read from the stored phase rows (this tree does not carry the probe change that records `models_by_function`, so the check
the earlier runs made from that field could not be made, and the rows' `model_used` stood in): triage tencent/hy4-flash x109, answer
deepseek x97 (and the architecture model x12, as in the tally where it ran 14 times), decision tier pplx x109, recompute haiku x78.
The reader tier read 547 of 639 documents (2,444 calls); its served model is not recorded in these rows.

## Results against the preregistered predictions

| Measure | Prediction | Read |
|---|---|---|
| Proofs: words named for lookups that read a page | at least 60% | **100 of 104 (96.2%)** (A 24/24, B 40/42, C 36/38); 9 of 193 before |
| False alarms: gap beside right answers of A and the control | at most 3% | **6 of 63 (9.5%)**; control alone **0 of 39**; all four groups' right answers 10 of 98 |
| No "no result" gap beside a right answer with enough results | none | **held** (the 2 left are Y68 ea6441bb, one result for two value asks, and X36 94325d6b) |
| Right "none stated" answers (X36, X19) that use the typed channel | at least half | **4 of 6** (X19 3 of 3, X36 1 of 3); X41 3 of 3 |
| Catches: gap beside not-right answers of B | at least 30%, pointing 4 of 5 | **2 of 8 (25%)**, pointing **2 of 2** (X31 asks 2 and 3 are the missing figures; H9's ask 1 is the declined one) |
| Not-right answers | about 28% in B | **B 7 of 42 (17%)**, control 1 of 40 (2.5%) |
| The risk written down: an answer says "none stated" where it is not so | said, listed | **realised twice** (X31, H9), see below |

The 10 right answers with a gap are 3 of X19, 3 of X36, 3 of X41 and 1 of Y68. **Nine of the ten are on questions whose key is "the
document states none"**, which is what group A was chosen for; the control, an unselected sample, had no false alarm in 39. So 9.5
percent is a number for a sample chosen for these questions, and the measure the preregistration set counts it against the bar anyway.
Over the unselected tally the same rule would stand beside roughly the "none stated" family only (X19, X36, X41, 3 of 311 questions);
that is an estimate, not a measurement, and the bar is reported as missed.

## The not-right answers (8 of 106)

| Question | Why not right | Gap | Shipped | Points at the wrong part |
|---|---|---|---|---|
| X31 | no figures; the schedule "not retrieved", claims asks 2 and 3 "not stated" on a 1,770-character cover page | **yes (2)** | different pages differ | yes |
| H9 (control) | declined to give CVSS 10.0 from a 72-character NVD page, claimed "not stated" | **yes (1)** | none | yes |
| X14 | says the requirements apply (key: no, Article 2(1)) | no | vote did not run; lookup read nothing | n/a |
| Y9 | cites Article 3(1)(b),(c) for the early repeal (key: Article 3(2), 4(2)) | no | same two | n/a |
| T4-58 x2 | B-500 is valid but not the cheapest (the drop omits sin phi) | no | figures in no passage (one also: different pages differ) | n/a |
| T4-42 | uses I_n as RMS, crest current 40.5 A exceeds 33 A | no | none: **comes clean** | n/a |
| Y68 | answers "wheel", misses the move to Pointer Events | no | none: **comes clean** | n/a |

Shipped-or-gap on 6 of 8; **2 come clean** (T4-42, Y68), as the review of the frozen design said some would.

## The risk that came true: a proof on a page that is not the document

With the words named, an answer can say "the document states none" and a proof is made by searching **every page read in full**. Two
answers did so on pages that cannot hold the document:

| Answer | Claimed none for | Pages the proof searched (largest) | Right? |
|---|---|---|---|
| H9 (control) | the CVSS score | 72 characters (NVD, rendered by script), 40,567 (a news page) | **no** (key 10.0; this question's earlier answers were all right) |
| X31 | ask 2 and 3 | 1,770 (the register's cover page), 2,079, 17,638 | **no** (key 4 W, 25 mW per 3 kHz) |
| X19 x2, X41 x3 | the figure | 195,852 to 1,561,656 characters (SP 800-53 PDFs), 295,348 to 684,061 (datasheet pages) | right |
| X36 018bce49 | the frequency | 7,708 (a standards page) | right |

Both wrong "none stated" answers are marked by the new "not stated" gap, which names what the claim rests on: **the cautions are the
safety on this channel.** The size of the largest page searched separates these two from five of the six right ones, but one right
claim rests on 7,708 characters and the sample is eleven answers, so a threshold from it would be tuned on its own data. **Not built.**
Cheapest next steps, both free of the harness: print the largest page's size in the existing caution (display only, no rule), and
read the same figure on every stored "none stated" claim from now on.

## What was changed, and what was not

* **Merged nowhere.** Branch `fix/20261123-caution-flaw` at `957bc08` (gap cautions of the frozen design + slip rule + thinking off);
  no pull request. The test measured exactly that tree.
* No key changed. Y13 (stale, see `docs/reviews/2026-11-23-independent-key-check.md`) was left out of the test.

## Limits

* 106 answers; 8 not right. The catch figure (2 of 8) has wide bounds and is not a bar in the design; the false-alarm figure is for a
  sample chosen on the questions that had false alarms.
* B's questions had failed before, so B's not-right rate falls under regression to the mean as well as under the changes; the reader
  tier was also back on, so this test cannot say which of the two changes (or the reader) moved the answers. It is a test of the
  cautions, not of accuracy, and the accuracy figures are not a bar.
* One reading each by five blind readers plus the executor's reading of 28 answers (every not-right and 20 sampled right ones).
* The control's one not-right answer (H9) is a probable regression from the working proofs; one answer.
