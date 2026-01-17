from __future__ import annotations

import re
from typing import List, Dict

from sqlalchemy import text

from app import db
from app.models import Lecture, Block


def _normalize_query(text_content: str, max_chars: int = 4000) -> str:
    if not text_content:
        return ""
    cleaned = text_content.replace("\u00A0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars]
    tokens = re.findall(r"[0-9A-Za-z\uac00-\ud7a3]+", cleaned)
    if tokens:
        return " ".join(tokens)
    return cleaned


def _build_fts_query(normalized: str, max_terms: int = 16) -> str:
    tokens = [t for t in normalized.split() if t]
    if not tokens:
        return ""
    seen = set()
    deduped = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
        if len(deduped) >= max_terms:
            break
    if len(deduped) == 1:
        return deduped[0]
    return " OR ".join(deduped)


def search_chunks_bm25(
    query: str,
    top_n: int = 80,
    lecture_ids: List[int] | None = None,
) -> List[Dict]:
    normalized = _normalize_query(query)
    fts_query = _build_fts_query(normalized)
    if not fts_query:
        return []

    if lecture_ids is not None and not lecture_ids:
        return []

    where_clause = "WHERE lecture_chunks_fts MATCH :query"
    params: Dict[str, object] = {"query": fts_query, "top_n": top_n}

    if lecture_ids is not None:
        placeholders = []
        for idx, lecture_id in enumerate(lecture_ids):
            key = f"lecture_id_{idx}"
            placeholders.append(f":{key}")
            params[key] = lecture_id
        where_clause += f" AND lecture_id IN ({', '.join(placeholders)})"

    sql = text(
        f"""
        SELECT
            chunk_id,
            lecture_id,
            page_start,
            page_end,
            snippet(lecture_chunks_fts, 0, '', '', '...', 24) AS snippet,
            bm25(lecture_chunks_fts) AS bm25_score
        FROM lecture_chunks_fts
        {where_clause}
        ORDER BY bm25_score
        LIMIT :top_n
        """
    )
    rows = db.session.execute(sql, params).mappings().all()
    results = []
    for row in rows:
        snippet_text = (row.get("snippet") or "").replace("\n", " ").strip()
        results.append(
            {
                "chunk_id": row.get("chunk_id"),
                "lecture_id": row.get("lecture_id"),
                "page_start": row.get("page_start"),
                "page_end": row.get("page_end"),
                "snippet": snippet_text,
                "bm25_score": float(row.get("bm25_score") or 0.0),
            }
        )
    return results


def aggregate_candidates(
    chunks: List[Dict],
    top_k_lectures: int = 8,
    evidence_per_lecture: int = 3,
) -> List[Dict]:
    if not chunks:
        return []

    per_lecture: Dict[int, Dict] = {}
    for chunk in chunks:
        lecture_id = chunk.get("lecture_id")
        if lecture_id is None:
            continue
        score = -(chunk.get("bm25_score") or 0.0)
        entry = per_lecture.setdefault(lecture_id, {"score": 0.0, "evidence": []})
        entry["score"] += score
        entry["evidence"].append(
            {
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "snippet": chunk.get("snippet") or "",
                "chunk_id": chunk.get("chunk_id"),
                "score": score,
            }
        )

    lecture_ids = list(per_lecture.keys())
    lecture_rows = (
        Lecture.query.join(Block).filter(Lecture.id.in_(lecture_ids)).all()
        if lecture_ids
        else []
    )
    lecture_map = {lecture.id: lecture for lecture in lecture_rows}

    candidates = []
    for lecture_id, info in per_lecture.items():
        lecture = lecture_map.get(lecture_id)
        if not lecture:
            continue
        evidence = sorted(info["evidence"], key=lambda e: e["score"], reverse=True)[:evidence_per_lecture]
        candidates.append(
            {
                "id": lecture.id,
                "title": lecture.title,
                "block_name": lecture.block.name if lecture.block else "",
                "full_path": f"{lecture.block.name} > {lecture.title}" if lecture.block else lecture.title,
                "score": info["score"],
                "evidence": [
                    {
                        "page_start": e["page_start"],
                        "page_end": e["page_end"],
                        "snippet": e["snippet"],
                        "chunk_id": e["chunk_id"],
                    }
                    for e in evidence
                ],
            }
        )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:top_k_lectures]
