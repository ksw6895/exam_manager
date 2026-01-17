from __future__ import annotations

import re
from typing import List, Dict

import numpy as np
from flask import current_app
from sqlalchemy import text, bindparam

from app import db
from app.models import Lecture, Block
from app.services.embedding_utils import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_MODEL_NAME,
    embed_texts,
    decode_embedding,
)
from app.services.query_transformer import get_query_payload


# FTS5 reserved operators (case-insensitive)
_FTS_RESERVED = {"OR", "AND", "NOT", "NEAR"}
_BM25_STOPWORDS = {
    "다음", "중", "옳은", "틀린", "아닌", "것", "가장", "맞는",
    "고른", "고르시오", "선지", "문항", "보기", "위", "아래",
    "다음중", "해당", "설명", "것은",
}

# Token patterns:
#  - ratios like 120/80
#  - decimals like 7.35
#  - integers like 140
#  - words (Korean/English) like "Cr", "Na", "알칼리증"
_TOKEN_RE = re.compile(
    r"""
    \d+/\d+            # ratio
    |\d+\.\d+          # decimal
    |[A-Za-z]+[0-9]+[A-Za-z0-9]*[+-]?  # alnum like HCO3, HbA1c, pCO2
    |[0-9]+[A-Za-z]+[A-Za-z0-9]*       # alnum like 2A
    |[A-Za-z]+[+-]?                    # english word, optional +/-
    |[가-힣]+           # korean word
    |\d+               # integer
    """,
    re.VERBOSE,
)


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


def _filter_negative_terms(tokens: List[str], negatives: List[str]) -> List[str]:
    if not tokens or not negatives:
        return tokens
    neg = {t.lower() for t in negatives if t}
    return [t for t in tokens if t.lower() not in neg]


def _clean_tokens(tokens: List[str]) -> List[str]:
    if not tokens:
        return []
    return [t for t in tokens if t not in _BM25_STOPWORDS]


def make_bm25_match_query(raw_question_text: str) -> str:
    tokens = _normalize_query(raw_question_text)
    return _build_fts_query(tokens, max_terms=16, mode="OR")


def safe_match_query_variants(raw_question_text: str) -> List[str]:
    tokens = _normalize_query(raw_question_text)
    if not tokens:
        return []
    return [
        _build_fts_query(tokens, max_terms=16, mode="OR"),
        _build_fts_query(tokens, max_terms=8, mode="OR"),
        _build_fts_query(tokens, max_terms=4, mode="OR"),
    ]


def _get_hyde_payload(question_id: int | None, question_text: str):
    if not question_id:
        return None
    if not current_app.config.get("HYDE_ENABLED", False):
        return None
    allow_generate = current_app.config.get("HYDE_AUTO_GENERATE", False)
    return get_query_payload(
        question_id,
        question_text,
        allow_generate=allow_generate,
    )


