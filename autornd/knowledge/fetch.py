"""Fetch a page a lookup quoted, and record which version was read (Ruling D56 (2)).

A lookup's citations are the provider's word that it read a page. This module
reads the page itself, so a quoted passage can be looked for in what the page
actually says. Every fetch records what it read: the final address, when, the
sha256 of the bytes, and the server's own version marks (Last-Modified, ETag),
so a later reader can tell whether the page has changed since.

The addresses come from model output, and a page can steer a model, so a fetch
refuses anything that is not a public web address: no other scheme, no
loopback, private or link-local network. Each redirect is checked the same way.
The request goes to the address the check approved, with the name in the Host
header and the TLS server name, so the name is resolved once per hop: a name
that answers one way to the check and another to the connection cannot pass
(D56, amended 2026-10-28; the first version resolved it twice).
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import ipaddress
import json
import logging
import re
import socket
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

# The whole fetch, redirects included, in seconds. A lookup's pages are
# fetched together, so it waits for its slowest page, not the sum. Was 10,
# set by judgment. Measured live 2026-11-12: three of seven quoted pages, all
# PDFs from one standards body, gave no answer within 10 s, and their answers
# went unverified. 25 is still a judgment, not a measured optimum: long
# enough for a PDF of a few megabytes on a slow host, short beside a run
# that takes minutes.
FETCH_TIMEOUT_SECONDS = 25.0

# A page larger than this is not read. Was 2 MB, sized for HTML. Measured
# live 2026-11-12: a quoted specification PDF was over it. Standards and
# datasheets as PDF run to several megabytes; 15 MB covers them and still
# bounds what a run holds.
FETCH_MAX_BYTES = 15_000_000

# Redirects followed, each checked as the first address was.
MAX_REDIRECTS = 3

# Distinct pages fetched for one lookup. A bundled lookup quotes a few pages
# per question; past this many the rest are recorded unfetched.
MAX_FETCHES = 8

# What can be read as text. A PDF is read through pypdf: standards bodies
# and makers publish datasheets and codes as PDF, and before this every one
# of them was recorded unfetched (audit of 2026-11-11). A scanned PDF has no
# text layer and is recorded failed, so the gap shows.
# XML is read as HTML is, its markup dropped: govinfo.gov publishes the Code
# of Federal Regulations as XML, and on 2026-11-12 both such pages a lookup
# quoted were recorded unfetched for their content type.
# Feeds are XML too: open paper indexes answer a query as Atom.
HTML_TYPES = ("text/html", "application/xhtml+xml", "application/xml",
              "text/xml", "application/atom+xml", "application/rss+xml")
TEXT_TYPES = ("text/plain", "text/markdown", "text/csv",
              "text/tab-separated-values")
PDF_TYPES = ("application/pdf",)
# The answer of a public database's web interface (a paper index, a
# chemical or materials register, a standards catalogue) is JSON. It is
# read as its keys and values, one per line, so a quoted value is found as
# written and not behind JSON's escapes. Any type ending +json is JSON.
JSON_TYPES = ("application/json", "text/json")
# Books and office documents: each is a zip of XML, read with the standard
# library. Added on the owner's word of 2026-11-13, to read as much of what
# a lookup can quote as the fetch safely can; none has been met live yet.
EPUB_TYPES = ("application/epub+zip",)
DOCX_TYPES = ("application/vnd.openxmlformats-officedocument"
              ".wordprocessingml.document",)
PPTX_TYPES = ("application/vnd.openxmlformats-officedocument"
              ".presentationml.presentation",)
XLSX_TYPES = ("application/vnd.openxmlformats-officedocument"
              ".spreadsheetml.sheet",)
# A server that does not say what a file is. Makers' sites serve datasheets
# this way. The file is then read by its first bytes and, for a zip, by the
# members that mark it as a book or an office document; anything else is
# refused as before.
UNNAMED_TYPES = ("application/octet-stream", "binary/octet-stream",
                 "application/zip", "application/x-zip-compressed", "")

# What one zipped document may unpack to, in bytes, summed over the members
# read. A zip can hold far more than its size, so the read is bounded as the
# fetch is. A judgment: four times the fetch cap, above any real book's text.
ZIP_MAX_BYTES = 60_000_000

# The eCFR's reader page answers an automated client with a "Request Access"
# challenge, HTTP 200; its renderer API returns the same section as HTML
# (read live 2026-11-11: the section text came back and its quote was
# found). A section address is fetched through the API instead.
_ECFR_SECTION = re.compile(
    r"^https?://(?:www\.)?ecfr\.gov/current/title-(?P<title>\d+)/"
    r"(?:[^?#]*/)?section-(?P<part>\d+)\.(?P<section>[\w.-]+?)/?(?:[?#].*)?$",
    re.IGNORECASE)

# A page that asks the reader to prove they are a person. It arrives as HTTP
# 200 with a little text, so without this it was recorded as fetched and
# every quote read as "not found in the page" when the page was never read.
_CHALLENGE_MARKS = ("captcha", "request access", "verify you are human",
                    "are you a robot", "unusual traffic",
                    "enable javascript and cookies")
# A real page that mentions one of the marks is longer than this. Not
# measured: the eCFR challenge page read on 2026-11-11 was about 900
# characters of text.
CHALLENGE_MAX_CHARS = 2500

USER_AGENT = "AutoRnD-OS source check"

# The suite blocks the network: tests set an httpx.MockTransport here.
_transport: httpx.AsyncBaseTransport | None = None


@dataclass
class Source:
    """One fetch of one page: what was read, and which version it was."""

    url: str
    status: str                  # "fetched", "refused" or "failed"
    reason: str = ""
    final_url: str = ""
    fetched_at: str = ""         # UTC, ISO 8601, to the second
    sha256: str = ""             # of the bytes read
    last_modified: str = ""
    etag: str = ""
    content_type: str = ""
    text: str = ""

    @property
    def fetched(self) -> bool:
        return self.status == "fetched"


async def fetch_source(url: str) -> Source:
    """Fetch one page. Never raises: the Source says what happened."""
    try:
        async with asyncio.timeout(FETCH_TIMEOUT_SECONDS):
            return await _fetch(url)
    except TimeoutError:
        return Source(url, "failed",
                      f"no answer within {FETCH_TIMEOUT_SECONDS:g} s")
    except Exception as exc:
        return Source(url, "failed", f"{type(exc).__name__}: {exc}"[:200])


def readable_address(url: str) -> str:
    """The address to fetch for `url`: itself, or a route known to return
    the same text to an automated client."""
    match = _ECFR_SECTION.match(url.strip())
    if match:
        return ("https://www.ecfr.gov/api/renderer/v1/content/enhanced/current/"
                f"title-{match['title']}?part={match['part']}"
                f"&section={match['part']}.{match['section']}")
    return url


def challenge_page(text: str) -> bool:
    """Is this the text of a prove-you-are-a-person page, not of a source?"""
    if len(text) > CHALLENGE_MAX_CHARS:
        return False
    folded = text.casefold()
    return any(mark in folded for mark in _CHALLENGE_MARKS)


class UnreadableDocument(ValueError):
    """A document the fetch holds but cannot turn into text."""


class PasswordProtected(UnreadableDocument):
    """A PDF that needs a password to open."""


class UnpacksTooLarge(UnreadableDocument):
    """A zipped document that unpacks past ZIP_MAX_BYTES."""


def pdf_text(raw: bytes) -> str:
    """The text layer of a PDF, pages in order. Raises when it cannot be read.

    Many datasheets are encrypted with an empty password, to forbid editing
    and not reading; a viewer opens them without asking. They are opened the
    same way. Measured live 2026-11-13: one such PDF was recorded failed
    with DependencyError, the cipher library not being installed. A PDF
    that needs a real password stays unread and says so.
    """
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted and not reader.decrypt(""):
        raise PasswordProtected("the PDF needs a password")
    return "\n".join(page.extract_text() or "" for page in reader.pages)


class _Zip:
    """A zipped document's members, read under one size bound."""

    def __init__(self, raw: bytes) -> None:
        self.archive = zipfile.ZipFile(io.BytesIO(raw))
        self.names = self.archive.namelist()
        self._read = 0

    def read(self, name: str) -> str:
        self._read += self.archive.getinfo(name).file_size
        if self._read > ZIP_MAX_BYTES:
            raise UnpacksTooLarge(f"unpacks past {ZIP_MAX_BYTES} bytes")
        return self.archive.read(name).decode("utf-8", errors="replace")


