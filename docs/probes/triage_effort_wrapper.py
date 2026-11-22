"""PROBE ONLY (not harness code): run the eval CLI with the triage call sending reasoning={"effort": $EFFORT}."""
import asyncio, os, sys
from autornd.routing.openrouter import OpenRouterClient
from autornd.evals import cli
_orig = OpenRouterClient.chat_json
async def _eff(self, function, *a, **kw):
    if function == "triage" and kw.get("reasoning") is None:
        kw["reasoning"] = {"effort": os.environ["EFFORT"]}
    return await _orig(self, function, *a, **kw)
OpenRouterClient.chat_json = _eff
sys.exit(asyncio.run(cli.main()))
