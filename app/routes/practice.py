"""연습 모드 Blueprint - 강의별 기출문제 풀이"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app.models import Block, Lecture, Choice
from app.services.practice_service import (
    build_question_groups,
    get_lecture_questions_ordered,
    get_prev_next,
    get_question_by_seq,
    grade_questions,
    normalize_answers_payload,
)

practice_bp = Blueprint('practice', __name__)


@practice_bp.route('/')
def list_lectures():
    """연습할 강의 목록 표시"""
    blocks = Block.query.order_by(Block.order).all()
    return render_template('practice/list.html', blocks=blocks)


@practice_bp.route('/lecture/<int:lecture_id>')
def dashboard(lecture_id):
    """강의별 문제 대시보드 (바둑판 형태) - 유형별 분리"""
    lecture = Lecture.query.get_or_404(lecture_id)
    questions = get_lecture_questions_ordered(lecture_id) or []
    
    groups = build_question_groups(questions)
    objective_questions = groups['objective_questions']
    subjective_questions = groups['subjective_questions']
    question_map = groups['question_map']

    return render_template('practice/dashboard.html', 
                         lecture=lecture, 
                         questions=questions,
                         question_map=question_map,
                         objective_questions=objective_questions,
                         subjective_questions=subjective_questions,
                         total_count=len(questions),
                         objective_count=len(objective_questions),
                         subjective_count=len(subjective_questions))


@practice_bp.route('/lecture/<int:lecture_id>/q/<int:question_id>')
def question_by_id(lecture_id, question_id):
    """개별 문제 풀이 페이지 (question_id 기반)"""
    lecture = Lecture.query.get_or_404(lecture_id)
    questions = get_lecture_questions_ordered(lecture_id) or []
    index = next((i for i, q in enumerate(questions) if q.id == question_id), None)
    if index is None:
        flash('유효하지 않은 문제 번호입니다.', 'error')
        return redirect(url_for('practice.dashboard', lecture_id=lecture_id))

    current_question = questions[index]
    choices = current_question.choices.order_by(Choice.choice_number).all()
    prev_question_id, next_question_id = get_prev_next(questions, index)
    has_prev = prev_question_id is not None
    has_next = next_question_id is not None

    return render_template('practice/question.html',
                         lecture=lecture,
                         question=current_question,
                         choices=choices,
                         seq=index + 1,
                         total_count=len(questions),
                         has_prev=has_prev,
                         has_next=has_next,
                         prev_question_id=prev_question_id,
                         next_question_id=next_question_id)


@practice_bp.route('/lecture/<int:lecture_id>/question/<int:seq>')
def question(lecture_id, seq):
    """레거시 seq 라우트 -> question_id 라우트로 리다이렉트"""
    Lecture.query.get_or_404(lecture_id)
    question, _, _ = get_question_by_seq(lecture_id, seq)
    if not question:
        flash('유효하지 않은 문제 번호입니다.', 'error')
        return redirect(url_for('practice.dashboard', lecture_id=lecture_id))

    return redirect(url_for('practice.question_by_id',
                            lecture_id=lecture_id,
                            question_id=question.id))


@practice_bp.route('/lecture/<int:lecture_id>/submit', methods=['POST'])
def submit(lecture_id):
    """답안 제출 및 채점 - 유형별 분리 채점"""
    lecture = Lecture.query.get_or_404(lecture_id)
    questions = get_lecture_questions_ordered(lecture_id) or []
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '데이터가 없습니다.'}), 400
    
    answers = normalize_answers_payload(data.get('answers', {}))
    counts, results = grade_questions(questions, answers, include_content=True)

    return jsonify({
        'success': True,
        'total_count': counts['total'],
        'answered_count': counts['answered'],
        'correct_count': counts['correct'],
        'incorrect_count': counts['answered'] - counts['correct'],
        'objective_total': counts['objective_total'],
        'objective_answered': counts['objective_answered'],
        'objective_correct': counts['objective_correct'],
        'objective_incorrect': counts['objective_answered'] - counts['objective_correct'],
        'subjective_total': counts['subjective_total'],
        'subjective_answered': counts['subjective_answered'],
        'subjective_correct': counts['subjective_correct'],
        'subjective_incorrect': counts['subjective_answered'] - counts['subjective_correct'],
        'results': results
    })


@practice_bp.route('/lecture/<int:lecture_id>/result')
def result(lecture_id):
    """결과 페이지 (GET 방식으로 표시, 실제 데이터는 JS에서 처리)"""
    lecture = Lecture.query.get_or_404(lecture_id)
    questions = get_lecture_questions_ordered(lecture_id) or []
    
    # 문제 정보 (JS에서 사용)
    question_data = []
    for idx, q in enumerate(questions):
        choices = q.choices.order_by(Choice.choice_number).all()
        question_data.append({
            'seq': idx + 1,
            'id': q.id,
            'content': q.content,
            'choices': [{'choice_number': c.choice_number, 'content': c.content} for c in choices],
            'correct_answer': q.correct_choice_numbers if not q.is_short_answer else q.correct_answer_text,
            'explanation': q.explanation,
            'exam_name': q.exam.title if q.exam else '',
            'question_number': q.question_number,
            'is_short_answer': q.is_short_answer
        })
    
    return render_template('practice/result.html',
                         lecture=lecture,
                         questions=question_data,
                         total_count=len(questions))

