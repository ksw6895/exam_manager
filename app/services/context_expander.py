"""
Context Expander Service

Semantic expansion within the same lecture using BM25 similarity to the
candidate chunk text. Falls back to no expansion when semantic neighbors
are unavailable.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from config import get_config
from sqlalchemy import text

from app import db
from app.models import LectureChunk
from app.services import retrieval


def _fetch_chunk(chunk_id: int) -> Optional[LectureChunk]:
    if not chunk_id:
        return None
    return LectureChunk.query.get(chunk_id)


def _semantic_neighbors(
    seed_chunk: LectureChunk,
    *,
    top_n: int,
    query_max_chars: int,
) -> List[LectureChunk]:
    content = (seed_chunk.content or "").strip()
    if not content:
        return []
    if len(content) > query_max_chars:
        content = content[:query_max_chars]

    match_query = retrieval.make_bm25_match_query(content)
    if not match_query:
        return []

    sql = text(
        """
        SELECT c.id AS chunk_id,
               c.page_start,
               c.page_end,
               c.content,
               bm25(lecture_chunks_fts) AS bm25_score
        FROM lecture_chunks_fts
        JOIN lecture_chunks c ON c.id = lecture_chunks_fts.chunk_id
        WHERE lecture_chunks_fts MATCH :query
          AND c.lecture_id = :lecture_id
        ORDER BY bm25_score
        LIMIT :top_n
        """
    )
    rows = (
        db.session.execute(
            sql,
            {"query": match_query, "lecture_id": seed_chunk.lecture_id, "top_n": top_n},
        )
        .mappings()
        .all()
    )
    chunks = []
    for row in rows:
        chunk_id = row.get("chunk_id")
        if not chunk_id or chunk_id == seed_chunk.id:
            continue
        chunk = LectureChunk.query.get(chunk_id)
        if chunk:
            chunks.append(chunk)
    return chunks


def _assemble_parent_text(
    chunks: List[LectureChunk], max_chars: int
) -> tuple[str, List[int]]:
    separator = "\n\n---\n\n"
    selected = []
    total = 0
    for chunk in chunks:
        content = chunk.content or ""
        add_len = len(content) + (len(separator) if selected else 0)
        if selected and total + add_len > max_chars:
            break
        if not selected and len(content) > max_chars:
            selected = [chunk]
            total = len(content)
            break
        selected.append(chunk)
        total += add_len

    if not selected:
        return "", []

    text_block = separator.join(c.content or "" for c in selected)
    if len(text_block) > max_chars:
        text_block = text_block[:max_chars] + "...(truncated)"
    return text_block, [c.id for c in selected]


def expand_candidates(candidates: List[Dict]) -> List[Dict]:
    """
    Expand candidate chunks with semantic neighbors inside the same lecture.

    Returns candidates with:
      - parent_text
      - parent_page_ranges
      - parent_chunk_ids
    """
    if not candidates:
        return []

    if not get_config().experiment.semantic_expansion_enabled:
        return candidates

    max_chars = get_config().experiment.parent_max_chars
    top_n = get_config().experiment.semantic_expansion_top_n
    max_extra = get_config().experiment.semantic_expansion_max_extra
    query_max_chars = get_config().experiment.semantic_expansion_query_max_chars

    for cand in candidates:
        evidence = cand.get("evidence") or []
        if not evidence:
            continue
        seed_chunk_id = evidence[0].get("chunk_id")
        if not seed_chunk_id:
            continue
        seed_chunk = _fetch_chunk(seed_chunk_id)
        if not seed_chunk:
            continue

        neighbor_chunks = _semantic_neighbors(
            seed_chunk,
            top_n=top_n,
            query_max_chars=query_max_chars,
        )
        extra = neighbor_chunks[:max_extra]
        ordered_chunks = [seed_chunk] + extra

        # Deduplicate while keeping order
        seen = set()
        unique_chunks = []
        for chunk in ordered_chunks:
            if chunk.id in seen:
                continue
            seen.add(chunk.id)
            unique_chunks.append(chunk)

        parent_text, parent_chunk_ids = _assemble_parent_text(unique_chunks, max_chars)
        if not parent_text:
            continue

        cand["parent_text"] = parent_text
        cand["parent_chunk_ids"] = parent_chunk_ids
        cand["parent_page_ranges"] = [
            (chunk.page_start, chunk.page_end)
            for chunk in unique_chunks
            if chunk.id in parent_chunk_ids
        ]

    return candidates
