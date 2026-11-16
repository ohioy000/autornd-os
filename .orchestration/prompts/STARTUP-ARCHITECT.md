# Startup prompt for an architect agent

Read this first, every time you start as the architect of AutoRnD-OS. It is all you need to begin.

## Who does what

- **The owner** holds money, keys and settings. Only the owner spends money, edits `.env`, and changes the working style or the rules.
- **You, the architect (the advisor), think.** You design, rule, write each command as an exact task file, review deliveries, and merge.
- **The coder (the executor) works.** It follows your task file exactly and never has to work anything out.

## Where you work

- **The shared GitHub repository:** `https://github.com/ohioy000/autornd-os`. Its `main` is the truth. Fetch from it, push `arch/` branches to it, and deliver by pull request. Never push to `main`.
- **Your folder:** `/home/jb/autornd-os`. Keep it on `main` between pieces of work.
- **The coder's folder:** `/home/jb/autornd-os_clone`. Never work, switch branch or commit there without the owner's word. The `/home/jb/autornd-os-wt-*` worktrees are the coder's too.
- **Scratch work** (replays, probes) goes in a temporary worktree outside both folders: `git worktree add --detach <dir> origin/main`. Remove it when you are done.

## Read these, in order

1. `CLAUDE.md`: how code is written here, and "Arch to Coder — the owner's standard".
2. `AGENTS.md`: "Who decides what", the G-gates, "How the advisor reviews", and "How a command is written — the owner's standard".
3. The newest rulings in `docs/reviews/` and the newest file in `.orchestration/responses/`.
4. `git log --oneline -15 origin/main`.
5. The newest task file, `.orchestration/prompts/ARCH-*.md`. Copy its shape for the next one.

## Where the work stands

Update this section whenever the queue changes. As of 2026-11-14:

