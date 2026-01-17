"""AI 분류 서비스 모듈

Google Gemini API를 활용한 문제-강의 자동 분류 서비스.
2단계 분류 프로세스: 1) 텍스트 기반 후보 추출 2) LLM 정밀 분류
"""
import json
import os
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
from app.models import (
    Question,
    Lecture,
    Block,
    ClassificationJob,
    LectureChunk,
    QuestionChunkMatch,
)
from app.services import retrieval
from app.services.folder_scope import parse_bool, resolve_lecture_ids

# ============================================================
# Job payload helpers (idempotency + compatibility)
# ============================================================

def build_job_payload(request_meta: Optional[Dict], results: Optional[List[Dict]] = None) -> Dict:
    return {
        'request': request_meta or {},
        'results': results or [],
    }

def parse_job_payload(result_json: Optional[str]) -> Tuple[Dict, List[Dict]]:
    if not result_json:
        return {}, []
    try:
        payload = json.loads(result_json)
    except (TypeError, ValueError):
        return {}, []
    if isinstance(payload, list):
        return {}, payload
    if isinstance(payload, dict):
        results = payload.get('results')
        if isinstance(results, list):
            return payload.get('request', {}) or {}, results
        return payload.get('request', {}) or {}, []
    return {}, []


def _extract_first_json_object(text: str) -> Optional[str]:
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _sanitize_json_text(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'```(?:json)?', '', text, flags=re.IGNORECASE)
    text = text.replace('```', '')
    text = re.sub(r'[\x00-\x1F\x7F]', ' ', text)
    text = (
        text.replace('\u201c', '"')
            .replace('\u201d', '"')
            .replace('\u2018', "'")
            .replace('\u2019', "'")
    )
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text.strip()


def _fallback_parse_result(text: str) -> Dict:
    cleaned = _sanitize_json_text(text)
    data: Dict = {}

    m = re.search(r'lecture_id\s*[:=]\s*(null|\d+)', cleaned, re.IGNORECASE)
    if m:
        raw = m.group(1).lower()
        data['lecture_id'] = None if raw == 'null' else int(raw)

    m = re.search(r'no_match\s*[:=]\s*(true|false)', cleaned, re.IGNORECASE)
    if m:
        data['no_match'] = m.group(1).lower() == 'true'

    m = re.search(r'confidence\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)', cleaned, re.IGNORECASE)
    if m:
        try:
            data['confidence'] = float(m.group(1))
        except ValueError:
            pass

    for key in ('reason', 'study_hint'):
        m = re.search(rf'"?{key}"?\s*[:=]\s*"(.*?)"', cleaned, re.IGNORECASE | re.DOTALL)
        if not m:
            m = re.search(rf'"?{key}"?\s*[:=]\s*([^\n\r]+)', cleaned, re.IGNORECASE)
        if m:
            data[key] = m.group(1).strip().strip('"').strip()

    data.setdefault('lecture_id', None)
    if 'no_match' not in data:
        data['no_match'] = data['lecture_id'] is None
    data.setdefault('confidence', 0.0)
    data.setdefault('reason', '')
    data.setdefault('study_hint', '')
    data.setdefault('evidence', [])
    return data


# ============================================================
# 1단계: 후보 강의 추출 (검색 기반)
# ============================================================

