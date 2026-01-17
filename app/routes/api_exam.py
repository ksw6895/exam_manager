"""JSON API for exam screens (unclassified queue)."""
from flask import Blueprint, request, jsonify, current_app, abort
from sqlalchemy import or_

from app.models import PreviousExam, Question, Block, Lecture
from app.services.folder_scope import parse_bool, resolve_lecture_ids

api_exam_bp = Blueprint('api_exam', __name__, url_prefix='/api/exam')


@api_exam_bp.before_request
def restrict_to_local_admin():
    if not current_app.config.get('LOCAL_ADMIN_ONLY'):
        return None
    remote_addr = request.remote_addr or ''
    if remote_addr not in {'127.0.0.1', '::1'}:
        abort(404)
    return None


def ok(data=None, status=200):
    return jsonify({'ok': True, 'data': data}), status


def _exam_payload(exam):
    return {
        'id': exam.id,
        'title': exam.title,
        'examDate': exam.exam_date.isoformat() if exam.exam_date else None,
        'questionCount': exam.question_count,
    }


def _lecture_payload(lecture):
    return {
        'id': lecture.id,
        'title': lecture.title,
        'blockId': lecture.block_id,
        'blockName': lecture.block.name if lecture.block else None,
        'folderId': lecture.folder_id,
    }


def _block_payload(block):
    return {
        'id': block.id,
        'name': block.name,
        'lectures': [_lecture_payload(lecture) for lecture in block.lectures.order_by(Lecture.order)],
    }


def _question_payload(question):
    content = question.content or ''
    snippet = content.replace('\n', ' ').strip()
    if len(snippet) > 160:
        snippet = snippet[:157] + '...'
    return {
        'id': question.id,
        'examId': question.exam_id,
        'examTitle': question.exam.title if question.exam else None,
        'questionNumber': question.question_number,
        'type': question.q_type,
        'lectureId': question.lecture_id,
        'lectureTitle': question.lecture.title if question.lecture else None,
        'blockId': question.lecture.block_id if question.lecture else None,
        'blockName': question.lecture.block.name if question.lecture else None,
        'lectureFolderId': question.lecture.folder_id if question.lecture else None,
        'isClassified': question.is_classified,
        'snippet': snippet,
        'hasImage': bool(question.image_path),
    }


@api_exam_bp.get('/unclassified')
def list_unclassified():
    status = request.args.get('status', 'all')
    exam_id = request.args.get('examId')
    query = request.args.get('query', '').strip()
    block_id = request.args.get('blockId') or request.args.get('block_id')
    folder_id = request.args.get('folderId') or request.args.get('folder_id')
    include_descendants = parse_bool(
        request.args.get('includeDescendants') or request.args.get('include_descendants'),
        True,
    )
    filter_scope = parse_bool(
        request.args.get('filterScope') or request.args.get('filter_scope'),
        False,
    )

    try:
        limit = int(request.args.get('limit', 200))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        limit = 200
        offset = 0

    q = Question.query
    if status == 'unclassified':
        q = q.filter_by(is_classified=False)
    elif status == 'classified':
        q = q.filter_by(is_classified=True)
    if exam_id:
        try:
            exam_id_value = int(exam_id)
            q = q.filter(Question.exam_id == exam_id_value)
        except ValueError:
            return jsonify(
                {'ok': False, 'code': 'INVALID_EXAM_ID', 'message': 'Invalid exam id.'}
            ), 400
    if query:
        q = q.filter(Question.content.contains(query))

    block_id_value = None
    if block_id:
        try:
            block_id_value = int(block_id)
        except ValueError:
            return jsonify(
                {'ok': False, 'code': 'INVALID_BLOCK_ID', 'message': 'Invalid block id.'}
            ), 400
    folder_id_value = None
    if folder_id:
        try:
            folder_id_value = int(folder_id)
        except ValueError:
            return jsonify(
                {'ok': False, 'code': 'INVALID_FOLDER_ID', 'message': 'Invalid folder id.'}
            ), 400

    lecture_ids = resolve_lecture_ids(block_id_value, folder_id_value, include_descendants)
    if filter_scope and lecture_ids is not None:
        if status == 'classified':
            q = q.filter(Question.lecture_id.in_(lecture_ids))
        elif status == 'all':
            q = q.filter(or_(Question.lecture_id.is_(None), Question.lecture_id.in_(lecture_ids)))

    total = q.count()
    questions = (
        q.order_by(Question.is_classified, Question.exam_id, Question.question_number)
        .offset(offset)
        .limit(limit)
        .all()
    )

    blocks = Block.query.order_by(Block.order).all()
    exams = PreviousExam.query.order_by(PreviousExam.created_at.desc()).all()
    unclassified_count = Question.query.filter_by(is_classified=False).count()

    candidate_lectures = None
    if lecture_ids is not None:
        if lecture_ids:
            lecture_rows = (
                Lecture.query.filter(Lecture.id.in_(lecture_ids))
                .order_by(Lecture.order)
                .all()
            )
            candidate_lectures = [_lecture_payload(lecture) for lecture in lecture_rows]
        else:
            candidate_lectures = []

    return ok(
        {
            'items': [_question_payload(question) for question in questions],
            'total': total,
            'offset': offset,
            'limit': limit,
            'unclassifiedCount': unclassified_count,
            'blocks': [_block_payload(block) for block in blocks],
            'exams': [_exam_payload(exam) for exam in exams],
            'scope': {
                'blockId': block_id_value,
                'folderId': folder_id_value,
                'includeDescendants': include_descendants,
                'filterScope': filter_scope,
                'lectureIds': lecture_ids,
            },
            'candidateLectures': candidate_lectures,
        }
    )
