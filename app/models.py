"""데이터베이스 모델 정의 - 블록제 수업 기출 학습 시스템"""
from datetime import datetime
from app import db


class Block(db.Model):
    """블록(과목) 모델 - 여러 강의를 포함하는 상위 단위"""
    __tablename__ = 'blocks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)  # 예: 심혈관학, 호흡기학
    description = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)  # 표시 순서
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계: 블록 → 강의들
    lectures = db.relationship('Lecture', backref='block', lazy='dynamic', 
                               cascade='all, delete-orphan', order_by='Lecture.order')
    
    def __repr__(self):
        return f'<Block {self.name}>'
    
    @property
    def lecture_count(self):
        return self.lectures.count()
    
    @property
    def question_count(self):
        """이 블록에 분류된 총 문제 수"""
        return sum(lecture.question_count for lecture in self.lectures)


class Lecture(db.Model):
    """강의 모델 - 학습의 최소 단위"""
    __tablename__ = 'lectures'
    
    id = db.Column(db.Integer, primary_key=True)
    block_id = db.Column(db.Integer, db.ForeignKey('blocks.id'), nullable=False)
    title = db.Column(db.String(300), nullable=False)  # 예: 심전도의 원리
    professor = db.Column(db.String(100))  # 교수명
    order = db.Column(db.Integer, default=0)  # 강의 순서 (1강, 2강...)
    description = db.Column(db.Text)
    # 강의 키워드 (AI 분류 정확도 향상용)
    keywords = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    
    # 관계: 강의 → 분류된 문제들 (lecture_id FK 사용)
    questions = db.relationship('Question', 
                               foreign_keys='Question.lecture_id',
                               backref='lecture', 
                               lazy='dynamic')
    
    def __repr__(self):
        return f'<Lecture {self.order}. {self.title}>'
    
    @property
    def question_count(self):
        return self.questions.count()
    
    @property
    def classified_question_count(self):
        return self.questions.filter_by(is_classified=True).count()


class PreviousExam(db.Model):
    """기출 시험지 모델 - 원본 데이터"""
    __tablename__ = 'previous_exams'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)  # 예: 21년 생리학 1차
    exam_date = db.Column(db.Date)  # 시험 날짜
    subject = db.Column(db.String(100))  # 과목명 (생리학, 해부학 등)
    year = db.Column(db.Integer)  # 시험 연도
    term = db.Column(db.String(50))  # 차수 (1차, 2차, 기말 등)
    description = db.Column(db.Text)
    source_file = db.Column(db.String(500))  # 원본 CSV 파일명
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계: 시험 → 문제들
    questions = db.relationship('Question', backref='exam', lazy='dynamic',
                               cascade='all, delete-orphan', order_by='Question.question_number')
    
    def __repr__(self):
        return f'<PreviousExam {self.title}>'
    
    @property
    def question_count(self):
        return self.questions.count()
    
    @property
    def classified_count(self):
        """분류된 문제 수"""
        return self.questions.filter_by(is_classified=True).count()
    
    @property
    def unclassified_count(self):
        """미분류 문제 수"""
        return self.questions.filter_by(is_classified=False).count()


