from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.models import LectureChunk
from app.services import retrieval


@dataclass
class RetrievalArtifacts:
    bm25_chunks: List[Dict]
    embed_chunks: List[Dict]
    hybrid_chunks: List[Dict]
    features: Dict[str, object]


def _ranked_list(chunks: List[Dict], score_key: str, top_k: int) -> List[Dict]:
    ranked = []
    for idx, chunk in enumerate(chunks[:top_k]):
        ranked.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "lecture_id": chunk.get("lecture_id"),
                "score": float(chunk.get(score_key) or 0.0),
                "rank": idx + 1,
            }
        )
    return ranked


def _margin(chunks: List[Dict], score_key: str) -> Optional[float]:
    if len(chunks) < 2:
        return None
    return float(chunks[0].get(score_key) or 0.0) - float(
        chunks[1].get(score_key) or 0.0
    )


def _top1_pair(chunks: List[Dict]) -> tuple[Optional[int], Optional[int]]:
    if not chunks:
        return None, None
    return chunks[0].get("chunk_id"), chunks[0].get("lecture_id")


def _chunk_length(chunk_id: Optional[int]) -> Optional[int]:
    if chunk_id is None:
        return None
    chunk = LectureChunk.query.get(chunk_id)
    if not chunk:
        return None
    if chunk.char_len is not None:
        return int(chunk.char_len)
    return len(chunk.content or "")


def build_retrieval_artifacts(
    question_text: str,
    question_id: Optional[int],
    *,
    top_n: int = 80,
    top_k: int = 5,
) -> RetrievalArtifacts:
    bm25_chunks = retrieval.search_chunks_bm25(
        question_text,
        top_n=top_n,
        question_id=question_id,
    )
    embed_chunks = retrieval.search_chunks_embedding(
        question_text,
        top_n=top_n,
        candidate_chunks=bm25_chunks,
        question_id=question_id,
    )
    hybrid_chunks = retrieval.search_chunks_hybrid_rrf(
        question_text,
        top_n=top_n,
        question_id=question_id,
    )

    bm25_topk = _ranked_list(bm25_chunks, "bm25_score", top_k)
    embed_topk = _ranked_list(embed_chunks, "embedding_score", top_k)
    hybrid_topk = _ranked_list(hybrid_chunks, "rrf_score", top_k)

    bm25_top1_chunk, bm25_top1_lecture = _top1_pair(bm25_chunks)
    embed_top1_chunk, embed_top1_lecture = _top1_pair(embed_chunks)
    hybrid_top1_chunk, hybrid_top1_lecture = _top1_pair(hybrid_chunks)

    bm25_rank_map = {
        chunk.get("chunk_id"): idx + 1
        for idx, chunk in enumerate(bm25_chunks)
        if chunk.get("chunk_id") is not None
    }
    embed_rank_map = {
        chunk.get("chunk_id"): idx + 1
        for idx, chunk in enumerate(embed_chunks)
        if chunk.get("chunk_id") is not None
    }

    bm25_margin = _margin(bm25_chunks, "bm25_score")
    embed_margin = _margin(embed_chunks, "embedding_score")

    features = {
        "bm25_top1_chunk_id": bm25_top1_chunk,
        "bm25_top1_lecture_id": bm25_top1_lecture,
        "embed_top1_chunk_id": embed_top1_chunk,
        "embed_top1_lecture_id": embed_top1_lecture,
        "hybrid_top1_chunk_id": hybrid_top1_chunk,
        "hybrid_top1_lecture_id": hybrid_top1_lecture,
        "bm25_margin": bm25_margin,
        "embed_margin": embed_margin,
        "bm25_hybrid_agree": bool(
            bm25_top1_chunk and bm25_top1_chunk == hybrid_top1_chunk
        ),
        "embed_hybrid_agree": bool(
            embed_top1_chunk and embed_top1_chunk == hybrid_top1_chunk
        ),
        "bm25_embed_agree": bool(
            bm25_top1_chunk and bm25_top1_chunk == embed_top1_chunk
        ),
        "hybrid_top1_bm25_rank": bm25_rank_map.get(hybrid_top1_chunk),
        "hybrid_top1_embed_rank": embed_rank_map.get(hybrid_top1_chunk),
        "hybrid_top1_chunk_len": _chunk_length(hybrid_top1_chunk),
        "bm25_topk": bm25_topk,
        "embed_topk": embed_topk,
        "hybrid_topk": hybrid_topk,
    }

    return RetrievalArtifacts(
        bm25_chunks=bm25_chunks,
        embed_chunks=embed_chunks,
        hybrid_chunks=hybrid_chunks,
        features=features,
    )


def auto_confirm_v2(
    features: Dict[str, object], *, delta: float, max_bm25_rank: int
) -> bool:
    if not features:
        return False
    bm25_top1 = features.get("bm25_top1_chunk_id")
    hybrid_top1 = features.get("hybrid_top1_chunk_id")
    if not bm25_top1 or not hybrid_top1:
        return False
    if bm25_top1 != hybrid_top1:
        return False
    embed_margin = features.get("embed_margin")
    if embed_margin is None or float(embed_margin) < delta:
        return False
    hybrid_bm25_rank = features.get("hybrid_top1_bm25_rank")
    if hybrid_bm25_rank is None or int(hybrid_bm25_rank) > max_bm25_rank:
        return False
    return True


def is_uncertain(
    features: Dict[str, object],
    *,
    delta_uncertain: float,
    min_chunk_len: int,
    auto_confirm: bool,
) -> bool:
    if not auto_confirm:
        return True
    embed_margin = features.get("embed_margin")
    if embed_margin is None or float(embed_margin) < delta_uncertain:
        return True
    bm25_top1 = features.get("bm25_top1_chunk_id")
    hybrid_top1 = features.get("hybrid_top1_chunk_id")
    if bm25_top1 and hybrid_top1 and bm25_top1 != hybrid_top1:
        return True
    chunk_len = features.get("hybrid_top1_chunk_len")
    if chunk_len is None or int(chunk_len) < min_chunk_len:
        return True
    return False
