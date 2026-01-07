"""AI 분류 서비스 모듈

Google Gemini API를 활용한 문제-강의 자동 분류 서비스.
2단계 분류 프로세스: 1) 키워드 기반 후보 추출 2) LLM 정밀 분류
"""
import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import threading

from flask import current_app
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from app import db
from app.models import Question, Lecture, Block, ClassificationJob


# ============================================================
# 1단계: 후보 강의 추출 (Keyword/TF-IDF 기반)
# ============================================================

class LectureRetriever:
    """강의 후보 검색기 - 키워드 매칭 기반 Top-K 추출"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """싱글톤 패턴"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._lectures_cache = []
        self._initialized = True
    
    def refresh_cache(self):
        """강의 캐시 갱신 (앱 컨텍스트 내에서 호출)"""
        lectures = Lecture.query.join(Block).order_by(Block.order, Lecture.order).all()
        self._lectures_cache = []
        for lecture in lectures:
            self._lectures_cache.append({
                'id': lecture.id,
                'title': lecture.title,
                'block_name': lecture.block.name,
                'full_path': f"{lecture.block.name} > {lecture.title}",
                'keywords_text': lecture.keywords or '',  # 사용자가 입력한 키워드 (LLM 제공용)
                'keywords': self._extract_keywords(f"{lecture.block.name} {lecture.title} {lecture.keywords or ''}")
            })
    
    def _extract_keywords(self, text: str) -> set:
        """텍스트에서 키워드 추출 (간단한 토큰화)"""
        # 한글, 영문, 숫자만 추출
        tokens = re.findall(r'[가-힣a-zA-Z0-9]+', text.lower())
        # 불용어 제거 (간단 버전)
        stopwords = {'및', '의', '에', '를', '을', '이', '가', 'the', 'a', 'an', 'and', 'or'}
        return set(t for t in tokens if t not in stopwords and len(t) > 1)
    
    def find_candidates(self, question_text: str, top_k: int = 15) -> List[Dict]:
        """
        문제 텍스트와 가장 관련 있는 강의 후보 Top-K 추출
        
        Args:
            question_text: 문제 내용 텍스트
            top_k: 반환할 후보 수
        
        Returns:
            [{'id': 1, 'title': '...', 'block_name': '...', 'score': 0.5}, ...]
        """
        if not self._lectures_cache:
            self.refresh_cache()
        
        if not self._lectures_cache:
            return []
        
        question_keywords = self._extract_keywords(question_text)
        
        scored = []
        for lecture in self._lectures_cache:
            # Jaccard 유사도 계산
            intersection = len(question_keywords & lecture['keywords'])
            union = len(question_keywords | lecture['keywords'])
            score = intersection / union if union > 0 else 0
            
            if score > 0 or len(scored) < top_k:
                scored.append({
                    'id': lecture['id'],
                    'title': lecture['title'],
                    'block_name': lecture['block_name'],
                    'full_path': lecture['full_path'],
                    'score': score
                })
        
        # 점수 내림차순 정렬
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored[:top_k]


# ============================================================
# 2단계: LLM 기반 정밀 분류
# ============================================================

