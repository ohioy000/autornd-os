# Handover: 2026-11-16, for the architect who starts on 2026-11-17

Written by the outgoing architect on the owner's word. It says what the job is, what was done on
2026-11-15 and 16, where the harness stands, and a plan of three weeks at most to finish it.
Read `CLAUDE.md` and `AGENTS.md` first for the rules; this file does not repeat them.

Main is at the merge of the pull request that adds this file. The suite is 2075 tests in 91 files (2074 passed, 1 skipped), network guard 0.

## The goal

A **general** harness that lets low-cost models answer expert questions correctly and says
honestly what it checked. The owner's target is professional use: precise questions that name
their rule or standard. Work on vague requests was dropped on the owner's word.

## Your role

- **You design, build, measure and report. The owner rules.** There is no separate coder now.
  The owner said so on 2026-11-11 and authorised subagents. `CLAUDE.md` and `AGENTS.md` still
  describe an architect who writes task files for a coder; that relay has not run since
  2026-10-29. Whether to rewrite those rules is the owner's (see week 2 below).
- **The test for what you may change alone is in `CLAUDE.md`:** does it change what the harness
  would conclude, or only how reliably it gets there? The first needs the owner's ruling.
- **Money, keys and model pins are the owner's.** Never read `.env`. Every paid run needs the
  owner's word and a preregistration with an amount and a stop, pushed before the run.
- **Deliver by pull request, merge on green, never push to main.** The `gh` command works on
  this machine.
- **Write simply,** to the owner and in every document. Lead with the point.
- **How the owner works with you:** short messages, quick decisions, and hypotheses stated
  before results. Give a recommendation every time, say plainly when the data does not support
  an idea, and record the owner's hypothesis before the result is known.

## What was done on 2026-11-15 and 16

The owner approved a four-step plan on 2026-11-15 (`docs/carryover-2026-11-15.md`). All four
steps are done.

| | What | Pull request | State |
|---|---|---|---|
| 1 | The delivery's cautions rebuilt around the text the harness hands on | #270 | Live |
| 2 | The lookup that reads the documents is the default | #271 | Live |
| 3 | A second request for documents when the first brought nothing | #272 | Built, switched off; measured, see below |
| 4 | A set of 12 questions where a summary misleads, and a three-arm run on it | #273, #274 | Run and read |
| | The vote's "compared nothing" caution, said only when nothing else checked the answer | #274 | Live |
| | A test of the recompute step with six models | #275, #276, #277 | Run and read |

### What the measurements said

- **The three-arm run, 432 answers read blind** (`docs/reviews/2026-11-16-misleading-set-run.md`):
  right in 141 of 144 for the lookup that asks for an answer, 144 of 144 for the lookup that
  reads the documents, 141 of 144 with the second request on. No wrong answer carried a
  "verified" line. The set did not separate the lookups; it is at the ceiling.
- **The second request for documents** fired in 13 of 144 lookups and gained nothing. It stays
  off.
- **The stale page:** the two wrong answers of the asking lookup gave the BasicMed limits from
  before 2024, read off the FAA's own advisory circular, with no caution.
- **The recompute step** (`docs/reviews/2026-11-16-recompute-samplers.md`): on the run's real
  wrong answers the samples made the same mistake and the vote flagged none, at about a fifth of
  an answer's cost. The owner ruled it off by default and kept for calculations (#278).
- **The user's path** (`docs/reviews/2026-11-16-user-path-audit.md`): October's API findings
  mostly fixed; seven defects found on the path and repaired, each break-proved; a lookup and a
  calculation walked through the API and came back right.

## Where the harness stands

**What works.**
- **Precise professional questions whose answer is on a page that can be read.** Three sets, 44
  questions, are answered right nearly every time with the lookup that reads the documents.
- **Reading is solved.** The harness fetches the pages and hands on their own words. Quotes are
  found on their pages 97 percent of the time, against 66 before.
- **The delivery says what it checked.** "Verified" lines for figures that stand in a found
  passage, and cautions for a figure on no page, two pages that differ, nothing read, and a vote
  that disagrees.

**What does not, yet.**
- **A source that misleads when nothing in its text shows it.** A stale official page or a
  sister rule, found word for word. The new lookup avoids most of these by asking for the rule's
  own page. No check catches the rest.
- **Answers in words.** The vote compares typed values and the cautions read figures. A wrong
  condition or a wrong paragraph in prose passes unseen (the inspection-authorization request).
- **Checks that cost more than they catch.** The three recompute samples are the largest line
  of an answer's cost. See the sampler test above for what they are worth.
- **Sites that refuse to be read,** osha.gov above all.

**What the measurements cannot tell any more.** Every set is near the ceiling for both lookups.
A further change will not show on them. That is the main reason to stop building and finish.

**Known defects, found and not fixed.**
Five, each needing the owner's ruling, in `docs/reviews/2026-11-16-user-path-audit.md`,
"Left open": no episode is ever saved; a restart strands a run in flight; sites learned as
refusing are shared by every run; 8 of 13 runtime settings named as changeable are refused; health
does not list the recompute and decision tiers. And from the sampler test: the vote reads
"RFC 7540, RFC 8740" and "75408740" as different, and does not read a reply whose values sit
under another key. Both change what the vote concludes.

## Money

Spent on 2026-11-15 and 16: about '$5.03' on the three-arm run (approved about '$5.60'),
'$1.02' on the sampler test (planned '$1.76'), and '$0.013' on the walk. Every figure is from
the run's own records in `docs/traces/`. The acceptance run of week 3 is about '$3.50' and needs
the owner's word.

## The plan: three weeks at most, 2026-11-17 to 2026-12-07

The owner asked for polishing, tightening and finishing, not new mechanisms. Three rules hold
for all three weeks:

