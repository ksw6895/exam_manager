"""JSON API for manage screens (blocks/lectures/exams)."""
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app, abort, url_for

from app import db
import os
import shutil
from werkzeug.utils import secure_filename

from app.models import Block, Lecture, PreviousExam, Question, Choice
from app.services.exam_cleanup import delete_exam_with_assets
from app.services.markdown_images import strip_markdown_images
from app.services.db_guard import guard_write_request

api_manage_bp = Blueprint('api_manage', __name__, url_prefix='/api/manage')


@api_manage_bp.before_request
def restrict_to_local_admin():
    if not current_app.config.get('LOCAL_ADMIN_ONLY'):
        return None
    remote_addr = request.remote_addr or ''
    if remote_addr not in {'127.0.0.1', '::1'}:
        abort(404)
    return None


@api_manage_bp.before_request
def guard_read_only():
    blocked = guard_write_request()
    if blocked is not None:
        return blocked
    return None


def ok(data=None, status=200):
    return jsonify({'ok': True, 'data': data}), status


def error_response(message, code='BAD_REQUEST', status=400, details=None):
    payload = {'ok': False, 'code': code, 'message': message}
    if details is not None:
        payload['details'] = details
    return jsonify(payload), status


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            return None
    return None


def _format_date(value):
    return value.isoformat() if value else None


def _block_payload(block):
    return {
        'id': block.id,
        'name': block.name,
        'description': block.description,
        'order': block.order,
        'lectureCount': block.lecture_count,
        'questionCount': block.question_count,
        'createdAt': block.created_at.isoformat() if block.created_at else None,
        'updatedAt': block.updated_at.isoformat() if block.updated_at else None,
    }


def _lecture_payload(lecture):
    return {
        'id': lecture.id,
        'blockId': lecture.block_id,
        'blockName': lecture.block.name if lecture.block else None,
        'title': lecture.title,
        'professor': lecture.professor,
        'order': lecture.order,
        'description': lecture.description,
        'questionCount': lecture.question_count,
        'classifiedCount': lecture.classified_question_count,
        'createdAt': lecture.created_at.isoformat() if lecture.created_at else None,
        'updatedAt': lecture.updated_at.isoformat() if lecture.updated_at else None,
    }


def _exam_payload(exam):
    return {
        'id': exam.id,
        'title': exam.title,
        'examDate': _format_date(exam.exam_date),
        'subject': exam.subject,
        'year': exam.year,
        'term': exam.term,
        'description': exam.description,
        'questionCount': exam.question_count,
        'classifiedCount': exam.classified_count,
        'unclassifiedCount': exam.unclassified_count,
        'createdAt': exam.created_at.isoformat() if exam.created_at else None,
        'updatedAt': exam.updated_at.isoformat() if exam.updated_at else None,
    }


def _question_payload(question):
    return {
        'id': question.id,
        'questionNumber': question.question_number,
        'type': question.q_type,
        'lectureId': question.lecture_id,
        'lectureTitle': question.lecture.title if question.lecture else None,
        'isClassified': question.is_classified,
        'classificationStatus': question.classification_status,
        'hasImage': bool(question.image_path),
    }


def _choice_payload(choice):
    return {
        'id': choice.id,
        'number': choice.choice_number,
        'content': choice.content,
        'imagePath': choice.image_path,
        'isCorrect': choice.is_correct,
    }


def _question_detail_payload(question):
    original_image_url = None
    try:
        from app.services.pdf_cropper import find_question_crop_image, to_static_relative
        crop_path = find_question_crop_image(question.exam_id, question.question_number)
        if crop_path:
            relative_path = to_static_relative(crop_path, static_root=current_app.static_folder)
            if relative_path:
                original_image_url = url_for('static', filename=relative_path)
    except Exception:
        original_image_url = None
    return {
        'id': question.id,
        'examId': question.exam_id,
        'examTitle': question.exam.title if question.exam else None,
        'questionNumber': question.question_number,
        'type': question.q_type,
        'lectureId': question.lecture_id,
        'lectureTitle': question.lecture.title if question.lecture else None,
        'content': question.content,
        'explanation': question.explanation,
        'imagePath': question.image_path,
        'originalImageUrl': original_image_url,
        'answer': question.answer,
        'correctAnswerText': question.correct_answer_text,
        'choices': [_choice_payload(choice) for choice in question.choices.order_by(Choice.choice_number)],
    }


