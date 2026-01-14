"""관리 Blueprint - 블록, 강의, 시험 CRUD"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import shutil
from app import db
from app.models import Block, Lecture, PreviousExam, Question, Choice, LectureMaterial, LectureChunk
from app.services.exam_cleanup import delete_exam_with_assets
from app.services.markdown_images import strip_markdown_images
from pathlib import Path
from sqlalchemy import text

manage_bp = Blueprint('manage', __name__)


@manage_bp.before_request
def restrict_to_local_admin():
    if not current_app.config.get('LOCAL_ADMIN_ONLY'):
        return None
    remote_addr = request.remote_addr or ''
    if remote_addr not in {'127.0.0.1', '::1'}:
        abort(404)
    return None


def allowed_file(filename, allowed_extensions):
    """허용된 파일 확장자 확인"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def _resolve_upload_folder() -> Path:
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        upload_folder = Path(current_app.static_folder) / 'uploads'
    return Path(upload_folder)


# ===== 대시보드 =====

@manage_bp.route('/')
def dashboard():
    """관리 대시보드"""
    block_count = Block.query.count()
    lecture_count = Lecture.query.count()
    exam_count = PreviousExam.query.count()
    question_count = Question.query.count()
    unclassified_count = Question.query.filter_by(is_classified=False).count()
    
    # 최근 추가된 시험
    recent_exams = PreviousExam.query.order_by(PreviousExam.created_at.desc()).limit(5).all()
    
    return render_template('manage/dashboard.html', 
                         block_count=block_count,
                         lecture_count=lecture_count,
                         exam_count=exam_count,
                         question_count=question_count,
                         unclassified_count=unclassified_count,
                         recent_exams=recent_exams)


# ===== 블록 관리 =====

@manage_bp.route('/blocks')
def list_blocks():
    """블록 목록"""
    blocks = Block.query.order_by(Block.order).all()
    return render_template('manage/blocks.html', blocks=blocks)


@manage_bp.route('/block/new', methods=['GET', 'POST'])
def create_block():
    """새 블록 생성"""
    if request.method == 'POST':
        block = Block(
            name=request.form.get('name'),
            description=request.form.get('description'),
            order=int(request.form.get('order', 0))
        )
        db.session.add(block)
        db.session.commit()
        flash('블록이 생성되었습니다.', 'success')
        return redirect(url_for('manage.list_blocks'))
    return render_template('manage/block_form.html', block=None)


@manage_bp.route('/block/<int:block_id>/edit', methods=['GET', 'POST'])
def edit_block(block_id):
    """블록 수정"""
    block = Block.query.get_or_404(block_id)
    if request.method == 'POST':
        block.name = request.form.get('name')
        block.description = request.form.get('description')
        block.order = int(request.form.get('order', 0))
        db.session.commit()
        flash('블록이 수정되었습니다.', 'success')
        return redirect(url_for('manage.list_blocks'))
    return render_template('manage/block_form.html', block=block)


@manage_bp.route('/block/<int:block_id>/delete', methods=['POST'])
def delete_block(block_id):
    """블록 삭제"""
    block = Block.query.get_or_404(block_id)
    db.session.delete(block)
    db.session.commit()
    flash('블록이 삭제되었습니다.', 'success')
    return redirect(url_for('manage.list_blocks'))


# ===== 강의 관리 =====

@manage_bp.route('/block/<int:block_id>/lectures')
def list_lectures(block_id):
    """블록 내 강의 목록"""
    block = Block.query.get_or_404(block_id)
    lectures = block.lectures.order_by(Lecture.order).all()
    return render_template('manage/lectures.html', block=block, lectures=lectures)


@manage_bp.route('/block/<int:block_id>/lecture/new', methods=['GET', 'POST'])
def create_lecture(block_id):
    """새 강의 생성"""
    block = Block.query.get_or_404(block_id)
    if request.method == 'POST':
        lecture = Lecture(
            block_id=block_id,
            title=request.form.get('title'),
            professor=request.form.get('professor'),
            order=int(request.form.get('order', 1)),
        )
        db.session.add(lecture)
        db.session.commit()
        flash('강의가 생성되었습니다.', 'success')
        return redirect(url_for('manage.list_lectures', block_id=block_id))
    
    # 다음 순서 번호 계산 (현재 최대값 + 1)
    max_order = db.session.query(db.func.max(Lecture.order)).filter_by(block_id=block_id).scalar()
    next_order = (max_order or 0) + 1
    
    return render_template('manage/lecture_form.html', block=block, lecture=None, next_order=next_order)



