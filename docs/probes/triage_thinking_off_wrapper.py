"""PROBE ONLY (not harness code): run the eval CLI with the triage call sending reasoning={"enabled": False}.
Wraps OpenRouterClient.chat_json for function == "triage"; nothing in the repo is changed."""
import asyncio, sys
from autornd.routing.openrouter import OpenRouterClient
from autornd.evals import cli

_orig = OpenRouterClient.chat_json

async def _off(self, function, *a, **kw):
    if function == "triage" and kw.get("reasoning") is None:
        kw["reasoning"] = {"enabled": False}
    return await _orig(self, function, *a, **kw)

OpenRouterClient.chat_json = _off
sys.exit(asyncio.run(cli.main()))
