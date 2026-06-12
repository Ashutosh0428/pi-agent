"""web_fetch — retrieve a public web page as readable text.

Dependency-free (stdlib ``urllib``). This is a **local/trusted** tool, kept off
the public web demo because any server-side fetcher is a Server-Side Request
Forgery (SSRF) risk. Even locally we defend against the obvious abuse:

* only ``http``/``https`` URLs (no ``file://``, ``gopher://``, …);
* the hostname is resolved and rejected if it maps to a private, loopback,
  link-local, or reserved IP range (blocks ``localhost`` and cloud-metadata
  endpoints like ``169.254.169.254``);
* redirects are followed but **re-validated on every hop**, so a public URL
  can't bounce the request onto an internal address;
* response size, read time, and returned text are all capped.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from pi_agent.sandbox import Sandbox
from pi_agent.tools.base import Tool

TIMEOUT_SECONDS = 15
MAX_BYTES = 2 * 1024 * 1024  # read at most 2 MB from the network
MAX_TEXT_CHARS = 20_000  # return at most this much text to the model
_USER_AGENT = "pi-agent/0.3 (+https://github.com/Ashutosh0428/pi-agent)"

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
_WS_RE = re.compile(r"\n\s*\n\s*\n+")


def _blocked_reason(url: str) -> str | None:
    """Return why ``url`` is disallowed, or ``None`` if it is safe to fetch."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"only http/https URLs are allowed (got '{parsed.scheme or '?'}')."
    host = parsed.hostname
    if not host:
        return "URL has no host."
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        return f"could not resolve host '{host}'."
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return f"host '{host}' resolves to a non-public address ({ip})."
    return None


class _ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validate the target of every redirect (prevents SSRF via redirect)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        reason = _blocked_reason(newurl)
        if reason is not None:
            raise urllib.error.URLError(f"blocked redirect: {reason}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _html_to_text(html: str) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    lines = [line.strip() for line in text.splitlines()]
    return _WS_RE.sub("\n\n", "\n".join(line for line in lines if line))


def _web_fetch(args: dict[str, Any], sb: Sandbox) -> str:  # noqa: ARG001 - no sandbox I/O
    url = (args.get("url") or "").strip()
    if not url:
        return "Error: 'url' is required."
    reason = _blocked_reason(url)
    if reason is not None:
        return f"Error: {reason}"

    opener = urllib.request.build_opener(_ValidatingRedirectHandler())
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_BYTES + 1)
            content_type = response.headers.get("Content-Type", "")
            final_url = response.geturl()
    except urllib.error.URLError as exc:
        return f"Error fetching {url}: {getattr(exc, 'reason', exc)}"
    except (OSError, ValueError) as exc:
        return f"Error fetching {url}: {exc}"

    truncated = len(raw) > MAX_BYTES
    body = raw[:MAX_BYTES].decode("utf-8", errors="replace")
    if "html" in content_type.lower() or body.lstrip()[:1] == "<":
        body = _html_to_text(body)
    if len(body) > MAX_TEXT_CHARS:
        body = body[:MAX_TEXT_CHARS] + "\n... [truncated]"
    elif truncated:
        body += "\n... [truncated]"

    header = f"GET {final_url}\n({content_type or 'unknown type'})\n\n"
    return header + body.strip()


def web_tools() -> list[Tool]:
    """The web_fetch tool (local/trusted contexts only — SSRF-guarded)."""
    return [
        Tool(
            name="web_fetch",
            description=(
                "Fetch a public http/https web page and return it as readable text "
                "(HTML is stripped). Use to read docs, an API reference, or a raw "
                "file URL. Only public addresses are allowed; size is capped."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "An http(s) URL to fetch."}
                },
                "required": ["url"],
            },
            handler=_web_fetch,
            mutating=False,
        )
    ]
