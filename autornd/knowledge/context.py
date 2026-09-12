"""Context loader — builds relevant context for each workflow phase.

Combines two sources:
1. Deterministic docs from docs/manifest.json (always loaded for matching domains)
2. ChromaDB retrieval (semantic search for query-specific context)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from autornd.knowledge.store import retrieve
from autornd.models.verdicts import Domain, SpecialistRole

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
MAX_CONTEXT_CHARS = 32000


def _load_manifest() -> dict:
    from autornd.profiles import get_profile

    profile = get_profile()
    profile_manifest = DOCS_DIR / profile.get_docs_dir() / "manifest.json"
    if profile_manifest.exists():
        return json.loads(profile_manifest.read_text(encoding="utf-8"))

    fallback = DOCS_DIR / "manifest.json"
    if fallback.exists():
        return json.loads(fallback.read_text(encoding="utf-8"))

    return {"global": [], "domains": {}, "specialist_extras": {}}


def _read_doc(relative_path: str) -> str | None:
    full_path = DOCS_DIR / relative_path
    if not full_path.exists():
        logger.warning("Doc not found: %s", full_path)
        return None
    return full_path.read_text(encoding="utf-8", errors="replace")


def load_docs_context(
    domains: list[Domain],
    specialists: list[SpecialistRole] | None = None,
) -> str:
    """Load deterministic doc context based on triage domains and specialists."""
    manifest = _load_manifest()
    seen_paths: set[str] = set()
    sections: list[str] = []

    for path in manifest.get("global", []):
        if path not in seen_paths:
            content = _read_doc(path)
            if content:
                sections.append(f"--- {path} ---\n{content}")
                seen_paths.add(path)

    for domain in domains:
        domain_paths = manifest.get("domains", {}).get(domain.value, [])
        for path in domain_paths:
            if path not in seen_paths:
                content = _read_doc(path)
                if content:
                    sections.append(f"--- {path} ---\n{content}")
                    seen_paths.add(path)

    if specialists:
        for spec in specialists:
            extra_paths = manifest.get("specialist_extras", {}).get(spec.value, [])
            for path in extra_paths:
                if path not in seen_paths:
                    content = _read_doc(path)
                    if content:
                        sections.append(f"--- {path} ---\n{content}")
                        seen_paths.add(path)

    combined = "\n\n".join(sections)
    if len(combined) > MAX_CONTEXT_CHARS:
        combined = combined[:MAX_CONTEXT_CHARS] + "\n\n[... context truncated ...]"
    return combined


def load_retrieval_context(query: str, n_results: int = 5) -> str:
    """Retrieve semantically relevant chunks from ChromaDB."""
    results = retrieve(query, n_results=n_results)
    if not results:
        return ""

    sections = []
    for r in results:
        sections.append(f"[{r['tag']}] (distance: {r['distance']:.3f})\n{r['text']}")

    return "\n\n".join(sections)


def build_phase_context(
    request: str,
    domains: list[Domain],
    specialists: list[SpecialistRole] | None = None,
    include_retrieval: bool = True,
) -> str:
    """Build full context string for a workflow phase.

    Combines deterministic docs (always) + ChromaDB retrieval (when available).
    """
    parts: list[str] = []

    docs_ctx = load_docs_context(domains, specialists)
    if docs_ctx:
        parts.append("=== PROJECT DOCUMENTATION ===\n" + docs_ctx)

    if include_retrieval:
        retrieval_ctx = load_retrieval_context(request)
        if retrieval_ctx:
            parts.append("=== RELEVANT KNOWLEDGE ===\n" + retrieval_ctx)

    return "\n\n".join(parts)
