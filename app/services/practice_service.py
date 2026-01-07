import json

from app import db
from app.models import Lecture, Question, StudyHistory


def map_question_type(question):
    if question.is_short_answer:
        return "short"
    return "mcq"


def normalize_answers_payload(raw_answers):
    if not isinstance(raw_answers, dict):
        return {}

    normalized = {}
    for key, value in raw_answers.items():
        try:
            question_id = str(int(key))
        except (TypeError, ValueError):
            continue

        if isinstance(value, dict) and "value" in value:
            normalized[question_id] = value.get("value")
        else:
            normalized[question_id] = value

    return normalized


def _is_numeric_key(value):
    return str(value).isdigit()


def _coerce_mcq_values(values):
    if not isinstance(values, list):
        return None
    normalized = []
    for entry in values:
        if isinstance(entry, bool):
            return None
        if isinstance(entry, int):
            normalized.append(entry)
            continue
        if isinstance(entry, float) and entry.is_integer():
            normalized.append(int(entry))
            continue
        return None
    return normalized


def _normalize_legacy_mcq_value(value):
    if value is None:
        return None
    if isinstance(value, list):
        return _coerce_mcq_values(value)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return [value]
    if isinstance(value, float) and value.is_integer():
        return [int(value)]
    if isinstance(value, str):
        parts = []
        for token in value.split(','):
            token = token.strip()
            if not token:
                continue
            if not token.isdigit():
                return None
            parts.append(int(token))
        return parts if parts else None
    return None


def _normalize_legacy_short_value(value):
    if value is None:
        return None
    if isinstance(value, list):
        value = ','.join([str(item) for item in value if item is not None])
    text = str(value).strip()
    return text if text else None


def _normalize_v1_mcq_value(value):
    if not isinstance(value, list):
        return None
    normalized = _coerce_mcq_values(value)
    if normalized is None:
        return None
    return normalized if normalized else None


