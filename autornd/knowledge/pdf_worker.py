"""Read some of one PDF's pages with PDFium and write their text to stdout. Run as a script:

    python pdf_worker.py PATH STRIPE STRIDE

It reads pages STRIPE, STRIPE + STRIDE, STRIPE + 2 * STRIDE, ... of the PDF at PATH and writes each
the moment it is read, so a parent that stops waiting still knows how far it got. The parent
(`pdf_read.py`) starts one of these for each stripe and joins the pages in order.

Standalone on purpose: it imports nothing from autornd, so it starts in a fraction of a second and
does not depend on where the parent was started from. PDFium is not thread-safe, which is the other
reason for a process of its own.

What it writes, all on stdout:

    N <pages>                      first: how many pages the PDF has
    P <index> <bytes>              then for each page read: its number (from 0) and the byte length,
    <the page's text, UTF-8>       followed by that many bytes of text
    E <ErrorName>                  instead of the rest, if it cannot go on; the exit status is 2

A page's text is what `page_text` below makes of PDFium's, which is not the text `fetch.pdf_text` (pypdf,
the fallback) gives: the two libraries put spaces and line ends in different places. Lone surrogates
are written and read back as they are (`surrogatepass`).
"""
from __future__ import annotations

import sys

# PDFium writes this character where a line ended in a hyphen and the word went on in the next line
# ("organization-" and "defined" come out as "organization", this, "defined"), and joins the two lines.
# It is a hyphen: a compound word's own ("organization-defined") or a typesetter's, so it is written
# as the hyphen the page shows and not as a character no reader would type into a quote. Measured
# 2026-11-21 (docs/traces/20261121T-pdfium-passage-parity.jsonl): 28 of 35 PDFs of the second
# hold-out's pages have it, 58 to 300 times in the larger ones; but on the 356 passages the extract
# kept, writing it as a hyphen, dropping it and leaving it found the same 303, so this is chosen for
# being faithful to the page and not because a count needed it. chr() and not an escape, because an
# escape typed into a tool arrives as the invisible character itself.
HYPHEN_MARK = chr(0xFFFE)


def page_text(page) -> str:
    """One page's text: PDFium's, with its line ends (carriage return and line feed) as line feeds and
    the mark it leaves for a hyphen at the end of a line written as that hyphen."""
    textpage = page.get_textpage()
    try:
        text = textpage.get_text_range()
    finally:
        textpage.close()
    return text.replace("\r\n", "\n").replace(HYPHEN_MARK, "-")


def main(argv: list[str]) -> int:
    path, stripe, stride = argv[1], int(argv[2]), int(argv[3])
    out = sys.stdout.buffer
    try:
        import pypdfium2 as pdfium
        import pypdfium2.raw as pdfium_c
        try:
            document = pdfium.PdfDocument(path)
        except pdfium.PdfiumError as exc:
            # A document locked against editing only opens without a word, as in a viewer. Only the
            # error code tells one that needs a password from one that is damaged.
            if exc.err_code == pdfium_c.FPDF_ERR_PASSWORD:
                out.write(b"E PasswordProtected\n")
                out.flush()
                return 2
            raise
        count = len(document)
        out.write(b"N %d\n" % count)
        out.flush()
        for index in range(stripe, count, stride):
            page = document[index]
            try:
                text = page_text(page).encode("utf-8", "surrogatepass")
            finally:
                page.close()
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
