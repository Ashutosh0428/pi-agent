"""Knowledge base tests — chunking, BM25, ingest/search round trip (no network)."""

from __future__ import annotations

from pi_agent.kb import (
    CHUNK_CHARS,
    chunk_text,
    format_context,
    ingest,
    kb_exists,
    knowledge_tools,
    search,
)


def _write(d, name, text):
    p = d / name
    p.write_text(text, encoding="utf-8")
    return p


class TestChunking:
    def test_short_text_one_chunk(self):
        chunks = chunk_text("hello world", "a.md")
        assert len(chunks) == 1
        assert chunks[0].source == "a.md"

    def test_paragraph_packing(self):
        # 12 paragraphs × ~300 chars ≈ 3600 chars, well over CHUNK_CHARS=1200.
        text = "\n\n".join(["para " + str(i) * 300 for i in range(12)])
        chunks = chunk_text(text, "a.md")
        assert len(chunks) >= 2
        assert all(len(c.text) <= CHUNK_CHARS + CHUNK_CHARS for c in chunks)

    def test_long_paragraph_hard_split(self):
        chunks = chunk_text("x" * (CHUNK_CHARS * 3), "big.md")
        assert len(chunks) >= 3


class TestIngestSearch:
    def test_ingest_counts(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        _write(docs, "auth.md", "Authentication uses JWT bearer tokens validated by Keycloak.")
        _write(docs, "db.md", "The database is PostgreSQL with pgvector for embeddings.")
        stats = ingest(docs, tmp_path)
        assert stats["files"] == 2
        assert stats["chunks"] >= 2
        assert kb_exists(tmp_path)

    def test_search_finds_relevant_chunk(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        _write(docs, "auth.md", "Authentication uses JWT bearer tokens validated by Keycloak.")
        _write(docs, "db.md", "The database is PostgreSQL with pgvector for embeddings.")
        ingest(docs, tmp_path)
        hits = search("how does authentication work", tmp_path)
        assert hits
        assert hits[0][1] == "auth.md"  # top hit is the auth doc

    def test_search_empty_kb_returns_nothing(self, tmp_path):
        assert search("anything", tmp_path) == []

    def test_reingest_is_deterministic(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        _write(docs, "x.md", "alpha beta gamma delta")
        first = ingest(docs, tmp_path)
        second = ingest(docs, tmp_path)
        assert first == second  # rebuild, not append

    def test_irrelevant_query_scores_zero(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        _write(docs, "x.md", "Authentication uses JWT tokens.")
        ingest(docs, tmp_path)
        assert search("xyzzy quux flibbertigibbet", tmp_path) == []


class TestKnowledgeTool:
    def test_tool_absent_without_kb(self, tmp_path):
        assert knowledge_tools(tmp_path) == []

    def test_tool_present_and_searches(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        _write(docs, "x.md", "The cache layer uses Redis with a 60 second TTL.")
        ingest(docs, tmp_path)
        tools = knowledge_tools(tmp_path)
        assert len(tools) == 1
        out = tools[0].handler({"query": "what cache do we use"}, None)
        assert "Redis" in out

    def test_format_context_cites_sources(self):
        ctx = format_context([(1.0, "auth.md", "JWT details")])
        assert "[auth.md]" in ctx