def _normalize_v1_short_value(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if text else None


def normalize_practice_answers_payload(payload, lecture_questions_meta):
    if payload is None or not isinstance(payload, dict):
        return None, False, 'INVALID_PAYLOAD', 'Invalid request payload.'

    deprecated_input = False
    version = payload.get('version')
    if version is not None:
        if version != 1:
            return None, False, 'INVALID_VERSION', 'Only version 1 is supported.'
        answers_payload = payload.get('answers')
        if not isinstance(answers_payload, dict):
            return None, False, 'INVALID_PAYLOAD', 'Invalid answers payload.'
        answers_v1 = {}
        for key, item in answers_payload.items():
            if not _is_numeric_key(key):
                return None, False, 'INVALID_PAYLOAD', 'Invalid question id.'
            if not isinstance(item, dict):
                return None, False, 'INVALID_PAYLOAD', 'Invalid answer item.'
            answer_type = item.get('type')
            value = item.get('value')
            if answer_type not in ('mcq', 'short'):
                return None, False, 'INVALID_PAYLOAD', 'Invalid answer type.'
            if lecture_questions_meta and key in lecture_questions_meta:
                expected_type = 'short' if lecture_questions_meta[key] else 'mcq'
                if answer_type != expected_type:
                    return None, False, 'INVALID_PAYLOAD', 'Answer type mismatch.'
            if answer_type == 'mcq':
                normalized_value = _normalize_v1_mcq_value(value)
            else:
                normalized_value = _normalize_v1_short_value(value)
            if normalized_value is None:
                continue
            answers_v1[str(key)] = {
                'type': answer_type,
                'value': normalized_value,
            }
        return answers_v1, deprecated_input, None, None

    deprecated_input = True
    answers_payload = payload.get('answers') if 'answers' in payload else payload
    if not isinstance(answers_payload, dict):
        return None, True, 'INVALID_PAYLOAD', 'Invalid answers payload.'

    answers_v1 = {}
    for key, value in answers_payload.items():
        if not _is_numeric_key(key):
            continue
        if lecture_questions_meta and key in lecture_questions_meta:
            answer_type = 'short' if lecture_questions_meta[key] else 'mcq'
        elif isinstance(value, dict) and value.get('type') in ('mcq', 'short'):
            answer_type = value.get('type')
        elif isinstance(value, (list, int, float)):
            answer_type = 'mcq'
        else:
            answer_type = 'short'

        raw_value = value
        if isinstance(value, dict) and 'value' in value:
            raw_value = value.get('value')

        if answer_type == 'mcq':
            normalized_value = _normalize_legacy_mcq_value(raw_value)
        else:
            normalized_value = _normalize_legacy_short_value(raw_value)

        if normalized_value is None:
            continue

        answers_v1[str(key)] = {
            'type': answer_type,
            'value': normalized_value,
        }

    return answers_v1, deprecated_input, None, None


def grade_practice_submission(lecture_id, answers_v1):
    questions = get_lecture_questions_ordered(lecture_id) or []
    items = []

    all_total = len(questions)
    all_answered = 0
    all_correct = 0
    mcq_total = 0
    mcq_answered = 0
    mcq_correct = 0
    short_total = 0
    short_answered = 0
    short_correct = 0

    for question in questions:
        question_id = str(question.id)
        is_short = question.is_short_answer
        answer_entry = answers_v1.get(question_id)
        answer_type = 'short' if is_short else 'mcq'
        can_auto_grade = (not is_short) or bool(question.correct_answer_text)
        correct_answer = question.correct_choice_numbers if not is_short else None
        correct_answer_text = question.correct_answer_text if is_short else None

        if is_short:
            short_total += 1
        else:
            mcq_total += 1

        is_answered = False
        user_answer = None
        is_correct = None

        if answer_entry and answer_entry.get('type') == answer_type:
            if answer_type == 'mcq':
                value = answer_entry.get('value', [])
                if isinstance(value, list) and value:
                    is_answered = True
                    user_answer = value
            else:
                value = answer_entry.get('value', '')
                if isinstance(value, str) and value.strip():
                    is_answered = True
                    user_answer = value

        if is_answered:
            all_answered += 1
            if is_short:
                short_answered += 1
            else:
                mcq_answered += 1

            is_correct, correct_value = question.check_answer(user_answer)
            if is_short:
                correct_answer_text = correct_value
            else:
                correct_answer = correct_value

            if is_correct:
                all_correct += 1
                if is_short:
                    short_correct += 1
                else:
                    mcq_correct += 1

            # StudyHistory is append-only; multiple submissions are recorded by design.
            if is_answered:
                if answer_type == 'mcq':
                    serialized_answer = json.dumps(user_answer, ensure_ascii=True)
                else:
                    serialized_answer = str(user_answer)
                # Schema requires boolean; ungradable answers are stored as False.
                history = StudyHistory(
                    question_id=question.id,
                    is_correct=is_correct if is_correct is not None else False,
                    user_answer=serialized_answer,
                )
                db.session.add(history)

        item = {
            'questionId': question.id,
            'type': answer_type,
            'isAnswered': is_answered,
            'isCorrect': is_correct,
            'userAnswer': user_answer,
            'canAutoGrade': can_auto_grade,
        }
        if answer_type == 'mcq':
            item['correctAnswer'] = correct_answer
        else:
            item['correctAnswerText'] = correct_answer_text
        items.append(item)

    db.session.commit()

    summary = {
        'all': {'total': all_total, 'answered': all_answered, 'correct': all_correct},
        'mcq': {'total': mcq_total, 'answered': mcq_answered, 'correct': mcq_correct},
        'short': {'total': short_total, 'answered': short_answered, 'correct': short_correct},
    }

    return summary, items


def get_lecture_questions_ordered(lecture_id):
    lecture = Lecture.query.get(lecture_id)
    if lecture is None:
        return None
    return lecture.questions.order_by(Question.question_number).all()


def get_question_by_seq(lecture_id, seq):
    questions = get_lecture_questions_ordered(lecture_id)
    if not questions:
        return None, None, questions
    index = seq - 1
    if index < 0 or index >= len(questions):
        return None, None, questions
    return questions[index], index, questions


def get_prev_next(ordered_questions, index):
    if not ordered_questions or index is None:
        return None, None

    prev_question_id = None
    next_question_id = None

    if index > 0:
        prev_question_id = ordered_questions[index - 1].id
    if index + 1 < len(ordered_questions):
        next_question_id = ordered_questions[index + 1].id

    return prev_question_id, next_question_id


def is_answered(answer):
    if answer is None:
        return False
    if isinstance(answer, list):
        return len(answer) > 0
    if isinstance(answer, str):
        return answer.strip() != ""
    return True


def build_question_groups(questions):
    objective_questions = []
    subjective_questions = []
    question_map = []
    question_meta = []
    objective_seq = 0
    subjective_seq = 0

    for idx, question in enumerate(questions):
        question_map.append({"id": question.id, "number": question.question_number})

        is_short = question.is_short_answer
        if is_short:
            subjective_seq += 1
            type_seq = subjective_seq
        else:
            objective_seq += 1
            type_seq = objective_seq

        meta = {
            "id": question.id,
            "number": question.question_number,
            "original_seq": idx + 1,
            "type_seq": type_seq,
            "type": map_question_type(question),
            "is_short_answer": is_short,
            "is_multiple_response": question.is_multiple_response,
        }

        question_meta.append(meta)
        if is_short:
            subjective_questions.append(meta)
        else:
            objective_questions.append(meta)

    return {
        "objective_questions": objective_questions,
        "subjective_questions": subjective_questions,
        "question_map": question_map,
        "question_meta": question_meta,
    }


def grade_questions(questions, answers, include_content=False):
    results = []
    answered_count = 0
    correct_count = 0
    objective_total = 0
    objective_answered = 0
    objective_correct = 0
    subjective_total = 0
    subjective_answered = 0
    subjective_correct = 0

    for idx, question in enumerate(questions):
        question_id = str(question.id)
        user_answer = answers.get(question_id)
        is_short = question.is_short_answer
        can_auto_grade = (not is_short) or bool(question.correct_answer_text)

        if is_short:
            subjective_total += 1
        else:
            objective_total += 1

        if not is_answered(user_answer):
            result = {
                "seq": idx + 1,
                "question_id": question.id,
                "user_answer": None,
                "correct_answer": question.correct_choice_numbers
                if not is_short
                else question.correct_answer_text,
                "is_correct": None,
                "is_short_answer": is_short,
                "can_auto_grade": can_auto_grade,
            }
            if include_content:
                result["content"] = question.content[:100] if question.content else ""
            results.append(result)
            continue

        answered_count += 1
        if is_short:
            subjective_answered += 1
        else:
            objective_answered += 1

        is_correct, correct_answer = question.check_answer(user_answer)

        if is_correct:
            correct_count += 1
            if is_short:
                subjective_correct += 1
            else:
                objective_correct += 1

        result = {
            "seq": idx + 1,
            "question_id": question.id,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "is_short_answer": is_short,
            "can_auto_grade": can_auto_grade,
        }
        if include_content:
            result["content"] = question.content[:100] if question.content else ""
        results.append(result)

        history = StudyHistory(
            question_id=question.id,
            is_correct=is_correct if is_correct is not None else False,
            user_answer=str(user_answer),
        )
        db.session.add(history)

    db.session.commit()

    counts = {
        "total": len(questions),
        "answered": answered_count,
        "correct": correct_count,
        "objective_total": objective_total,
        "objective_answered": objective_answered,
        "objective_correct": objective_correct,
        "subjective_total": subjective_total,
        "subjective_answered": subjective_answered,
        "subjective_correct": subjective_correct,
    }

    return counts, results
