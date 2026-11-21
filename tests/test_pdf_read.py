"""A PDF is read in processes that can be stopped, not in a thread that cannot.

pypdf is pure Python, so the old read (a thread each) took turns on one core and went on running after
its page had been given up. Measured 2026-11-21 on 16 PDFs that gave no answer in earlier runs, read
four at a time in processes of their own with no network and no model: they took 8.9 to 134.4 s, a
653-page datasheet 49.9 s, NIST SP 800-53 Rev. 5 80.6 s. The tests here pin what the change must keep
(the text is exactly the one-process text), what it must do (stop the processes when the time is up,
never run more than the set number at once, fall back to a thread when processes cannot start) and
what the fetch says about a PDF that ran out of time.
"""

from __future__ import annotations

import ast
import asyncio
import io
import os
import signal
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from autornd.knowledge import fetch, pdf_read
from autornd.knowledge.fetch import pdf_text
from autornd.knowledge.pdf_read import PdfFailed, read_pdf

PAGE = "https://example.org/standard.pdf"


def _pdf_pages(texts: list[str]) -> bytes:
    """A PDF with one page for each of `texts` (empty: a page with no text layer)."""
    count = len(texts)
    font = 3 + 2 * count
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(count))
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode()]
    for i, text in enumerate(texts):
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode() if text else b""
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> >>".encode())
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream
                       + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, xref))
    return bytes(out)


def _encrypted(pdf: bytes, user_password: str) -> bytes:
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf)))
    writer.encrypt(user_password, owner_password="owner", algorithm="AES-256")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.fixture
def served(monkeypatch):
    """A page address that serves the PDF handed to it, with names resolving
    to a public address and every PDF big enough to be read in processes."""
    async def public(host):
        return ["93.184.216.34"]

    def serve(raw: bytes) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"content-type": "application/pdf"},
                                  content=raw)
        monkeypatch.setattr(fetch, "_transport", httpx.MockTransport(handler))

    monkeypatch.setattr(fetch, "_addresses", public)
    monkeypatch.setattr(fetch, "PARALLEL_MIN_BYTES", 0)
    return serve


class TestTheTextIsTheOneProcessText:
    @pytest.mark.parametrize("pages, processes", [
        (7, 3),    # the stripes hold 3, 2 and 2 pages
        (2, 4),    # more processes than pages: two have nothing to read
        (1, 2),
        (12, 1),
    ])
    async def test_pages_come_back_in_order_whatever_process_read_them(
            self, monkeypatch, pages, processes):
        monkeypatch.setattr(pdf_read, "workers", lambda: processes)
        raw = _pdf_pages([f"page number {i}" for i in range(pages)])
        text = await read_pdf(raw)
        assert text == pdf_text(raw)
        where = [text.index(f"page number {i}") for i in range(pages)]
        assert where == sorted(where), "page order is the document's"

    async def test_a_page_with_no_text_keeps_its_place(self, monkeypatch):
        monkeypatch.setattr(pdf_read, "workers", lambda: 2)
        raw = _pdf_pages(["first", "", "third"])
        text = await read_pdf(raw)
        assert text == pdf_text(raw)
        assert text.index("first") < text.index("third")

    async def test_progress_says_how_many_pages_there_are_and_how_many_are_read(
            self, monkeypatch):
        monkeypatch.setattr(pdf_read, "workers", lambda: 2)
        progress: dict[str, int] = {}
        await read_pdf(_pdf_pages(["a", "b", "c", "d", "e"]), progress)
        assert progress == {"pages": 5, "done": 5}

    async def test_the_temporary_file_is_gone_afterwards(self, monkeypatch):
        seen: list[str] = []
        real = pdf_read.tempfile.mkstemp

        def watching(*args, **kwargs):
            handle, name = real(*args, **kwargs)
            seen.append(name)
            return handle, name

        monkeypatch.setattr(pdf_read.tempfile, "mkstemp", watching)
        monkeypatch.setattr(pdf_read, "workers", lambda: 2)
        await read_pdf(_pdf_pages(["a", "b"]))
        assert len(seen) == 1 and not os.path.exists(seen[0])


