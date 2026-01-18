"""Domain models for application core concepts.

Lightweight dataclasses representing Question, LectureChunk, Candidate, etc.
No dependencies on Flask, DB, or ML libraries.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class LectureChunk:
    """Represents a lecture note chunk."""

    id: int
    lecture_id: int
    page_start: int
    page_end: int
    content: str
    char_len: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "id": self.id,
            "lecture_id": self.lecture_id,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "content": self.content,
            "char_len": self.char_len,
        }


@dataclass
class Question:
    """Represents a question from database."""

    id: int
    exam_id: int
    question_number: int
    lecture_id: Optional[int]
    is_classified: bool
    content: Optional[str]
    image_path: Optional[str]
    q_type: Optional[str]
    answer: Optional[str]
    correct_answer_text: Optional[str]
    explanation: Optional[str]
    difficulty: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "id": self.id,
            "exam_id": self.exam_id,
            "question_number": self.question_number,
            "lecture_id": self.lecture_id,
            "is_classified": self.is_classified,
            "content": self.content,
            "image_path": self.image_path,
            "q_type": self.q_type,
            "answer": self.answer,
            "correct_answer_text": self.correct_answer_text,
            "explanation": self.explanation,
            "difficulty": self.difficulty,
        }


@dataclass
class Candidate:
    """Represents a lecture candidate for a question."""

    id: int
    title: str
    block_name: Optional[str]
    full_path: str
    score: float
    evidence: List["Evidence"]
    bm25_score: Optional[float] = None
    embedding_score: Optional[float] = None
    rrf_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "block_name": self.block_name,
            "full_path": self.full_path,
            "score": self.score,
            "evidence": [
                e.to_dict() if hasattr(e, "to_dict") else {} for e in self.evidence
            ],
            "bm25_score": self.bm25_score,
            "embedding_score": self.embedding_score,
            "rrf_score": self.rrf_score,
        }


@dataclass
class Evidence:
    """Evidence snippet for a retrieval candidate."""

    page_start: int
    page_end: int
    snippet: str
    chunk_id: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "page_start": self.page_start,
            "page_end": self.page_end,
            "snippet": self.snippet,
            "chunk_id": self.chunk_id,
        }


@dataclass
class RetrievalResult:
    """Output from retrieval stage."""

    question_id: int
    candidates: List[Candidate]
    timings: Optional[Dict[str, float]] = None
    debug: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "question_id": self.question_id,
            "candidates": [c.to_dict() for c in self.candidates],
            "timings": self.timings,
            "debug": self.debug,
        }


@dataclass
class ClassificationDecision:
    """Output from LLM classification stage."""

    lecture_id: Optional[int]
    confidence: float
    reason: str
    study_hint: str
    evidence: List[Dict[str, Any]]
    no_match: bool
    model_name: str
    candidate_ids: List[int]
    is_autoconfirmed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "lecture_id": self.lecture_id,
            "confidence": self.confidence,
            "reason": self.reason,
            "study_hint": self.study_hint,
            "evidence": self.evidence,
            "no_match": self.no_match,
            "model_name": self.model_name,
            "candidate_ids": self.candidate_ids,
            "is_autoconfirmed": self.is_autoconfirmed,
        }


@dataclass
class HealthStatus:
    """Health check response for API monitoring."""

    status: str
    schema_version: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "status": self.status,
            "schema_version": self.schema_version,
        }


__all__ = [
    "LectureChunk",
    "Question",
    "Candidate",
    "Evidence",
    "RetrievalResult",
    "ClassificationDecision",
    "HealthStatus",
]
