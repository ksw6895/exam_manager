#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classification Pipeline Service

Single entry point for "문제 1개 분류" (classify one question).
Orchestrates the classification pipeline with clear stages:
1. RETRIEVE: Search/retrieve candidate lectures
2. EXPAND: Optionally expand context for uncertain cases
3. JUDGE: LLM-based classification decision

This module provides a unified interface for classification operations.
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from config import get_config

from app.services import retrieval
from app.services import context_expander
from app.services.ai_classifier import (
    LectureRetriever,
    GeminiClassifier,
)
from app.models import Question
from app.services.folder_scope import resolve_lecture_ids


@dataclass
class ClassificationContext:
    """Context passed through pipeline stages."""

    question: Question
    question_text: str
    lecture_ids: Optional[List[int]]
    block_id: Optional[int]
    folder_id: Optional[int]
    include_descendants: bool
    metadata: Dict[str, Any]


@dataclass
class RetrievalResult:
    """Output from RETRIEVE stage."""

    candidates: List[Dict]


@dataclass
class ExpansionResult:
    """Output from EXPAND stage."""

    candidates: List[Dict]


@dataclass
class JudgmentResult:
    """Output from JUDGE stage."""

    lecture_id: Optional[int]
    confidence: float
    reason: str
    study_hint: str
    evidence: List[Dict]
    no_match: bool
    model_name: str
    candidate_ids: List[int]


def classify_single_question(
    question: Question,
    lecture_ids: Optional[List[int]] = None,
    block_id: Optional[int] = None,
    folder_id: Optional[int] = None,
    include_descendants: bool = True,
) -> JudgmentResult:
    """
    Single entry point for classifying one question.

    Pipeline stages (in order):
        1. RETRIEVE: Search for candidate lectures
        2. EXPAND: Optionally expand context (when uncertain)
        3. JUDGE: LLM classification decision

    Args:
        question: Question object to classify
        lecture_ids: Optional list of lecture IDs to restrict search
        block_id: Optional block ID for scope filtering
        folder_id: Optional folder ID for scope filtering
        include_descendants: Whether to include descendant lectures

    Returns:
        JudgmentResult with classification decision
    """
    choices = [c.content for c in question.choices.order_by("choice_number").all()]
    question_text = question.content or ""
    if choices:
        question_text = f"{question_text}\n" + " ".join(choices)
    question_text = question_text.strip()
    if len(question_text) > 4000:
        question_text = question_text[:4000]

    context = ClassificationContext(
        question=question,
        question_text=question_text,
        lecture_ids=lecture_ids,
        block_id=block_id,
        folder_id=folder_id,
        include_descendants=include_descendants,
        metadata={},
    )

    retrieval = _retrieve_stage(context)
    expansion = _expand_stage(context, retrieval.candidates)
    judgment = _judge_stage(context, expansion.candidates, choices)

    return judgment


def _retrieve_stage(context: ClassificationContext) -> RetrievalResult:
    """
    Stage 1: RETRIEVE
    Search/retrieve candidate lectures based on question text.

    Returns:
        RetrievalResult with candidate lectures list
    """
    from app.services.ai_classifier import LectureRetriever

    retriever = LectureRetriever()
    retriever.refresh_cache()

    if not context.lecture_ids and (context.block_id or context.folder_id):
        context.lecture_ids = resolve_lecture_ids(
            context.block_id,
            context.folder_id,
            context.include_descendants,
        )

    candidates = retriever.find_candidates(
        context.question_text,
        top_k=8,
        question_id=context.question.id,
        lecture_ids=context.lecture_ids,
    )

    return RetrievalResult(candidates=candidates)


def _expand_stage(
    context: ClassificationContext,
    candidates: List[Dict],
) -> ExpansionResult:
    """
    Stage 2: EXPAND
    Optionally expand context with semantic neighbors when uncertain.

    This stage only runs when:
        - PARENT_ENABLED is True
        - Retrieval features indicate uncertainty

    Returns:
        ExpansionResult with (potentially expanded) candidates list
    """
    if not get_config().experiment.parent_enabled:
        return ExpansionResult(candidates=candidates)

    from app.services import retrieval_features

    artifacts = retrieval_features.build_retrieval_artifacts(
        context.question_text,
        context.question.id,
    )
    features = artifacts.features

    auto_confirm = False
    if get_config().experiment.auto_confirm_v2_enabled:
        auto_confirm = retrieval_features.auto_confirm_v2(
            features,
            delta=get_config().experiment.auto_confirm_v2_delta,
            max_bm25_rank=get_config().experiment.auto_confirm_v2_max_bm25_rank,
        )

    uncertain = retrieval_features.is_uncertain(
        features,
        delta_uncertain=get_config().experiment.auto_confirm_v2_delta_uncertain,
        min_chunk_len=get_config().experiment.auto_confirm_v2_min_chunk_len,
        auto_confirm=auto_confirm,
    )

    if not uncertain:
        return ExpansionResult(candidates=candidates)

    expanded = context_expander.expand_candidates(candidates)
    return ExpansionResult(candidates=expanded)


def _judge_stage(
    context: ClassificationContext,
    candidates: List[Dict],
    choices: List[str],
) -> JudgmentResult:
    """
    Stage 3: JUDGE
    LLM-based classification decision.

    Returns:
        JudgmentResult with final classification decision
    """
    from app.services.ai_classifier import GeminiClassifier

    classifier = GeminiClassifier()
    result = classifier.classify_single(context.question, candidates)

    candidate_ids = [c.get("id") for c in candidates if c.get("id") is not None]

    return JudgmentResult(
        lecture_id=result.get("lecture_id"),
        confidence=result.get("confidence", 0.0),
        reason=result.get("reason", ""),
        study_hint=result.get("study_hint", ""),
        evidence=result.get("evidence", []),
        no_match=result.get("no_match", False),
        model_name=result.get("model_name", ""),
        candidate_ids=candidate_ids,
    )


__all__ = [
    "ClassificationContext",
    "RetrievalResult",
    "ExpansionResult",
    "JudgmentResult",
    "classify_single_question",
]
