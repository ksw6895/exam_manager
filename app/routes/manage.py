"""관리 Blueprint - 블록, 강의, 시험 CRUD"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from app import db
from app.models import Block, Lecture, PreviousExam, Question, Choice

manage_bp = Blueprint('manage', __name__)


def allowed_file(filename, allowed_extensions):
    """허용된 파일 확장자 확인"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


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
            keywords=request.form.get('keywords')
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
        lecture.keywords = request.form.get('keywords')
        db.session.commit()
        flash('강의가 수정되었습니다.', 'success')
        return redirect(url_for('manage.list_lectures', block_id=lecture.block_id))
    return render_template('manage/lecture_form.html', block=lecture.block, lecture=lecture)


@manage_bp.route('/lecture/<int:lecture_id>/keywords', methods=['POST'])
def update_lecture_keywords(lecture_id):
    """강의 키워드 수정 API"""
    try:
        data = request.get_json()
        if not data:
            return {'success': False, 'error': '데이터가 없습니다.'}, 400
            
        lecture = Lecture.query.get_or_404(lecture_id)
        lecture.keywords = data.get('keywords')
        db.session.commit()
        
        return {'success': True}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 500


@manage_bp.route('/lecture/<int:lecture_id>/extract-keywords', methods=['POST'])
def extract_keywords_from_pdf(lecture_id):
    """PDF 업로드 후 키워드 추출 API"""
    import tempfile
    
    lecture = Lecture.query.get_or_404(lecture_id)
    
    if 'pdf_file' not in request.files:
        return {'success': False, 'error': 'PDF 파일을 선택해주세요.'}, 400
    
    file = request.files['pdf_file']
    if file.filename == '':
        return {'success': False, 'error': '파일이 선택되지 않았습니다.'}, 400
    
    if not file.filename.lower().endswith('.pdf'):
        return {'success': False, 'error': 'PDF 파일만 업로드 가능합니다.'}, 400
    
    try:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        
        # 키워드 추출 서비스 호출
        from app.services.keyword_extractor import process_pdf_and_extract_keywords
        result = process_pdf_and_extract_keywords(tmp_path, lecture.title)
        
        # 임시 파일 삭제
        import os
        os.unlink(tmp_path)
        
        if result['success']:
            return {
                'success': True,
                'keywords': result['keywords'],
                'keywords_text': ', '.join(result['keywords']),
                'text_length': result.get('text_length', 0)
            }
        else:
            return {'success': False, 'error': result.get('error', '알 수 없는 오류')}, 500
            
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500


@manage_bp.route('/extract-keywords-only', methods=['POST'])
def extract_keywords_only():
    """강의 ID 없이 PDF에서 키워드만 추출 (새 강의 생성용)"""
    import tempfile
    import os
    
    if 'pdf_file' not in request.files:
        return {'success': False, 'error': 'PDF 파일을 선택해주세요.'}, 400
    
    file = request.files['pdf_file']
    if file.filename == '':
        return {'success': False, 'error': '파일이 선택되지 않았습니다.'}, 400
    
    if not file.filename.lower().endswith('.pdf'):
        return {'success': False, 'error': 'PDF 파일만 업로드 가능합니다.'}, 400
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        
        from app.services.keyword_extractor import process_pdf_and_extract_keywords
        result = process_pdf_and_extract_keywords(tmp_path, '')
        
        os.unlink(tmp_path)
        
        if result['success']:
            return {
                'success': True,
                'keywords': result['keywords'],
                'keywords_text': ', '.join(result['keywords']),
                'text_length': result.get('text_length', 0)
            }
        else:
            return {'success': False, 'error': result.get('error', '알 수 없는 오류')}, 500
            
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500


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
    db.session.delete(exam)
    db.session.commit()
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
            from app.services.pdf_parser import parse_pdf_to_questions
            
            # PDF 파일 임시 저장
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
            os.unlink(tmp_path)
            
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
            return redirect(url_for('manage.list_exams'))
            
        except ImportError as e:
            flash(f'PDF 파서를 불러올 수 없습니다. pdfplumber 설치가 필요합니다: {str(e)}', 'error')
            return redirect(request.url)
        except Exception as e:
            db.session.rollback()
            flash(f'PDF 파싱 오류: {str(e)}', 'error')
            return redirect(request.url)
    
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
        question.content = request.form.get('content', '')
        question.explanation = request.form.get('explanation', '')
        question.q_type = request.form.get('q_type', question.q_type)
        
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
    return render_template('manage/question_edit.html', question=question, exam=exam, blocks=blocks, from_practice=from_practice)


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
    upload_folder = os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    
    try:
        file.save(filepath)
        # 마크다운 이미지 경로 반환
        image_url = url_for('static', filename='uploads/' + filename)
        return {'success': True, 'url': image_url, 'filename': filename}
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500
