"""시험 관련 Blueprint - 기출 시험 및 문제 조회"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import PreviousExam, Question, Block, Lecture
from app.services.db_guard import guard_write_request

exam_bp = Blueprint('exam', __name__)


@exam_bp.before_request
def guard_read_only():
    blocked = guard_write_request()
    if blocked is not None:
        return blocked
    return None


@exam_bp.route('/')
def list_exams():
    """기출 시험 목록 조회"""
    exams = PreviousExam.query.order_by(PreviousExam.exam_date.desc()).all()
    return render_template('exam/list.html', exams=exams)


@exam_bp.route('/<int:exam_id>')
def view_exam(exam_id):
    """기출 시험 상세 조회"""
    exam = PreviousExam.query.get_or_404(exam_id)
    questions = exam.questions.order_by(Question.question_number).all()
    
    # 분류 현황 계산
    classified_count = exam.classified_count
    total_count = exam.question_count
    
    return render_template('exam/detail.html', 
                         exam=exam, 
                         questions=questions,
                         classified_count=classified_count,
                         total_count=total_count)


@exam_bp.route('/<int:exam_id>/question/<int:question_number>')
def view_question(exam_id, question_number):
    """문제 상세 조회"""
    exam = PreviousExam.query.get_or_404(exam_id)
    question = Question.query.filter_by(
        exam_id=exam_id, 
        question_number=question_number
    ).first_or_404()
    
    # 분류 가능한 강의 목록
    blocks = Block.query.order_by(Block.order).all()
    
    return render_template('exam/question.html', 
                         exam=exam, 
                         question=question,
                         blocks=blocks)


@exam_bp.route('/unclassified')
def unclassified_questions():
    """분류 대기소 페이지 - 미분류/분류된 문제 모두 표시"""
    # 모든 문제 조회 (기본적으로 미분류 우선)
    questions = Question.query.order_by(
        Question.is_classified,  # False(미분류)가 먼저
        Question.exam_id,
        Question.question_number
    ).all()
    
    # 블록 목록 (강의 포함)
    blocks = Block.query.order_by(Block.order).all()
    
    # 시험 목록 (필터용)
    exams = PreviousExam.query.order_by(PreviousExam.created_at.desc()).all()
    
    # 미분류 문제 수
    unclassified_count = Question.query.filter_by(is_classified=False).count()
    
    return render_template('exam/unclassified.html', 
                         questions=questions,
                         blocks=blocks,
                         exams=exams,
                         unclassified_count=unclassified_count)


@exam_bp.route('/question/<int:question_id>/classify', methods=['POST'])
def classify_question(question_id):
    """문제를 강의에 분류 (AJAX 지원)"""
    question = Question.query.get_or_404(question_id)
    lecture_id = request.form.get('lecture_id', type=int)
    
    # AJAX 요청 확인
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if lecture_id:
        lecture = Lecture.query.get(lecture_id)
        if lecture:
            question.classify(lecture_id)
            db.session.commit()
            
            if is_ajax:
                return jsonify({
                    'success': True,
                    'lecture_name': f"{lecture.block.name} > {lecture.title}",
                    'lecture_id': lecture_id
                })
            
            flash('문제가 분류되었습니다.', 'success')
        else:
            if is_ajax:
                return jsonify({'success': False, 'error': '강의를 찾을 수 없습니다.'})
            flash('강의를 찾을 수 없습니다.', 'error')
    else:
        if is_ajax:
            return jsonify({'success': False, 'error': '강의를 선택해주세요.'})
        flash('강의를 선택해주세요.', 'error')
    
    return redirect(url_for('exam.view_question', 
                          exam_id=question.exam_id, 
                          question_number=question.question_number))


@exam_bp.route('/question/<int:question_id>/unclassify', methods=['POST'])
def unclassify_question(question_id):
    """문제 분류 해제"""
    question = Question.query.get_or_404(question_id)
    question.unclassify()
    db.session.commit()
    
    # AJAX 요청 확인
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('분류가 해제되었습니다.', 'info')
    return redirect(url_for('exam.view_question', 
                          exam_id=question.exam_id, 
                          question_number=question.question_number))


@exam_bp.route('/questions/bulk-classify', methods=['POST'])
def bulk_classify():
    """여러 문제를 한 번에 분류"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': '데이터가 없습니다.'}), 400
    
    question_ids = data.get('question_ids', [])
    lecture_id = data.get('lecture_id')
    
    if not question_ids:
        return jsonify({'success': False, 'error': '선택된 문제가 없습니다.'}), 400
    
    if not lecture_id:
        return jsonify({'success': False, 'error': '강의를 선택해주세요.'}), 400
    
    lecture = Lecture.query.get(lecture_id)
    if not lecture:
        return jsonify({'success': False, 'error': '강의를 찾을 수 없습니다.'}), 404
    
    # 선택된 문제들 일괄 분류
    updated_count = 0
    for qid in question_ids:
        question = Question.query.get(qid)
        if question:
            question.classify(lecture_id)
            updated_count += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'updated_count': updated_count,
        'lecture_name': f"{lecture.block.name} > {lecture.title}"
    })