class LectureRetriever:
    """강의 후보 검색기 - 검색 기반 Top-K 추출"""
    
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
                'full_path': f"{lecture.block.name} > {lecture.title}"
            })
    
    def find_candidates(
        self,
        question_text: str,
        top_k: int = 8,
        lecture_ids: Optional[List[int]] = None,
    ) -> List[Dict]:
        """FTS5 BM25 기반 후보 강의 검색"""
        mode = current_app.config.get('RETRIEVAL_MODE', 'bm25')
        if mode != 'bm25':
            return []
        chunks = retrieval.search_chunks_bm25(
            question_text,
            top_n=80,
            lecture_ids=lecture_ids,
        )
        return retrieval.aggregate_candidates(chunks, top_k_lectures=top_k, evidence_per_lecture=3)


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
        """Build the classification prompt."""
        candidate_lines = []
        for c in candidates:
            evidence_lines = []
            for e in c.get('evidence', []) or []:
                page_start = e.get('page_start')
                page_end = e.get('page_end')
                if page_start is None or page_end is None:
                    page_label = "p.?"
                else:
                    page_label = f"p.{page_start}" if page_start == page_end else f"p.{page_start}-{page_end}"
                snippet = e.get('snippet') or ''
                evidence_lines.append(
                    f'  - {page_label}: "{snippet}" (chunk_id: {e.get("chunk_id")})'
                )
            if not evidence_lines:
                evidence_lines.append("  - evidence: none")
            candidate_lines.append(
                f"- ID: {c['id']}, Lecture: {c['full_path']}\n" + "\n".join(evidence_lines)
            )
        candidates_text = "\n".join(candidate_lines) if candidate_lines else "(no candidates)"

        choices_text = "\n".join([f"  {i + 1}. {c}" for i, c in enumerate(choices)]) if choices else "(no choices)"

        prompt = f"""You are a medical education expert. Analyze the exam question and choose the most relevant lecture.

## Question
{question_content}

## Choices
{choices_text}

## Candidate Lectures (with evidence)
{candidates_text}

## Instructions
1. Identify the key concept of the question.
2. Select only a lecture that clearly matches.
3. If none match, set no_match = true and lecture_id = null.
4. evidence.quote must be copied from the provided snippets only.
5. study_hint must point to the exact pages to review.
6. Output JSON only, following the schema below.

## Response JSON
{{
    "lecture_id": (selected lecture ID or null),
    "confidence": (0.0~1.0),
    "reason": "short reason in Korean",
    "study_hint": "e.g., Review p.12-13 for the definition and compare with related concepts.",
    "no_match": (true/false),
    "evidence": [
        {{
            "lecture_id": 123,
            "page_start": 12,
            "page_end": 13,
            "quote": "copied snippet text",
            "chunk_id": 991
        }}
    ]
}}
"""
        return prompt

    def _normalize_evidence(self, lecture_id: int, candidates: List[Dict], evidence_raw: List[Dict]) -> List[Dict]:
        selected = next((c for c in candidates if c.get('id') == lecture_id), None)
        if not selected:
            return []
        candidate_evidence = {
            e.get('chunk_id'): e for e in (selected.get('evidence', []) or []) if e.get('chunk_id') is not None
        }
        cleaned = []
        for item in evidence_raw or []:
            if not isinstance(item, dict):
                continue
            item_lecture_id = item.get('lecture_id')
            if item_lecture_id is not None:
                try:
                    if int(item_lecture_id) != lecture_id:
                        continue
                except (TypeError, ValueError):
                    continue
            chunk_id = item.get('chunk_id')
            try:
                chunk_id = int(chunk_id)
            except (TypeError, ValueError):
                continue
            candidate_item = candidate_evidence.get(chunk_id)
            if not candidate_item:
                continue
            snippet = candidate_item.get('snippet') or ''
            quote = str(item.get('quote') or '').strip()
            if quote and quote in snippet:
                cleaned.append(
                    {
                        'lecture_id': lecture_id,
                        'page_start': candidate_item.get('page_start'),
                        'page_end': candidate_item.get('page_end'),
                        'quote': quote,
                        'chunk_id': chunk_id,
                    }
                )
            elif snippet:
                cleaned.append(
                    {
                        'lecture_id': lecture_id,
                        'page_start': candidate_item.get('page_start'),
                        'page_end': candidate_item.get('page_end'),
                        'quote': snippet,
                        'chunk_id': chunk_id,
                    }
                )

        if cleaned:
            return cleaned

        fallback = []
        for candidate_item in (selected.get('evidence', []) or [])[:2]:
            snippet = candidate_item.get('snippet') or ''
            if not snippet:
                continue
            fallback.append(
                {
                    'lecture_id': lecture_id,
                    'page_start': candidate_item.get('page_start'),
                    'page_end': candidate_item.get('page_end'),
                    'quote': snippet,
                    'chunk_id': candidate_item.get('chunk_id'),
                }
            )
        return fallback
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((Exception,))
    )
    def classify_single(self, question: Question, candidates: List[Dict]) -> Dict:
        """
        ?? ?? ??

        Returns:
            {
                'lecture_id': int or None,
                'confidence': float,
                'reason': str,
                'study_hint': str,
                'evidence': list,
                'no_match': bool,
                'model_name': str
            }
        """
        choices = [c.content for c in question.choices.order_by('choice_number').all()]
        content = question.content or "(image-only question)"

        if not candidates:
            return {
                'lecture_id': None,
                'confidence': 0.0,
                'reason': 'No lecture candidates available.',
                'study_hint': '',
                'evidence': [],
                'no_match': True,
                'model_name': self.model_name
            }

        prompt = self._build_classification_prompt(content, choices, candidates)

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    top_p=0.8,
                    max_output_tokens=650,
                    response_mime_type="application/json",
                )
            )

            result_text = (response.text or '').strip()
            json_text = _extract_first_json_object(result_text) or result_text
            json_text = _sanitize_json_text(json_text)
            try:
                result = json.loads(json_text)
            except json.JSONDecodeError:
                result = _fallback_parse_result(result_text)

            lecture_id = result.get('lecture_id')
            no_match = bool(result.get('no_match', False))
            if no_match:
                lecture_id = None
            if lecture_id is not None:
                valid_ids = {c['id'] for c in candidates}
                if lecture_id not in valid_ids:
                    lecture_id = None
                    no_match = True

            confidence = float(result.get('confidence', 0.0))
            reason = result.get('reason', '')
            study_hint = result.get('study_hint', '')
            evidence_raw = result.get('evidence') if isinstance(result.get('evidence'), list) else []
            evidence = []
            if lecture_id and not no_match:
                evidence = self._normalize_evidence(lecture_id, candidates, evidence_raw)

            if no_match:
                evidence = []

            return {
                'lecture_id': lecture_id,
                'confidence': confidence,
                'reason': reason,
                'study_hint': study_hint,
                'evidence': evidence,
                'no_match': no_match,
                'model_name': self.model_name
            }

        except json.JSONDecodeError as e:
            return {
                'lecture_id': None,
                'confidence': 0.0,
                'reason': f'JSON parse error: {str(e)}',
                'study_hint': '',
                'evidence': [],
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
    def start_classification_job(
        cls,
        question_ids: List[int],
        request_meta: Optional[Dict] = None,
    ) -> int:
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
        job.result_json = json.dumps(
            build_job_payload(request_meta, []),
            ensure_ascii=False,
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
        config_name = os.environ.get('FLASK_CONFIG') or 'default'
        app = create_app(config_name)
        
        with app.app_context():
            job = ClassificationJob.query.get(job_id)
            if not job:
                return
            
            request_meta, _ = parse_job_payload(job.result_json)
            job.status = ClassificationJob.STATUS_PROCESSING
            db.session.commit()

            retriever = LectureRetriever()
            retriever.refresh_cache()

            scope = request_meta.get('scope') or {}
            block_id = scope.get('block_id') or scope.get('blockId')
            folder_id = scope.get('folder_id') or scope.get('folderId')
            include_descendants = scope.get('include_descendants')
            if include_descendants is None:
                include_descendants = scope.get('includeDescendants')
            include_descendants = parse_bool(include_descendants, True)
            lecture_ids = scope.get('lecture_ids') or scope.get('lectureIds')
            if lecture_ids is not None:
                try:
                    lecture_ids = [int(lid) for lid in lecture_ids]
                except (TypeError, ValueError):
                    lecture_ids = None
            if lecture_ids is None and (block_id or folder_id):
                lecture_ids = resolve_lecture_ids(
                    int(block_id) if block_id is not None else None,
                    int(folder_id) if folder_id is not None else None,
                    include_descendants,
                )

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
                        choices = [c.content for c in question.choices.order_by('choice_number').all()]
                        question_text = (question.content or '')
                        if choices:
                            question_text = f"{question_text}\n" + " ".join(choices)
                        question_text = question_text.strip()
                        if len(question_text) > 4000:
                            question_text = question_text[:4000]

                        candidates = retriever.find_candidates(
                            question_text,
                            top_k=8,
                            lecture_ids=lecture_ids,
                        )

                        result = classifier.classify_single(question, candidates)
                        result['question_content'] = question.content or ''
                        result['question_choices'] = choices

                        
                        # 결과 저장 (DB에는 아직 반영하지 않음 - preview용)
                        result['question_id'] = qid
                        result['question_number'] = question.question_number
                        result['exam_title'] = question.exam.title if question.exam else ''

                        current_lecture = question.lecture
                        result['current_lecture_id'] = question.lecture_id
                        result['current_lecture_title'] = (
                            f"{current_lecture.block.name} > {current_lecture.title}"
                            if current_lecture
                            else None
                        )
                        result['current_block_name'] = (
                            current_lecture.block.name if current_lecture else None
                        )
                        
                        if result['lecture_id']:
                            lecture = Lecture.query.get(result['lecture_id'])
                            if lecture:
                                result['lecture_title'] = lecture.title
                                result['block_name'] = lecture.block.name
                            else:
                                result['lecture_title'] = None
                                result['block_name'] = None

                        suggested_id = result.get('lecture_id')
                        result['will_change'] = bool(
                            suggested_id and suggested_id != question.lecture_id
                        )
                        
                        results.append(result)
                        job.success_count += 1
                        
                    except Exception as e:
                        results.append({
                            'question_id': qid,
                            'question_number': question.question_number,
                            'exam_title': question.exam.title if question.exam else '',
                            'question_content': question.content or '',
                            'question_choices': choices,
                            'current_lecture_id': question.lecture_id,
                            'current_lecture_title': (
                                f"{question.lecture.block.name} > {question.lecture.title}"
                                if question.lecture
                                else None
                            ),
                            'current_block_name': (
                                question.lecture.block.name if question.lecture else None
                            ),
                            'lecture_id': None,
                            'confidence': 0.0,
                            'reason': f'Error: {str(e)}',
                            'study_hint': '',
                            'evidence': [],
                            'no_match': True,
                            'error': True,
                            'will_change': False,
                        })
                        job.failed_count += 1
                    
                    job.processed_count += 1
                    db.session.commit()
                
                # 완료
                job.status = ClassificationJob.STATUS_COMPLETED
                job.result_json = json.dumps(
                    build_job_payload(request_meta, results),
                    ensure_ascii=False,
                )
                job.completed_at = datetime.utcnow()
                
            except Exception as e:
                job.status = ClassificationJob.STATUS_FAILED
                job.error_message = str(e)
                job.result_json = json.dumps(
                    build_job_payload(request_meta, results),
                    ensure_ascii=False,
                )
                job.completed_at = datetime.utcnow()
            
            db.session.commit()


# ============================================================
# 유틸리티 함수
# ============================================================

def apply_classification_results(
    question_ids: List[int],
    job_id: int,
    apply_mode: str = "all",
) -> int:
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
    
    _, results = parse_job_payload(job.result_json)
    if not results:
        return 0
    results_map = {r['question_id']: r for r in results}
    
    applied_count = 0
    apply_mode = (apply_mode or "all").lower()
    if apply_mode not in {"all", "only_unclassified", "only_changes"}:
        apply_mode = "all"

    for qid in question_ids:
        result = results_map.get(qid)
        if not result:
            continue

        question = Question.query.get(qid)
        if not question:
            continue

        lecture_id = result.get('lecture_id')
        lecture = Lecture.query.get(lecture_id) if lecture_id else None
        no_match = bool(result.get('no_match', False))
        try:
            confidence = float(result.get('confidence', 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        # AI 제안 정보는 항상 저장
        if lecture and not no_match:
            question.ai_suggested_lecture_id = lecture.id
            question.ai_suggested_lecture_title_snapshot = f"{lecture.block.name} > {lecture.title}"
            if not question.is_classified:
                question.classification_status = 'ai_suggested'
        else:
            question.ai_suggested_lecture_id = None
            question.ai_suggested_lecture_title_snapshot = None
            if not question.is_classified:
                question.classification_status = 'manual'

        question.ai_confidence = confidence
        question.ai_reason = result.get('reason', '')
        question.ai_model_name = result.get('model_name', '')
        question.ai_classified_at = datetime.utcnow()

        should_apply = True
        if apply_mode == "only_unclassified" and question.is_classified:
            should_apply = False
        elif apply_mode == "only_changes":
            if not lecture or lecture.id == question.lecture_id:
                should_apply = False

        if should_apply and lecture and not no_match:
            question.lecture_id = lecture.id
            question.is_classified = True
            question.classification_status = 'ai_confirmed'
            applied_count += 1

        if should_apply:
            QuestionChunkMatch.query.filter_by(question_id=question.id).delete(
                synchronize_session=False
            )
            evidence_list = result.get('evidence') or []
            if isinstance(evidence_list, list) and evidence_list:
                chunk_ids = [
                    e.get('chunk_id') for e in evidence_list if e.get('chunk_id')
                ]
                chunk_map = {}
                if chunk_ids:
                    chunk_rows = (
                        LectureChunk.query.filter(LectureChunk.id.in_(chunk_ids)).all()
                    )
                    chunk_map = {row.id: row for row in chunk_rows}

                matches = []
                for idx, evidence in enumerate(evidence_list):
                    chunk_id = evidence.get('chunk_id')
                    if not chunk_id:
                        continue
                    chunk = chunk_map.get(chunk_id)
                    evidence_lecture_id = (
                        evidence.get('lecture_id')
                        or (lecture.id if lecture else None)
                        or (chunk.lecture_id if chunk else None)
                    )
                    if not evidence_lecture_id:
                        continue
                    snippet = (
                        evidence.get('quote')
                        or evidence.get('snippet')
                        or (chunk.content if chunk else '')
                    )
                    snippet = (snippet or '').strip()
                    if len(snippet) > 500:
                        snippet = snippet[:497] + '...'
                    matches.append(
                        QuestionChunkMatch(
                            question_id=question.id,
                            lecture_id=evidence_lecture_id,
                            chunk_id=chunk_id,
                            material_id=chunk.material_id if chunk else None,
                            page_start=evidence.get('page_start')
                            or (chunk.page_start if chunk else None),
                            page_end=evidence.get('page_end')
                            or (chunk.page_end if chunk else None),
                            snippet=snippet,
                            score=evidence.get('score') or confidence,
                            source='ai',
                            job_id=job_id,
                            is_primary=(idx == 0),
                        )
                    )
                if matches:
                    db.session.add_all(matches)

    db.session.commit()
    return applied_count
