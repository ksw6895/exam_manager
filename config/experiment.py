"""Experiment configuration - experimental toggles and thresholds.

Reads experiment-related environment variables with clear namespacing.
"""

import os

from .base import (
    DEFAULT_RETRIEVAL_MODE,
    DEFAULT_RRF_K,
    DEFAULT_EMBEDDING_MODEL_NAME,
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_TOP_N,
    DEFAULT_HYDE_ENABLED,
    DEFAULT_HYDE_AUTO_GENERATE,
    DEFAULT_HYDE_PROMPT_VERSION,
    DEFAULT_HYDE_STRATEGY,
    DEFAULT_HYDE_BM25_VARIANT,
    DEFAULT_HYDE_NEGATIVE_MODE,
    DEFAULT_HYDE_MARGIN_EPS,
    DEFAULT_HYDE_MAX_KEYWORDS,
    DEFAULT_HYDE_MAX_NEGATIVE,
    DEFAULT_HYDE_EMBED_WEIGHT,
    DEFAULT_HYDE_EMBED_WEIGHT_ORIG,
    DEFAULT_PDF_PARSER_MODE,
    DEFAULT_AUTO_CONFIRM_V2_ENABLED,
    DEFAULT_AUTO_CONFIRM_V2_DELTA,
    DEFAULT_AUTO_CONFIRM_V2_MAX_BM25_RANK,
    DEFAULT_AUTO_CONFIRM_V2_DELTA_UNCERTAIN,
    DEFAULT_AUTO_CONFIRM_V2_MIN_CHUNK_LEN,
    DEFAULT_PARENT_ENABLED,
    DEFAULT_PARENT_WINDOW_PAGES,
    DEFAULT_PARENT_MAX_CHARS,
    DEFAULT_PARENT_TOPK,
    DEFAULT_SEMANTIC_EXPANSION_ENABLED,
    DEFAULT_SEMANTIC_EXPANSION_TOP_N,
    DEFAULT_SEMANTIC_EXPANSION_MAX_EXTRA,
    DEFAULT_SEMANTIC_EXPANSION_QUERY_MAX_CHARS,
)
from .schema import ExperimentConfig


def _env_flag(name, default=False):
    """Read a boolean environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


def _env_float(name, default):
    """Read a float environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name, default):
    """Read an integer environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_experiment_config() -> ExperimentConfig:
    """
    Build experiment configuration from environment variables.

    Returns:
        ExperimentConfig instance
    """
    return ExperimentConfig(
        ai_confidence_threshold=0.7,
        ai_auto_apply_margin=0.2,
        ai_auto_apply=_env_flag("AI_AUTO_APPLY", default=False),
        auto_confirm_v2_enabled=_env_flag("AUTO_CONFIRM_V2_ENABLED", default=True),
        auto_confirm_v2_delta=_env_float(
            "AUTO_CONFIRM_V2_DELTA", default=DEFAULT_AUTO_CONFIRM_V2_DELTA
        ),
        auto_confirm_v2_max_bm25_rank=_env_int(
            "AUTO_CONFIRM_V2_MAX_BM25_RANK",
            default=DEFAULT_AUTO_CONFIRM_V2_MAX_BM25_RANK,
        ),
        auto_confirm_v2_delta_uncertain=_env_float(
            "AUTO_CONFIRM_V2_DELTA_UNCERTAIN",
            default=DEFAULT_AUTO_CONFIRM_V2_DELTA_UNCERTAIN,
        ),
        auto_confirm_v2_min_chunk_len=_env_int(
            "AUTO_CONFIRM_V2_MIN_CHUNK_LEN",
            default=DEFAULT_AUTO_CONFIRM_V2_MIN_CHUNK_LEN,
        ),
        parent_enabled=_env_flag("PARENT_ENABLED", default=False),
        parent_window_pages=_env_int(
            "PARENT_WINDOW_PAGES", default=DEFAULT_PARENT_WINDOW_PAGES
        ),
        parent_max_chars=_env_int("PARENT_MAX_CHARS", default=DEFAULT_PARENT_MAX_CHARS),
        parent_topk=_env_int("PARENT_TOPK", default=DEFAULT_PARENT_TOPK),
        semantic_expansion_enabled=_env_flag(
            "SEMANTIC_EXPANSION_ENABLED", default=True
        ),
        semantic_expansion_top_n=_env_int(
            "SEMANTIC_EXPANSION_TOP_N", default=DEFAULT_SEMANTIC_EXPANSION_TOP_N
        ),
        semantic_expansion_max_extra=_env_int(
            "SEMANTIC_EXPANSION_MAX_EXTRA", default=DEFAULT_SEMANTIC_EXPANSION_MAX_EXTRA
        ),
        semantic_expansion_query_max_chars=_env_int(
            "SEMANTIC_EXPANSION_QUERY_MAX_CHARS",
            default=DEFAULT_SEMANTIC_EXPANSION_QUERY_MAX_CHARS,
        ),
        retrieval_mode=os.environ.get("RETRIEVAL_MODE", DEFAULT_RETRIEVAL_MODE),
        rrf_k=_env_int("RRF_K", default=DEFAULT_RRF_K),
        embedding_model_name=os.environ.get(
            "EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_MODEL_NAME
        ),
        embedding_dim=_env_int("EMBEDDING_DIM", default=DEFAULT_EMBEDDING_DIM),
        embedding_top_n=_env_int("EMBEDDING_TOP_N", default=DEFAULT_EMBEDDING_TOP_N),
        hyde_enabled=_env_flag("HYDE_ENABLED", default=DEFAULT_HYDE_ENABLED),
        hyde_auto_generate=_env_flag(
            "HYDE_AUTO_GENERATE", default=DEFAULT_HYDE_AUTO_GENERATE
        ),
        hyde_prompt_version=os.environ.get(
            "HYDE_PROMPT_VERSION", DEFAULT_HYDE_PROMPT_VERSION
        ),
        hyde_model_name=os.environ.get("HYDE_MODEL_NAME"),
        hyde_strategy=os.environ.get("HYDE_STRATEGY", DEFAULT_HYDE_STRATEGY),
        hyde_bm25_variant=os.environ.get(
            "HYDE_BM25_VARIANT", DEFAULT_HYDE_BM25_VARIANT
        ),
        hyde_negative_mode=os.environ.get(
            "HYDE_NEGATIVE_MODE", DEFAULT_HYDE_NEGATIVE_MODE
        ),
        hyde_margin_eps=_env_float("HYDE_MARGIN_EPS", default=DEFAULT_HYDE_MARGIN_EPS),
        hyde_max_keywords=_env_int(
            "HYDE_MAX_KEYWORDS", default=DEFAULT_HYDE_MAX_KEYWORDS
        ),
        hyde_max_negative=_env_int(
            "HYDE_MAX_NEGATIVE", default=DEFAULT_HYDE_MAX_NEGATIVE
        ),
        hyde_embed_weight=_env_float(
            "HYDE_EMBED_WEIGHT", default=DEFAULT_HYDE_EMBED_WEIGHT
        ),
        hyde_embed_weight_orig=_env_float(
            "HYDE_EMBED_WEIGHT_ORIG", default=DEFAULT_HYDE_EMBED_WEIGHT_ORIG
        ),
        pdf_parser_mode=os.environ.get("PDF_PARSER_MODE", DEFAULT_PDF_PARSER_MODE),
    )


__all__ = ["get_experiment_config", "_env_flag", "_env_float", "_env_int"]