@api_manage_bp.get('/summary')
def manage_summary():
    block_count = Block.query.count()
    lecture_count = Lecture.query.count()
    exam_count = PreviousExam.query.count()
    question_count = Question.query.count()
    unclassified_count = Question.query.filter_by(is_classified=False).count()
    recent_exams = PreviousExam.query.order_by(PreviousExam.created_at.desc()).limit(5).all()

    return ok(
        {
            'counts': {
                'blocks': block_count,
                'lectures': lecture_count,
                'exams': exam_count,
                'questions': question_count,
                'unclassified': unclassified_count,
            },
            'recentExams': [_exam_payload(exam) for exam in recent_exams],
        }
    )


@api_manage_bp.get('/blocks')
def list_blocks():
    blocks = Block.query.order_by(Block.order).all()
    return ok([_block_payload(block) for block in blocks])


@api_manage_bp.post('/blocks')
def create_block():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    if not name:
        return error_response('Block name is required.', code='BLOCK_NAME_REQUIRED')

    block = Block(
        name=str(name),
        description=data.get('description'),
        order=int(data.get('order') or 0),
    )
    db.session.add(block)
    db.session.commit()
    return ok(_block_payload(block), status=201)


@api_manage_bp.get('/blocks/<int:block_id>')
def get_block(block_id):
    block = Block.query.get_or_404(block_id)
    return ok(_block_payload(block))


@api_manage_bp.put('/blocks/<int:block_id>')
def update_block(block_id):
    block = Block.query.get_or_404(block_id)
    data = request.get_json(silent=True) or {}
    if 'name' in data and data['name'] is not None:
        block.name = str(data['name'])
    if 'description' in data:
        block.description = data.get('description')
    if 'order' in data and data['order'] is not None:
        block.order = int(data['order'])
    db.session.commit()
    return ok(_block_payload(block))


@api_manage_bp.delete('/blocks/<int:block_id>')
def delete_block(block_id):
    block = Block.query.get_or_404(block_id)
    db.session.delete(block)
    db.session.commit()
    return ok({'id': block_id})


@api_manage_bp.get('/blocks/<int:block_id>/lectures')
def list_lectures(block_id):
    block = Block.query.get_or_404(block_id)
    lectures = block.lectures.order_by(Lecture.order).all()
    return ok(
        {
            'block': _block_payload(block),
            'lectures': [_lecture_payload(lecture) for lecture in lectures],
        }
    )


@api_manage_bp.post('/blocks/<int:block_id>/lectures')
def create_lecture(block_id):
    Block.query.get_or_404(block_id)
    data = request.get_json(silent=True) or {}
    title = data.get('title')
    if not title:
        return error_response('Lecture title is required.', code='LECTURE_TITLE_REQUIRED')

    lecture = Lecture(
        block_id=block_id,
        title=str(title),
        professor=data.get('professor'),
        order=int(data.get('order') or 1),
        description=data.get('description'),
    )
    db.session.add(lecture)
    db.session.commit()
    return ok(_lecture_payload(lecture), status=201)


@api_manage_bp.get('/lectures/<int:lecture_id>')
def get_lecture(lecture_id):
    lecture = Lecture.query.get_or_404(lecture_id)
    return ok(_lecture_payload(lecture))


@api_manage_bp.get('/lectures')
def list_all_lectures():
    lectures = Lecture.query.order_by(Lecture.order).all()
    return ok([_lecture_payload(lecture) for lecture in lectures])


@api_manage_bp.put('/lectures/<int:lecture_id>')
def update_lecture(lecture_id):
    lecture = Lecture.query.get_or_404(lecture_id)
    data = request.get_json(silent=True) or {}
    if 'title' in data and data['title'] is not None:
        lecture.title = str(data['title'])
    if 'professor' in data:
        lecture.professor = data.get('professor')
    if 'order' in data and data['order'] is not None:
        lecture.order = int(data['order'])
    if 'description' in data:
        lecture.description = data.get('description')
    db.session.commit()
    return ok(_lecture_payload(lecture))


@api_manage_bp.delete('/lectures/<int:lecture_id>')
def delete_lecture(lecture_id):
    lecture = Lecture.query.get_or_404(lecture_id)
    db.session.delete(lecture)
    db.session.commit()
    return ok({'id': lecture_id})


@api_manage_bp.get('/exams')
def list_exams():
    exams = PreviousExam.query.order_by(PreviousExam.exam_date.desc()).all()
    return ok([_exam_payload(exam) for exam in exams])


