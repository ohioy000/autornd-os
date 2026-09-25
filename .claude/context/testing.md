# Testing conventions

Load when writing tests. Source: `tests/conftest.py` and the 54 test files beside it.

## What exists, honestly

- **54 test files, 1003 tests, ~52 s, no network and no spend.** That is
  deliberate, not incidental: the shape of a workflow, its gates and loops, the
  deterministic checks, the condition language and the eval scoring are all
  decidable without a provider.
- **There is no coverage threshold and no coverage tooling.** Don't claim one.
- **There is no linter, formatter or type-checker.** Match surrounding style by hand.
- Tests are `tests/test_<subject>.py` with `class Test<Behaviour>` groupings
  (211 such classes). `asyncio_mode = "auto"` — async tests need no decorator.
- Many test modules open with a **module docstring stating why the behaviour
  exists and what measured it** (`tests/test_green_resolution.py:1-21` is the
  model). Match that when the test encodes a hard-won rule.

## Fixtures

`tests/conftest.py` provides:

- `db_session` — in-memory SQLite, tables created and dropped per test.
- `api_client` — httpx `AsyncClient` over `ASGITransport`, with `get_session`
  overridden.
- `make_mock_response(content, model)` and `make_mock_client(responses)`.

Note `conftest.py:9-12`: placeholder `MODEL_*` env vars are set **before any
autornd import**, because `config.py` validates the six required tiers at import
time and exits without them.

## Test doubles must bill

`make_mock_client` calls `client._account(function, response.cost)` on every mocked
call (`conftest.py`). **Any new double does the same.** A free double once hid a
real accounting bug — from the very tests meant to prove one workflow was cheaper
than another.

## Rules for writing a guard

These were ratified after five instruments failed in one day, four that could not
fail and one that could not survive.

1. **An instrument's test simulates the condition it watches, end to end.** Five
   instruments in two design docs reported less than they measured, every one
   against a green suite. An instrument written in the same commit as the fix it
   watches gets no run of its own to prove it on — so prove it by breaking the
   thing deliberately.
2. **A guard asserts that it computed its subject before it asserts anything about
   it.** An empty match set, an unread file, a dropped row and an absent tier are
   all *no evidence*, and **no evidence must never be reported as no problem.**
   The sharpest exhibit: a provenance-stamp guard's regex used `\s*` between label
   and sha where the document has `**HEAD:**`, so `findall` returned `[]` and all
   three deliberate break attempts passed.
3. **Prove a guard by reverting the source.** The structural-roles work is the
   worked example: 4 regression guards pass against both the pre- and post-change
   code, while 9 feature tests fail before and pass after — checked by actually
   reverting.
4. **When a fix invalidates a test, ask which of the two is wrong first.** Two
   tests here had enshrined a wrong error message and were corrected rather than
   appeased.

## Facts about the repo are generated or guarded, never hand-stamped

`tests/test_handover_truth.py` re-derives every count in the documentation. A
commit stamp records when someone last believed a number, not that it was right —
twelve drifts in one document is the exhibit. `tests/test_docs.py` enforces model
anonymity across user-facing docs.

That guard needs full git history: it asserts the sha the record names is an
**ancestor** of the commit under test, which is unanswerable in a depth-1 clone.
CI checks out with `fetch-depth: 0` for exactly this reason.

## Isolate the knowledge store

Experiments and eval tests use `_isolated_store()`
(`autornd/evals/runner.py:315`, used at `tests/test_evals.py:621`). The eval suite
once read a developer's local Chroma directory and every gap came back
pre-answered.