def _local(tag: str) -> str:
    """An XML tag without its namespace."""
    return tag.rsplit("}", 1)[-1]


def _numbered(names: list[str], pattern: str) -> list[str]:
    """The members matching `pattern`, ordered by the number it captures."""
    found = [(int(m.group(1)), n) for n in names
             if (m := re.fullmatch(pattern, n))]
    return [n for _, n in sorted(found)]


def epub_text(raw: bytes) -> str:
    """A book's text, chapters in reading order.

    The order is the package file's spine. A book whose package file cannot
    be followed is read in the order of its member names instead.
    """
    book = _Zip(raw)
    pages: list[str] = []
    try:
        container = ElementTree.fromstring(book.read("META-INF/container.xml"))
        package_name = next(e.get("full-path") for e in container.iter()
                            if _local(e.tag) == "rootfile")
        package = ElementTree.fromstring(book.read(package_name))
        items = {e.get("id"): e.get("href") for e in package.iter()
                 if _local(e.tag) == "item"}
        base = package_name.rsplit("/", 1)[0] + "/" if "/" in package_name else ""
        for ref in (e for e in package.iter() if _local(e.tag) == "itemref"):
            href = (items.get(ref.get("idref")) or "").split("#")[0]
            if base + href in book.names:
                pages.append(base + href)
    except (KeyError, StopIteration, TypeError, ElementTree.ParseError):
        pages = []
    if not pages:
        pages = sorted(n for n in book.names
                       if n.lower().endswith((".xhtml", ".html", ".htm")))
    return "\n".join(html_text(book.read(name)) for name in pages)


