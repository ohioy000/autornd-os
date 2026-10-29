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
import ipaddress
import logging
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

logger = logging.getLogger(__name__)

# The whole fetch, redirects included, in seconds. Not measured: a judgment
# that a page slower than this is not worth holding a run for. A lookup's
# pages are fetched together, so it waits for its slowest page, not the sum.
FETCH_TIMEOUT_SECONDS = 10.0

# A page larger than this is not read. Not measured: a standards page or a
# datasheet's HTML is well under it, and a run should not hold more.
FETCH_MAX_BYTES = 2_000_000

# Redirects followed, each checked as the first address was.
MAX_REDIRECTS = 3

# Distinct pages fetched for one lookup. A bundled lookup quotes a few pages
# per question; past this many the rest are recorded unfetched.
MAX_FETCHES = 8

# What can be read as text. A PDF cannot yet: it is recorded unfetched with
# its content type, so the gap shows.
HTML_TYPES = ("text/html", "application/xhtml+xml")
TEXT_TYPES = ("text/plain", "text/markdown")

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


async def _fetch(url: str) -> Source:
    current = url
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
                if content_type not in HTML_TYPES + TEXT_TYPES:
                    return Source(url, "failed",
                                  f"content type {content_type or 'none'} is not "
                                  f"read as text", final_url=current,
                                  content_type=content_type)
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > FETCH_MAX_BYTES:
                        return Source(url, "failed",
                                      f"larger than {FETCH_MAX_BYTES} bytes",
                                      final_url=current, content_type=content_type)
                raw = bytes(body)
                try:
                    text = raw.decode(response.charset_encoding or "utf-8",
                                      errors="replace")
                except LookupError:
                    text = raw.decode("utf-8", errors="replace")
                if content_type in HTML_TYPES:
                    text = html_text(text)
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
