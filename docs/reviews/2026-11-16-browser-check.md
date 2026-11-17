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
