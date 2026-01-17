<<<<<<< HEAD
"""Flask 애플리케이션 설정"""
import os
from pathlib import Path

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).parent.absolute()

=======
"""Flask 애플리케이션 설정"""
import os
from pathlib import Path

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).parent.absolute()


def _sqlite_uri(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _resolve_sqlite_uri(value: str | None, fallback: Path) -> str:
    if value:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = BASE_DIR / candidate
        return _sqlite_uri(candidate)
    return _sqlite_uri(fallback)

>>>>>>> 56f8c31 (WIP: Ai classifier update)
def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in ('1', 'true', 'yes', 'on')

def _env_int(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Config:
<<<<<<< HEAD
    """기본 설정 클래스"""
    
    # 보안 키 (환경변수 또는 기본값)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 데이터베이스 설정
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'data' / 'exam.db'}"
=======
    """기본 설정 클래스"""
    
    # 보안 키 (환경변수 또는 기본값)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 데이터베이스 설정
    SQLALCHEMY_DATABASE_URI = _resolve_sqlite_uri(None, BASE_DIR / 'data' / 'exam.db')
>>>>>>> 56f8c31 (WIP: Ai classifier update)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Optional hot-backup hook before write operations.
    AUTO_BACKUP_BEFORE_WRITE = _env_flag('AUTO_BACKUP_BEFORE_WRITE', default=False)
    AUTO_BACKUP_KEEP = _env_int('AUTO_BACKUP_KEEP', default=30)
    AUTO_BACKUP_DIR = os.environ.get('AUTO_BACKUP_DIR', str(BASE_DIR / 'backups'))
    ENFORCE_BACKUP_BEFORE_WRITE = _env_flag('ENFORCE_BACKUP_BEFORE_WRITE', default=False)
    
    # 업로드 설정
    UPLOAD_FOLDER = BASE_DIR / 'app' / 'static' / 'uploads'
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB 최대 업로드 크기
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # AI 분류 설정 (Google Gemini)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL_NAME = os.environ.get('GEMINI_MODEL_NAME', 'gemini-2.0-flash-lite')
    AI_CONFIDENCE_THRESHOLD = 0.7
    AI_AUTO_APPLY_MARGIN = 0.2
    AI_AUTO_APPLY = _env_flag('AI_AUTO_APPLY', default=False)

    AUTO_CONFIRM_V2_ENABLED = _env_flag('AUTO_CONFIRM_V2_ENABLED', default=True)
    AUTO_CONFIRM_V2_DELTA = float(os.environ.get('AUTO_CONFIRM_V2_DELTA', '0.05'))
    AUTO_CONFIRM_V2_MAX_BM25_RANK = _env_int('AUTO_CONFIRM_V2_MAX_BM25_RANK', default=5)
    AUTO_CONFIRM_V2_DELTA_UNCERTAIN = float(os.environ.get('AUTO_CONFIRM_V2_DELTA_UNCERTAIN', '0.03'))
    AUTO_CONFIRM_V2_MIN_CHUNK_LEN = _env_int('AUTO_CONFIRM_V2_MIN_CHUNK_LEN', default=200)

    CLASSIFIER_CACHE_PATH = os.environ.get(
        'CLASSIFIER_CACHE_PATH', str(BASE_DIR / 'data' / 'classifier_cache.json')
    )

    # Parent Context Expansion
    PARENT_ENABLED = _env_flag('PARENT_ENABLED', default=False)
    PARENT_WINDOW_PAGES = _env_int('PARENT_WINDOW_PAGES', default=1)
    PARENT_MAX_CHARS = _env_int('PARENT_MAX_CHARS', default=3500)
    PARENT_TOPK = _env_int('PARENT_TOPK', default=5)
    SEMANTIC_EXPANSION_ENABLED = _env_flag('SEMANTIC_EXPANSION_ENABLED', default=True)
    SEMANTIC_EXPANSION_TOP_N = _env_int('SEMANTIC_EXPANSION_TOP_N', default=6)
    SEMANTIC_EXPANSION_MAX_EXTRA = _env_int('SEMANTIC_EXPANSION_MAX_EXTRA', default=2)
    SEMANTIC_EXPANSION_QUERY_MAX_CHARS = _env_int('SEMANTIC_EXPANSION_QUERY_MAX_CHARS', default=1200)

    # Retrieval mode: bm25|off (future: hybrid/rerank)
<<<<<<< HEAD
    RETRIEVAL_MODE = os.environ.get('RETRIEVAL_MODE', 'bm25')
=======
    RETRIEVAL_MODE = os.environ.get('RETRIEVAL_MODE', 'hybrid_rrf')
    GEMINI_MAX_OUTPUT_TOKENS = _env_int('GEMINI_MAX_OUTPUT_TOKENS', default=2048)  # Increased for Gemini 3.0
    RRF_K = _env_int('RRF_K', default=60)
    EMBEDDING_MODEL_NAME = os.environ.get(
        'EMBEDDING_MODEL_NAME', 'intfloat/multilingual-e5-base'
    )
    EMBEDDING_DIM = _env_int('EMBEDDING_DIM', default=768)
    EMBEDDING_TOP_N = _env_int('EMBEDDING_TOP_N', default=300)
    HYDE_ENABLED = _env_flag('HYDE_ENABLED', default=False)
    HYDE_AUTO_GENERATE = _env_flag('HYDE_AUTO_GENERATE', default=False)
    HYDE_PROMPT_VERSION = os.environ.get('HYDE_PROMPT_VERSION', 'hyde_v1')
    HYDE_MODEL_NAME = os.environ.get('HYDE_MODEL_NAME')
    HYDE_STRATEGY = os.environ.get('HYDE_STRATEGY', 'blend')  # blend | best_of_two
    HYDE_BM25_VARIANT = os.environ.get('HYDE_BM25_VARIANT', 'mixed_light')
    HYDE_NEGATIVE_MODE = os.environ.get('HYDE_NEGATIVE_MODE', 'stopwords')
    HYDE_MARGIN_EPS = float(os.environ.get('HYDE_MARGIN_EPS', '0.0'))
    HYDE_MAX_KEYWORDS = _env_int('HYDE_MAX_KEYWORDS', default=7)
    HYDE_MAX_NEGATIVE = _env_int('HYDE_MAX_NEGATIVE', default=6)
    HYDE_EMBED_WEIGHT = float(os.environ.get('HYDE_EMBED_WEIGHT', '0.7'))
    HYDE_EMBED_WEIGHT_ORIG = float(os.environ.get('HYDE_EMBED_WEIGHT_ORIG', '0.3'))
>>>>>>> 56f8c31 (WIP: Ai classifier update)

    # Read-only guard for write paths.
    DB_READ_ONLY = _env_flag('DB_READ_ONLY', default=False)

    # Pending migration checks at startup.
    CHECK_PENDING_MIGRATIONS = _env_flag('CHECK_PENDING_MIGRATIONS', default=True)
    FAIL_ON_PENDING_MIGRATIONS = _env_flag('FAIL_ON_PENDING_MIGRATIONS', default=False)

    # DB auto-create (dev convenience; disable for production safety)
    AUTO_CREATE_DB = _env_flag('AUTO_CREATE_DB', default=False)

    # Lock admin routes to localhost only when enabled.
    LOCAL_ADMIN_ONLY = _env_flag('LOCAL_ADMIN_ONLY', default=False)

    # PDF parser selection: "legacy" or "experimental".
    PDF_PARSER_MODE = os.environ.get('PDF_PARSER_MODE', 'legacy')


class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    AUTO_CREATE_DB = _env_flag('AUTO_CREATE_DB', default=True)


class ProductionConfig(Config):
    """프로덕션 환경 설정"""
    DEBUG = False


class LocalAdminConfig(DevelopmentConfig):
    """Local-only admin sandbox configuration."""
    _local_admin_db = os.environ.get('LOCAL_ADMIN_DB')
    SQLALCHEMY_DATABASE_URI = (
        f"sqlite:///{_local_admin_db}"
        if _local_admin_db
        else f"sqlite:///{BASE_DIR / 'data' / 'admin_local.db'}"
    )
    UPLOAD_FOLDER = BASE_DIR / 'app' / 'static' / 'uploads_admin'
    LOCAL_ADMIN_ONLY = True
    PDF_PARSER_MODE = 'experimental'


# 설정 매핑
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'local_admin': LocalAdminConfig,
    'default': DevelopmentConfig
}
