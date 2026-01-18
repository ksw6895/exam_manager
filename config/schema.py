"""Configuration schema dataclasses.

Minimal dataclasses for runtime and experiment configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class RuntimeConfig:
    """Runtime configuration - environment-driven settings."""

    # Database
    db_uri: str
    db_read_only: bool = False

    # Backup
    auto_backup_before_write: bool = False
    auto_backup_keep: int = 30
    auto_backup_dir: Path = field(default_factory=lambda: Path("backups"))
    enforce_backup_before_write: bool = False

    # Migration checks
    check_pending_migrations: bool = True
    fail_on_pending_migrations: bool = False
    auto_create_db: bool = False

    # File handling
    upload_folder: Path = field(default_factory=lambda: Path("app/static/uploads"))
    max_content_length: int = 100 * 1024 * 1024  # 100MB
    allowed_extensions: set = field(
        default_factory=lambda: {"png", "jpg", "jpeg", "gif"}
    )

    # AI/Gemini
    gemini_api_key: Optional[str] = None
    gemini_model_name: str = "gemini-2.0-flash-lite"
    gemini_max_output_tokens: int = 2048

    # Classifier cache
    classifier_cache_path: Path = field(
        default_factory=lambda: Path("data/classifier_cache.json")
    )

    # Cache/artifacts
    data_cache_dir: Path = field(default_factory=lambda: Path("data/cache"))
    reports_dir: Path = field(default_factory=lambda: Path("reports"))

    # Admin/security
    local_admin_only: bool = False

    # CORS
    cors_allowed_origins: str = "http://localhost:3000"

    def __post_init__(self):
        """Validate after initialization."""
        if self.auto_backup_keep < 0:
            raise ValueError("AUTO_BACKUP_KEEP must be >= 0")
        if self.max_content_length <= 0:
            raise ValueError("MAX_CONTENT_LENGTH must be > 0")
        if self.auto_backup_dir and not isinstance(self.auto_backup_dir, Path):
            self.auto_backup_dir = Path(self.auto_backup_dir)


@dataclass
class ExperimentConfig:
    """Experiment configuration - experimental toggles and thresholds."""

    # AI Classification thresholds
    ai_confidence_threshold: float = 0.7
    ai_auto_apply_margin: float = 0.2
    ai_auto_apply: bool = False

    # Auto-Confirm V2
    auto_confirm_v2_enabled: bool = True
    auto_confirm_v2_delta: float = 0.05
    auto_confirm_v2_max_bm25_rank: int = 5
    auto_confirm_v2_delta_uncertain: float = 0.03
    auto_confirm_v2_min_chunk_len: int = 200

    # Context Expansion
    parent_enabled: bool = False
    parent_window_pages: int = 1
    parent_max_chars: int = 3500
    parent_topk: int = 5

    # Semantic Expansion
    semantic_expansion_enabled: bool = True
    semantic_expansion_top_n: int = 6
    semantic_expansion_max_extra: int = 2
    semantic_expansion_query_max_chars: int = 1200

    # Retrieval mode
    retrieval_mode: str = "hybrid_rrf"
    rrf_k: int = 60

    # Embedding model
    embedding_model_name: str = "intfloat/multilingual-e5-base"
    embedding_dim: int = 768
    embedding_top_n: int = 300

    # HYDE (Hypothetical Document Embeddings)
    hyde_enabled: bool = False
    hyde_auto_generate: bool = False
    hyde_prompt_version: str = "hyde_v1"
    hyde_model_name: Optional[str] = None
    hyde_strategy: str = "blend"  # blend | best_of_two
    hyde_bm25_variant: str = "mixed_light"
    hyde_negative_mode: str = "stopwords"
    hyde_margin_eps: float = 0.0
    hyde_max_keywords: int = 7
    hyde_max_negative: int = 6
    hyde_embed_weight: float = 0.7
    hyde_embed_weight_orig: float = 0.3

    # PDF Processing
    pdf_parser_mode: str = "legacy"

    def __post_init__(self):
        """Validate after initialization."""
        if not 0.0 <= self.ai_confidence_threshold <= 1.0:
            raise ValueError("AI_CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")
        if not 0.0 <= self.ai_auto_apply_margin <= 1.0:
            raise ValueError("AI_AUTO_APPLY_MARGIN must be between 0.0 and 1.0")
        if self.auto_confirm_v2_delta < 0:
            raise ValueError("AUTO_CONFIRM_V2_DELTA must be >= 0")
        if self.auto_confirm_v2_delta_uncertain < 0:
            raise ValueError("AUTO_CONFIRM_V2_DELTA_UNCERTAIN must be >= 0")
        if self.auto_confirm_v2_min_chunk_len < 0:
            raise ValueError("AUTO_CONFIRM_V2_MIN_CHUNK_LEN must be >= 0")
        if self.rrf_k <= 0:
            raise ValueError("RRF_K must be > 0")
        if self.embedding_dim <= 0:
            raise ValueError("EMBEDDING_DIM must be > 0")
        if not 0.0 <= self.hyde_embed_weight <= 1.0:
            raise ValueError("HYDE_EMBED_WEIGHT must be between 0.0 and 1.0")
        if not 0.0 <= self.hyde_embed_weight_orig <= 1.0:
            raise ValueError("HYDE_EMBED_WEIGHT_ORIG must be between 0.0 and 1.0")
        if self.hyde_strategy not in ("blend", "best_of_two"):
            raise ValueError("HYDE_STRATEGY must be 'blend' or 'best_of_two'")


@dataclass
class AppConfig:
    """Application configuration - composition of runtime and experiment configs."""

    runtime: RuntimeConfig
    experiment: ExperimentConfig

    # Flask-specific settings
    secret_key: str = "dev-secret-key-change-in-production"

    def __post_init__(self):
        """Validate derived configuration."""
        if (
            not self.secret_key
            or self.secret_key == "dev-secret-key-change-in-production"
        ):
            # In production, this would be a warning or error
            pass


__all__ = ["RuntimeConfig", "ExperimentConfig", "AppConfig"]
