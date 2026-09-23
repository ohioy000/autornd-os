# The command channel — shape, and the paths that are always in scope

`AGENTS.md` is the protocol and governs authority; this file governs **shape**.
Where they differ, `AGENTS.md` wins.

- `COMMAND_TEMPLATE.json` — the canonical command, ready to copy.
- `commands/<command_id>.json` — work out, written by the advisor.
- `responses/<command_id>.response.json` — work back, written by the executor.

---

## The always-in-scope set, and what bought it

**Measured 2026-09-22.** Six commands ran through this channel in one day, and
**six of them logged a scope deviation for the same reason**: the command's
`include` list omitted a file that the command's own acceptance criteria forced
the executor to write. Not one of those deviations was a judgement call. Every
one was arithmetic.

So `scope.include` now carries these by default, on top of whatever the command
itself touches:

| path | why it is always in scope |
|---|---|
| `.orchestration/responses/` | **Every command writes its response here**, and no `include` list this week named it. The channel's own artifact was out of scope on every command that used the channel. |
| `HANDOVER.md` | The bug ledger, and **four generated counts** (`§3.7` total, `§4.2` pass count, the file count, the directory tree). Any command that adds a bug row or a test file must write it. |
| `README.md` | The test badge and two more stated counts. |
| `AGENTS.md` | The test-file count in *Current shape*. |
| `CLAUDE.md` · `.claude/context/testing.md` | Test counts and test-class counts. |

**This is permission, not instruction.** These paths are *writable* by any
command; nothing here says a command should touch them. A command that adds no
test and opens no ledger row leaves all five alone.

### Why the counts force this

`tests/test_handover_truth.py` and `tests/test_docs.py` re-derive every count
from disk and fail if the documents disagree (convention 24 — *a fact about the
repo is generated or guarded, never hand-stamped*). So **adding a single test
file turns four guards red**, and a command cannot satisfy "suite passes"
without writing files its `include` list did not name. The guards are correct
and stay; the `include` list was the thing that was wrong.

### The two-branch case, which is sharper

Two commands branched from the same `main` on 2026-09-22, each added tests, and
each re-derived the counts **against its own tree**. Neither was wrong alone.
Together they were guaranteed to be wrong: one landed at 881, the other carried
878, and the truth after both was 889. The merge conflicted on three count
lines, and **resolving it either way produces a silently false number.**

Only the guards caught it, on the rebase, and they named the real figure.

**So: re-derive counts after a rebase, never carry them across one.** A count is
a reading of the tree at a moment, and a rebase moves the tree.

---

## Other paths worth naming when they apply

Not in the default set, because most commands do not touch them:

- `docs/traces/` — committed run evidence. A command that produces or reads a
  live run needs it. **`*.log` is gitignored**, so run stderr is committed with a
  `.txt` extension; `b17-validation-STDOUT-ONLY.txt` is the precedent.
- `docs/handover-review.md` — the notebook. Frequently *excluded* on purpose, so
  a command touching the ledger does not also rewrite the evidence.
- `docs/preregistration-*.md` — required before any paid run, committed first.

## Preconditions: blindness is not absence

**Measured 2026-09-22 (-027, -029).** Two preconditions reported "absent" when
the subject was present but the search could not see it:

- `-027` precondition 2 ran `ls docs/traces/ | tail -3` to check for a file
  whose name sorted before the last three entries. The file was there; the
  search window was too narrow.
- `-027` precondition 4 tested `echo $OPENROUTER_API_KEY` in the shell when
  `config.py:128` reads from `.env`. The key was set; the precondition looked
  in the wrong place.

Both reported PASS or absence. Neither was true. Convention 28 says an
instrument asserts that it computed its subject before it asserts anything about
it, and convention 26 says a reading that can be mistaken for a stronger claim
is a defect in the instrument.

**The rule:** a precondition that searches for a subject must be able to report
three outcomes, not two:

| outcome | meaning |
|---|---|
| **present** | found what was asked for |
| **absent** | searched exhaustively and the subject is not there |
| **blind** | the search could not have seen the subject — the window was too narrow, the path was wrong, or the method does not reach where the subject lives |

A precondition that can only say "found" or "not found" conflates absence with
blindness. When it reports "not found", the executor cannot tell whether to
BLOCK (subject genuinely missing) or to REPAIR THE SEARCH (method was wrong).

**How to write a precondition that is not blind:**
- Search the full population, not a window: `ls dir/` not `ls dir/ | tail -3`.
- Test the subject where it lives: if the code reads `.env`, test `.env`, not
  the shell environment.
- When a glob returns nothing, check whether the glob's own directory exists
  before concluding the files are absent.

---

## What is never in scope

- **`.env`** — the owner's, and only the owner's (G-3). It carries a live key.
- **`evals/results/`** — git-ignored deliberately. B20: a `git stash -u` takes
  untracked files but **not ignored ones**, which is why the default results
  path was never exposed and `docs/traces/` was. Results reach the repo by
  deliberate copy, never by being tracked.
- **Private corpora** — `profiles/milkhouse.yaml`, `docs/private*/` and the rest
  of `.gitignore`'s corpus block. These must never reach a public repo.