class Question(db.Model):
    """문제 모델 - 기출문제 개별 항목"""
    __tablename__ = 'questions'
    
    # 문제 유형 상수
    TYPE_MULTIPLE_CHOICE = 'multiple_choice'      # 단일 정답 객관식
    TYPE_MULTIPLE_RESPONSE = 'multiple_response'  # 복수 정답 객관식
    TYPE_SHORT_ANSWER = 'short_answer'            # 주관식/서술형
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 원본 시험지와의 관계 (필수)
    exam_id = db.Column(db.Integer, db.ForeignKey('previous_exams.id'), nullable=False)
    question_number = db.Column(db.Integer, nullable=False)  # 문제 번호
    
    # 강의 분류 (선택적 - 분류 전에는 null)
    lecture_id = db.Column(db.Integer, db.ForeignKey('lectures.id'), nullable=True)
    is_classified = db.Column(db.Boolean, default=False)  # 분류 완료 여부
    
    # AI 분류 결과 및 이력
    ai_suggested_lecture_id = db.Column(db.Integer, db.ForeignKey('lectures.id'))
    ai_suggested_lecture_title_snapshot = db.Column(db.String(300))  # 강의 삭제/변경 대비 스냅샷
    ai_confidence = db.Column(db.Float)  # 0.0 ~ 1.0 신뢰도
    ai_reason = db.Column(db.Text)  # AI 분류 근거
    ai_model_name = db.Column(db.String(100))  # 사용된 모델명
    ai_classified_at = db.Column(db.DateTime)  # AI 분류 시점
    # 상태: 'manual'(기본), 'ai_suggested'(AI제안), 'ai_confirmed'(사용자승인), 'ai_rejected'(거절)
    classification_status = db.Column(db.String(20), default='manual')
    
    # 문제 유형
    q_type = db.Column(db.String(50), default=TYPE_MULTIPLE_CHOICE)
    
    # 문제 내용
    content = db.Column(db.Text)  # 문제 텍스트
    image_path = db.Column(db.String(500))  # 문제 이미지 경로
    
    # 정답 및 해설
    answer = db.Column(db.String(500))  # 객관식 정답 (번호, 복수일 경우 콤마 구분)
    correct_answer_text = db.Column(db.Text)  # 주관식 정답 텍스트
    explanation = db.Column(db.Text)  # 해설
    
    # 부가 정보
    difficulty = db.Column(db.Integer, default=3)  # 난이도 (1-5)
    tags = db.Column(db.String(500))  # 태그 (콤마 구분)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계: 문제 → 선택지
    choices = db.relationship('Choice', backref='question', lazy='dynamic',
                             cascade='all, delete-orphan', order_by='Choice.choice_number')
    
    # 관계: 문제 → 사용자 노트
    notes = db.relationship('UserNote', backref='question', lazy='dynamic',
                           cascade='all, delete-orphan')
    
    def __repr__(self):
        status = "분류됨" if self.is_classified else "미분류"
        return f'<Question {self.exam_id}-{self.question_number} ({self.q_type}, {status})>'
    
    def classify(self, lecture_id):
        """문제를 특정 강의로 분류"""
        self.lecture_id = lecture_id
        self.is_classified = True
    
    def unclassify(self):
        """문제 분류 해제"""
        self.lecture_id = None
        self.is_classified = False
    
    @property
    def correct_choice_numbers(self):
        """정답 선택지 번호 목록 반환"""
        return [c.choice_number for c in self.choices if c.is_correct]
    
    @property
    def is_short_answer(self):
        """주관식 문제 여부"""
        return self.q_type == self.TYPE_SHORT_ANSWER
    
    @property
    def is_multiple_response(self):
        """복수 정답 문제 여부"""
        return self.q_type == self.TYPE_MULTIPLE_RESPONSE
    
    def check_answer(self, user_answer):
        """
        사용자 답안 채점
        
        Args:
            user_answer: 객관식이면 선택한 번호 리스트 [1, 2], 주관식이면 텍스트
        
        Returns:
            (is_correct: bool, correct_answer: 정답 정보)
        """
        if self.is_short_answer:
            # 주관식: 텍스트 비교 (공백 제거, 대소문자 무시)
            if not self.correct_answer_text:
                return None, None  # 자동 채점 불가
            
            user_text = str(user_answer).strip().lower().replace(' ', '')
            correct_text = self.correct_answer_text.strip().lower().replace(' ', '')
            
            return user_text == correct_text, self.correct_answer_text
        else:
            # 객관식: 선택지 번호 비교
            correct_numbers = set(self.correct_choice_numbers)
            
            # user_answer를 set으로 변환
            if isinstance(user_answer, (list, tuple)):
                user_numbers = set(user_answer)
            else:
                user_numbers = {int(user_answer)} if user_answer else set()
            
            # 복수 정답: 모든 정답을 선택해야 정답
            is_correct = user_numbers == correct_numbers
            
            return is_correct, list(correct_numbers)
    
    def determine_type(self):
        """선택지 기반으로 문제 유형 자동 결정"""
        choice_count = self.choices.count()
        
        if choice_count == 0:
            self.q_type = self.TYPE_SHORT_ANSWER
        else:
            correct_count = len(self.correct_choice_numbers)
            if correct_count > 1:
                self.q_type = self.TYPE_MULTIPLE_RESPONSE
            else:
                self.q_type = self.TYPE_MULTIPLE_CHOICE


