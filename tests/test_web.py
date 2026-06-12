"""Tests for web_fetch — SSRF guard and HTML extraction (no network).

The blocked-host cases use literal IPs, so ``getaddrinfo`` resolves them without
a DNS query; the one allowed case uses a literal public IP for the same reason.
"""

from __future__ import annotations

from pi_agent.sandbox import Sandbox
from pi_agent.tools.registry import build_default_tools
from pi_agent.tools.web import _blocked_reason, _html_to_text, web_tools


class TestSSRFGuard:
    def test_rejects_non_http_scheme(self):
        assert "http/https" in (_blocked_reason("file:///etc/passwd") or "")

    def test_rejects_loopback(self):
        assert "non-public" in (_blocked_reason("http://127.0.0.1/") or "")

    def test_rejects_private_range(self):
        assert "non-public" in (_blocked_reason("http://10.0.0.1/admin") or "")

    def test_rejects_cloud_metadata_ip(self):
        # 169.254.169.254 — the classic cloud metadata SSRF target (link-local).
        assert "non-public" in (_blocked_reason("http://169.254.169.254/") or "")

    def test_allows_public_ip(self):
        assert _blocked_reason("https://8.8.8.8/") is None


class TestHtmlExtraction:
    def test_strips_tags_and_scripts(self):
        html = "<html><body><script>steal()</script><h1>Title</h1><p>Hello</p></body></html>"
        text = _html_to_text(html)
        assert "Title" in text and "Hello" in text
        assert "steal" not in text  # script body removed, not just tags

    def test_decodes_entities(self):
        assert "a & b" in _html_to_text("<p>a &amp; b</p>")


class TestRegistration:
    def test_registered_only_when_enabled(self):
        assert "web_fetch" in build_default_tools(enable_shell=False, enable_web=True)
        assert "web_fetch" not in build_default_tools(enable_shell=False)

    def test_not_mutating(self):
        assert web_tools()[0].mutating is False

    def test_empty_url(self, tmp_path):
        reg = build_default_tools(enable_shell=False, enable_web=True)
        assert "required" in reg.run("web_fetch", {"url": "  "}, Sandbox(tmp_path))