class GeminiClassifier:
    """Google Gemini API를 사용한 문제 분류기"""
    
    def __init__(self):
        if not GENAI_AVAILABLE:
            raise RuntimeError("google-genai 패키지가 설치되지 않았습니다. pip install google-genai 실행하세요.")
        
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = current_app.config.get('GEMINI_MODEL_NAME', 'gemini-1.5-flash-002')
        self.confidence_threshold = current_app.config.get('AI_CONFIDENCE_THRESHOLD', 0.7)
        self.auto_apply_margin = current_app.config.get('AI_AUTO_APPLY_MARGIN', 0.2)
    
    def _build_classification_prompt(self, question_content: str, choices: List[str], candidates: List[Dict]) -> str:
        """분류 프롬프트 생성"""
        candidates_text = "\n".join([
            f"- ID: {c['id']}, 강의명: {c['full_path']}" + (f", 키워드: {c['keywords_text']}" if c.get('keywords_text') else "")
            for c in candidates
        ])
        
        choices_text = "\n".join([f"  {i+1}. {c}" for i, c in enumerate(choices)]) if choices else "(선택지 없음)"
        
        prompt = f"""당신은 의학 교육 전문가입니다. 아래 시험 문제를 분석하여 가장 적합한 강의를 선택해주세요.

## 문제 내용
{question_content}

## 선택지
{choices_text}

## 후보 강의 목록
{candidates_text}

## 중요 지시사항
1. 문제의 핵심 주제와 개념을 파악하세요.
2. **반드시 정확하게 매칭되는 강의만 선택하세요.**
3. **강의 목록에 적합한 강의가 없다면, 억지로 분류하지 마세요!**
   - 주제가 명확히 일치하지 않으면 no_match = true로 설정
   - 애매하거나 확신이 없으면 no_match = true로 설정
   - 주제가 명확히 일치하지 않으면 no_match = true로 설정
   - 애매하거나 확신이 없으면 no_match = true로 설정
   - 이 문제는 일부 강의만 등록된 상태이므로, 미분류가 많아도 괜찮습니다.
4. **강의에 '키워드'가 명시되어 있다면, 이를 가장 중요한 판단 기준으로 삼으세요.**
   - 키워드에 포함된 내용이라면 제목이 조금 달라도 해당 강의일 확률이 높습니다.
5. 확신도(confidence)는 솔직하게 평가하세요:
   - 0.9 이상: 확실히 이 강의 내용
   - 0.7-0.9: 관련성 높음
   - 0.5-0.7: 관련 있을 수 있음
   - 0.5 미만: 확신 없음 (이 경우 no_match = true 권장)
5. 반드시 아래 JSON 형식으로만 응답하세요.

## 응답 형식 (JSON)
{{
    "lecture_id": (선택한 강의 ID, 정수. 적합한 강의가 없으면 null),
    "confidence": (확신도 0.0~1.0),
    "reason": "(한국어로 1-2문장 분류 근거 또는 분류하지 않은 이유)",
    "no_match": (적합한 강의가 없거나 확신이 없으면 true, 확실히 매칭되면 false)
}}
"""
        return prompt
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((Exception,))
    )
    def classify_single(self, question: Question, candidates: List[Dict]) -> Dict:
        """
        단일 문제 분류
        
        Returns:
            {
                'lecture_id': int or None,
                'confidence': float,
                'reason': str,
                'no_match': bool,
                'model_name': str
            }
        """
        # 선택지 텍스트 추출
        choices = [c.content for c in question.choices.order_by('choice_number').all()]
        
        # 문제 내용 (이미지 문제의 경우 빈 문자열일 수 있음)
        content = question.content or "(이미지 문제)"
        
        prompt = self._build_classification_prompt(content, choices, candidates)
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    top_p=0.8,
                    max_output_tokens=500,
                )
            )
            
            # JSON 파싱
            result_text = response.text.strip()
            # JSON 블록 추출 (markdown 코드 블록 처리)
            json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(result_text)
            
            # 유효성 검증
            lecture_id = result.get('lecture_id')
            if lecture_id is not None:
                # 후보 목록에 있는지 확인
                valid_ids = {c['id'] for c in candidates}
                if lecture_id not in valid_ids:
                    lecture_id = None
                    result['no_match'] = True
            
            return {
                'lecture_id': lecture_id,
                'confidence': float(result.get('confidence', 0.0)),
                'reason': result.get('reason', ''),
                'no_match': result.get('no_match', False),
                'model_name': self.model_name
            }
            
        except json.JSONDecodeError as e:
            return {
                'lecture_id': None,
                'confidence': 0.0,
                'reason': f'JSON 파싱 오류: {str(e)}',
                'no_match': True,
                'model_name': self.model_name
            }
        except Exception as e:
            raise  # tenacity가 재시도 처리


# ============================================================
# 비동기 배치 처리
# ============================================================