@manage_bp.route('/lecture/<int:lecture_id>/edit', methods=['GET', 'POST'])
def edit_lecture(lecture_id):
    """강의 수정"""
    lecture = Lecture.query.get_or_404(lecture_id)
    if request.method == 'POST':
        lecture.title = request.form.get('title')
        lecture.professor = request.form.get('professor')
        lecture.order = int(request.form.get('order', 1))
        db.session.commit()
        flash('강의가 수정되었습니다.', 'success')
        return redirect(url_for('manage.list_lectures', block_id=lecture.block_id))
    return render_template('manage/lecture_form.html', block=lecture.block, lecture=lecture)


@manage_bp.route('/lecture/<int:lecture_id>/upload-note', methods=['POST'])
def upload_lecture_note(lecture_id):
    """강의 노트 PDF 업로드 및 인덱싱"""
    lecture = Lecture.query.get_or_404(lecture_id)

    if 'pdf_file' not in request.files:
        return jsonify({'success': False, 'error': 'PDF 파일이 필요합니다.'}), 400

    file = request.files['pdf_file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '파일명이 없습니다.'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'error': 'PDF 파일만 업로드 가능합니다.'}), 400

    try:
        upload_folder = _resolve_upload_folder()
        target_dir = upload_folder / 'lecture_notes' / str(lecture.id)
        target_dir.mkdir(parents=True, exist_ok=True)

        original_name = Path(file.filename).name
        safe_name = secure_filename(original_name)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        stored_name = f"{timestamp}_{safe_name}"
        stored_path = target_dir / stored_name
        file.save(stored_path)

        relative_path = os.path.relpath(stored_path, upload_folder)
        relative_path = Path(relative_path).as_posix()

        material = LectureMaterial(
            lecture_id=lecture.id,
            file_path=relative_path,
            original_filename=original_name,
            status=LectureMaterial.STATUS_UPLOADED,
        )
        db.session.add(material)
        db.session.commit()

        from app.services.lecture_indexer import index_material
        index_result = index_material(material)

        return jsonify(
            {
                'success': True,
                'material_id': material.id,
                'chunks': index_result.get('chunks', 0),
                'pages': index_result.get('pages', 0),
            }
        )
    except Exception as e:
        current_app.logger.exception('Lecture note indexing failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@manage_bp.route('/lecture/<int:lecture_id>/note-status')
def lecture_note_status(lecture_id):
    """강의 노트 업로드 상태 조회"""
    lecture = Lecture.query.get_or_404(lecture_id)
    materials = (
        LectureMaterial.query.filter_by(lecture_id=lecture.id)
        .order_by(LectureMaterial.uploaded_at.desc())
        .all()
    )
    payload = []
    for material in materials:
        chunk_count = LectureChunk.query.filter_by(material_id=material.id).count()
        payload.append(
            {
                'id': material.id,
                'originalFilename': material.original_filename,
                'filePath': material.file_path,
                'status': material.status,
                'uploadedAt': material.uploaded_at.isoformat() if material.uploaded_at else None,
                'indexedAt': material.indexed_at.isoformat() if material.indexed_at else None,
                'chunks': chunk_count,
            }
        )

    return jsonify({'success': True, 'materials': payload})


@manage_bp.route('/lecture/<int:lecture_id>/note/<int:material_id>/delete', methods=['POST'])
def delete_lecture_note(lecture_id, material_id):
    """Delete an uploaded lecture note and related chunks/FTS rows."""
    lecture = Lecture.query.get_or_404(lecture_id)
    material = LectureMaterial.query.filter_by(id=material_id, lecture_id=lecture.id).first_or_404()

    try:
        chunk_ids = [
            row.id for row in LectureChunk.query.filter_by(material_id=material.id).all()
        ]
        if chunk_ids:
            placeholders = ", ".join([f":id_{idx}" for idx in range(len(chunk_ids))])
            params = {f"id_{idx}": cid for idx, cid in enumerate(chunk_ids)}
            try:
                db.session.execute(
                    text(f"DELETE FROM lecture_chunks_fts WHERE chunk_id IN ({placeholders})"),
                    params,
                )
            except Exception:
                current_app.logger.warning("FTS delete failed for material %s", material.id)

        file_path = Path(material.file_path)
        if not file_path.is_absolute():
            file_path = _resolve_upload_folder() / file_path
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            current_app.logger.warning("Lecture note file delete failed: %s", file_path)

        db.session.delete(material)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Failed to delete lecture note %s", material.id)
        return jsonify({'success': False, 'error': str(e)}), 500


@manage_bp.route('/lecture/<int:lecture_id>')
def view_lecture(lecture_id):
    """강의 상세보기 - 분류된 문제 목록"""
    lecture = Lecture.query.get_or_404(lecture_id)
    
    # 해당 강의에 분류된 문제들 가져오기
    from app.models import Question
    questions = Question.query.filter_by(lecture_id=lecture_id).order_by(Question.question_number).all()
    
    # 모든 블록과 강의 정보 가져오기 (이동 모달용)
    all_blocks = Block.query.order_by(Block.order).all()
    
    return render_template('manage/lecture_detail.html', 
                         lecture=lecture, 
                         block=lecture.block,
                         questions=questions,
                         all_blocks=all_blocks)


@manage_bp.route('/lecture/<int:lecture_id>/delete', methods=['POST'])
def delete_lecture(lecture_id):
    """강의 삭제"""
    lecture = Lecture.query.get_or_404(lecture_id)
    block_id = lecture.block_id
    db.session.delete(lecture)
    db.session.commit()
    flash('강의가 삭제되었습니다.', 'success')
    return redirect(url_for('manage.list_lectures', block_id=block_id))


# ===== 기출 시험 관리 =====

@manage_bp.route('/exams')
def list_exams():
    """기출 시험 관리 목록"""
    exams = PreviousExam.query.order_by(PreviousExam.exam_date.desc()).all()
    return render_template('manage/exams.html', exams=exams)


@manage_bp.route('/exam/new', methods=['GET', 'POST'])
def create_exam():
    """새 기출 시험 생성"""
    if request.method == 'POST':
        exam = PreviousExam(
            title=request.form.get('title'),
            subject=request.form.get('subject'),
            year=int(request.form.get('year')) if request.form.get('year') else None,
            term=request.form.get('term'),
            exam_date=datetime.strptime(request.form.get('exam_date'), '%Y-%m-%d').date() 
                      if request.form.get('exam_date') else None,
            description=request.form.get('description')
        )
        db.session.add(exam)
        db.session.commit()
        flash('기출 시험이 생성되었습니다.', 'success')
        return redirect(url_for('manage.list_exams'))
    return render_template('manage/exam_form.html', exam=None)


@manage_bp.route('/exam/<int:exam_id>/edit', methods=['GET', 'POST'])
def edit_exam(exam_id):
    """기출 시험 수정"""
    exam = PreviousExam.query.get_or_404(exam_id)
    if request.method == 'POST':
        exam.title = request.form.get('title')
        exam.subject = request.form.get('subject')
        exam.year = int(request.form.get('year')) if request.form.get('year') else None
        exam.term = request.form.get('term')
        exam.exam_date = datetime.strptime(request.form.get('exam_date'), '%Y-%m-%d').date() \
                         if request.form.get('exam_date') else None
        exam.description = request.form.get('description')
        db.session.commit()
        flash('기출 시험이 수정되었습니다.', 'success')
        return redirect(url_for('manage.list_exams'))
    return render_template('manage/exam_form.html', exam=exam)


@manage_bp.route('/exam/<int:exam_id>/delete', methods=['POST'])
def delete_exam(exam_id):
    """기출 시험 삭제"""
    exam = PreviousExam.query.get_or_404(exam_id)
    delete_exam_with_assets(exam)
    flash('기출 시험이 삭제되었습니다.', 'success')
    return redirect(url_for('manage.list_exams'))


# ===== 문제 관리 =====

@manage_bp.route('/exam/<int:exam_id>/question/new', methods=['GET', 'POST'])
def create_question(exam_id):
    """새 문제 생성"""
    exam = PreviousExam.query.get_or_404(exam_id)
    if request.method == 'POST':
        # 이미지 업로드 처리
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename, {'png', 'jpg', 'jpeg', 'gif'}):
                filename = secure_filename(file.filename)
                unique_filename = f"{exam_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename))
                image_path = unique_filename
        
        question = Question(
            exam_id=exam_id,
            question_number=int(request.form.get('question_number', 1)),
            content=request.form.get('content'),
            image_path=image_path,
            answer=request.form.get('answer'),
            explanation=request.form.get('explanation'),
            difficulty=int(request.form.get('difficulty', 3)),
            tags=request.form.get('tags'),
            is_classified=False  # 수동 생성 시에도 기본값은 미분류
        )
        db.session.add(question)
        db.session.commit()
        flash('문제가 생성되었습니다.', 'success')
        return redirect(url_for('exam.view_exam', exam_id=exam_id))
    return render_template('manage/question_form.html', exam=exam, question=None)


# ===== PDF 업로드 =====

@manage_bp.route('/upload-pdf', methods=['GET', 'POST'])
def upload_pdf():
    """PDF 파일 업로드 및 파싱"""
    if request.method == 'POST':
        # 필수 필드 확인
        if 'pdf_file' not in request.files:
            flash('PDF 파일을 선택해주세요.', 'error')
            return redirect(request.url)
        
        file = request.files['pdf_file']
        if file.filename == '':
            flash('파일이 선택되지 않았습니다.', 'error')
            return redirect(request.url)
        
        if not file.filename.lower().endswith('.pdf'):
            flash('PDF 파일만 업로드 가능합니다.', 'error')
            return redirect(request.url)
        
        title = request.form.get('title')
        if not title:
            flash('시험 이름을 입력해주세요.', 'error')
            return redirect(request.url)
        
        try:
            parser_mode = current_app.config.get('PDF_PARSER_MODE', 'legacy')
            if parser_mode == 'experimental':
                from app.services.pdf_parser_experimental import parse_pdf_to_questions
            else:
                from app.services.pdf_parser import parse_pdf_to_questions
            
            # PDF 파일 임시 저장
            tmp_path = None
            crop_dir = None
            crop_question_count = 0
            crop_image_count = 0
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name
            
            # 시험 레코드 생성 (prefix 용)
            exam_prefix = secure_filename(title.replace(' ', '_'))[:20]
            
            # PDF 파싱 (이미지는 uploads 폴더에 저장)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            questions_data = parse_pdf_to_questions(tmp_path, upload_folder, exam_prefix)
            
            # 임시 파일 삭제
            if not questions_data:
                flash('문제를 추출할 수 없습니다. PDF 형식을 확인해주세요.', 'error')
                return redirect(request.url)
            
            # 시험 레코드 생성
            exam = PreviousExam(
                title=title,
                subject=request.form.get('subject'),
                year=int(request.form.get('year')) if request.form.get('year') else None,
                term=request.form.get('term'),
                source_file=secure_filename(file.filename)
            )
            db.session.add(exam)
            db.session.flush()

            from app.services.pdf_cropper import crop_pdf_to_questions, get_exam_crop_dir
            crop_dir = get_exam_crop_dir(exam.id, upload_folder)
            crop_result = crop_pdf_to_questions(tmp_path, exam.id, upload_folder=upload_folder)
            crop_meta = crop_result.get('meta') or {}
            crop_question_count = len(crop_meta.get('questions', []))
            crop_image_count = len(crop_result.get('question_images', {}))
            
            question_count = 0
            choice_count = 0
            
            for q_data in questions_data:
                # 문제 유형 결정
                answer_count = len(q_data.get('answer_options', []))
                has_options = len(q_data.get('options', [])) > 0
                
                if not has_options:
                    q_type = Question.TYPE_SHORT_ANSWER
                elif answer_count > 1:
                    q_type = Question.TYPE_MULTIPLE_RESPONSE
                else:
                    q_type = Question.TYPE_MULTIPLE_CHOICE
                
                # Question 생성
                question = Question(
                    exam_id=exam.id,
                    question_number=q_data['question_number'],
                    content=q_data.get('content', ''),
                    image_path=q_data.get('image_path'),
                    q_type=q_type,
                    answer=','.join(map(str, q_data.get('answer_options', []))),
                    correct_answer_text=q_data.get('answer_text') if q_type == Question.TYPE_SHORT_ANSWER else None,
                    explanation=q_data.get('answer_text') if q_type != Question.TYPE_SHORT_ANSWER else None,
                    is_classified=False,
                    lecture_id=None
                )
                db.session.add(question)
                db.session.flush()
                
                # Choice 생성
                for opt in q_data.get('options', []):
                    if opt.get('content') or opt.get('image_path'):
                        choice = Choice(
                            question_id=question.id,
                            choice_number=opt['number'],
                            content=opt.get('content', ''),
                            image_path=opt.get('image_path'),
                            is_correct=opt.get('is_correct', False)
                        )
                        db.session.add(choice)
                        choice_count += 1
                
                question_count += 1
            
            db.session.commit()
            flash(f'PDF 파싱 완료! {question_count}개 문제, {choice_count}개 선택지가 저장되었습니다.', 'success')
            if crop_image_count:
                flash(f'Original images created: {crop_image_count}', 'success')
            if crop_question_count and crop_question_count != question_count:
                flash('Crop count differs from parsed question count. Verify the exam.', 'error')
            return redirect(url_for('manage.list_exams'))
            
        except ImportError as e:
            db.session.rollback()
            if crop_dir:
                shutil.rmtree(crop_dir, ignore_errors=True)
            flash(f'PDF 파서를 불러올 수 없습니다. pdfplumber 설치가 필요합니다: {str(e)}', 'error')
            return redirect(request.url)
        except RuntimeError as e:
            db.session.rollback()
            if crop_dir:
                shutil.rmtree(crop_dir, ignore_errors=True)
            flash(f'PDF crop error: {str(e)}', 'error')
            return redirect(request.url)
        except Exception as e:
            db.session.rollback()
            if crop_dir:
                shutil.rmtree(crop_dir, ignore_errors=True)
            flash(f'PDF 파싱 오류: {str(e)}', 'error')
            return redirect(request.url)
    
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return render_template('manage/pdf_upload.html')


# ===== 문제 수정 =====

@manage_bp.route('/question/<int:question_id>/edit', methods=['GET', 'POST'])
def edit_question(question_id):
    """문제 수정"""
    from app.models import Question, Choice
    
    question = Question.query.get_or_404(question_id)
    exam = question.exam
    from_practice = request.args.get('from_practice', '0') == '1'
    
    if request.method == 'POST':
        # 문제 내용 수정
        raw_content = request.form.get('content', '')
        uploaded_image = request.form.get('uploaded_image', '').strip()
        remove_image = request.form.get('remove_image', '0') == '1'
        upload_folder = current_app.config.get('UPLOAD_FOLDER') or os.path.join(
            current_app.static_folder, 'uploads'
        )
        upload_relative = os.path.relpath(
            os.fspath(upload_folder), os.fspath(current_app.static_folder)
        ).replace('\\', '/').strip('/')
        if upload_relative == '.':
            upload_relative = ''

        if uploaded_image:
            cleaned_content, _markdown_filename = strip_markdown_images(
                raw_content, upload_relative, keep_unmatched=False
            )
        else:
            cleaned_content, _markdown_filename = strip_markdown_images(
                raw_content, upload_relative, keep_unmatched=True
            )

        question.content = cleaned_content
        question.explanation = request.form.get('explanation', '')
        question.q_type = request.form.get('q_type', question.q_type)

        if uploaded_image:
            question.image_path = uploaded_image
        elif remove_image:
            question.image_path = None
        elif _markdown_filename:
            question.image_path = _markdown_filename
        
        # 강의 분류 변경
        new_lecture_id = request.form.get('lecture_id')
        if new_lecture_id:
            from app.models import Lecture
            new_lecture = Lecture.query.get(int(new_lecture_id))
            if new_lecture:
                question.lecture_id = new_lecture.id
        
        # 주관식 정답 수정
        if question.q_type == Question.TYPE_SHORT_ANSWER:
            question.correct_answer_text = request.form.get('correct_answer_text', '')
            question.answer = request.form.get('correct_answer_text', '')
            # 주관식으로 변경 시 기존 선택지 모두 삭제
            for choice in question.choices.all():
                db.session.delete(choice)
        else:
            # 객관식 선택지 수정
            correct_answers = request.form.getlist('correct_answers')
            question.answer = ','.join(correct_answers)
            
            # 삭제된 선택지 처리
            deleted_choices_str = request.form.get('deleted_choices', '')
            if deleted_choices_str:
                deleted_ids = [int(x) for x in deleted_choices_str.split(',') if x.strip()]
                for choice_id in deleted_ids:
                    choice_to_delete = Choice.query.get(choice_id)
                    if choice_to_delete and choice_to_delete.question_id == question.id:
                        db.session.delete(choice_to_delete)
            
            # 폼에서 선택지 데이터 수집
            choice_data = []
            i = 1
            while True:
                choice_content = request.form.get(f'choice_{i}')
                if choice_content is None:
                    break
                is_correct = str(i) in correct_answers
                choice_data.append({
                    'number': i,
                    'content': choice_content,
                    'is_correct': is_correct
                })
                i += 1
            
            # 기존 선택지 가져오기 (삭제되지 않은 것들)
            existing_choices = list(question.choices.filter(
                ~Choice.id.in_([int(x) for x in deleted_choices_str.split(',') if x.strip()]) if deleted_choices_str else True
            ).order_by(Choice.choice_number).all())
            
            # 기존 선택지 업데이트 또는 새 선택지 생성
            for idx, data in enumerate(choice_data):
                if idx < len(existing_choices):
                    # 기존 선택지 업데이트
                    choice = existing_choices[idx]
                    choice.choice_number = data['number']
                    choice.content = data['content']
                    choice.is_correct = data['is_correct']
                else:
                    # 새 선택지 생성
                    new_choice = Choice(
                        question_id=question.id,
                        choice_number=data['number'],
                        content=data['content'],
                        is_correct=data['is_correct']
                    )
                    db.session.add(new_choice)
            
            # 남는 기존 선택지 삭제 (폼에서 더 적게 제출된 경우)
            for idx in range(len(choice_data), len(existing_choices)):
                db.session.delete(existing_choices[idx])
        
        db.session.commit()
        
        # 연습 모드에서 왔으면 창 닫기 페이지 표시
        if request.form.get('from_practice') == '1':
            return render_template('manage/edit_complete.html')
        
        flash('문제가 수정되었습니다.', 'success')
        return redirect(url_for('exam.view_question', exam_id=exam.id, question_number=question.question_number))
    
    blocks = Block.query.order_by(Block.order).all()
    original_image_url = None
    upload_folder = current_app.config.get('UPLOAD_FOLDER') or os.path.join(
        current_app.static_folder, 'uploads'
    )
    from app.services.pdf_cropper import find_question_crop_image, to_static_relative
    crop_path = find_question_crop_image(exam.id, question.question_number, upload_folder=upload_folder)
    if crop_path:
        relative_path = to_static_relative(crop_path, static_root=current_app.static_folder)
        if relative_path:
            original_image_url = url_for('static', filename=relative_path)
    return render_template(
        'manage/question_edit.html',
        question=question,
        exam=exam,
        blocks=blocks,
        from_practice=from_practice,
        original_image_url=original_image_url,
    )


# ===== 문제 일괄 관리 =====

@manage_bp.route('/questions/move', methods=['POST'])
def move_questions():
    """선택한 문제 이동"""
    from app.models import Question
    
    data = request.json
    question_ids = data.get('question_ids', [])
    target_lecture_id = data.get('target_lecture_id')
    
    if not question_ids:
        return {'success': False, 'error': '선택된 문제가 없습니다.'}, 400
    
    if not target_lecture_id:
        return {'success': False, 'error': '이동할 강의가 지정되지 않았습니다.'}, 400
        
    try:
        Question.query.filter(Question.id.in_(question_ids)).update(
            {'lecture_id': target_lecture_id},
            synchronize_session=False
        )
        db.session.commit()
        return {'success': True, 'moved_count': len(question_ids)}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 500


@manage_bp.route('/questions/reset', methods=['POST'])
def reset_questions():
    """선택한 문제 분류 초기화 (미분류로)"""
    from app.models import Question
    
    data = request.json
    question_ids = data.get('question_ids', [])
    
    if not question_ids:
        return {'success': False, 'error': '선택된 문제가 없습니다.'}, 400
        
    try:
        Question.query.filter(Question.id.in_(question_ids)).update(
            {'lecture_id': None},
            synchronize_session=False
        )
        db.session.commit()
        return {'success': True, 'reset_count': len(question_ids)}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 500


@manage_bp.route('/upload-image', methods=['POST'])
def upload_image():
    """클립보드 이미지 업로드"""
    import uuid
    
    if 'image' not in request.files:
        return {'success': False, 'error': '이미지가 없습니다.'}, 400
    
    file = request.files['image']
    if file.filename == '':
        return {'success': False, 'error': '파일명이 없습니다.'}, 400
    
    # 고유 파일명 생성
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'png'
    if ext not in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
        return {'success': False, 'error': '허용되지 않는 이미지 형식입니다.'}, 400
    
    filename = f"{uuid.uuid4().hex}.{ext}"
    
    # 저장 경로
    upload_folder = current_app.config.get('UPLOAD_FOLDER') or os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    
    try:
        file.save(filepath)
        # 마크다운 이미지 경로 반환
        relative_folder = os.path.relpath(upload_folder, current_app.static_folder)
        relative_folder = relative_folder.replace('\\', '/').strip('/')
        image_url = url_for('static', filename=f"{relative_folder}/{filename}")
        return {'success': True, 'url': image_url, 'filename': filename}
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500
