# The page in a real browser, 2026-11-16

The owner asked for the Docker and browser check on the Linux machine the work was
done on. Both halves were done, the browser first and the Docker image a day later.

## What was done

Chromium (the headless build that Playwright 1.49 downloads) drove the page served by
the real API, started from a fresh directory with placeholder model tiers and no
provider key. No provider call was made and nothing was spent.

- **Desktop, 1280 px.** The page loads. The health banner names every model as
  unavailable, which is true. The Settings tab lists the tiers. A question typed
  into the chat ends in a red BLOCKED card that says
  `MissingProviderKey: No provider key is set. Put OPENROUTER_API_KEY in .env and
  restart the server.` No console error and no page error.
- **Phone, 390 px.** One defect. The header's Refresh button ran 20 px past the
  edge, and the body hides overflow, so the button was cut off and could not be
  reached. The workflows table was 435 px wide in a box that could not scroll
  sideways.

## What was changed

Three CSS properties in `autornd/api/templates/dashboard.html`: the header and its
controls wrap, and the workflows box scrolls both ways. Re-measured at 390 px: the page
is 390 px wide on all three tabs and the table scrolls inside its box. One test pins
the three lines, and each was broken in turn to see it fail. This changes how the page
fits a screen. It does not change what the harness concludes.

## The Docker image, added 2026-11-17

**The Docker image was built and run by hand on 2026-11-17,** after Docker was installed and the
user was added to its group, from a fresh clone of main at `757aad1`. With placeholder tiers and
no provider key: the image built (301 MB of content) and the container was up within 4 seconds.
`/api/health` said `degraded` and named all six tiers as unverified. With no `API_KEY` or
`JWT_SECRET`, a request to `/api/workflows` from the host was refused with 403 and the sentence
that names the fix, and so was the page itself, because a browser on the host is a remote caller
to the container. With `API_KEY` set the page returned 200, a request with no key or a wrong key
401, and a request with the right key 200. In Chromium at 1280 px and at 390 px the page took the
key from its "API Key" button, the Settings and Workflows tabs loaded, the page fitted without
sideways scroll, and a question ended in the red "No provider key is set" card. The one console
message was a 401 that appears while the page loads, before the key is entered. The container log
carries the missing-key traceback at error level. The image and container were removed.

**Not seen in a browser:** a signed-in caller, and a run that completes (it needs a
provider key and a spend).

## A flaky test, repaired in the same change

`TestProgressIsVisibleMidRun` failed once on CI with "the run had already ended
(completed) when the phase was first seen". Each call slept 0.25 s to make the run long
enough to watch, but a slow machine can starve the watcher for longer than the run. The
run is now held after its first call by a gate the test opens when it has looked. With
the watcher made to sleep 3 s first, the old test's condition fails with the CI message
and the gated test passes. Breaking the write-as-you-go line in
`engine/workflow.py` still fails the test.

## A real run through the image with a real key, 2026-11-17

The last open item on the release list was a run that gets all the way through the
container with a real key and a signed-in browser caller. It was done by hand.

- **The image** was built from a fresh clone of main at `00c3281`, so the build context held
  no `.env`. The key reached the container as environment variables passed by name from the
  owner's `.env`; it was never printed and never written into the image. `JWT_SECRET` was set
  to a test value. `/api/health` said `ok` and all ten tiers were available.
- **The account** was registered from inside the container (a loopback caller there), then
  signed in through the page in Chromium. The sign-in worked and the page held its token.
- **The question** was "Under 49 CFR § 173.120(a), what flash point threshold defines a Class 3
  flammable liquid?" The run completed in 68 seconds with a correct answer, a confirmation
  tick, no caution mark, and a cost of '$0.0080'. The Workflows tab listed the run. The only
  console error was the expected 401 before sign-in.
- **One defect found:** the Workflows table said "-21600s ago". The server writes UTC, SQLite
  returns the time with no zone marker, and the page read that as local time (US Central). It
  is fixed in pull request 298 with a test that runs the page's own function under two zones.
- **One risk found the same day, by a cold start from the README** (an agent, not a person,
  with only the README): an image built from a tree that holds a working `.env` carried it. An
  image built here on 2026-11-16 held a 3.4 KB `/app/.env`. It was deleted, and a
  `.dockerignore` now keeps every `.env*` file except the template out of the build
  (pull request 299). The image built from the owner's tree with the fix holds only `.env.example`.

The container and the image used for this check were removed afterwards.
