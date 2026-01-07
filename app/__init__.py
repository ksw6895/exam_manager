"""Flask 애플리케이션 팩토리"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from config import config

# SQLAlchemy 인스턴스 (다른 모듈에서 import 가능)
db = SQLAlchemy()


def create_app(config_name='default'):
    """
    Flask 애플리케이션 팩토리
    
    Args:
        config_name: 설정 이름 ('development', 'production', 'default')
    
    Returns:
        Flask 앱 인스턴스
    """
    app = Flask(__name__)
    
    # 설정 로드
    app.config.from_object(config[config_name])
    
    # SQLAlchemy 초기화
    db.init_app(app)
    
    # 업로드 디렉토리 생성
    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder and not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # data 디렉토리 생성 (SQLite DB용)
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    # Blueprint 등록
    from app.routes.main import main_bp
    from app.routes.exam import exam_bp
    from app.routes.manage import manage_bp
    from app.routes.history import history_bp
    from app.routes.ai import ai_bp
    from app.routes.practice import practice_bp
    from app.routes.api_practice import api_practice_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(exam_bp, url_prefix='/exam')
    app.register_blueprint(manage_bp, url_prefix='/manage')
    app.register_blueprint(history_bp, url_prefix='/history')
    app.register_blueprint(ai_bp)
    app.register_blueprint(practice_bp, url_prefix='/practice')
    app.register_blueprint(api_practice_bp, url_prefix='/api/practice')
    
    # 앱 컨텍스트에서 DB 테이블 생성
    with app.app_context():
        db.create_all()
    
    return app
