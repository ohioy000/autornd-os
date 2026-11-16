# The user's path: the API re-checked and walked (2026-11-16)

Week 2 of the handover's plan, done early on the owner's word. Two things: the outside reviews'
API findings of 2026-10-02 checked again on today's main, and the path a user takes walked end
to end with two real requests.

## The point

- **Most of October's findings are fixed and pinned by tests.** The open endpoint, the dead
  handle, settings without bound, runs without limits, the spend guard's gaps and the missing
  cap on concurrent runs are all closed.
- **Seven defects were found on the path and repaired here,** each with a test proven by
  breaking the line it guards.
- **Five things are left open for the owner,** because closing them changes what the harness
  does or needs a design. They are listed below.
- **The walk worked.** A lookup question and a calculation went through the API and came back
  right. It was the first live sighting of the new `needs_calculation` switch, and it sorted
  both the right way.
- **The walk cost '$0.013'.** No browser and no Docker are installed on this machine; what
  that leaves unseen is said at the end.

## October's list, on today's main

Checked by a read-only audit, with file and line, then spot-checked by the architect.

| | Finding of 2026-10-02 | Today |
|---|---|---|
| 1 | The submitted row stayed pending and lost its owner | **Fixed.** One row, the caller's. One gap left, repaired here (a workflow file that will not load) |
| 2 | An open, money-spending endpoint | **Fixed.** With no key set, only loopback callers are served; anyone else gets 403 with the fix named |
| 3 | Settings could be raised without bound | **Fixed.** Loopback only, and a setting can only be tightened. One gap left, repaired here (nought and negative values) |
| 4 | `/api/episodes` not filtered by owner | **Fixed** for signed-in callers. But see "Left open" 1 |
| 5 | No time budget and no spend ceiling | **Fixed.** 1,800 seconds and a ceiling a run, on both submit paths |
| 6 | Phases written only after the run; no durable job | **Half fixed.** Each phase is written as it ends and the status moves. A restart still strands a run in flight; see "Left open" 2 |
| 7 | Spend guard gaps: the rerank call, concurrent calls, failed calls | **Fixed.** Reserved before dispatch, released by identity, failed calls kept as liability |
| 8 | Process-wide state shared by runs | **Holds in part.** See "Left open" 3 |
| 9 | No cap on concurrent runs | **Fixed.** Two at once; a third gets 429, a duplicate 409 |
| 10 | Starting with nothing configured | Missing tiers stop the start with a plain list. **A missing key did not;** repaired here |

## Repaired here

| | What a user met | The repair |
|---|---|---|
| 1 | With no provider key, health said "ok" and the first run failed on "Illegal header value" | A call with no key now says "No provider key is set. Put OPENROUTER_API_KEY in .env and restart the server." Health reports `provider_key_configured` |
| 2 | A 500 returned the server's full traceback to the caller | The traceback is logged; the caller gets the error's name and message |
| 3 | A runtime limit of 0 or −5 was accepted, being "tighter" | Refused with 422 |
| 4 | A workflow file that would not load left the run pending for ever | The run ends blocked with the reason |
| 5 | The page never showed the draft of a run that did not complete: it read a key the record never had | It reads `candidate.answer` |
| 6 | The Workflows tab showed a run's raw phases and no answer, no "verified" lines, no cautions | It shows the same delivery as the chat |
| 7 | **A false caution of the architect's own, from step 1.** A right answer of 20 minutes carried two "two pages differ" cautions | See the next section |

The measurement runner had the same wrong key as the page (5): a run that delivered no answer
was recorded with an empty draft. Fixed in `docs/probes/short_workflows_measurement.py`.

### The false "two pages differ" caution

Found on the walk's first answer, and once before on the three-arm run.

- **A PDF wraps its lines.** The check split text at every line break, so the last wrapped line
  of the helicopter paragraph, "to fly after that for at least 20 minutes.", stood as a sentence
  of its own and matched the airplane's "(1) During the day, to fly after that for at least 30
  minutes". A line break inside a sentence is now read as a space.