@api_manage_bp.post('/upload-pdf')
def upload_pdf():
    if 'pdf_file' not in request.files:
        return error_response('PDF file is required.', code='PDF_REQUIRED', status=400)

    file = request.files['pdf_file']
    if file.filename == '':
        return error_response('PDF filename is missing.', code='PDF_NAME_REQUIRED', status=400)

    if not file.filename.lower().endswith('.pdf'):
        return error_response('Only PDF files are allowed.', code='PDF_INVALID_TYPE', status=400)

    title = (request.form.get('title') or '').strip()
    if not title:
        return error_response('Exam title is required.', code='EXAM_TITLE_REQUIRED', status=400)

    try:
        parser_mode = current_app.config.get('PDF_PARSER_MODE', 'legacy')
        if parser_mode == 'experimental':
            from app.services.pdf_parser_experimental import parse_pdf_to_questions
        else:
            from app.services.pdf_parser import parse_pdf_to_questions

        tmp_path = None
        crop_dir = None
        crop_question_count = 0
        crop_image_count = 0
        crop_meta_url = None
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        exam_prefix = secure_filename(title.replace(' ', '_'))[:20]
        upload_folder = current_app.config['UPLOAD_FOLDER']
        questions_data = parse_pdf_to_questions(tmp_path, upload_folder, exam_prefix)
        if not questions_data:
            return error_response(
                'No questions extracted. Check PDF formatting.',
                code='PDF_PARSE_EMPTY',
                status=400,
            )

        exam = PreviousExam(
            title=title,
            subject=request.form.get('subject'),
            year=int(request.form.get('year')) if request.form.get('year') else None,
            term=request.form.get('term'),
            source_file=secure_filename(file.filename),
        )
        db.session.add(exam)
        db.session.flush()

        from app.services.pdf_cropper import crop_pdf_to_questions, get_exam_crop_dir, to_static_relative
        crop_dir = get_exam_crop_dir(exam.id, upload_folder)
        crop_result = crop_pdf_to_questions(tmp_path, exam.id, upload_folder=upload_folder)
        crop_meta = crop_result.get('meta') or {}
        crop_question_count = len(crop_meta.get('questions', []))
        crop_image_count = len(crop_result.get('question_images', {}))
        meta_path = crop_result.get('meta_path')
        if meta_path:
            relative_path = to_static_relative(meta_path, static_root=current_app.static_folder)
            if relative_path:
                crop_meta_url = url_for('static', filename=relative_path)

        question_count = 0
        choice_count = 0

        for q_data in questions_data:
            answer_count = len(q_data.get('answer_options', []))
            has_options = len(q_data.get('options', [])) > 0

            if not has_options:
                q_type = Question.TYPE_SHORT_ANSWER
            elif answer_count > 1:
                q_type = Question.TYPE_MULTIPLE_RESPONSE
            else:
                q_type = Question.TYPE_MULTIPLE_CHOICE

            question = Question(
                exam_id=exam.id,
                question_number=q_data['question_number'],
                content=q_data.get('content', ''),
                image_path=q_data.get('image_path'),
                q_type=q_type,
                answer=','.join(map(str, q_data.get('answer_options', []))),
                correct_answer_text=q_data.get('answer_text')
                if q_type == Question.TYPE_SHORT_ANSWER
                else None,
                explanation=q_data.get('answer_text')
                if q_type != Question.TYPE_SHORT_ANSWER
                else None,
                is_classified=False,
                lecture_id=None,
            )
            db.session.add(question)
            db.session.flush()

            for opt in q_data.get('options', []):
                if opt.get('content') or opt.get('image_path'):
                    choice = Choice(
                        question_id=question.id,
                        choice_number=opt['number'],
                        content=opt.get('content', ''),
                        image_path=opt.get('image_path'),
                        is_correct=opt.get('is_correct', False),
                    )
                    db.session.add(choice)
                    choice_count += 1

            question_count += 1

        db.session.commit()
        return ok(
            {
                'examId': exam.id,
                'questionCount': question_count,
                'choiceCount': choice_count,
                'cropImageCount': crop_image_count,
                'cropQuestionCount': crop_question_count,
                'cropMetaUrl': crop_meta_url,
            },
            status=201,
        )
    except ImportError as exc:
        db.session.rollback()
        if crop_dir:
            shutil.rmtree(crop_dir, ignore_errors=True)
        return error_response(
            f'PDF parser import failed: {exc}',
            code='PDF_PARSER_IMPORT',
            status=500,
        )
    except RuntimeError as exc:
        db.session.rollback()
        if crop_dir:
            shutil.rmtree(crop_dir, ignore_errors=True)
        return error_response(
            f'PDF crop error: {exc}',
            code='PDF_CROP_ERROR',
            status=500,
        )
    except Exception as exc:
        db.session.rollback()
        if crop_dir:
            shutil.rmtree(crop_dir, ignore_errors=True)
        return error_response(f'PDF parsing error: {exc}', code='PDF_PARSE_ERROR', status=500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@api_manage_bp.post('/exams')
def create_exam():
    data = request.get_json(silent=True) or {}
    title = data.get('title')
    if not title:
        return error_response('Exam title is required.', code='EXAM_TITLE_REQUIRED')

    exam = PreviousExam(
        title=str(title),
        exam_date=_parse_date(data.get('examDate') or data.get('exam_date')),
        subject=data.get('subject'),
        year=int(data['year']) if data.get('year') is not None else None,
        term=data.get('term'),
        description=data.get('description'),
    )
    db.session.add(exam)
    db.session.commit()
    return ok(_exam_payload(exam), status=201)


@api_manage_bp.get('/exams/<int:exam_id>')
def get_exam(exam_id):
    exam = PreviousExam.query.get_or_404(exam_id)
    questions = exam.questions.order_by(Question.question_number).all()
    return ok(
        {
            'exam': _exam_payload(exam),
            'questions': [_question_payload(question) for question in questions],
        }
    )


@api_manage_bp.get('/questions/<int:question_id>')
def get_question(question_id):
    question = Question.query.get_or_404(question_id)
    return ok(_question_detail_payload(question))


@api_manage_bp.put('/questions/<int:question_id>')
def update_question(question_id):
    question = Question.query.get_or_404(question_id)
    data = request.get_json(silent=True) or {}

    raw_content = data.get('content') or ''
    uploaded_image = (data.get('uploadedImage') or '').strip()
    remove_image = bool(data.get('removeImage'))

    upload_folder = current_app.config.get('UPLOAD_FOLDER') or os.path.join(
        current_app.static_folder, 'uploads'
    )
    upload_relative = os.path.relpath(
        os.fspath(upload_folder), os.fspath(current_app.static_folder)
    ).replace('\\', '/').strip('/')
    if upload_relative == '.':
        upload_relative = ''

    if uploaded_image:
        cleaned_content, markdown_filename = strip_markdown_images(
            raw_content, upload_relative, keep_unmatched=False
        )
    else:
        cleaned_content, markdown_filename = strip_markdown_images(
            raw_content, upload_relative, keep_unmatched=True
        )

    question.content = cleaned_content
    question.explanation = data.get('explanation') or ''
    q_type = data.get('type') or question.q_type
    question.q_type = q_type

    if uploaded_image:
        question.image_path = uploaded_image
    elif remove_image:
        question.image_path = None
    elif markdown_filename:
        question.image_path = markdown_filename

    if 'lectureId' in data:
        lecture_id = data.get('lectureId')
        if lecture_id:
            lecture = Lecture.query.get(int(lecture_id))
            if lecture:
                question.lecture_id = lecture.id
        else:
            question.lecture_id = None

    if q_type == Question.TYPE_SHORT_ANSWER:
        correct_text = data.get('correctAnswerText') or ''
        question.correct_answer_text = correct_text
        question.answer = correct_text
        for choice in question.choices.all():
            db.session.delete(choice)
    else:
        choices_payload = data.get('choices') or []
        correct_numbers = []
        for choice in choices_payload:
            if choice.get('isCorrect'):
                correct_numbers.append(str(choice.get('number')))
        question.answer = ','.join(correct_numbers)
        question.correct_answer_text = None
        for choice in question.choices.all():
            db.session.delete(choice)
        db.session.flush()
        for choice in choices_payload:
            content = choice.get('content', '')
            if content is None:
                content = ''
            new_choice = Choice(
                question_id=question.id,
                choice_number=int(choice.get('number') or 0),
                content=content,
                image_path=choice.get('imagePath'),
                is_correct=bool(choice.get('isCorrect')),
            )
            db.session.add(new_choice)

    db.session.commit()
    return ok(_question_detail_payload(question))


@api_manage_bp.put('/exams/<int:exam_id>')
def update_exam(exam_id):
    exam = PreviousExam.query.get_or_404(exam_id)
    data = request.get_json(silent=True) or {}
    if 'title' in data and data['title'] is not None:
        exam.title = str(data['title'])
    if 'examDate' in data or 'exam_date' in data:
        exam.exam_date = _parse_date(data.get('examDate') or data.get('exam_date'))
    if 'subject' in data:
        exam.subject = data.get('subject')
    if 'year' in data:
        exam.year = int(data['year']) if data.get('year') is not None else None
    if 'term' in data:
        exam.term = data.get('term')
    if 'description' in data:
        exam.description = data.get('description')
    db.session.commit()
    return ok(_exam_payload(exam))


@api_manage_bp.delete('/exams/<int:exam_id>')
def delete_exam(exam_id):
    exam = PreviousExam.query.get_or_404(exam_id)
    delete_exam_with_assets(exam)
    return ok({'id': exam_id})
