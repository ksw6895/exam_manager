"""데이터베이스 스키마 마이그레이션 - AI 분류 필드 추가"""
from app import create_app, db
from sqlalchemy import text

def migrate():
    app = create_app()
    with app.app_context():
        # Add new columns to questions table
        columns_to_add = [
            'ALTER TABLE questions ADD COLUMN ai_suggested_lecture_id INTEGER REFERENCES lectures(id)',
            'ALTER TABLE questions ADD COLUMN ai_suggested_lecture_title_snapshot VARCHAR(300)',
            'ALTER TABLE questions ADD COLUMN ai_confidence FLOAT',
            'ALTER TABLE questions ADD COLUMN ai_reason TEXT',
            'ALTER TABLE questions ADD COLUMN ai_model_name VARCHAR(100)',
            'ALTER TABLE questions ADD COLUMN ai_classified_at DATETIME',
            'ALTER TABLE questions ADD COLUMN classification_status VARCHAR(20) DEFAULT "manual"',
        ]
        
        for col_sql in columns_to_add:
            try:
                db.session.execute(text(col_sql))
                col_name = col_sql.split('ADD COLUMN ')[1].split()[0]
                print(f'Added: {col_name}')
            except Exception as e:
                col_name = col_sql.split('ADD COLUMN ')[1].split()[0]
                if 'duplicate column' in str(e).lower():
                    print(f'Already exists: {col_name}')
                else:
                    print(f'Skipped {col_name}: {e}')
        
        # Create classification_jobs table if not exists
        db.create_all()
        print('Created classification_jobs table if not exists')
        
        db.session.commit()
        print('Schema migration complete!')

if __name__ == '__main__':
    migrate()
