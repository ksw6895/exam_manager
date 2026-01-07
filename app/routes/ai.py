"""AI 분류 관련 API Blueprint"""
import json
import re
from flask import Blueprint, request, jsonify, render_template, current_app
from app import db
from app.models import Question, Block, ClassificationJob
from app.services.ai_classifier import (
    AsyncBatchProcessor,
    apply_classification_results,
    LectureRetriever,
    GENAI_AVAILABLE
)

# Google GenAI SDK (for text correction)
try:
    from google import genai
    from google.genai import types
except ImportError:
    pass

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')


@ai_bp.route('/classify/start', methods=['POST'])
def start_classification():
    """AI 분류 작업 시작"""
    if not GENAI_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'google-genai 패키지가 설치되지 않았습니다.'
        }), 500
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '데이터가 없습니다.'}), 400
    
    question_ids = data.get('question_ids', [])
    if not question_ids:
        return jsonify({'success': False, 'error': '선택된 문제가 없습니다.'}), 400
    
    # 유효한 문제 ID만 필터링
    valid_ids = [
        q.id for q in Question.query.filter(Question.id.in_(question_ids)).all()
    ]
    
    if not valid_ids:
        return jsonify({'success': False, 'error': '유효한 문제가 없습니다.'}), 400
    
    try:
        job_id = AsyncBatchProcessor.start_classification_job(valid_ids)
        return jsonify({
            'success': True,
            'job_id': job_id,
            'total_count': len(valid_ids)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/classify/status/<int:job_id>')
def get_classification_status(job_id):
    """분류 작업 상태 조회 (Polling용)"""
    job = ClassificationJob.query.get(job_id)
    if not job:
        return jsonify({'success': False, 'error': '작업을 찾을 수 없습니다.'}), 404
    
    return jsonify({
        'success': True,
        'status': job.status,
        'total_count': job.total_count,
        'processed_count': job.processed_count,
        'success_count': job.success_count,
        'failed_count': job.failed_count,
        'progress_percent': job.progress_percent,
        'is_complete': job.is_complete,
        'error_message': job.error_message
    })


@ai_bp.route('/classify/result/<int:job_id>')
def get_classification_result(job_id):
    """분류 결과 조회 (Preview 데이터)"""
    job = ClassificationJob.query.get(job_id)
    if not job:
        return jsonify({'success': False, 'error': '작업을 찾을 수 없습니다.'}), 404
    
    if not job.is_complete:
        return jsonify({'success': False, 'error': '작업이 아직 완료되지 않았습니다.'}), 400
    
    if job.status == ClassificationJob.STATUS_FAILED:
        return jsonify({
            'success': False,
            'error': job.error_message or '작업 실패'
        }), 500
    
    results = json.loads(job.result_json) if job.result_json else []
    
    # 블록별로 그룹화
    blocks_map = {}
    no_match_list = []
    
    for r in results:
        if r.get('no_match') or not r.get('lecture_id'):
            no_match_list.append(r)
        else:
            block_name = r.get('block_name', '미지정')
            if block_name not in blocks_map:
                blocks_map[block_name] = {
                    'block_name': block_name,
                    'lectures': {}
                }
            
            lecture_title = r.get('lecture_title', '미지정')
            lecture_id = r.get('lecture_id')
            
            if lecture_id not in blocks_map[block_name]['lectures']:
                blocks_map[block_name]['lectures'][lecture_id] = {
                    'lecture_id': lecture_id,
                    'lecture_title': lecture_title,
                    'questions': []
                }
            
            blocks_map[block_name]['lectures'][lecture_id]['questions'].append(r)
    
    # 정렬 및 리스트 변환
    grouped_results = []
    for block_name in sorted(blocks_map.keys()):
        block_data = blocks_map[block_name]
        lectures_list = sorted(
            block_data['lectures'].values(),
            key=lambda x: x['lecture_title']
        )
        grouped_results.append({
            'block_name': block_name,
            'lectures': lectures_list
        })
    
    return jsonify({
        'success': True,
        'job_id': job_id,
        'grouped_results': grouped_results,
        'no_match_list': no_match_list,
        'summary': {
            'total': job.total_count,
            'success': job.success_count,
            'failed': job.failed_count,
            'no_match': len(no_match_list)
        }
    })


@ai_bp.route('/classify/apply', methods=['POST'])
def apply_classification():
    """분류 결과 적용 (사용자 확인 후)"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '데이터가 없습니다.'}), 400
    
    job_id = data.get('job_id')
    question_ids = data.get('question_ids', [])
    
    if not job_id:
        return jsonify({'success': False, 'error': 'job_id가 필요합니다.'}), 400
    
    if not question_ids:
        return jsonify({'success': False, 'error': '적용할 문제가 없습니다.'}), 400
    
    try:
        applied_count = apply_classification_results(question_ids, job_id)
        return jsonify({
            'success': True,
            'applied_count': applied_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/classify/recent')
def get_recent_jobs():
    """최근 AI 분류 작업 목록 조회"""
    # 최근 7일 이내, 최대 10개의 작업을 가져옴
    from datetime import datetime, timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    jobs = ClassificationJob.query.filter(
        ClassificationJob.created_at >= week_ago
    ).order_by(ClassificationJob.created_at.desc()).limit(10).all()
    
    result = []
    for job in jobs:
        status_label = {
            'pending': '대기중',
            'processing': '진행중',
            'completed': '완료',
            'failed': '실패'
        }.get(job.status, job.status)
        
        result.append({
            'id': job.id,
            'created_at': job.created_at.strftime('%m/%d %H:%M'),
            'status': job.status,
            'status_label': status_label,
            'total_count': job.total_count,
            'success_count': job.success_count,
            'is_complete': job.is_complete
        })
    
    return jsonify({
        'success': True,
        'jobs': result
    })


@ai_bp.route('/classify/preview/<int:job_id>')
def preview_classification(job_id):
    """분류 결과 미리보기 페이지"""
    job = ClassificationJob.query.get_or_404(job_id)
    blocks = Block.query.order_by(Block.order).all()
    
    return render_template('exam/ai_classification_preview.html',
                         job=job,
                         blocks=blocks)


@ai_bp.route('/correct-text', methods=['POST'])
def correct_text():
    """AI 텍스트 교정 (띄어쓰기, 맞춤법)"""
    if not GENAI_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'google-genai 패키지가 설치되지 않았습니다.'
        }), 500
    
    data = request.get_json()
    if not data or not data.get('text'):
        return jsonify({'success': False, 'error': '텍스트가 없습니다.'}), 400
    
    original_text = data['text']
    
    # Gemini API 초기화
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        return jsonify({
            'success': False, 
            'error': 'GEMINI_API_KEY가 설정되지 않았습니다.'
        }), 500
    
    try:
        client = genai.Client(api_key=api_key)
        model_name = current_app.config.get('GEMINI_MODEL_NAME', 'gemini-1.5-flash-002')
        
        prompt = f"""당신은 의학 시험 문제 전문 교정사입니다. 아래 텍스트의 띄어쓰기와 맞춤법 오류를 수정해주세요.

## 규칙
1. 띄어쓰기 오류만 수정하세요 (예: "심장 근육세포" → "심장근육세포" 또는 그 반대).
2. 명백한 오타만 수정하세요.
3. 의학/생물학 전문 용어, 영어 표현, 숫자는 절대 변경하지 마세요.
4. 내용을 추가하거나 삭제하지 마세요.
5. 교정된 텍스트만 출력하세요. 설명이나 추가 문구는 넣지 마세요.

## 원본 텍스트
{original_text}

## 교정된 텍스트"""
        
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                top_p=0.9,
                max_output_tokens=2000,
            )
        )
        
        corrected_text = response.text.strip()
        
        return jsonify({
            'success': True,
            'original': original_text,
            'corrected': corrected_text
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
