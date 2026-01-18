"""
Flask 애플리케이션 설정 (Backward Compatibility Shim)

This file is kept for backward compatibility. All configuration is now managed by
the `config/` package. Import from `config` instead of this module.

TODO(deprecate): Migrate imports to use `from config import get_config`
"""

from config import get_config
from pathlib import Path

# Get configuration singleton
_app_config = get_config()

# Project root directory (exported for legacy usage)
BASE_DIR = Path(__file__).parent.absolute()


# Backward compatibility: export configuration from config package
class Config:
    """기본 설정 클래스 (backward compatibility shim)"""

    # ========================================================================
    # Core Settings
    # ========================================================================
    SECRET_KEY = _app_config.secret_key

    # ========================================================================
    # Database Operations
    # ========================================================================
    SQLALCHEMY_DATABASE_URI = str(_app_config.runtime.db_uri)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTO_BACKUP_BEFORE_WRITE = _app_config.runtime.auto_backup_before_write
    AUTO_BACKUP_KEEP = _app_config.runtime.auto_backup_keep
    AUTO_BACKUP_DIR = str(_app_config.runtime.auto_backup_dir)
    ENFORCE_BACKUP_BEFORE_WRITE = _app_config.runtime.enforce_backup_before_write
    DB_READ_ONLY = _app_config.runtime.db_read_only
    CHECK_PENDING_MIGRATIONS = _app_config.runtime.check_pending_migrations
    FAIL_ON_PENDING_MIGRATIONS = _app_config.runtime.fail_on_pending_migrations
    AUTO_CREATE_DB = _app_config.runtime.auto_create_db

    # ========================================================================
    # File Handling
    # ========================================================================
    UPLOAD_FOLDER = _app_config.runtime.upload_folder
    MAX_CONTENT_LENGTH = _app_config.runtime.max_content_length
    ALLOWED_EXTENSIONS = _app_config.runtime.allowed_extensions

    # ========================================================================
    # AI Classification (Gemini)
    # ========================================================================
    GEMINI_API_KEY = _app_config.runtime.gemini_api_key
    GEMINI_MODEL_NAME = _app_config.runtime.gemini_model_name
    GEMINI_MAX_OUTPUT_TOKENS = _app_config.runtime.gemini_max_output_tokens

    # ========================================================================
    # Classifier Cache
    # ========================================================================
    CLASSIFIER_CACHE_PATH = str(_app_config.runtime.classifier_cache_path)

    # ========================================================================
    # Auto-Confirm V2 (Classifier Enhancement)
    # ========================================================================
    AUTO_CONFIRM_V2_ENABLED = _app_config.experiment.auto_confirm_v2_enabled
    AUTO_CONFIRM_V2_DELTA = _app_config.experiment.auto_confirm_v2_delta
    AUTO_CONFIRM_V2_MAX_BM25_RANK = _app_config.experiment.auto_confirm_v2_max_bm25_rank
    AUTO_CONFIRM_V2_DELTA_UNCERTAIN = (
        _app_config.experiment.auto_confirm_v2_delta_uncertain
    )
    AUTO_CONFIRM_V2_MIN_CHUNK_LEN = _app_config.experiment.auto_confirm_v2_min_chunk_len

    # ========================================================================
    # Context Expansion
    # ========================================================================
    PARENT_ENABLED = _app_config.experiment.parent_enabled
    PARENT_WINDOW_PAGES = _app_config.experiment.parent_window_pages
    PARENT_MAX_CHARS = _app_config.experiment.parent_max_chars
    PARENT_TOPK = _app_config.experiment.parent_topk
    SEMANTIC_EXPANSION_ENABLED = _app_config.experiment.semantic_expansion_enabled
    SEMANTIC_EXPANSION_TOP_N = _app_config.experiment.semantic_expansion_top_n
    SEMANTIC_EXPANSION_MAX_EXTRA = _app_config.experiment.semantic_expansion_max_extra
    SEMANTIC_EXPANSION_QUERY_MAX_CHARS = (
        _app_config.experiment.semantic_expansion_query_max_chars
    )

    # ========================================================================
    # Retrieval & Search
    # ========================================================================
    RETRIEVAL_MODE = _app_config.experiment.retrieval_mode
    RRF_K = _app_config.experiment.rrf_k
    EMBEDDING_MODEL_NAME = _app_config.experiment.embedding_model_name
    EMBEDDING_DIM = _app_config.experiment.embedding_dim
    EMBEDDING_TOP_N = _app_config.experiment.embedding_top_n
    HYDE_ENABLED = _app_config.experiment.hyde_enabled
    HYDE_AUTO_GENERATE = _app_config.experiment.hyde_auto_generate
    HYDE_PROMPT_VERSION = _app_config.experiment.hyde_prompt_version
    HYDE_MODEL_NAME = _app_config.experiment.hyde_model_name
    HYDE_STRATEGY = _app_config.experiment.hyde_strategy
    HYDE_BM25_VARIANT = _app_config.experiment.hyde_bm25_variant
    HYDE_NEGATIVE_MODE = _app_config.experiment.hyde_negative_mode
    HYDE_MARGIN_EPS = _app_config.experiment.hyde_margin_eps
    HYDE_MAX_KEYWORDS = _app_config.experiment.hyde_max_keywords
    HYDE_MAX_NEGATIVE = _app_config.experiment.hyde_max_negative
    HYDE_EMBED_WEIGHT = _app_config.experiment.hyde_embed_weight
    HYDE_EMBED_WEIGHT_ORIG = _app_config.experiment.hyde_embed_weight_orig

    # ========================================================================
    # PDF Processing
    # ========================================================================
    PDF_PARSER_MODE = _app_config.experiment.pdf_parser_mode

    # ========================================================================
    # Admin & Security
    # ========================================================================
    LOCAL_ADMIN_ONLY = _app_config.runtime.local_admin_only

    # ========================================================================
    # Cache & Artifacts
    # ========================================================================
    DATA_CACHE_DIR = str(_app_config.runtime.data_cache_dir)
    REPORTS_DIR = str(_app_config.runtime.reports_dir)


class DevelopmentConfig(Config):
    """개발 환경 설정 (backward compatibility shim)"""

    DEBUG = True


class ProductionConfig(Config):
    """프로덕션 환경 설정 (backward compatibility shim)"""

    DEBUG = False


class LocalAdminConfig(Config):
    """Local-only admin sandbox configuration (backward compatibility shim)"""

    pass


# 설정 매핑 (backward compatibility shim)
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "local_admin": LocalAdminConfig,
    "default": DevelopmentConfig,
}