def _normalize_embedding_text(text: str, max_chars: int = 4000) -> str:
    if not text:
        return ""
    s = text.replace("\u00A0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_chars:
        s = s[:max_chars]
    return s


def search_chunks_bm25(
    query: str,
    top_n: int = 80,
    *,
    question_id: int | None = None,
    lecture_ids: List[int] | None = None,    
) -> List[Dict]:
    tokens = _normalize_query(query)
    fts_query = _build_fts_query(tokens, max_terms=16, mode="OR")
    payload = _get_hyde_payload(question_id, query)
    if payload:
        variant = current_app.config.get("HYDE_BM25_VARIANT", "mixed_light")
        if variant == "orig_only":
            positive = tokens
        elif variant == "hyde_only":
            positive = payload.keywords
        else:
            positive = payload.keywords + _clean_tokens(tokens)

        negative_mode = current_app.config.get("HYDE_NEGATIVE_MODE", "stopwords")
        if negative_mode == "stopwords":
            positive = _filter_negative_terms(positive, payload.negative_keywords)

        if positive:
            fts_query = _build_fts_query(positive, max_terms=16, mode="OR")
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


def _fetch_embeddings_for_chunks(
    chunk_ids: List[int],
    model_name: str,
    dim: int,
) -> Dict[int, np.ndarray]:
    if not chunk_ids:
        return {}
    sql = text(
        """
        SELECT chunk_id, embedding
        FROM lecture_chunk_embeddings
        WHERE model_name = :model
          AND chunk_id IN :chunk_ids
        """
    ).bindparams(bindparam("chunk_ids", expanding=True))
    rows = db.session.execute(
        sql,
        {"model": model_name, "chunk_ids": chunk_ids},
    ).mappings().all()
    embeddings = {}
    for row in rows:
        vec = decode_embedding(row.get("embedding"), dim)
        if vec is None:
            continue
        embeddings[row.get("chunk_id")] = vec
    return embeddings


class EmbeddingIndex:
    """In-memory embedding index for hybrid retrieval."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._model_name = None
        self._dim = None
        self._embeddings = None
        self._meta = []
        self._initialized = True

    def load(self, model_name: str, dim: int) -> None:
        if self._model_name == model_name and self._dim == dim and self._embeddings is not None:
            return
        try:
            rows = db.session.execute(
                text(
                    """
                    SELECT e.chunk_id, e.lecture_id, e.embedding,
                           c.page_start, c.page_end, c.content
                    FROM lecture_chunk_embeddings e
                    JOIN lecture_chunks c ON c.id = e.chunk_id
                    WHERE e.model_name = :model
                    """
                ),
                {"model": model_name},
            ).mappings().all()
        except Exception:
            rows = []

        embeddings = []
        meta = []
        for row in rows:
            vec = decode_embedding(row.get("embedding"), dim)
            if vec is None:
                continue
            content = row.get("content") or ""
            snippet = content.replace("\n", " ").strip()
            if len(snippet) > 160:
                snippet = snippet[:157] + "..."
            meta.append(
                {
                    "chunk_id": row.get("chunk_id"),
                    "lecture_id": row.get("lecture_id"),
                    "page_start": row.get("page_start"),
                    "page_end": row.get("page_end"),
                    "snippet": snippet,
                }
            )
            embeddings.append(vec)

        self._model_name = model_name
        self._dim = dim
        if embeddings:
            self._embeddings = np.vstack(embeddings)
        else:
            self._embeddings = np.zeros((0, dim), dtype=np.float32)
        self._meta = meta

    @property
    def embeddings(self) -> np.ndarray:
        return self._embeddings

    @property
    def meta(self) -> List[Dict]:
        return self._meta


def search_chunks_embedding(
    query: str,
    top_n: int = 80,
    candidate_chunks: List[Dict] | None = None,
    *,
    question_id: int | None = None,
) -> List[Dict]:
    normalized = _normalize_embedding_text(query)
    if not normalized:
        return []

    model_name = current_app.config.get("EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_MODEL_NAME)
    dim = int(current_app.config.get("EMBEDDING_DIM", DEFAULT_EMBEDDING_DIM))
    payload = _get_hyde_payload(question_id, query)
    strategy = current_app.config.get("HYDE_STRATEGY", "blend")
    weight_hyde = float(current_app.config.get("HYDE_EMBED_WEIGHT", 0.7))
    weight_orig = float(current_app.config.get("HYDE_EMBED_WEIGHT_ORIG", 0.3))
    try:
        orig_vec = embed_texts([normalized], model_name, dim, is_query=True)[0]
        query_vec = orig_vec
        if strategy == "blend" and payload and payload.lecture_style_query:
            hyde_norm = _normalize_embedding_text(payload.lecture_style_query)
            if hyde_norm:
                hyde_vec = embed_texts([hyde_norm], model_name, dim, is_query=True)[0]
                combined = (orig_vec * weight_orig) + (hyde_vec * weight_hyde)
                norm = float(np.linalg.norm(combined))
                if norm > 0:
                    combined = combined / norm
                query_vec = combined
    except Exception as exc:
        current_app.logger.warning("Embedding query failed: %s", exc)
        return []

    if candidate_chunks is not None:
        chunk_ids = [
            chunk.get("chunk_id")
            for chunk in candidate_chunks
            if chunk.get("chunk_id") is not None
        ]
        try:
            emb_map = _fetch_embeddings_for_chunks(chunk_ids, model_name, dim)
        except Exception as exc:
            current_app.logger.warning("Embedding fetch failed: %s", exc)
            return []
        if not emb_map:
            return []
        results = []
        for chunk in candidate_chunks:
            chunk_id = chunk.get("chunk_id")
            if chunk_id is None:
                continue
            vec = emb_map.get(chunk_id)
            if vec is None:
                continue
            score = float(vec @ query_vec)
            results.append(
                {
                    "chunk_id": chunk_id,
                    "lecture_id": chunk.get("lecture_id"),
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "snippet": chunk.get("snippet") or "",
                    "embedding_score": score,
                }
            )
        results.sort(key=lambda item: item.get("embedding_score", 0.0), reverse=True)
        return results[:top_n]

    index = EmbeddingIndex()
    index.load(model_name, dim)
    if index.embeddings.size == 0:
        return []

    scores = index.embeddings @ query_vec
    total = scores.shape[0]
    if total == 0:
        return []
    if top_n >= total:
        ranked_idx = np.argsort(scores)[::-1]
    else:
        idx = np.argpartition(scores, -top_n)[-top_n:]
        ranked_idx = idx[np.argsort(scores[idx])[::-1]]

    results = []
    for idx in ranked_idx:
        meta = index.meta[idx]
        results.append(
            {
                "chunk_id": meta.get("chunk_id"),
                "lecture_id": meta.get("lecture_id"),
                "page_start": meta.get("page_start"),
                "page_end": meta.get("page_end"),
                "snippet": meta.get("snippet"),
                "embedding_score": float(scores[idx]),
            }
        )
    return results


def search_chunks_hybrid_rrf(
    query: str,
    top_n: int = 80,
    *,
    question_id: int | None = None,
    lecture_ids: List[int] | None = None,
) -> List[Dict]:
    rrf_k = int(current_app.config.get("RRF_K", 60))
    embed_top_n = int(current_app.config.get("EMBEDDING_TOP_N", top_n))
    bm25_top_n = max(top_n, embed_top_n)
    strategy = current_app.config.get("HYDE_STRATEGY", "blend")
    bm25_chunks = search_chunks_bm25(
        query,
        top_n=bm25_top_n,
        question_id=question_id,
        lecture_ids=lecture_ids,
    )
    if not bm25_chunks:
        return []
    if strategy == "best_of_two":
        payload = _get_hyde_payload(question_id, query)
        if payload and payload.lecture_style_query:
            orig_chunks = search_chunks_embedding(
                query,
                top_n=embed_top_n,
                candidate_chunks=bm25_chunks,
                question_id=None,
            )
            hyde_chunks = search_chunks_embedding(
                payload.lecture_style_query,
                top_n=embed_top_n,
                candidate_chunks=bm25_chunks,
                question_id=None,
            )

            def _margin(chunks: List[Dict]) -> float:
                if not chunks:
                    return -1.0
                top1 = float(chunks[0].get("embedding_score") or 0.0)
                top2 = float(chunks[1].get("embedding_score") or 0.0) if len(chunks) > 1 else 0.0
                return top1 - top2

            margin_orig = _margin(orig_chunks)
            margin_hyde = _margin(hyde_chunks)
            eps = float(current_app.config.get("HYDE_MARGIN_EPS", 0.0))
            if margin_hyde > (margin_orig + eps):
                emb_chunks = hyde_chunks
            else:
                emb_chunks = orig_chunks
        else:
            emb_chunks = search_chunks_embedding(
                query,
                top_n=embed_top_n,
                candidate_chunks=bm25_chunks,
                question_id=question_id,
            )
    else:
        emb_chunks = search_chunks_embedding(
            query,
            top_n=embed_top_n,
            candidate_chunks=bm25_chunks,
            question_id=question_id,
        )

    if not emb_chunks:
        return [
            {**chunk, "rrf_score": 1.0 / (rrf_k + idx + 1)}
            for idx, chunk in enumerate(bm25_chunks)
        ]

    rrf_scores = {}
    meta_map = {}

    for idx, chunk in enumerate(bm25_chunks):
        chunk_id = chunk.get("chunk_id")
        if chunk_id is None:
            continue
        rrf_scores.setdefault(chunk_id, 0.0)
        rrf_scores[chunk_id] += 1.0 / (rrf_k + idx + 1)
        meta_map.setdefault(chunk_id, chunk)

    for idx, chunk in enumerate(emb_chunks):
        chunk_id = chunk.get("chunk_id")
        if chunk_id is None:
            continue
        rrf_scores.setdefault(chunk_id, 0.0)
        rrf_scores[chunk_id] += 1.0 / (rrf_k + idx + 1)
        meta_map.setdefault(chunk_id, chunk)

    combined = []
    for chunk_id, score in rrf_scores.items():
        meta = meta_map.get(chunk_id, {})
        combined.append(
            {
                "chunk_id": chunk_id,
                "lecture_id": meta.get("lecture_id"),
                "page_start": meta.get("page_start"),
                "page_end": meta.get("page_end"),
                "snippet": meta.get("snippet") or "",
                "rrf_score": score,
            }
        )

    combined.sort(key=lambda item: item.get("rrf_score", 0.0), reverse=True)
    return combined[:top_n]


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