class TestWhatAFailedReadSays:
    async def test_a_pdf_that_needs_a_password_says_so(self, monkeypatch):
        monkeypatch.setattr(pdf_read, "workers", lambda: 2)
        raw = _encrypted(_pdf_pages(["secret page"]), "secret")
        with pytest.raises(PdfFailed) as caught:
            await read_pdf(raw)
        assert caught.value.name == "PasswordProtected"

    async def test_a_pdf_encrypted_with_no_password_is_opened(self, monkeypatch):
        """Datasheets are encrypted against editing, not reading."""
        monkeypatch.setattr(pdf_read, "workers", lambda: 2)
        raw = _encrypted(_pdf_pages(["open page"]), "")
        assert "open page" in await read_pdf(raw)

    @pytest.mark.parametrize("raw, reason", [
        (_encrypted(_pdf_pages(["x"]), "secret"),
         "the PDF could not be read: PasswordProtected"),
        (b"%PDF-1.7 broken", "the PDF could not be read"),
        (_pdf_pages([""]), "the PDF has no text layer"),
    ])
    async def test_the_fetch_gives_the_same_reason_in_processes_as_in_a_thread(
            self, monkeypatch, served, raw, reason):
        served(raw)
        in_processes = await fetch.fetch_source(PAGE)
        monkeypatch.setattr(fetch, "PARALLEL_MIN_BYTES", 10**9)
        in_a_thread = await fetch.fetch_source(PAGE)
        assert in_processes.status == in_a_thread.status == "failed"
        assert in_processes.reason == in_a_thread.reason
        assert in_processes.reason.startswith(reason)


STUB = '''
import os, sys, time
stripe, stride = int(sys.argv[2]), int(sys.argv[3])
here = os.environ["STUB_DIR"]
mode = os.environ["STUB_MODE"]
out = sys.stdout.buffer
if mode == "hangs":
    open(os.path.join(here, "pid%d" % os.getpid()), "w").close()
    out.write(b"N 8\\n"); out.write(b"P %d 2\\nhi" % stripe); out.flush()
    time.sleep(60)
elif mode == "dies":
    out.write(b"N 8\\n"); out.flush()
    sys.exit(3)
else:
    with open(os.path.join(here, "events"), "a") as log:
        log.write("S %f\\n" % time.time())
    out.write(b"N 2\\n"); out.flush()
    time.sleep(0.4)
    for index in range(stripe, 2, stride):
        out.write(b"P %d 2\\np%d" % (index, index))
    out.flush()
    with open(os.path.join(here, "events"), "a") as log:
        log.write("E %f\\n" % time.time())
'''


@pytest.fixture
def stub(monkeypatch, tmp_path):
    """A reading process that does what a test asks of it instead of reading."""
    script = tmp_path / "stub_worker.py"
    script.write_text(STUB)
    monkeypatch.setattr(pdf_read, "WORKER", script)
    monkeypatch.setenv("STUB_DIR", str(tmp_path))
    monkeypatch.setattr(pdf_read, "workers", lambda: 2)

    def mode(name: str) -> Path:
        monkeypatch.setenv("STUB_MODE", name)
        return tmp_path

    yield mode
    for pid_file in tmp_path.glob("pid*"):    # a test that failed leaves none behind
        try:
            os.kill(int(pid_file.name[3:]), signal.SIGKILL)
        except ProcessLookupError:
            pass


class TestTheSourceSaysHowManyPages:
    """A proof of absence names the size of the document it searched (owner's ruling of 2026-11-21,
    option C), so a PDF read in processes says how many pages it has."""

    async def test_a_pdf_read_in_processes_has_its_page_count(self, monkeypatch, served):
        monkeypatch.setattr(pdf_read, "workers", lambda: 2)
        served(_pdf_pages([f"page {i}" for i in range(5)]))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "fetched" and source.pages == 5

    async def test_a_page_that_was_not_read_in_processes_has_none(self, monkeypatch, served):
        monkeypatch.setattr(fetch, "PARALLEL_MIN_BYTES", 10 ** 9)    # read in a thread, as a small one is
        served(_pdf_pages(["a", "b", "c"]))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "fetched" and source.pages == 0

    async def test_a_failed_read_has_none(self, served):
        served(b"%PDF-1.4 not a document")
        source = await fetch.fetch_source(PAGE)
        assert source.status == "failed" and source.pages == 0

    async def test_a_read_that_failed_after_the_count_was_known_has_none(self, monkeypatch):
        """The count is the size of a page read in full; a read that failed says nothing of size."""
        async def failed_after_counting(url, progress):
            progress["pages"] = 7
            return fetch.Source(url=url, status="failed", reason="the PDF could not be read: Broken")

        monkeypatch.setattr(fetch, "_fetch", failed_after_counting)
        source = await fetch.fetch_source(PAGE)
        assert source.status == "failed" and source.pages == 0


