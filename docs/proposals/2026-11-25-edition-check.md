# Proposal for a ruling: a "none stated" proof counts only on a page of the edition the question names (2026-11-25)

**Status: proposal, not built into main.** It changes which proofs of absence count, so it is the owner's to rule (CLAUDE.md, the permission
boundary: "gate routing ... anything changing which work ships"). Free replay only; no paid answer was made for it.

## The problem

Three of the remaining wrong answers are a "not stated" for something the sources state (X3, X26, X35). X35 has a clear cause: the question
asks for the CODATA **2018** value, and every page the proof was made on is about the **2022** adjustment (the 2022 wall card, the 2022 wallet
card, the 2022 lookup pages). A 2022 page cannot state a 2018 figure, so its lacking one proves nothing about the 2018 value; the proof code
did not know the page was of the wrong edition (absence.py: "Whether the page is the one the ask is about is the answer step's judgement").

## The rule

In `prove`, skip a page when a **four-digit year (1950 to 2049) that the request names and the ask's search words repeat** is on no part of the
page's text. A year in the search words but not in the request is a guessed answer (a model listing "2025 to 2043" for a date) and is not an
identifier; it is not counted. A page that does carry the year, or an ask that names no year, is unaffected. No model, no new syntax.

## What the free replay found (`docs/probes/edition_check_replay.py`)

453 proofs from every stored run (46 questions, 302 pages read again live on 2026-11-25, 289 fetched; 419 scored).

- **12 of 419 proofs would be dropped: 10 on X35 (every ask-3 proof on a 2022-only page) and 2 on X38 (a table of contents of the 11th
  edition for a question naming 2009). None of the 102 proofs on questions whose key says "none stated" is dropped** (X13, X19, X36, X41 and others).
- A rule on any year in the search words dropped 37 proofs but took guessed answer-years with it (X37's "2025 to 2043"); it was rejected for that.
- Two general signals were tried first and **separate nothing**: the share of the search words on the page (legit kept 82 percent, others 74)
  and the share of the request's words on the page (99 and 96 percent). They are not proposed.

## What it would and would not fix

- **X35's wrong refusals on the 2018 value:** the proof is not made, so the claim has no proof, the check in `graph/checks.py` blocks it, and with
  the second-look branch (`feat/20261124-second-look`, held) a further search for the 2018 page would run. Not shown by a paid run.
- **Not X3** (WHO landing pages of 15 to 32 thousand characters that carry the year and the topic but not the table) **and not X26** (a figure the
  pages only imply). The replay found no free signal for either; X3's pages looked like real pages by every measure tried.
- Too narrow to move a rate. It removes one known false proof family at no measured cost.

## Ask of the owner

1. **Rule on the edition check** (yes, no, or wider): a behaviour change in what counts as proof.
2. If yes, I build it on its own branch with tests and break-proofs (about a day's worth of lines: one function in `absence.py`, tests for the named
   year, the guessed year and the page that has it), then one capped paid test on X35, X38, X19, X36, X41 (about '$0.30'), preregistered first.
3. Independently: the second-look branch is the other half of X35's fix and stays held until you rule on it.
