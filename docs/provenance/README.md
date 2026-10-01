# Provenance: the advisor transcripts

These are the conversations in which the first two architects (the **advisor**
role in [`AGENTS.md`](../../AGENTS.md)) designed AutoRnD-OS and ruled on what it
concludes. The owner exported them verbatim from OpenRouter's chat playground on
2026-09-30. According to the owner, the playground sessions used two different
models in the architect role.

The first two architects had read-only access to the public repository. They
worked through the owner, who carried their commands to the coding agents. The
third architect works in the repository directly, through `.orchestration/`.
The third architect's session (2026-09-30 to 10-01) is recorded as a summary,
not a transcript. It covers the change of direction: the freeze (D41) and the
golden set.

| file | architect | turns (user / assistant) | bytes | sha256 |
|---|---|---|---|---|
| [`architect-1-chat.md`](architect-1-chat.md) | first | 13 / 13 | 293,993 | `a204e15f58a1dc13b7e7ae80e2928cb35216c50af09c5b979e88eec7277340ce` |
| [`architect-2-chat.md`](architect-2-chat.md) | second | 71 / 72 | 1,240,125 | `4d58c8d7a69644b476c08668a96828d95802663b3bf25e8e83c3a872321e5f85` |
| [`architect-3-summary.md`](architect-3-summary.md) | third: a summary written by the architect, not a transcript | — | — | — |

## What these are, and what they are not

- **Commentary, not rulings.** Ruling D7: *a ruling exists only when it is in a
  command file; a ruling stated in a transcript is a draft.* Where a transcript
  disagrees with a command file in `.orchestration/commands/` or with the
  notebook (`docs/handover-review.md`), the command file and the notebook win.
- **Verbatim, with no edits and no redactions.** The sha256 values above are the
  exported files' own. Before commit, both were checked for key material: no
  provider, GitHub or bearer-token patterns were found, and the two `API_KEY=`
  lines in the second transcript are empty placeholders. They were also checked
  for private-corpus content: none was found, and the two mentions of the
  excluded corpus only state the exclusion rule.
- **Not anonymous.** Model names appear here, as they do in `HANDOVER.md` §6 and
  the notebook. Selection is anonymous; the record is not. `docs/` is exempt from
  the model-name guard by policy (`tests/test_docs.py`).
- **They quote the protocol.** `docs/` sits outside the duplicate-protocol guard
  by design (`tests/test_protocol_file.py`), so a quotation here is not a second
  copy of `AGENTS.md`.

## Why they are here

The project is a working program and a record of how agents built it (see
*Scope and Provenance* in the [README](../../README.md)). The command channel
records what was asked and what was done. These transcripts record how each ask
was reasoned, including the rulings that were later revised and the advisor
errors the notebook records.
