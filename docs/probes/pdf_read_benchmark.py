"""How long does turning a PDF into text take, and does reading it in processes help?
Free: no model call, no spend, no key. The network is used only to download the sample.

    python docs/probes/pdf_read_benchmark.py download DIR
    python docs/probes/pdf_read_benchmark.py onecore DIR ID
    python docs/probes/pdf_read_benchmark.py alone DIR IDS
    python docs/probes/pdf_read_benchmark.py lookup DIR IDS old|new

IDS is a comma-separated list of sample numbers (0 to 15). `download` saves the 16 PDFs below as
DIR/00.pdf ... DIR/15.pdf: PDFs that gave no answer in the runs of 2026-11-17 to 21. `onecore` reads
one of them with the harness's own one-process reader (`pdf_text`) and prints the open time, the read
time and the cpu time. `alone` reads each through `read_pdf` (processes) and again through `pdf_text`,
and says whether the text is the same. `lookup` reads the IDS together under the fetch's own limit, as
a lookup's pages are, either in threads as the harness did before (`old`) or in processes (`new`), and
says when each finished (null: not read in time).

The records of 2026-11-21 are docs/traces/20261121T-pdf-read-onecore.jsonl (`onecore`, four at a time)
and 20261121T-pdf-read-old-vs-new.jsonl (`alone` and `lookup`, run one scenario to a process on an
idle machine); they were written by the two scratch scripts this one is made from, with the same fields.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION", "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"
os.environ.pop("OPENROUTER_API_KEY", None)

SAMPLE = [
    "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf",
    "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-171r3.pdf",
    "https://webassembly.github.io/spec/versions/core/WebAssembly-3.0.pdf",
    "https://gnssn.iaea.org/CSN/CSN%20training/Shared%20Documents/GSR%20Part%203.pdf",
    "https://assets.publishing.service.gov.uk/media/67d0230974b001c38a0287ad/Approved_Document_B_volume_1_-_Dwellings_2019_edition_incorporating_2020_and_2022_amendments_collated_with_2025_2026_and_2029_amendments.pdf",
    "https://www.microchip.com/content/dam/mchp/documents/MCU08/ProductDocuments/DataSheets/ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf",
    "https://cdn-shop.adafruit.com/datasheets/ATMEGA328P.pdf",
    "https://rampac.energy.gov/docs/default-source/iaeainfo/ssr-6-2025.pdf",
    "https://rampac.energy.gov/docs/default-source/transportation/SSG26.pdf",
    "https://mutcd.fhwa.dot.gov/pdfs/11th_Edition/Part4.pdf",
    "https://www-pub.iaea.org/MTCD/Publications/PDF/Pub1384_web.pdf",
    "https://datasheet.lcsc.com/datasheet/pdf/5e2a4d5387b552e1e87c18929a1566a3.pdf?productCode=C614188",
    "https://www.boe.es/doue/2026/1695/L00001-00121.pdf",
    "https://rampac.energy.gov/docs/default-source/iaeainfo/ssr-6-2018.pdf",
    "https://www-pub.iaea.org/mtcd/publications/pdf/pub1260_web.pdf",
    "https://mutcd.fhwa.dot.gov/pdfs/11th_Edition/mutcd11theditionhl.pdf",
]


def download(directory: Path) -> None:
    import httpx
    directory.mkdir(parents=True, exist_ok=True)
    for number, url in enumerate(SAMPLE):
        started = time.time()
        reply = httpx.get(url, follow_redirects=True, timeout=180,
                          headers={"User-Agent": "AutoRnD-OS PDF benchmark"})
        ok = reply.status_code == 200 and reply.content[:4] == b"%PDF"
        if ok:
            (directory / f"{number:02d}.pdf").write_bytes(reply.content)
        print(json.dumps({"i": number, "status": reply.status_code, "pdf": ok,
                          "bytes": len(reply.content), "seconds": round(time.time() - started, 1)}))


def one_core(directory: Path, number: str) -> None:
    from pypdf import PdfReader

    from autornd.knowledge.fetch import pdf_text
    raw = (directory / f"{int(number):02d}.pdf").read_bytes()
    cpu, started = time.process_time(), time.time()
    pages = len(PdfReader(io.BytesIO(raw)).pages)
    opened = time.time() - started
    began = time.time()
    text = pdf_text(raw)
    print(json.dumps({"file": f"{int(number):02d}.pdf", "mb": round(len(raw) / 1e6, 1),
                      "pages": pages, "open_s": round(opened, 2),
                      "read_s": round(time.time() - began, 1),
                      "cpu_s": round(time.process_time() - cpu, 1), "chars": len(text)}))


async def alone(directory: Path, numbers: list[str]) -> None:
    from autornd.knowledge import pdf_read
    from autornd.knowledge.fetch import pdf_text
    for number in numbers:
        raw = (directory / f"{int(number):02d}.pdf").read_bytes()
        began = time.time()
        text = await pdf_read.read_pdf(raw)
        new_s = time.time() - began
        began = time.time()
        reference = await asyncio.to_thread(pdf_text, raw)
        one_core_s = time.time() - began
        print(json.dumps({"mode": "alone", "i": int(number), "workers": pdf_read.workers(),
                          "new_s": round(new_s, 1), "one_core_s": round(one_core_s, 1),
                          "speedup": round(one_core_s / new_s, 2), "same_text": text == reference,
                          "chars": len(text)}), flush=True)


async def lookup(directory: Path, numbers: list[str], how: str) -> None:
    from autornd.knowledge import fetch, pdf_read
    limit = fetch.FETCH_TIMEOUT_SECONDS
    raws = {n: (directory / f"{int(n):02d}.pdf").read_bytes() for n in numbers}
    started, finished = time.time(), {}

    async def read(number: str) -> None:
        try:
            async with asyncio.timeout(limit):
                if how == "old":
                    await asyncio.to_thread(fetch.pdf_text, raws[number])
                else:
                    await pdf_read.read_pdf(raws[number])
            finished[number] = round(time.time() - started, 1)
        except TimeoutError:
            finished[number] = None

    await asyncio.gather(*(read(n) for n in numbers))
    print(json.dumps({"mode": "lookup", "how": how, "limit": limit,
                      "ids": [int(n) for n in numbers],
                      "finished_at_s": {int(n): finished[n] for n in numbers},
                      "read_in_time": sum(v is not None for v in finished.values()),
                      "of": len(numbers), "wall_s": round(time.time() - started, 1)}), flush=True)


if __name__ == "__main__":
    mode, folder = sys.argv[1], Path(sys.argv[2])
    if mode == "download":
        download(folder)
    elif mode == "onecore":
        one_core(folder, sys.argv[3])
    elif mode == "alone":
        asyncio.run(alone(folder, sys.argv[3].split(",")))
    else:
        asyncio.run(lookup(folder, sys.argv[3].split(","), sys.argv[4]))
    sys.stdout.flush()
    # A thread of the old read that ran past its limit is still reading; do not wait for it.
    os._exit(0)