- **One section under two addresses.** The same eCFR section fetched by two addresses was two
  "pages", and two of its paragraphs were set against each other. Two pages now differ on a
  sentence only when neither also prints the other's.

Replayed on the 283 recorded answers of 2026-11-15: 3 cautions are left where there were 5. Two
are the case the check was built for, the flight attendant's 10 hours beside 9. One is false and
the rule cannot tell it: two limits a rule prints in the same words ("More than 10 hours
following 8 consecutive hours off duty" beside "More than 15 hours following 8…"). The two
ozone cautions are gone: the part's page prints both the 2015 and the 2008 section, so the two
pages do not disagree.

After the repair the walk's first answer reads: one "verified" line, no caution.

## Left open, for the owner

1. **No episode is ever saved.** The engine adds the episode after its last commit and nothing
   commits it, so it is rolled back. It is also saved only when a run has a plan and a review,
   which the default workflow has not. Fixing the commit would start feeding past runs to later
   ones on the other workflows, which changes what they conclude. A ruling: repair it, or take
   episodic memory out.
2. **A restart strands a run in flight.** Its row stays in a running state for ever. October's
   reviews asked for a durable job record; it was deferred then. The small version is a sweep at
   start that ends such rows as blocked. That is safe for one server process and wrong for
   several sharing a database, so it needs a decision on how the server is meant to be run.
3. **Sites learned as refusing are shared by every run in the process.** One caller's two
   refusals change what the next caller's lookup is told. It is by design and it is not
   isolated.
4. **Thirteen settings are named as changeable at runtime and the endpoint accepts five.** The
   other eight are dropped without a word and the call returns 400. Either the list or the
   endpoint should change. The README's table is corrected in this pull request.
5. **Health does not list the recompute and decision tiers,** so a wrong model there shows
   only when a run reaches it. Preflight does check the recompute tier.

Not confirmed, and worth a look in week 3's acceptance run: whether a browser on the host of a
Docker container counts as a loopback caller (if not, a first-time Docker user gets 403 until a
key is set, as the README says to do); whether a reverse proxy on the same host makes every
caller look like loopback; and whether the time budget cuts a node already in flight.

## The walk

A local server on main plus this pull request's repairs, a scratch database, the owner's `.env`.
Two requests through `POST /api/workflows`, polled on `GET /api/workflows/{id}`.

| | A lookup | A calculation |
|---|---|---|
| Request | The VFR fuel reserve for a helicopter | A two-resistor voltage divider |
| Status | completed | completed; both within 90 seconds |
| Answer | 20 minutes, right | 3.84 V and 0.816 mA, right |
| `needs_sources` | 0.98, yes: the lookup ran | 0.001, no: no lookup |
| `needs_calculation` | **0.015, no: the recompute step was skipped** | **0.998, yes: three samples ran and agreed** |
| Delivery | one "verified" line, no caution (after repair 7) | "No lookup ran: figures … were not checked against a source." |
| Cost | '$0.0089' | '$0.0037' |

- **The new switch sorted both the right way,** with wide margins. Two requests are a first
  look and not a measurement.
- **The calculation's one caution is true and a little off the point.** Nothing was looked up
  because nothing needed to be, and the vote did check the figures. Whether to say "no lookup
  ran" beside an answer the vote agreed with is a small ruling for week 3.
- **The page.** No browser is installed here. The served page's own functions were run under
  Node on the real responses and on a blocked run: the answer, the draft and the error all
  render.

## What was not seen

- **The Docker image, by hand.** Docker is not installed on this machine. CI builds the image,
  boots it and checks its health on every pull request.
- **The page in a browser.**
- **A signed-in caller.** The walk was a loopback caller with no key set.

Each belongs in week 3's acceptance run, on a machine that has Docker and a browser.

## Proof

- `tests/test_user_path.py`, 10 tests, and two cases added to the pages-differ tests.
- 9 lines broken one at a time; each break failed its test.