def _paragraphs(xml: str, prefix: str) -> str:
    """Office XML as text, each paragraph on its own line."""
    xml = re.sub(rf"</{prefix}:p>|<{prefix}:br\s*/>", "\n", xml)
    return html_text(re.sub(rf"<{prefix}:tab\s*/>", "\t", xml))


def docx_text(raw: bytes) -> str:
    """A word-processor document's body text."""
    return _paragraphs(_Zip(raw).read("word/document.xml"), "w")


def pptx_text(raw: bytes) -> str:
    """A slide deck's text, slides in order."""
    deck = _Zip(raw)
    return "\n".join(_paragraphs(deck.read(name), "a") for name in
                     _numbered(deck.names, r"ppt/slides/slide(\d+)\.xml"))


def xlsx_text(raw: bytes) -> str:
    """A workbook's cells: a row per line, cells tab-separated, sheets in order."""
    book = _Zip(raw)
    shared: list[str] = []
    if "xl/sharedStrings.xml" in book.names:
        strings = ElementTree.fromstring(book.read("xl/sharedStrings.xml"))
        shared = ["".join(t.text or "" for t in item.iter()
                          if _local(t.tag) == "t")
                  for item in strings if _local(item.tag) == "si"]
    lines: list[str] = []
    for name in _numbered(book.names, r"xl/worksheets/sheet(\d+)\.xml"):
        sheet = ElementTree.fromstring(book.read(name))
        for row in (e for e in sheet.iter() if _local(e.tag) == "row"):
            cells: list[str] = []
            for cell in (e for e in row if _local(e.tag) == "c"):
                value = "".join(e.text or "" for e in cell.iter()
                                if _local(e.tag) in ("v", "t"))
                if cell.get("t") == "s" and value.isdigit():
                    value = shared[int(value)] if int(value) < len(shared) else ""
                cells.append(value)
            if any(cells):
                lines.append("\t".join(cells))
    return "\n".join(lines)


