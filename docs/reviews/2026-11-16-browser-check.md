# The page in a real browser, 2026-11-16

The owner asked for the Docker and browser check on the Linux machine the work was
done on. The browser half was done. The Docker half was not.

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

## What was not done

**The Docker image was not built or run.** The machine has no Docker or Podman, and no
root: `sudo` asks for a password and `uidmap` is not installed. Rootless Docker needs
`uidmap`. A static rootless Podman was tried; the tool that gates commands refused to
let a downloaded container engine be run with its cgroup and user-namespace limits
turned off, and that was not worked around. The CI job still builds the image, boots it
and asserts that `/api/health` reports `degraded`. What stays unseen is the image run by
hand on a machine with Docker.

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
