from datetime import datetime

from flask import Blueprint, jsonify, request

from app.models import Block, Lecture, Question, Choice
from app.services.practice_service import (
    build_question_groups,
    get_lecture_questions_ordered,
    grade_practice_submission,
    normalize_practice_answers_payload,
)

api_practice_bp = Blueprint('api_practice', __name__)


def error_response(message, code, status=400):
    return jsonify({'error': message, 'code': code}), status


@api_practice_bp.route('/lectures')
def list_lectures():
    blocks = Block.query.order_by(Block.order).all()
    blocks_payload = []

    for block in blocks:
        lectures = block.lectures.order_by(Lecture.order).all()
        lectures_payload = [
            {
                'lectureId': lecture.id,
                'title': lecture.title,
                'order': lecture.order,
            }
            for lecture in lectures
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
        return error_response('Question not in lecture.', 'QUESTION_NOT_IN_LECTURE', 400)

    summary, items = grade_practice_submission(lecture_id, answers_v1)
    submitted_at = datetime.utcnow().isoformat()

    return jsonify(
        {
            'lectureId': lecture.id,
            'submittedAt': submitted_at,
            'deprecatedInput': deprecated_input,
            'summary': summary,
            'items': items,
        }
    )


@api_practice_bp.route('/lecture/<int:lecture_id>/result')
def lecture_result(lecture_id):
    lecture = Lecture.query.get(lecture_id)
    if lecture is None:
        return error_response('Lecture not found.', 'LECTURE_NOT_FOUND', 404)

    include_answer = request.args.get('includeAnswer', 'true').lower() == 'true'
    questions = get_lecture_questions_ordered(lecture_id) or []
    questions_payload = []
    for question in questions:
        choices = question.choices.order_by(Choice.choice_number).all()
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
                question_payload['correctChoiceNumbers'] = question.correct_choice_numbers
        questions_payload.append(question_payload)

    return jsonify(
        {
            'lectureId': lecture.id,
            'title': lecture.title,
            'questions': questions_payload,
        }
    )