def json_text(text: str) -> str:
    """JSON as its keys and values, one per line; the text itself if it is not JSON."""
    try:
        data = json.loads(text)
    except ValueError:
        return text
    lines: list[str] = []

    def walk(value: Any, key: str) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, str(k))
        elif isinstance(value, list):
            for v in value:
                walk(v, key)
        elif value is not None:
            shown = value if isinstance(value, str) else json.dumps(value)
            lines.append(f"{key}: {shown}" if key else str(shown))

    walk(data, "")
    return "\n".join(lines)


# The documents read from their bytes, not decoded as text: kind -> (the
# name a failure gives it, what it says when it holds no text, its reader).
_DOCUMENT_READERS: dict[str, tuple[str, str, Callable[[bytes], str]]] = {
    "pdf": ("PDF", "the PDF has no text layer", pdf_text),
    "epub": ("EPUB", "the EPUB has no text", epub_text),
    "docx": ("document", "the document has no text", docx_text),
    "pptx": ("slide deck", "the slide deck has no text", pptx_text),
    "xlsx": ("workbook", "the workbook has no text", xlsx_text),
}
_KIND_BY_TYPE: dict[str, str] = {
    **{t: "html" for t in HTML_TYPES}, **{t: "text" for t in TEXT_TYPES},
    **{t: "json" for t in JSON_TYPES}, **{t: "pdf" for t in PDF_TYPES},
    **{t: "epub" for t in EPUB_TYPES}, **{t: "docx" for t in DOCX_TYPES},
    **{t: "pptx" for t in PPTX_TYPES}, **{t: "xlsx" for t in XLSX_TYPES},
}


def readable_type(content_type: str) -> bool:
    """Can a body of this type be read, or looked into to find out?"""
    return (content_type in _KIND_BY_TYPE or content_type in UNNAMED_TYPES
            or content_type.endswith("+json"))


def document_kind(content_type: str, raw: bytes) -> str | None:
    """How a body is read: by its stated type, else by what its bytes show.

    None when it is nothing the fetch reads as text.
    """
    if content_type in _KIND_BY_TYPE:
        return _KIND_BY_TYPE[content_type]
    if content_type.endswith("+json"):
        return "json"
    if content_type not in UNNAMED_TYPES:
        return None
    if raw.lstrip()[:5] == b"%PDF-":
        return "pdf"
    if raw[:2] != b"PK":
        return None
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
        names = set(archive.namelist())
        if "mimetype" in names and archive.getinfo("mimetype").file_size < 100 \
                and archive.read("mimetype").strip() == b"application/epub+zip":
            return "epub"
    except (zipfile.BadZipFile, KeyError, OSError):
        return None
    for member, kind in (("word/document.xml", "docx"),
                         ("ppt/presentation.xml", "pptx"),
                         ("xl/workbook.xml", "xlsx")):
        if member in names:
            return kind
    return None


