"""연습 모드 Blueprint - 강의별 기출문제 풀이"""
import json

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from urllib.parse import urlencode
from app import db
from app.models import Block, Lecture, Choice, PracticeSession, PracticeAnswer, Question
from app.services.practice_service import (
    build_question_groups,
    build_duplicate_question_map,
    get_lecture_questions_ordered,
    build_legacy_results,
    evaluate_practice_answers,
    grade_practice_submission,
    normalize_practice_answers_payload,
)
from app.services.practice_filters import (
    parse_exam_filter_args,
    apply_exam_filter,
    build_exam_options,
)
from app.services.db_guard import guard_write_request

practice_bp = Blueprint('practice', __name__)


@practice_bp.before_request
def guard_read_only():
    blocked = guard_write_request()
    if blocked is not None:
        return blocked
    return None


def _load_question_order(session):
    if not session.question_order:
        return []
    try:
        return json.loads(session.question_order)
    except (TypeError, ValueError):
        return []


def _format_answer_payload(answer):
    if not answer or not answer.answer_payload:
        return ''
    try:
        payload = json.loads(answer.answer_payload)
    except (TypeError, ValueError):
        return answer.answer_payload

    answer_type = payload.get('type')
    value = payload.get('value')
    if answer_type == 'mcq':
        if not isinstance(value, list):
            return ''
        return ', '.join(str(item) for item in value)
    if answer_type == 'short':
        return value if isinstance(value, str) else ''
    return ''


def _build_filter_query(exam_ids, filter_active):
    if not filter_active:
        return ''
    params = {'filter': 1}
    if exam_ids:
        params['exam_ids'] = exam_ids
    return f"?{urlencode(params, doseq=True)}"


@practice_bp.route('/')
def list_lectures():
    """연습할 강의 목록 표시"""
    blocks = Block.query.order_by(Block.order).all()
    return render_template('practice/list.html', blocks=blocks)


@practice_bp.route('/sessions')
def session_list():
    """Practice sessions list."""
    sessions = PracticeSession.query.order_by(PracticeSession.created_at.desc()).all()
    session_rows = []
    for session in sessions:
        answers = session.answers
        answered_count = answers.count()
        correct_count = answers.filter_by(is_correct=True).count()
        question_order = _load_question_order(session)
        if question_order:
            total_questions = len(question_order)
        elif session.lecture:
            total_questions = session.lecture.question_count
        else:
            total_questions = answered_count
        session_rows.append({
            'id': session.id,
            'lecture_id': session.lecture_id,
            'lecture_title': session.lecture.title if session.lecture else '',
            'mode': session.mode,
            'created_at': session.created_at,
            'finished_at': session.finished_at,
            'total_questions': total_questions,
            'answered_count': answered_count,
            'correct_count': correct_count,
        })
    return render_template('practice/sessions.html', sessions=session_rows)


@practice_bp.route('/sessions/<int:session_id>')
def session_detail(session_id):
    """Practice session detail."""
    session = PracticeSession.query.get_or_404(session_id)
    question_order = _load_question_order(session)
    answers = session.answers.all()
    answer_map = {answer.question_id: answer for answer in answers}

    ordered_questions = []
    if question_order:
        questions = Question.query.filter(Question.id.in_(question_order)).all()
        question_map = {question.id: question for question in questions}
        ordered_questions = [
            question_map[qid] for qid in question_order if qid in question_map
        ]

    if not ordered_questions and session.lecture_id:
        ordered_questions = get_lecture_questions_ordered(session.lecture_id) or []

    if not ordered_questions:
        ordered_questions = [answer.question for answer in answers if answer.question]

    items = []
    for question in ordered_questions:
        answer = answer_map.get(question.id)
        result = 'unanswered'
        if answer is not None:
            result = 'pending'
            if answer.is_correct is True:
                result = 'correct'
            elif answer.is_correct is False:
                result = 'wrong'

        items.append({
            'question_id': question.id,
            'question_number': question.question_number,
            'answer_text': _format_answer_payload(answer),
            'result': result,
        })

    return render_template(
        'practice/session_detail.html',
        session=session,
        items=items,
    )


@practice_bp.route('/lecture/<int:lecture_id>')
def dashboard(lecture_id):
    """강의별 문제 대시보드 (바둑판 형태) - 유형별 분리"""
    lecture = Lecture.query.get_or_404(lecture_id)
    exam_ids, filter_active = parse_exam_filter_args(request.args)
    all_questions = get_lecture_questions_ordered(lecture_id) or []
    questions = apply_exam_filter(all_questions, exam_ids, filter_active)
    
    groups = build_question_groups(questions)
    objective_questions = groups['objective_questions']
    subjective_questions = groups['subjective_questions']
    question_map = groups['question_map']
    exam_options = build_exam_options(all_questions)
    if filter_active:
        selected_exam_ids = exam_ids
    else:
        selected_exam_ids = [option['id'] for option in exam_options]
    filter_query = _build_filter_query(exam_ids, filter_active)

    return render_template('practice/dashboard.html', 
                         lecture=lecture, 
                         questions=questions,
                         question_map=question_map,
                         objective_questions=objective_questions,
                         subjective_questions=subjective_questions,
                         total_count=len(questions),
                         objective_count=len(objective_questions),
                         subjective_count=len(subjective_questions),
                         exam_options=exam_options,
                         selected_exam_ids=selected_exam_ids,
                         filter_query=filter_query,
                         filter_active=filter_active)


