import json
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.models import Block, Lecture, Question, Choice, PracticeSession
from app.services.practice_service import (
    build_question_groups,
    get_lecture_questions_ordered,
    grade_practice_submission,
    normalize_practice_answers_payload,
)

api_practice_bp = Blueprint('api_practice', __name__)


def error_response(message, code, status=400, details=None):
    payload = {'ok': False, 'code': code, 'message': message}
    if details is not None:
        payload['details'] = details
    return jsonify(payload), status


def _format_datetime(value):
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat() + 'Z'


def _parse_pagination_args():
    limit_param = request.args.get('limit')
    offset_param = request.args.get('offset')
    limit = None
    offset = 0

    if offset_param is not None:
        if not offset_param.isdigit():
            return None, None, ('Invalid offset.', 'INVALID_PAYLOAD')
        offset = int(offset_param)
        if offset < 0:
            return None, None, ('Invalid offset.', 'INVALID_PAYLOAD')

    if limit_param is not None:
        if not limit_param.isdigit():
            return None, None, ('Invalid limit.', 'INVALID_PAYLOAD')
        limit = int(limit_param)
        if limit <= 0:
            return None, None, ('Invalid limit.', 'INVALID_PAYLOAD')

    return limit, offset, None


def _load_choices_for_questions(question_ids):
    if not question_ids:
        return {}
    choices = Choice.query.filter(Choice.question_id.in_(question_ids)).order_by(
        Choice.question_id, Choice.choice_number
    ).all()
    choices_by_question = {}
    for choice in choices:
        choices_by_question.setdefault(choice.question_id, []).append(choice)
    return choices_by_question


def _load_session_question_order(session):
    if not session.question_order:
        return []
    try:
        order = json.loads(session.question_order)
    except (TypeError, ValueError):
        return []
    if not isinstance(order, list):
        return []
    normalized = []
    for item in order:
        try:
            normalized.append(int(item))
        except (TypeError, ValueError):
            continue
    return normalized


def _parse_answer_payload(value):
    if not value:
        return None
    if isinstance(value, dict):
        return value
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


@api_practice_bp.route('/lectures')
def list_lectures():
    blocks = Block.query.order_by(Block.order).all()
    lectures = Lecture.query.order_by(Lecture.block_id, Lecture.order).all()
    lectures_by_block = {}
    for lecture in lectures:
        lectures_by_block.setdefault(lecture.block_id, []).append(lecture)

    blocks_payload = []
    for block in blocks:
        block_lectures = lectures_by_block.get(block.id, [])
        lectures_payload = [
            {
                'lectureId': lecture.id,
                'title': lecture.title,
                'order': lecture.order,
            }
            for lecture in block_lectures
        ]
        blocks_payload.append(
            {
                'blockId': block.id,
                'title': block.name,
                'lectures': lectures_payload,
            }
        )

    return jsonify({'blocks': blocks_payload})


@api_practice_bp.route('/lecture/<int:lecture_id>')
def lecture_questions(lecture_id):
    lecture = Lecture.query.get(lecture_id)
    if lecture is None:
        return error_response('Lecture not found.', 'LECTURE_NOT_FOUND', 404)

    questions = get_lecture_questions_ordered(lecture_id) or []
    groups = build_question_groups(questions)
    question_meta = groups['question_meta']

    questions_payload = [
        {
            'questionId': meta['id'],
            'originalSeq': meta['original_seq'],
            'typeSeq': meta['type_seq'],
            'type': meta['type'],
            'isShortAnswer': meta['is_short_answer'],
            'isMultipleResponse': meta['is_multiple_response'],
        }
        for meta in question_meta
    ]

    return jsonify(
        {
            'lectureId': lecture.id,
            'title': lecture.title,
            'questions': questions_payload,
        }
    )


