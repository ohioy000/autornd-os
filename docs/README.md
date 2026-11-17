# A map of `docs/`

This folder is the project's record. Most of it is history kept on purpose: a measurement is
only worth what its trace and its preregistration can show. Files are cited by path and by
checksum from elsewhere, so they are not moved or renamed.

## Start here

| File | What it is |
|---|---|
| [`HOW-WE-GOT-HERE.md`](HOW-WE-GOT-HERE.md) | The story: how the harness changed, why there are so many tests, why the architect-and-coder form |
| [`MODELS.md`](MODELS.md) | The models chosen for each tier, how the choices changed, and why they stand |
| [`carryover-2026-11-16.md`](carryover-2026-11-16.md) | The latest handover: where the work stands and the plan to the release |
| [`reviews/`](reviews/) | One report for each measurement or audit, named by date. The newest are the current state |

## The record

| Path | What it holds |
|---|---|
| `preregistration-*.md` | What a paid run would do, its bars, its predictions and its spending limit, written and pushed before the run. Numbered ones (049 to 107) are from the command channel; dated ones are from November |
| `reviews/` | The report of each run or audit, read against its preregistration |
| `traces/` | The runs' own result files, copied byte for byte and cited by sha256. Never edited |
| `probes/` | The scripts that made the measurements and analysed them. A probe is kept as it ran |
| `handover-review.md` | The long history: every numbered ruling (D1 onward) and blueprint. Search it; do not read it through |
| `carryover-*.md` | Dated handovers between sessions |
| `provenance/` | The first two architects' conversations, verbatim, and the third's summary |
| `serving-ledger.md` | Which provider served which tier in each recorded run. Generated from the traces by a test |
| `readme-archive.md` | The detail that was in the README before it was shortened on 2026-11-16 |
| `successor-prompt.md` | The prompt that opens a new executor's session (see `AGENTS.md`) |
| `results/`, `tier4/`, `findings-*.md`, `shootout-086-*`, `recommended-roster-*.md` | Older measurement records, kept where they were first cited |

## Not part of the record

| Path | What it is |
|---|---|
| `manifest.json` | The default documentation manifest for a profile with no documents |
| `smartfactory/`, `cupline/`, `meridian_studio/` | Small example document sets that the example profiles ground on |

## Rules for this folder

- **Model names and prices may be written here** and nowhere a user reads first. The README,
  `.env.example` and the rules files stay anonymous, and a test holds them to it.
- **A trace is evidence.** It is copied, never edited, and cited with its checksum.
- **Private documents never enter the repository.**
