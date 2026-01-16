"""Flask 애플리케이션 설정"""
import os
from pathlib import Path

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).parent.absolute()

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
    """기본 설정 클래스"""
    
    # 보안 키 (환경변수 또는 기본값)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 데이터베이스 설정
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'data' / 'exam.db'}"
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

    # Retrieval mode: bm25|off (future: hybrid/rerank)
    RETRIEVAL_MODE = os.environ.get('RETRIEVAL_MODE', 'bm25')

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