@practice_bp.route('/lecture/<int:lecture_id>/q/<int:question_id>')
def question_by_id(lecture_id, question_id):
    """개별 문제 풀이 페이지 (question_id 기반)"""
    lecture = Lecture.query.get_or_404(lecture_id)
    exam_ids, filter_active = parse_exam_filter_args(request.args)
    all_questions = get_lecture_questions_ordered(lecture_id) or []
    questions = apply_exam_filter(all_questions, exam_ids, filter_active)
    filter_query = _build_filter_query(exam_ids, filter_active)
    index = next((i for i, q in enumerate(questions) if q.id == question_id), None)
    if index is None:
        flash('유효하지 않은 문제 번호입니다.', 'error')
        return redirect(url_for('practice.dashboard', lecture_id=lecture_id) + filter_query)

    current_question = questions[index]
    choices = current_question.choices.order_by(Choice.choice_number).all()
    objective_questions = [q for q in questions if not q.is_short_answer]
    subjective_questions = [q for q in questions if q.is_short_answer]
    objective_index = {q.id: idx for idx, q in enumerate(objective_questions)}
    subjective_index = {q.id: idx for idx, q in enumerate(subjective_questions)}

    is_short = current_question.is_short_answer
    question_type_label = "주관식" if is_short else "객관식"
    if is_short:
        type_questions = subjective_questions
        type_index = subjective_index.get(current_question.id, index)
    else:
        type_questions = objective_questions
        type_index = objective_index.get(current_question.id, index)
    if not type_questions:
        type_questions = questions
        type_index = index
    type_seq = type_index + 1
    type_total = len(type_questions)

    prev_question_id = None
    next_question_id = None
    prev_label = "이전"
    next_label = "다음"

    if is_short:
        if type_index > 0:
            prev_question_id = subjective_questions[type_index - 1].id
        elif objective_questions:
            prev_question_id = objective_questions[-1].id
            prev_label = "이전 문제(객관식)"
        if type_index + 1 < len(subjective_questions):
            next_question_id = subjective_questions[type_index + 1].id
    else:
        if type_index > 0:
            prev_question_id = objective_questions[type_index - 1].id
        if type_index + 1 < len(objective_questions):
            next_question_id = objective_questions[type_index + 1].id
        elif subjective_questions:
            next_question_id = subjective_questions[0].id
            next_label = "다음 문제(주관식)"

    has_prev = prev_question_id is not None
    has_next = next_question_id is not None

    duplicate_map = build_duplicate_question_map(questions)
    related_questions = []
    related_items = duplicate_map.get(current_question.id, [])
    if related_items:
        seq_map = {q.id: idx + 1 for idx, q in enumerate(questions)}
        related_questions = [
            {
                'id': q.id,
                'seq': seq_map.get(q.id),
                'exam_title': q.exam.title if q.exam else '',
                'question_number': q.question_number,
            }
            for q in related_items
        ]
        related_questions.sort(key=lambda item: item['seq'] or 0)

    return render_template('practice/question.html',
                         lecture=lecture,
                         question=current_question,
                         choices=choices,
                         seq=type_seq,
                         total_count=type_total,
                         question_type_label=question_type_label,
                         has_prev=has_prev,
                         has_next=has_next,
                         prev_question_id=prev_question_id,
                         next_question_id=next_question_id,
                         prev_label=prev_label,
                         next_label=next_label,
                         related_questions=related_questions,
                         filter_query=filter_query)


@practice_bp.route('/lecture/<int:lecture_id>/question/<int:seq>')
def question(lecture_id, seq):
    """레거시 seq 라우트 -> question_id 라우트로 리다이렉트"""
    Lecture.query.get_or_404(lecture_id)
    exam_ids, filter_active = parse_exam_filter_args(request.args)
    all_questions = get_lecture_questions_ordered(lecture_id) or []
    questions = apply_exam_filter(all_questions, exam_ids, filter_active)
    filter_query = _build_filter_query(exam_ids, filter_active)
    index = seq - 1
    if index < 0 or index >= len(questions):
        flash('유효하지 않은 문제 번호입니다.', 'error')
        return redirect(url_for('practice.dashboard', lecture_id=lecture_id) + filter_query)

    return redirect(url_for('practice.question_by_id',
                            lecture_id=lecture_id,
                            question_id=questions[index].id) + filter_query)


@practice_bp.route('/lecture/<int:lecture_id>/submit', methods=['POST'])
def submit(lecture_id):
    """답안 제출 및 채점 - 유형별 분리 채점"""
    lecture = Lecture.query.get_or_404(lecture_id)
    exam_ids, filter_active = parse_exam_filter_args(request.args)
    all_questions = get_lecture_questions_ordered(lecture_id) or []
    questions = apply_exam_filter(all_questions, exam_ids, filter_active)
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '데이터가 없습니다.'}), 400
    
    answers_payload = data.get('answers', {})
    question_meta = {str(question.id): question.is_short_answer for question in questions}
    answers_v1, _, error_code, _ = normalize_practice_answers_payload(
        {'answers': answers_payload},
        question_meta,
    )
    if error_code:
        return jsonify({'success': False, 'error': '?°ì´?°ê? ?†ìŠµ?ˆë‹¤.'}), 400

    _summary, items, counts = evaluate_practice_answers(questions, answers_v1 or {})
    results = build_legacy_results(questions, items, include_content=True)

    if answers_v1 and not error_code:
        try:
            grade_practice_submission(lecture_id, answers_v1, questions=questions)
        except Exception:
            db.session.rollback()

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
    exam_ids, filter_active = parse_exam_filter_args(request.args)
    all_questions = get_lecture_questions_ordered(lecture_id) or []
    questions = apply_exam_filter(all_questions, exam_ids, filter_active)
    filter_query = _build_filter_query(exam_ids, filter_active)
    
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
                         total_count=len(questions),
                         filter_query=filter_query)