class AsyncBatchProcessor:
    """비동기 배치 분류 처리기"""
    
    _executor = ThreadPoolExecutor(max_workers=2)
    
    @classmethod
    def start_classification_job(cls, question_ids: List[int]) -> int:
        """
        분류 작업 시작 (비동기)
        
        Returns:
            job_id: 생성된 작업 ID
        """
        # Job 생성
        job = ClassificationJob(
            status=ClassificationJob.STATUS_PENDING,
            total_count=len(question_ids)
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id
        
        # 백그라운드 처리 시작
        cls._executor.submit(cls._process_job, job_id, question_ids)
        
        return job_id
    
    @classmethod
    def _process_job(cls, job_id: int, question_ids: List[int]):
        """백그라운드에서 분류 작업 수행"""
        from app import create_app
        app = create_app()
        
        with app.app_context():
            job = ClassificationJob.query.get(job_id)
            if not job:
                return
            
            job.status = ClassificationJob.STATUS_PROCESSING
            db.session.commit()
            
            retriever = LectureRetriever()
            retriever.refresh_cache()
            
            results = []
            
            try:
                classifier = GeminiClassifier()
                
                for qid in question_ids:
                    question = Question.query.get(qid)
                    if not question:
                        job.failed_count += 1
                        job.processed_count += 1
                        continue
                    
                    try:
                        # 1단계: 후보 추출
                        candidates = retriever.find_candidates(
                            question.content or '', 
                            top_k=15
                        )
                        
                        if not candidates:
                            # 후보가 없으면 전체 강의 중 앞 15개
                            candidates = retriever._lectures_cache[:15]
                        
                        # 2단계: LLM 분류
                        result = classifier.classify_single(question, candidates)
                        
                        # 결과 저장 (DB에는 아직 반영하지 않음 - preview용)
                        result['question_id'] = qid
                        result['question_number'] = question.question_number
                        result['exam_title'] = question.exam.title if question.exam else ''
                        
                        if result['lecture_id']:
                            lecture = Lecture.query.get(result['lecture_id'])
                            if lecture:
                                result['lecture_title'] = lecture.title
                                result['block_name'] = lecture.block.name
                            else:
                                result['lecture_title'] = None
                                result['block_name'] = None
                        
                        results.append(result)
                        job.success_count += 1
                        
                    except Exception as e:
                        results.append({
                            'question_id': qid,
                            'question_number': question.question_number,
                            'exam_title': question.exam.title if question.exam else '',
                            'lecture_id': None,
                            'confidence': 0.0,
                            'reason': f'오류: {str(e)}',
                            'no_match': True,
                            'error': True
                        })
                        job.failed_count += 1
                    
                    job.processed_count += 1
                    db.session.commit()
                
                # 완료
                job.status = ClassificationJob.STATUS_COMPLETED
                job.result_json = json.dumps(results, ensure_ascii=False)
                job.completed_at = datetime.utcnow()
                
            except Exception as e:
                job.status = ClassificationJob.STATUS_FAILED
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
            
            db.session.commit()


# ============================================================
# 유틸리티 함수
# ============================================================

def apply_classification_results(question_ids: List[int], job_id: int) -> int:
    """
    분류 결과를 실제 DB에 적용
    
    Args:
        question_ids: 적용할 문제 ID 목록
        job_id: 분류 작업 ID
    
    Returns:
        적용된 문제 수
    """
    job = ClassificationJob.query.get(job_id)
    if not job or not job.result_json:
        return 0
    
    results = json.loads(job.result_json)
    results_map = {r['question_id']: r for r in results}
    
    applied_count = 0
    for qid in question_ids:
        result = results_map.get(qid)
        if not result or not result.get('lecture_id'):
            continue
        
        question = Question.query.get(qid)
        if not question:
            continue
        
        lecture = Lecture.query.get(result['lecture_id'])
        if not lecture:
            continue
        
        # 분류 적용
        question.lecture_id = lecture.id
        question.is_classified = True
        question.ai_suggested_lecture_id = lecture.id
        question.ai_suggested_lecture_title_snapshot = f"{lecture.block.name} > {lecture.title}"
        question.ai_confidence = result.get('confidence', 0.0)
        question.ai_reason = result.get('reason', '')
        question.ai_model_name = result.get('model_name', '')
        question.ai_classified_at = datetime.utcnow()
        question.classification_status = 'ai_confirmed'
        
        applied_count += 1
    
    db.session.commit()
    return applied_count