@api_practice_bp.route('/lecture/<int:lecture_id>/question/<int:question_id>')
def lecture_question(lecture_id, question_id):
    lecture = Lecture.query.get(lecture_id)
    if lecture is None:
        return error_response('Lecture not found.', 'LECTURE_NOT_FOUND', 404)

    question = Question.query.filter_by(id=question_id, lecture_id=lecture_id).first()
    if question is None:
        return error_response('Question not found in lecture.', 'QUESTION_NOT_IN_LECTURE', 404)

    choices = question.choices.order_by(Choice.choice_number).all()
    choices_payload = [
        {'number': choice.choice_number, 'content': choice.content} for choice in choices
    ]

    return jsonify(
        {
            'questionId': question.id,
            'stem': question.content or '',
            'choices': choices_payload,
            'isShortAnswer': question.is_short_answer,
            'isMultipleResponse': question.is_multiple_response,
            'hasExplanation': bool(question.explanation),
        }
    )


@api_practice_bp.route('/lecture/<int:lecture_id>/questions')
def lecture_question_list(lecture_id):
    lecture = Lecture.query.get(lecture_id)
    if lecture is None:
        return error_response('Lecture not found.', 'LECTURE_NOT_FOUND', 404)

    limit, offset, error = _parse_pagination_args()
    if error:
        message, code = error
        return error_response(message, code, 400)

    query = Question.query.filter_by(lecture_id=lecture_id).order_by(Question.question_number)
    total = query.count()
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    questions = query.all()

    question_ids = [question.id for question in questions]
    choices_by_question = _load_choices_for_questions(question_ids)

    questions_payload = []
    for question in questions:
        choices = choices_by_question.get(question.id, [])
        questions_payload.append(
            {
                'questionId': question.id,
                'stem': question.content or '',
                'choices': [
                    {'number': choice.choice_number, 'content': choice.content}
                    for choice in choices
                ],
                'isShortAnswer': question.is_short_answer,
                'isMultipleResponse': question.is_multiple_response,
            }
        )

    response_payload = {
        'lectureId': lecture.id,
        'title': lecture.title,
        'total': total,
        'offset': offset,
        'questions': questions_payload,
    }
    if limit is not None:
        response_payload['limit'] = limit

    return jsonify(response_payload)


@api_practice_bp.route('/lecture/<int:lecture_id>/submit', methods=['POST'])
def submit_answers(lecture_id):
    lecture = Lecture.query.get(lecture_id)
    if lecture is None:
        return error_response('Lecture not found.', 'LECTURE_NOT_FOUND', 404)

    raw_body = request.get_data(cache=False, as_text=True)
    data = request.get_json(silent=True)
    if data is None:
        if raw_body:
            return error_response('Invalid JSON.', 'INVALID_JSON', 400)
        return error_response('Invalid request payload.', 'INVALID_PAYLOAD', 400)

    questions = get_lecture_questions_ordered(lecture_id) or []
    question_meta = {str(q.id): q.is_short_answer for q in questions}

    answers_v1, deprecated_input, error_code, error_message = normalize_practice_answers_payload(
        data, question_meta
    )
    if error_code:
        return error_response(error_message, error_code, 400)

    invalid_ids = [
        key for key in answers_v1.keys() if key not in question_meta
    ]
    if invalid_ids:
        return error_response(
            'Question not in lecture.',
            'QUESTION_NOT_IN_LECTURE',
            400,
            details={'questionIds': invalid_ids},
        )

    summary, items = grade_practice_submission(lecture_id, answers_v1)
    submitted_at = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

    return jsonify(
        {
            'lectureId': lecture.id,
            'submittedAt': submitted_at,
            'deprecatedInput': deprecated_input,
            'summary': summary,
            'items': items,
        }
    )


@api_practice_bp.route('/sessions')
def list_sessions():
    lecture_id = request.args.get('lectureId')
    query = PracticeSession.query.order_by(PracticeSession.created_at.desc())
    if lecture_id:
        if not lecture_id.isdigit():
            return error_response('Invalid lecture id.', 'INVALID_PAYLOAD', 400)
        query = query.filter_by(lecture_id=int(lecture_id))

    sessions_payload = []
    for session in query.all():
        answers = session.answers
        answered_count = answers.count()
        correct_count = answers.filter_by(is_correct=True).count()
        question_order = _load_session_question_order(session)
        if question_order:
            total_questions = len(question_order)
        elif session.lecture:
            total_questions = session.lecture.question_count
        else:
            total_questions = answered_count

        sessions_payload.append(
            {
                'sessionId': session.id,
                'lectureId': session.lecture_id,
                'lectureTitle': session.lecture.title if session.lecture else None,
                'mode': session.mode,
                'createdAt': _format_datetime(session.created_at),
                'finishedAt': _format_datetime(session.finished_at),
                'totalQuestions': total_questions,
                'answeredCount': answered_count,
                'correctCount': correct_count,
            }
        )

    return jsonify({'sessions': sessions_payload})


