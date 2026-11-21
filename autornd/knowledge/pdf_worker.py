"""Read some of one PDF's pages and write their text to stdout. Run as a script:

    python pdf_worker.py PATH STRIPE STRIDE

It reads pages STRIPE, STRIPE + STRIDE, STRIPE + 2 * STRIDE, ... of the PDF at PATH and writes each
the moment it is read, so a parent that stops waiting still knows how far it got. The parent
(`pdf_read.py`) starts one of these for each stripe and joins the pages in order.

Standalone on purpose: it imports nothing from autornd, so it starts in a fraction of a second and
does not depend on where the parent was started from.

What it writes, all on stdout:

    N <pages>                      first: how many pages the PDF has
    P <index> <bytes>              then for each page read: its number (from 0) and the byte length,
    <the page's text, UTF-8>       followed by that many bytes of text
    E <ErrorName>                  instead of the rest, if it cannot go on; the exit status is 2

Lone surrogates are written and read back as they are (`surrogatepass`), so the text the parent gets
is exactly what `"\\n".join(page.extract_text() or "" ...)` gives in one process.
"""
from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    path, stripe, stride = argv[1], int(argv[2]), int(argv[3])
    out = sys.stdout.buffer
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        # Many datasheets are encrypted with an empty password, to forbid
        # editing and not reading; a viewer opens them without asking.
        if reader.is_encrypted and not reader.decrypt(""):
            out.write(b"E PasswordProtected\n")
            out.flush()
            return 2
        pages = reader.pages
        out.write(b"N %d\n" % len(pages))
        out.flush()
        for index in range(stripe, len(pages), stride):
            text = (pages[index].extract_text() or "").encode("utf-8", "surrogatepass")
            out.write(b"P %d %d\n" % (index, len(text)))
            out.write(text)
            out.flush()
    except Exception as exc:  # the parent reports the name
        out.write(b"E " + type(exc).__name__.encode("ascii", "replace") + b"\n")
        out.flush()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