async def _fetch(url: str) -> Source:
    current = readable_address(url)
    # trust_env=False: no proxy from the environment, which would resolve
    # the name itself, and no .netrc credentials sent to a quoted page.
    async with httpx.AsyncClient(transport=_transport, follow_redirects=False,
                                 timeout=FETCH_TIMEOUT_SECONDS, trust_env=False,
                                 headers={"User-Agent": USER_AGENT}) as client:
        for _ in range(MAX_REDIRECTS + 1):
            status, reason, address = await _check_address(current)
            if status:
                return Source(url, status, reason, final_url=current)
            name = httpx.URL(current)
            async with client.stream(
                    "GET",
                    name.copy_with(host=address, username=None, password=None),
                    headers={"Host": name.netloc.decode("ascii")},
                    extensions={"sni_hostname": name.host}) as response:
                if response.is_redirect:
                    current = urljoin(current, response.headers.get("location", ""))
                    continue
                if response.status_code != 200:
                    return Source(url, "failed", f"HTTP {response.status_code}",
                                  final_url=current)
                content_type = (response.headers.get("content-type", "")
                                .split(";")[0].strip().lower())
                unread = Source(url, "failed",
                                f"content type {content_type or 'none'} is not "
                                f"read as text", final_url=current,
                                content_type=content_type)
                if not readable_type(content_type):
                    return unread
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > FETCH_MAX_BYTES:
                        return Source(url, "failed",
                                      f"larger than {FETCH_MAX_BYTES} bytes",
                                      final_url=current, content_type=content_type)
                raw = bytes(body)
                kind = document_kind(content_type, raw)
                if kind is None:
                    return unread
                if kind in _DOCUMENT_READERS:
                    label, empty, reader = _DOCUMENT_READERS[kind]
                    try:
                        # Off the event loop: a large PDF takes seconds.
                        text = await asyncio.to_thread(reader, raw)
                    except Exception as exc:
                        return Source(url, "failed",
                                      f"the {label} could not be read: "
                                      f"{type(exc).__name__}"[:200],
                                      final_url=current,
                                      content_type=content_type)
                    if not text.strip():
                        return Source(url, "failed", empty,
                                      final_url=current,
                                      content_type=content_type)
                else:
                    try:
                        text = raw.decode(response.charset_encoding or "utf-8",
                                          errors="replace")
                    except LookupError:
                        text = raw.decode("utf-8", errors="replace")
                    if kind == "html":
                        text = html_text(text)
                    elif kind == "json":
                        text = json_text(text)
                    if challenge_page(text):
                        return Source(url, "failed",
                                      "the page asked for proof of a person "
                                      "(a challenge page), so it was not read",
                                      final_url=current,
                                      content_type=content_type)
                return Source(
                    url, "fetched", final_url=current,
                    fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    last_modified=response.headers.get("last-modified", ""),
                    etag=response.headers.get("etag", ""),
                    content_type=content_type, text=text)
    return Source(url, "failed", f"more than {MAX_REDIRECTS} redirects",
                  final_url=current)


async def _addresses(host: str) -> list[str]:
    """Every address `host` resolves to."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


async def _check_address(url: str) -> tuple[str, str, str]:
    """("", "", address) when `url` may be fetched, with the checked address
    to connect to; else the status, the reason and ""."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return ("refused",
                f"scheme {parts.scheme or 'none'!r} is not http or https", "")
    host = parts.hostname
    if not host:
        return "refused", "the address names no host", ""
    try:
        addresses = await _addresses(host)
    except OSError as exc:
        return "failed", f"{host} does not resolve: {exc}", ""
    if not addresses:
        return "failed", f"{host} does not resolve", ""
    for address in addresses:
        if not ipaddress.ip_address(address.split("%")[0]).is_global:
            return ("refused",
                    f"{host} resolves to {address}, not a public address", "")
    return "", "", addresses[0].split("%")[0]


class _Text(HTMLParser):
    """The text a reader of the page sees: no script, style or markup."""

    SKIP = {"script", "style", "noscript", "template"}
    BLOCK = {"address", "article", "aside", "blockquote", "br", "dd", "div",
             "dl", "dt", "figcaption", "footer", "h1", "h2", "h3", "h4", "h5",
             "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre",
             "section", "table", "td", "th", "tr", "ul"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skipping += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self._skipping = max(self._skipping - 1, 0)
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skipping:
            self.parts.append(data)


def html_text(html: str) -> str:
    """A page's readable text, block elements on their own lines."""
    parser = _Text()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)
