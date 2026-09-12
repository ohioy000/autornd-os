"""ChromaDB knowledge store — ingest docs and retrieve relevant chunks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from autornd.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "autornd_knowledge"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _get_chroma_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(
        path=settings.chromadb_path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by character count, breaking at newlines."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        nl = chunk.rfind("\n")
        if nl > chunk_size // 2 and end < len(text):
            end = start + nl + 1
            chunk = text[start:end]
        chunks.append(chunk.strip())
        start = end - overlap
    return [c for c in chunks if c]


def ingest_file(file_path: Path, source_tag: str | None = None) -> int:
    """Ingest a single file into the knowledge store. Returns chunk count."""
    client = _get_chroma_client()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    text = file_path.read_text(encoding="utf-8", errors="replace")
    tag = source_tag or file_path.stem
    chunks = _chunk_text(text)

    ids = [f"{tag}__chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"source": str(file_path), "tag": tag, "chunk_index": i} for i in range(len(chunks))]

    existing = set(collection.get(ids=ids, include=[])["ids"])
    new_ids = []
    new_chunks = []
    new_metas = []
    for cid, chunk, meta in zip(ids, chunks, metadatas):
        if cid not in existing:
            new_ids.append(cid)
            new_chunks.append(chunk)
            new_metas.append(meta)

    if new_ids:
        collection.add(ids=new_ids, documents=new_chunks, metadatas=new_metas)
        logger.info("Ingested %d new chunks from %s (tag: %s)", len(new_ids), file_path, tag)
    else:
        logger.info("No new chunks to ingest from %s", file_path)

    return len(new_ids)


def ingest_directory(dir_path: Path, extensions: tuple[str, ...] = (".md", ".txt", ".py")) -> int:
    """Ingest all matching files in a directory tree. Returns total chunk count."""
    total = 0
    for fpath in sorted(dir_path.rglob("*")):
        if fpath.is_file() and fpath.suffix in extensions:
            rel = fpath.relative_to(dir_path)
            tag = str(rel).replace("\\", "/").replace("/", "__").rsplit(".", 1)[0]
            total += ingest_file(fpath, source_tag=tag)
    return total


def retrieve(query: str, n_results: int = 5, where: dict | None = None) -> list[dict]:
    """Retrieve relevant chunks for a query. Returns list of {text, source, tag, distance}."""
    client = _get_chroma_client()
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        logger.warning("Knowledge collection not found — run ingestion first")
        return []

    kwargs: dict = {"query_texts": [query], "n_results": n_results}
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    return [
        {
            "text": doc,
            "source": meta.get("source", ""),
            "tag": meta.get("tag", ""),
            "distance": dist,
        }
        for doc, meta, dist in zip(docs, metas, distances)
    ]


def get_stats() -> dict:
    """Return collection stats."""
    client = _get_chroma_client()
    try:
        collection = client.get_collection(COLLECTION_NAME)
        return {"collection": COLLECTION_NAME, "count": collection.count()}
    except Exception:
        return {"collection": COLLECTION_NAME, "count": 0, "status": "not_initialized"}
