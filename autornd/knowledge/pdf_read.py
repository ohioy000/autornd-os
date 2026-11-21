"""Read a PDF's text in parallel processes, and stop them when the time is up.

pypdf is pure Python, so threads take turns on one core, and a thread cannot be stopped: the old read
ran in `asyncio.to_thread`, a lookup's PDFs queued behind each other, and a read that ran past the
limit went on burning the core after its page had been given up. Measured 2026-11-21 on 16 PDFs that
gave no answer in earlier runs, each read in a process of its own with no network and no model: four
at a time on this two-core laptop they took 8.9 to 134.4 s (the whole MUTCD, 1,161 pages, 134.4 s;
NIST SP 800-53 Rev. 5 80.6 s; a 653-page datasheet 49.9 s), and the 12 that were also read alone on
an idle machine took 3.7 to 47.1 s (SP 800-53 47.1 s, the datasheet 28.4 s). Cpu time was 78 to 100%
of wall time, so the time is pypdf's parse: nothing waits on a model, and the downloads took 0.7 to
15 s. Read together under the fetch's 60 s, as a lookup does, six IAEA PDFs gave 1 read before and 6
after (all by 23.5 s), and six heavy ones gave 0 before and 3 after.

So each PDF is written to a temporary file and read by `workers()` processes at once, each taking
every `workers()`-th page (`pdf_worker.py`); the pages are joined in order and are the text the one-process
read gives. A process is killed when its read is cancelled, which is what the fetch's time limit does.
At most `workers()` processes run at once across all the PDFs of a run, in the order they asked, so a
lookup's six large PDFs share the cores instead of each starting a full set.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

WORKER = Path(__file__).with_name("pdf_worker.py")

# A PDF smaller than this is read in a thread as before: starting a process and opening the file in
# it costs a fraction of a second, which a small PDF does not repay.
PARALLEL_MIN_BYTES = 250_000

# The most processes that read at once. One per core, up to this: each holds the whole document, and
# the two largest of the 16 measured (a 33 MB datasheet and a 29 MB manual) took 92 and 183 MB in a
# process, so eight is at most about 1.5 GB. A judgment, not a measured optimum.
MAX_WORKERS = 8


class PdfFailed(ValueError):
    """The document could not be read; `name` is the error the reading process hit."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class PdfUnavailable(RuntimeError):
    """The reading processes could not be started here; the caller reads in a thread."""


def workers() -> int:
    """How many processes read at once: one per core this process may use, at most MAX_WORKERS."""
    try:
        cores = len(os.sched_getaffinity(0))
    except AttributeError:
        cores = os.cpu_count() or 1
    return max(1, min(cores, MAX_WORKERS))


# The run-wide limit on reading processes, one per event loop (a semaphore belongs to the loop that
# first waits on it, and the suite runs each test on its own).
_slots: dict[int, tuple[asyncio.AbstractEventLoop, asyncio.Semaphore]] = {}


def _limit() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    for key in [k for k, (held, _) in _slots.items() if held.is_closed()]:
        del _slots[key]
    entry = _slots.get(id(loop))
    if entry is None or entry[0] is not loop:
        entry = _slots[id(loop)] = (loop, asyncio.Semaphore(workers()))
    return entry[1]


async def _read_stripe(path: Path, stripe: int, stride: int,
                       pages: dict[int, str], progress: dict[str, int]) -> None:
    """Start one reading process and take its pages as they arrive."""
    async with _limit():
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(WORKER), str(path), str(stripe), str(stride),
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL)
        except (OSError, NotImplementedError) as exc:
            raise PdfUnavailable(f"{type(exc).__name__}: {exc}") from exc
        try:
            while header := await process.stdout.readline():
                kind, *fields = header.split()
                if kind == b"N":
                    progress["pages"] = int(fields[0])
                elif kind == b"P":
                    index, size = int(fields[0]), int(fields[1])
                    body = await process.stdout.readexactly(size)
                    pages[index] = body.decode("utf-8", "surrogatepass")
                    progress["done"] = len(pages)
                elif kind == b"E":
                    raise PdfFailed(fields[0].decode("ascii", "replace")
                                    if fields else "Error")
                else:
                    raise PdfFailed("BadWorkerReply")
            if await process.wait() != 0:
                raise PdfFailed(f"WorkerExit{process.returncode}")
        except PdfFailed:
            raise
        except (ValueError, IndexError) as exc:
            raise PdfFailed("BadWorkerReply") from exc
        except asyncio.IncompleteReadError as exc:
            raise PdfFailed("WorkerDied") from exc
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()


async def read_pdf(raw: bytes, progress: dict[str, int] | None = None) -> str:
    """The text layer of a PDF, pages in order, the same text `pdf_text` gives.

    `progress` is filled as the pages come in ("pages": how many the PDF has, "done": how many are
    read), so a caller that gives up can say how far it got. Raises PdfFailed when the document
    cannot be read (a password, a broken file) and PdfUnavailable when the processes cannot start.
    """
    progress = progress if progress is not None else {}
    stride = workers()
    pages: dict[int, str] = {}
    handle, name = tempfile.mkstemp(prefix="autornd-", suffix=".pdf")
    os.close(handle)
    path = Path(name)
    tasks: list[asyncio.Future] = []
    try:
        await asyncio.to_thread(path.write_bytes, raw)
        tasks = [asyncio.ensure_future(_read_stripe(path, stripe, stride, pages, progress))
                 for stripe in range(stride)]
        try:
            # Not gather: it raises the moment ONE stripe is cancelled or fails, while the others are
            # still killing their process, and cancelling those again here cut their wait short and
            # left the process unreaped (found by CI on 2026-11-21: a killed process still there when
            # the fetch returned). `wait` stops nothing by itself.
            await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
            for task in tasks:
                if task.done():
                    task.result()      # the first stripe's failure, if one failed
        except BaseException:
            # One failed, or the caller's time ran out: stop the rest, once, and return only when
            # every process has been killed and reaped.
            for task in tasks:
                task.cancel()
            await asyncio.wait(tasks)
            for task in tasks:         # every outcome is read, so none is reported as never retrieved
                if not task.cancelled():
                    task.exception()
            raise
        total = progress.get("pages", 0)
        if len(pages) != total:
            raise PdfFailed("MissingPages")
        return "\n".join(pages[index] for index in range(total))
    finally:
        path.unlink(missing_ok=True)
