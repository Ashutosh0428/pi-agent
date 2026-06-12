"""Local knowledge base — ingest docs, retrieve by keyword. Standard library only.

``pi ingest <dir>`` chunks the markdown/text files under a directory and builds
a BM25 keyword index in a stdlib ``sqlite3`` database at ``<workspace>/.pi/kb.sqlite3``.
``pi ask "<question>"`` (and the ``search_knowledge`` chat tool) retrieve the
most relevant chunks for grounded, cited answers.

BM25 is implemented directly — no numpy, no embedding model, no API calls — so
the knowledge base works fully offline (pairs perfectly with local Ollama).
Embeddings/semantic search are a deliberate future step; keyword retrieval is
the lean, dependency-free baseline.
"""

from __future__ import annotations

import math
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pi_agent.tools.base import Tool

KB_RELPATH = ".pi/kb.sqlite3"
INGEST_EXTS = {".md", ".txt", ".rst"}
MAX_FILE_BYTES = 1_000_000
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 150
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_BM25_K1 = 1.5
_BM25_B = 0.75


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class Chunk:
    source: str  # relative file path
    text: str


def chunk_text(text: str, source: str) -> list[Chunk]:
    """Split on blank lines into paragraphs, packed to ~CHUNK_CHARS with overlap.

    Keeps paragraph boundaries where possible so a chunk reads coherently; long
    paragraphs are hard-split. Overlap preserves context across boundaries.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[Chunk] = []
    buf = ""
    for para in paragraphs:
        if len(buf) + len(para) + 2 <= CHUNK_CHARS:
            buf = f"{buf}\n\n{para}" if buf else para
            continue
        if buf:
            chunks.append(Chunk(source, buf))
            tail = buf[-CHUNK_OVERLAP:]
            buf = f"{tail}\n\n{para}" if len(para) < CHUNK_CHARS else para
        while len(para) > CHUNK_CHARS:
            chunks.append(Chunk(source, para[:CHUNK_CHARS]))
            para = para[CHUNK_CHARS - CHUNK_OVERLAP :]
        buf = para if not buf else buf
    if buf:
        chunks.append(Chunk(source, buf))
    return chunks


def _connect(kb_path: Path) -> sqlite3.Connection:
    kb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(kb_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chunks "
        "(id INTEGER PRIMARY KEY, source TEXT, text TEXT, length INTEGER)"
    )
    return conn


def ingest(docs_dir: Path | str, workspace_root: Path | str) -> dict[str, int]:
    """Build (rebuild) the knowledge base from the files under ``docs_dir``.

    Returns counts: files, chunks, bytes. Re-ingesting replaces the index so
    the result is deterministic.
    """
    docs = Path(docs_dir)
    kb_path = Path(workspace_root) / KB_RELPATH
    conn = _connect(kb_path)
    conn.execute("DELETE FROM chunks")

    files = 0
    total_chunks = 0
    total_bytes = 0
    for path in sorted(docs.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in INGEST_EXTS:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(docs))
        rows = [(c.source, c.text, len(_tokenize(c.text))) for c in chunk_text(text, rel)]
        conn.executemany("INSERT INTO chunks (source, text, length) VALUES (?, ?, ?)", rows)
        files += 1
        total_chunks += len(rows)
        total_bytes += len(text.encode("utf-8"))
    conn.commit()
    conn.close()
    return {"files": files, "chunks": total_chunks, "bytes": total_bytes}


def _bm25_search(conn: sqlite3.Connection, query: str, top_k: int) -> list[tuple[float, str, str]]:
    """Rank chunks by BM25 against the query. Returns [(score, source, text)]."""
    rows = conn.execute("SELECT source, text, length FROM chunks").fetchall()
    if not rows:
        return []
    n = len(rows)
    avg_len = sum(r[2] for r in rows) / n
    q_terms = set(_tokenize(query))
    if not q_terms:
        return []

    # Document frequency per query term.
    tokenized = [_tokenize(r[1]) for r in rows]
    df = {t: sum(1 for toks in tokenized if t in toks) for t in q_terms}

    scored: list[tuple[float, str, str]] = []
    for (source, text, length), toks in zip(rows, tokenized):
        counts = Counter(toks)
        score = 0.0
        for term in q_terms:
            tf = counts.get(term, 0)
            if tf == 0:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            denom = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * (length / avg_len))
            score += idf * (tf * (_BM25_K1 + 1)) / denom
        if score > 0:
            scored.append((score, source, text))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[:top_k]


def search(query: str, workspace_root: Path | str, top_k: int = 6) -> list[tuple[float, str, str]]:
    """Top-k (score, source, text) chunks for ``query``; [] if no KB or no hit."""
    kb_path = Path(workspace_root) / KB_RELPATH
    if not kb_path.is_file():
        return []
    conn = sqlite3.connect(kb_path)
    try:
        return _bm25_search(conn, query, top_k)
    finally:
        conn.close()


def format_context(hits: list[tuple[float, str, str]]) -> str:
    """Render retrieved chunks as a cited context block for the model."""
    if not hits:
        return ""
    return "\n\n".join(f"[{source}]\n{text}" for _score, source, text in hits)


def kb_exists(workspace_root: Path | str) -> bool:
    return (Path(workspace_root) / KB_RELPATH).is_file()


def knowledge_tools(workspace_root: Path | str) -> list[Tool]:
    """The ``search_knowledge`` tool — only when a KB exists in the workspace."""
    if not kb_exists(workspace_root):
        return []
    root = Path(workspace_root)

    def handler(args: dict[str, Any], _sandbox: Any) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' is required."
        hits = search(query, root)
        return format_context(hits) or "No matching content in the knowledge base."

    return [
        Tool(
            name="search_knowledge",
            description=(
                "Search the project's local knowledge base (ingested docs) for "
                "passages relevant to a query. Returns cited chunks; use it to "
                "ground answers in the project's own documentation."
            ),
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=handler,
            mutating=False,
        )
    ]
