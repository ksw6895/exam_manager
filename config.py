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


class Config:
    """기본 설정 클래스"""
    
    # 보안 키 (환경변수 또는 기본값)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 데이터베이스 설정
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'data' / 'exam.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 업로드 설정
    UPLOAD_FOLDER = BASE_DIR / 'app' / 'static' / 'uploads'
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB 최대 업로드 크기
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # AI 분류 설정 (Google Gemini)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL_NAME = os.environ.get('GEMINI_MODEL_NAME', 'gemini-2.0-flash-lite')
    AI_CONFIDENCE_THRESHOLD = 0.7
    AI_AUTO_APPLY_MARGIN = 0.2

    # DB auto-create (dev convenience; disable for production safety)
    AUTO_CREATE_DB = _env_flag('AUTO_CREATE_DB', default=False)


class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    AUTO_CREATE_DB = _env_flag('AUTO_CREATE_DB', default=True)


class ProductionConfig(Config):
    """프로덕션 환경 설정"""
    DEBUG = False


# 설정 매핑
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