@api_practice_bp.route('/sessions/<int:session_id>')
def session_detail(session_id):
    session = PracticeSession.query.get(session_id)
    if session is None:
        return error_response('Session not found.', 'SESSION_NOT_FOUND', 404)

    answers = session.answers.all()
    answer_map = {answer.question_id: answer for answer in answers}
    question_order = _load_session_question_order(session)

    if question_order:
        questions = Question.query.filter(Question.id.in_(question_order)).all()
        question_map = {question.id: question for question in questions}
        ordered_questions = [
            question_map[qid] for qid in question_order if qid in question_map
        ]
    elif session.lecture_id:
        ordered_questions = get_lecture_questions_ordered(session.lecture_id) or []
    else:
        ordered_questions = [answer.question for answer in answers if answer.question]

    items = []
    for question in ordered_questions:
        answer = answer_map.get(question.id)
        payload = _parse_answer_payload(answer.answer_payload) if answer else None
        is_answered = answer is not None
        is_correct = answer.is_correct if answer is not None else None
        result = 'unanswered'
        if answer is not None:
            result = 'pending'
            if answer.is_correct is True:
                result = 'correct'
            elif answer.is_correct is False:
                result = 'wrong'

        items.append(
            {
                'questionId': question.id,
                'questionNumber': question.question_number,
                'isAnswered': is_answered,
                'isCorrect': is_correct,
                'answer': payload,
                'result': result,
            }
        )

    answers_query = session.answers
    answered_count = answers_query.count()
    correct_count = answers_query.filter_by(is_correct=True).count()
    if question_order:
        total_questions = len(question_order)
    elif ordered_questions:
        total_questions = len(ordered_questions)
    else:
        total_questions = answered_count

    return jsonify(
        {
            'sessionId': session.id,
            'lectureId': session.lecture_id,
            'lectureTitle': session.lecture.title if session.lecture else None,
            'mode': session.mode,
            'createdAt': _format_datetime(session.created_at),
            'finishedAt': _format_datetime(session.finished_at),
            'totalQuestions': total_questions,
            'answeredCount': answered_count,
            'correctCount': correct_count,
            'questionOrder': question_order,
            'items': items,
        }
    )


@api_practice_bp.route('/lecture/<int:lecture_id>/result')
def lecture_result(lecture_id):
    lecture = Lecture.query.get(lecture_id)
    if lecture is None:
        return error_response('Lecture not found.', 'LECTURE_NOT_FOUND', 404)

    include_answer = request.args.get('includeAnswer', 'false').lower() == 'true'
    limit, offset, error = _parse_pagination_args()
    if error:
        message, code = error
        return error_response(message, code, 400)

    query = Question.query.filter_by(lecture_id=lecture_id).order_by(Question.question_number)
    total = query.count()
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    questions = query.all()
    question_ids = [question.id for question in questions]
    choices_by_question = _load_choices_for_questions(question_ids)
    questions_payload = []
    for question in questions:
        choices = choices_by_question.get(question.id, [])
        question_payload = {
            'questionId': question.id,
            'stem': question.content or '',
            'choices': [
                {'number': choice.choice_number, 'content': choice.content}
                for choice in choices
            ],
            'explanation': question.explanation,
            'isShortAnswer': question.is_short_answer,
            'isMultipleResponse': question.is_multiple_response,
        }
        if include_answer:
            if question.is_short_answer:
                question_payload['correctAnswerText'] = question.correct_answer_text
            else:
                question_payload['correctChoiceNumbers'] = [
                    choice.choice_number for choice in choices if choice.is_correct
                ]
        questions_payload.append(question_payload)

    response_payload = {
        'lectureId': lecture.id,
        'title': lecture.title,
        'total': total,
        'offset': offset,
        'questions': questions_payload,
    }
    if limit is not None:
        response_payload['limit'] = limit

    return jsonify(response_payload)
