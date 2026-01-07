"""연습 모드 Blueprint - 강의별 기출문제 풀이"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app import db
from app.models import Block, Lecture, Question, Choice, StudyHistory

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
    questions = lecture.questions.order_by(Question.question_number).all()
    
    # 문제 유형별 분리
    objective_questions = []  # 객관식 (단일/복수 정답)
    subjective_questions = []  # 주관식
    
    for idx, q in enumerate(questions):
        q_info = {
            'id': q.id, 
            'number': q.question_number,
            'original_seq': idx + 1,  # 원래 순번 유지
            'is_short_answer': q.is_short_answer,
            'is_multiple_response': q.is_multiple_response
        }
        if q.is_short_answer:
            subjective_questions.append(q_info)
        else:
            objective_questions.append(q_info)
    
    # 유형별 순번 부여
    for idx, q in enumerate(objective_questions):
        q['type_seq'] = idx + 1
    for idx, q in enumerate(subjective_questions):
        q['type_seq'] = idx + 1
    
    # 전체 문제 맵 (기존 호환성 유지)
    question_map = [{'id': q.id, 'number': q.question_number} for q in questions]
    
    return render_template('practice/dashboard.html', 
                         lecture=lecture, 
                         questions=questions,
                         question_map=question_map,
                         objective_questions=objective_questions,
                         subjective_questions=subjective_questions,
                         total_count=len(questions),
                         objective_count=len(objective_questions),
                         subjective_count=len(subjective_questions))


@practice_bp.route('/lecture/<int:lecture_id>/question/<int:seq>')
def question(lecture_id, seq):
    """개별 문제 풀이 페이지 (seq: 1-based 순번)"""
    lecture = Lecture.query.get_or_404(lecture_id)
    questions = lecture.questions.order_by(Question.question_number).all()
    
    # 유효성 검사
    if seq < 1 or seq > len(questions):
        flash('유효하지 않은 문제 번호입니다.', 'error')
        return redirect(url_for('practice.dashboard', lecture_id=lecture_id))
    
    current_question = questions[seq - 1]
    choices = current_question.choices.order_by(Choice.choice_number).all()
    
    # 이전/다음 문제 존재 여부
    has_prev = seq > 1
    has_next = seq < len(questions)
    
    return render_template('practice/question.html',
                         lecture=lecture,
                         question=current_question,
                         choices=choices,
                         seq=seq,
                         total_count=len(questions),
                         has_prev=has_prev,
                         has_next=has_next)


@practice_bp.route('/lecture/<int:lecture_id>/submit', methods=['POST'])
def submit(lecture_id):
    """답안 제출 및 채점 - 유형별 분리 채점"""
    lecture = Lecture.query.get_or_404(lecture_id)
    questions = lecture.questions.order_by(Question.question_number).all()
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '데이터가 없습니다.'}), 400
    
    answers = data.get('answers', {})  # {question_id: [선택한 번호들]}
    
    results = []
    
    # 전체 통계
    correct_count = 0
    total_answered = 0
    
    # 유형별 통계
    objective_total = 0
    objective_answered = 0
    objective_correct = 0
    subjective_total = 0
    subjective_answered = 0
    subjective_correct = 0
    
    for idx, q in enumerate(questions):
        question_id_str = str(q.id)
        user_answer = answers.get(question_id_str)
        is_short_answer = q.is_short_answer
        
        # 유형별 전체 카운트
        if is_short_answer:
            subjective_total += 1
        else:
            objective_total += 1
        
        if user_answer is None or user_answer == [] or user_answer == '':
            # 미응답
            results.append({
                'seq': idx + 1,
                'question_id': q.id,
                'user_answer': None,
                'correct_answer': q.correct_choice_numbers if not is_short_answer else q.correct_answer_text,
                'is_correct': None,  # 미응답
                'is_short_answer': is_short_answer,
                'content': q.content[:100] if q.content else ''
            })
            continue
        
        total_answered += 1
        if is_short_answer:
            subjective_answered += 1
        else:
            objective_answered += 1
        
        # 채점
        is_correct, correct_answer = q.check_answer(user_answer)
        
        if is_correct:
            correct_count += 1
            if is_short_answer:
                subjective_correct += 1
            else:
                objective_correct += 1
        
        results.append({
            'seq': idx + 1,
            'question_id': q.id,
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'is_short_answer': is_short_answer,
            'content': q.content[:100] if q.content else ''
        })
        
        # StudyHistory 저장
        history = StudyHistory(
            question_id=q.id,
            is_correct=is_correct if is_correct is not None else False,
            user_answer=str(user_answer)
        )
        db.session.add(history)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'total_count': len(questions),
        'answered_count': total_answered,
        'correct_count': correct_count,
        'incorrect_count': total_answered - correct_count,
        # 객관식 통계
        'objective_total': objective_total,
        'objective_answered': objective_answered,
        'objective_correct': objective_correct,
        'objective_incorrect': objective_answered - objective_correct,
        # 주관식 통계
        'subjective_total': subjective_total,
        'subjective_answered': subjective_answered,
        'subjective_correct': subjective_correct,
        'subjective_incorrect': subjective_answered - subjective_correct,
        'results': results
    })


@practice_bp.route('/lecture/<int:lecture_id>/result')
def result(lecture_id):
    """결과 페이지 (GET 방식으로 표시, 실제 데이터는 JS에서 처리)"""
    lecture = Lecture.query.get_or_404(lecture_id)
    questions = lecture.questions.order_by(Question.question_number).all()
    
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