- **No new mechanism.** A change either removes something, repairs something found, or makes
  the user's path work. An idea for a new check goes on a list for after the release.
- **Every fix names the measurement it serves.** If it serves none, it waits.
- **On 2026-12-07 what is there ships.** What is not done is written down as a known limit.

### Week 1, 17 to 23 November: decide and tighten

The harness carries more switches and half-built paths than a finished one should. Each gets a
ruling from the owner: live, or removed. Bring them as one list, with a recommendation for each.

| | Item | The architect's recommendation |
|---|---|---|
| 1 | The recompute step and its model | Ruled (#278): off by default, kept for calculations. Measure how the `needs_calculation` switch sorts lookups from calculations, for cents. The model is the owner's pin; the owner said Haiku, which goes in `.env` |
| 2 | `lookup_documents_ask_again` (step 3) | Remove, with its tests. Measured on 432 answers: it fired in 13 of 144 lookups and gained nothing |
| 3 | The older lookup, kept behind `lookup_reads_documents` with 46 tests | Remove it, with its tests, once the owner agrees the default has stood. One lookup is easier to trust than two |
| 4 | `lookup_withhold_unverified`, off | Remove. Measured: an unverified answer was right three times in four |
| 5 | `workflows/answer-and-recompute-claims.yaml`, the claim check in shadow | Remove. Measured twice; it cannot supply a sentence the lookup never found |
| 6 | The four switches still in shadow (`hard_request`, `ask_covered`, `chunk_helps`, `finding_answers`) | Each live on its evidence or removed. None has been measured since 2026-11-14 |
| 7 | The repairs listed under "Known defects" above | Fix each as found, with a test proven by breaking the line it guards |

End of week 1: one configuration, written down, with nothing in shadow and nothing switched off
that is not meant to stay.

### Week 2, 24 to 30 November: the user's path and the documents

Every measurement so far went through a probe script. A user comes through the API and the
dashboard.

1. **Walk the user's path end to end,** on the Docker image: start it, submit a request, read
   the answer, its "verified" lines, its cautions and its sources in the dashboard. Fix what
   stands in the way. Nothing counts as fixed until it is seen there.
2. **Check the API against the outside reviews of 2026-10-02.** They listed an open,
   money-spending endpoint, runs with no time or spend limit, and a handle that never completes.
   Much was fixed since (Ruling D38 and after). The outgoing architect did not re-verify the
   list on today's main; do that first, and report each item as holds, fixed, or open.
3. **Make the documents true and short.**
   - `README.md`: what the harness does today, how to run it, what it costs, with figures from
     the record only.
   - `HANDOVER.md` says its snapshot is of 2026-10-21 and is 1,900 lines; the history behind it
     is 13,400 more. Propose to the owner one current page and an archive.
   - `CLAUDE.md` and `AGENTS.md` describe the architect-and-coder relay. Rule 5 of `CLAUDE.md`
     makes a change to the rules the owner's. Ask once, with a draft.
4. **A second reader as standing practice.** The blind reading used on 2026-11-16 (packets
   without the arm, one Sonnet reader a question, the architect re-reading every answer not
   marked right and a sample of the rest) is cheap and answers most of D50. Put the two scripts
   in `docs/probes/` to use and say so in `.claude/context/evals.md`.

End of week 2: a person who has never seen the project can start it, ask a question and
understand the answer's "verified" lines and cautions.

### Week 3, 1 to 7 December: freeze, measure once, release

1. **Freeze on 1 December.** After it, only a fix that blocks the final run.
2. **One preregistered acceptance run** on the final configuration: the three professional sets,
   44 questions, six answers each, through the API path and not a probe. About '$3.50' at
   today's cost an answer; it needs the owner's word. Read blind by two readers.
3. **The bars, to be set in the preregistration with the owner,** on what the release claims:
   answers right; no "verified" line beside a wrong figure; how often a right answer comes
   clean; how often a wrong one carries a caution that points at it; cost an answer.
4. **Release.** The figures of that run go into the README with their traces. Tag the release.
   Write the known limits down beside it, the ones under "What does not, yet" first.
5. **A last handover,** one page.

**What is deliberately not in this plan:** a harder question set, a check for answers in words,
a way to tell a current page from a stale one, and vague requests. Each is real. Each is a new
mechanism or a new measurement, and the owner asked for a finish.

## Things that bite

- **No git operation in a tree while a paid run writes into it.** Do the git work in a second
  clone, as was done on 2026-11-15.
- **A background wait may not wake you.** On 2026-11-15 two runs finished and nothing happened
  for three and a half hours. Set a timed check-in beside every wait.
- **More than about five processes fetching ecfr.gov at once draws challenge pages.**
- **A probe must name its database before it imports the engine.**
- **Waiting with `pgrep -fc` in the same shell hangs.** Wait on the result files' line counts.
- **The free figure check is a pointer, not the result.** Read the answers.
- **A model that answers in another reply shape looks like a model that knows nothing.** Two of
  the six models tested put their values under a key the harness does not read.
- The older list in `docs/carryover-2026-11-15.md` still holds.

## Where to read more

| For | Read |
|---|---|
| The rules of work | `CLAUDE.md`, then `AGENTS.md` |
| The plan these two days carried out | `docs/carryover-2026-11-15.md` |
| The cautions and how they decide | `docs/reviews/2026-11-15-cautions-on-handed-on-text.md` |
| The three-arm run | `docs/reviews/2026-11-16-misleading-set-run.md` |
| The test of the recompute step | `docs/reviews/2026-11-16-recompute-samplers.md` |
| The question sets | `evals/professional/` and its `verify_keys.py` |
| The switches and their rulings | `switches/default.yaml` |