class TestWhenTheTimeIsUp:
    async def test_the_processes_are_stopped_and_the_fetch_says_how_far_it_got(
            self, monkeypatch, served, stub):
        """A PDF that cannot finish in time: its processes must not go on
        burning the cores, and the record says 2 of 8 pages were read."""
        here = stub("hangs")
        served(b"%PDF-1.4 stand-in")
        monkeypatch.setattr(fetch, "FETCH_TIMEOUT_SECONDS", 1.5)
        source = await fetch.fetch_source(PAGE)
        assert source.status == "failed"
        assert source.reason == "no answer within 1.5 s (read 2 of 8 pages)"
        pids = [int(p.name[3:]) for p in here.glob("pid*")]
        assert len(pids) == 2
        for pid in pids:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)

    async def test_every_process_is_reaped_before_the_read_gives_up(
            self, monkeypatch, served, stub):
        """One stripe finishing its kill first must not cut the others' wait
        short. Found by CI on 2026-11-21: `gather` raised as soon as the first
        stripe was cancelled, and cancelling the second again, mid-wait, left
        its killed process there when the fetch returned."""
        stub("hangs")
        served(b"%PDF-1.4 stand-in")
        real_wait = asyncio.subprocess.Process.wait
        started: list[int] = []
        ended: list[int] = []

        async def slow_second(self):
            started.append(self.pid)
            if len(started) == 2:      # the second process is reaped later than the first
                await asyncio.sleep(0.3)
            code = await real_wait(self)
            ended.append(self.pid)
            return code

        monkeypatch.setattr(asyncio.subprocess.Process, "wait", slow_second)
        monkeypatch.setattr(fetch, "FETCH_TIMEOUT_SECONDS", 1.5)
        source = await fetch.fetch_source(PAGE)
        assert source.status == "failed"
        assert len(started) == 2
        assert sorted(ended) == sorted(started), "a process was left unreaped"

    async def test_a_worker_that_dies_is_a_failed_read_not_a_hang(
            self, served, stub):
        stub("dies")
        served(b"%PDF-1.4 stand-in")
        source = await fetch.fetch_source(PAGE)
        assert source.status == "failed"
        assert source.reason == "the PDF could not be read: WorkerExit3"

    async def test_a_page_that_is_not_a_pdf_says_nothing_about_pages(
            self, monkeypatch, served):
        """The reason of an ordinary timeout is unchanged."""
        async def slow(request):
            await asyncio.sleep(5)

        monkeypatch.setattr(fetch, "FETCH_TIMEOUT_SECONDS", 0.05)
        monkeypatch.setattr(fetch, "_transport", httpx.MockTransport(slow))
        source = await fetch.fetch_source(PAGE)
        assert source.reason == "no answer within 0.05 s"


class TestTheNumberOfProcessesRunningAtOnce:
    async def test_no_more_than_the_set_number_run_at_once(self, stub):
        here = stub("counts")
        await asyncio.gather(*(read_pdf(b"%PDF-1.4 stand-in") for _ in range(3)))
        events = sorted(
            (float(line.split()[1]), line[0])
            for line in (here / "events").read_text().splitlines())
        running = peak = 0
        for _, kind in events:
            running += 1 if kind == "S" else -1
            peak = max(peak, running)
        assert len(events) == 12, "three reads of two processes each"
        assert peak == 2


class TestWhenProcessesCannotStart:
    async def test_the_read_falls_back_to_a_thread(self, monkeypatch, served, caplog):
        async def refuse(*args, **kwargs):
            raise OSError("no processes here")

        monkeypatch.setattr(pdf_read.asyncio, "create_subprocess_exec", refuse)
        served(_pdf_pages(["a sentence read in a thread"]))
        with caplog.at_level("WARNING"):
            source = await fetch.fetch_source(PAGE)
        assert source.status == "fetched"
        assert "a sentence read in a thread" in source.text
        assert "could not start" in caplog.text

    async def test_a_small_pdf_starts_no_process(self, monkeypatch, served):
        async def forbidden(*args, **kwargs):
            raise AssertionError("a small PDF is read in a thread")

        monkeypatch.setattr(pdf_read.asyncio, "create_subprocess_exec", forbidden)
        monkeypatch.setattr(fetch, "PARALLEL_MIN_BYTES", 10**9)
        served(_pdf_pages(["a small one"]))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "fetched" and "a small one" in source.text


class TestTheWorkerOnItsOwn:
    def test_it_imports_nothing_from_autornd(self):
        """It starts in a fraction of a second and does not depend on where
        the parent was started from."""
        tree = ast.parse(pdf_read.WORKER.read_text())
        imported = {alias.name.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, ast.Import) for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.module}
        assert "autornd" not in imported

    def test_it_writes_the_page_count_then_each_page_of_its_stripe(self, tmp_path):
        from pypdf import PdfReader
        path = tmp_path / "three.pdf"
        path.write_bytes(_pdf_pages(["zero", "one", "two"]))
        page = PdfReader(str(path)).pages[1].extract_text().encode()
        done = subprocess.run(
            [sys.executable, str(pdf_read.WORKER), str(path), "1", "2"],
            capture_output=True, timeout=60)
        assert done.returncode == 0
        assert done.stdout == b"N 3\n" + b"P 1 %d\n" % len(page) + page

    def test_it_names_the_error_and_exits_2_when_it_cannot_go_on(self, tmp_path):
        path = tmp_path / "broken.pdf"
        path.write_bytes(b"%PDF-1.7 broken")
        done = subprocess.run(
            [sys.executable, str(pdf_read.WORKER), str(path), "0", "1"],
            capture_output=True, timeout=60)
        assert done.returncode == 2
        assert done.stdout.startswith(b"E ") and done.stdout.endswith(b"\n")
