"""Is the root of the wrong answers what text reaches the answer step? Paid.

    ARM=oracle|fetched|fetched_primary python docs/probes/root_cause_probe.py \
        OUT_DIR REPEATS MAX_SPEND SET QUESTION_ID

Today the lookup asks a search model to answer and to quote, and the harness
then tries to find the quoted words on the page. The answer step reads the
search model's summary and those quotes. This probe changes only what the
lookup hands on, by putting a wrapper in place of research_gaps, and runs
docs/probes/short_workflows_measurement.py unchanged:

  oracle           no search at all: the harness fetches the governing source
                   named in ORACLE and hands on its text. The upper bound: if
                   answers are still wrong with the right text in front of
                   the model, retrieval is not the root.
  fetched          the real lookup, and then the harness itself fetches the
                   pages that lookup cited and hands on excerpts of their
                   text, chosen by the request's own words.
  fetched_primary  the same, with two sentences on which text governs when
                   the fetched texts differ.

Main's code is not changed. The screen is recorded and is not the result:
the answers are read by hand (D50).
"""
from __future__ import annotations

import os
import re
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ARM = os.environ.get("ARM", "")
out, repeats, max_spend, question_set, question_id = sys.argv[1:6]
Path(out).mkdir(parents=True, exist_ok=True)
# Before anything of the engine is imported, so the run's rows go to the
# run's own database (the slip of 2026-11-14 was this order the other way).
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(out).resolve()}/shard-0.db"
os.environ["MEASURE_SET"] = question_set
os.environ["MEASURE_WORKFLOWS"] = "answer-and-recompute"
sys.path.insert(0, str(ROOT))

from autornd.knowledge import research  # noqa: E402
from autornd.knowledge.fetch import fetch_source  # noqa: E402

E = "https://www.ecfr.gov/current/"
# The governing source of each request this probe is run on, and the words
# of its governing sentence, both from the frozen keys.
ORACLE = {
    "how much rest does a US airline": (
        E + "title-14/section-121.467",
        "A flight attendant scheduled to a duty period of 14 hours or less as "
        "provided under paragraph (b)(1) of this section must be given a "
        "scheduled rest period of at least 10 consecutive hours."),
    "what are the qualifaications for inspection auth": (
        E + "title-14/section-65.91",
        "Have been actively engaged, for at least the 2-year period before the "
        "date he applies, in maintaining aircraft certificated and maintained "
        "in accordance with this chapter"),
}
PAGE_CHARS = 14000        # an eCFR section; the two here are under 10,000
EXCERPT_CHARS = 2500      # of each fetched page, in the fetched arms
MAX_PAGES = 6
PRIMARY = (
    "Where these texts differ, the text of the rule or standard itself, in "
    "its current edition, governs over a page that describes it and over an "
    "earlier edition. If the fetched texts give different figures for the "
    "same thing, say so, and say which text you relied on and why.")
ORIGINAL = research.research_gaps
WORD = re.compile(r"[a-z]{4,}")


async def oracle(client, request, gaps, **kwargs):
    url, passage = next(v for k, v in ORACLE.items() if request.startswith(k))
    page = await fetch_source(url)
    if not page.fetched:
        raise RuntimeError(f"oracle source not read: {page.reason}")
    finding = research.Finding(
        question=request, citations=[url], model="harness", asked=[request],
        answer=(f"The text of the governing source, fetched by the harness "
                f"from {url} on {page.fetched_at}:\n\n{page.text[:PAGE_CHARS]}"),
        quotes=[research.Quote(1, passage, url)])
    await research._check(finding)
    return [finding]


def excerpt(text: str, request: str) -> str:
    """The paragraphs of a page that share most words with the request, in
    the page's own order, up to EXCERPT_CHARS."""
    wanted = set(WORD.findall(request.casefold()))
    paragraphs = [p.strip() for p in text.splitlines() if len(p.strip()) > 40]
    ranked = sorted(range(len(paragraphs)), key=lambda i: -len(
        wanted & set(WORD.findall(paragraphs[i].casefold()))))
    keep, used = [], 0
    for i in ranked:
        if used + len(paragraphs[i]) > EXCERPT_CHARS:
            continue
        keep.append(i)
        used += len(paragraphs[i])
    return "\n".join(paragraphs[i] for i in sorted(keep))


async def fetched(client, request, gaps, **kwargs):
    findings = await ORIGINAL(client, request, gaps, **kwargs)
    for finding in findings:
        urls = list(dict.fromkeys(
            [q.url for q in finding.quotes] + list(finding.citations)))[:MAX_PAGES]
        blocks = []
        for url in urls:
            page = await fetch_source(url)
            if page.fetched:
                blocks.append(f"--- {url} (fetched {page.fetched_at}) ---\n"
                              f"{excerpt(page.text, request)}")
        if blocks:
            finding.answer += (
                "\n\nTEXT OF THE PAGES CITED, AS FETCHED BY THE HARNESS. These "
                "are the pages' own words; the answer above is a search "
                "model's summary of them.\n"
                + (PRIMARY + "\n" if ARM == "fetched_primary" else "")
                + "\n\n".join(blocks))
    return findings


if ARM == "oracle":
    research.research_gaps = oracle
elif ARM in ("fetched", "fetched_primary"):
    research.research_gaps = fetched
else:
    raise SystemExit(f"ARM {ARM!r} is not oracle, fetched or fetched_primary")
sys.argv = ["short_workflows_measurement.py", out, "0", "1", repeats,
            max_spend, question_id]
runpy.run_path(str(HERE / "short_workflows_measurement.py"), run_name="__main__")