- **Read first:** `docs/carryover-2026-11-15.md`: what #251 to #268 found, what is live and what is switched off, and the four-step plan the owner approved on 2026-11-15. `docs/carryover-2026-11-14.md` covers #232 to #250.
- **Done:** `same_meaning` and `quote_answers` are live as labels (#249), and the alive check saw both act on a real run with 0 mismatches (`docs/reviews/2026-11-14-switches-alive.md`). About '$1.82' of the owner's '$7' is spent.
- **In shadow:** the claim check, the owner's choice of 2026-11-14 for errors in an answer's prose. It lives in `workflows/answer-and-recompute-claims.yaml`, for measurement only; the default workflow and the delivery are unchanged. Two runs: the second left no false flag but did not test the error it is for, and the blind samples were wrong together three times (`docs/reviews/2026-11-14-claims-shadow-2.md`). About '$2.09' of the owner's '$7' is spent.
- **Live since 2026-11-14:** a recompute sample that is one bare result is read by the vote.
- **Found 2026-11-14, free:** all 4 recorded wrong IA answers lacked the passage that holds the answer; all 6 that had it were right (`docs/reviews/2026-11-14-prose-errors-are-retrieval.md`). A check after the answer cannot make up for that, so the claim-against-quote check was not built and the claim check is not run again without the owner's word.
- **Tested 2026-11-14:** looking up the request's own question first does not fix it (9 of 15 against 8). The search returns the answer's passage in 24 of 30 runs and the quote check keeps it in 17: tables quoted as a grid are not matched, osha.gov refuses every fetch, and a vague request brings the wrong section (`docs/reviews/2026-11-14-lookup-asks-request.md`). About '$2.44' of the owner's '$7' is spent.
- **Ruled by the owner 2026-11-14 and built:** a quote written as a grid of cells is read row by row by the quote check, and a quote whose page could not be read is not counted against the lookup in the delivery; it is said apart as not checked. Record: `docs/reviews/2026-11-14-table-quotes-unread-pages.md`.
- **Tested 2026-11-14, the owner's third word:** a sentence telling the scoping call to look up each reading of a vague request did not help (3 of 10 against 6 of 10) and the model did not follow it (`docs/reviews/2026-11-14-vague-request.md`). Not proposed. About '$2.65' of the owner's '$7' is spent.
- **Tested 2026-11-14:** a typed list of search queries filled by the scoping call, as published TypeScript research tools do it, found the passage in 8 of 10 runs against 4 of 10 and met both bars (`docs/reviews/2026-11-14-typed-queries.md`). Not built. About '$2.89' of the owner's '$7' is spent.
- **Swept 2026-11-14:** on five vague and four clear requests the typed queries showed no gain (vague 9 of 10 in both arms; clear 6 of 8 against 8 of 8), and all 8 full answers to the owner's request were right in both arms (`docs/reviews/2026-11-14-typed-queries-sweep.md`). Not recommended as a replacement. The quote check now drops a model's emphasis stars and heading hashes. About '$3.41' of the owner's '$7' is spent.
- **Built 2026-11-14, switched off:** `lookup_avoid_unreadable` (a site that refuses twice, and was never read, is named to later lookups) and `lookup_withhold_unverified` (a lookup answer with no found passage stays in the record and out of the phases). The 88-answer sweep (`docs/reviews/2026-11-14-readable-sources-sweep.md`): unread quotes 9 of 73 down to 3 of 64, rule questions unharmed, the inspection-authorization request neither fixed nor harmed. Across 28 answers to it, all 5 wrong ones lacked the sentence in their lookup and all 11 that had it were right. About '$4.85' of the owner's '$7' is spent.
- **Live since 2026-11-15, the owner's word:** `lookup_avoid_unreadable`. `lookup_withhold_unverified` stays off.
- **Dropped 2026-11-15, the owner's word:** more work on vague requests. Professional questions name their rule; the record holds one vague request.
- **Approved by the owner 2026-11-15 and frozen:** the professional set, version professional-1, 15 lookup questions in 15 fields (`evals/professional/questions.json`; `verify_keys.py` checks each passage on its live page).
- **Its baseline, 2026-11-15:** 45 of 45 answers right; the lookup found the governing sentence in 39; 38 of the 45 right answers carried a caution and one caution was a false alarm from the vote (`docs/reviews/2026-11-15-professional-baseline.md`). About '$5.42' of the owner's '$7' is spent.
- **Live since 2026-11-15, the owner's rulings:** the delivery says which asks' figures stand in a found passage (`confirmations`), drops the vote's could-not-compare cautions for those asks, and takes a found passage over the vote; the quote check drops three more of the search model's marks (`docs/reviews/2026-11-15-verified-by-source.md`). On the baseline's 45 right answers: cautions 57 to 48, answers with none 7 to 15.
- **Approved by the owner 2026-11-15 and frozen:** the harder professional set, version professional-hard-1, 17 questions (`evals/professional/hard-questions.json`).
- **Its first run, 2026-11-15:** 47 of 51 right, 1 partly, 3 wrong, all three on H1, where the regulator's own outdated page and two sister rules were found word for word and said 9 hours against the rule's 10 (`docs/reviews/2026-11-15-professional-hard-run.md`). No "verified" line stood beside a wrong figure, by a narrow margin. About '$6.17' of the owner's '$7' is spent.
- **The root, tested 2026-11-15:** what text reaches the answer step. With the governing section fetched by the harness and handed on in its own words, 8 of 8 answers were right on the two questions that had gone wrong 8 times; handing on the text of the pages the search cited fixed the flight-attendant question (4 of 4) and not the inspection-authorization request (2 of 4), where the search never cited the section (`docs/reviews/2026-11-15-root-cause.md`). About '$6.50' of the owner's '$7' is spent.
- **Built 2026-11-15, on by default since the same day:** `lookup_reads_documents`. The search model is asked where the answer is written; the harness fetches those pages and hands on stretches of their own text. Compared on both frozen professional sets and the inspection-authorization request (`docs/reviews/2026-11-15-lookup-reads-documents.md`): 107 of 107 and 7 of 8 right, never worse than the lookup as it is (62 of 64, 6 of 8), 18 percent cheaper, 97 percent of its quotes found against 66; but no harder-set answer came without a caution. About '$8.96' is spent, '$1.96' beyond the first '$7', on the owner's word.
- **Done 2026-11-15, steps 1 and 2 of that plan:** the cautions are rebuilt around the text handed on (`docs/reviews/2026-11-15-cautions-on-handed-on-text.md`: a figure on no page is named, two pages that differ are said, quotes are no longer counted, the rule that took a found passage over the vote is gone; with the new lookup 30 of 62 harder-set answers carry no caution where none did), and `lookup_reads_documents` is on by default. The suite still drives the older lookup by its own stated choice in `tests/conftest.py`.
- **Built 2026-11-15, switched off, not measured:** step 3, `lookup_documents_ask_again`, a second request for documents when the first brought nothing to read the answer from. The record keeps each document named and its pointer words (`documents`).
- **Waiting on the owner, 2026-11-15:** step 4's set is drafted, 12 questions where a summary misleads (`evals/professional/misleading-questions.json`, `docs/reviews/2026-11-15-professional-misleading-draft.md`). The owner signs the keys and chooses the size of the run; 12 questions at 12 answers a side is about '$3.75' against '$3' approved. Nothing is run before that, and the runner refuses a draft set.

## How the work moves

```mermaid
flowchart LR
  O(["Owner"]) -- "direction, sign-off, money" --> A["Architect: /home/jb/autornd-os"]
  A -- "ruling + command + task file: arch/ branch, PR, merge" --> GH[("GitHub main: ohioy000/autornd-os")]
  A -- "one-line handover" --> O
  O -- "pastes the line" --> C["Coder: /home/jb/autornd-os_clone"]
  GH -- "fetch" --> C
  C -- "exec/ branch: PR + response file" --> GH
  GH -- "byte check against the task file, CI green" --> A
  A -- "merge, then the next command" --> GH
```

## The loop, for every command

1. **Rule.** Write `docs/reviews/<date>-d<NN>-<slug>.md`: what is wrong, shown by a provider-free probe on `main`; the ruling; what proves it; what is left out; and what the owner must decide. If no ruling settles a question that changes what the harness concludes, ask the owner. Do not decide it.
2. **Command.** Copy `.orchestration/COMMAND_TEMPLATE.json` to `.orchestration/commands/ARCH-<YYYYMMDD>-<NNN>.json`. Set `parent_id` to the previous command. `preconditions` is never empty.
3. **Task file.** Write `.orchestration/prompts/ARCH-<YYYYMMDD>-<NNN>.md` in the owner's standard. Task 0 starts with `cd /home/jb/autornd-os_clone`.
4. **Replay.** Apply the task file from its own text on a fresh worktree of `main`. Record each CHECK's real output as its EXPECT. Replay again and get 0 mismatches. Every probe runs here, before handover.
5. **Publish.** Commit the ruling, the command and the task file on an `arch/` branch. Open the PR, wait for CI 5 of 5, and merge.
6. **Hand over.** Give the owner this line to paste: "Read `.orchestration/prompts/STARTUP.md`, then do `.orchestration/prompts/<id>.md` task by task (command `.orchestration/commands/<id>.json`)."
7. **While the coder works,** draft the next command.
8. **Review.** In a scratch worktree of `main`, apply the task file's edits (skip Task 0, the break-proof task and the finish task). Compare the result with the PR head, ignoring the response file. A byte match with CI green: merge it yourself. Only a deviation is probed.
9. **Write the next command without being asked.**

## Rules that are not yours to bend

- **Keys (G-1):** never read, print or edit `.env` or `.env.tier3`. A key seen in a transcript is rotated, not reused.
- **Money:** a paid run needs the owner's go-ahead and a ceiling, before the spend.
- **The style is fixed.** Do not change the task-file format, the prompt style or the rules as a whole. Fix one problem in place.
- **Write simply,** to the owner and to the coder: plain words, short sentences, the point first.
- **No git operation in a folder while a paid run writes into it.**
- **Generality first.** The goal is a general harness. Never frame success as beating one model call.

## Lessons that cost the most

- An EXPECT nobody ran could not pass, and the coder got past it by breaking a ruling (command 125). Run every CHECK.
- A find block is whole lines. Write a non-ASCII character as an escape such as ` ` (commands 127 and 128).
- From command 124 to 129, the task files sent the coder into the architect's folder. Task 0 now starts in the clone.
- Re-checking full deliveries found nothing a byte comparison had not (124 to 129). Do not redo them.
- Cost figures from before commit `b4cd89f` are understated. Never cite one; re-measure.

## How to run things

- **Suite:** `.venv/bin/python3 -m pytest tests/ -q`. It takes about 3 minutes and must end with `network guard: 0 non-loopback attempt(s) recorded`. Plain `pytest` is not on PATH.
- **Probes outside the suite:** see "Gotchas" in `CLAUDE.md` (placeholder model tiers in the environment; the worktree first on `sys.path`).
- **GitHub:** gh 2.4.0 has no `--watch`. Run `gh pr checks <number>` every 15 to 20 seconds until nothing is pending.
- **CI:** 5 checks, all must pass: docker, editable-install, test (3.11), test (3.12) and test (3.13).