class Choice(db.Model):

    """선택지 모델 - 문제의 보기"""
    __tablename__ = 'choices'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    choice_number = db.Column(db.Integer, nullable=False)  # 선택지 번호 (1, 2, 3, 4, 5)
    content = db.Column(db.Text, nullable=False)  # 선택지 내용
    image_path = db.Column(db.String(500))  # 선택지 이미지 (선택적)
    is_correct = db.Column(db.Boolean, default=False)  # 정답 여부
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        mark = "✓" if self.is_correct else ""
        return f'<Choice {self.choice_number}{mark}>'


class UserNote(db.Model):
    """사용자 메모 모델 - 문제별 개인 노트"""
    __tablename__ = 'user_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    note_text = db.Column(db.Text, nullable=False)  # 메모 내용
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserNote Q{self.question_id}>'


class PracticeSession(db.Model):
    """Practice session model for repeated exams and replays."""
    __tablename__ = 'practice_sessions'

    id = db.Column(db.Integer, primary_key=True)
    lecture_id = db.Column(db.Integer, db.ForeignKey('lectures.id'), nullable=True)
    mode = db.Column(db.String(50), default='practice')
    lecture_ids_json = db.Column(db.Text)
    seed = db.Column(db.Integer)
    question_order = db.Column(db.Text)
    total_time_spent = db.Column(db.Integer)
    submission_count = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)

    lecture = db.relationship('Lecture', backref=db.backref('practice_sessions', lazy='dynamic'))
    answers = db.relationship(
        'PracticeAnswer',
        backref='session',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f'<PracticeSession {self.id}>'


class PracticeAnswer(db.Model):
    """Per-question answer saved for a practice session."""
    __tablename__ = 'practice_answers'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('practice_sessions.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    answer_payload = db.Column(db.Text)
    is_correct = db.Column(db.Boolean, nullable=True)
    time_spent = db.Column(db.Integer)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)

    question = db.relationship('Question', backref=db.backref('practice_answers', lazy='dynamic'))

    def __repr__(self):
        return f'<PracticeAnswer S{self.session_id} Q{self.question_id}>'


class ClassificationJob(db.Model):
    """AI 분류 작업 모델 - 비동기 배치 처리 추적"""
    __tablename__ = 'classification_jobs'
    
    # 상태 상수
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default=STATUS_PENDING)
    total_count = db.Column(db.Integer, default=0)  # 총 문제 수
    processed_count = db.Column(db.Integer, default=0)  # 처리된 문제 수
    success_count = db.Column(db.Integer, default=0)  # 성공한 분류 수
    failed_count = db.Column(db.Integer, default=0)  # 실패한 분류 수
    error_message = db.Column(db.Text)  # 전체 작업 실패 시 에러 메시지
    result_json = db.Column(db.Text)  # 분류 결과 JSON (미리보기용)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)  # 완료 시점
    
    def __repr__(self):
        return f'<ClassificationJob {self.id} ({self.status}: {self.processed_count}/{self.total_count})>'
    
    @property
    def progress_percent(self):
        """진행률 (0-100)"""
        if self.total_count == 0:
            return 0
        return int((self.processed_count / self.total_count) * 100)
    
    @property
    def is_complete(self):
        return self.status in (self.STATUS_COMPLETED, self.STATUS_FAILED)
