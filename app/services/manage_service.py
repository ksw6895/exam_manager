"""Manage service for admin operations (blocks/lectures/exams).

This service centralizes management operations for blocks, lectures, and exams.
Routes should delegate to these functions rather than implementing business logic.
"""

from __future__ import annotations

from typing import List, Optional

from app import db
from app.models import Block, Lecture, PreviousExam, Question, Choice
from app.services.folder_scope import (
    build_folder_tree,
    resolve_folder_ids,
    resolve_lecture_ids,
)
from app.services.exam_cleanup import delete_exam_with_assets
from app.services.markdown_images import strip_markdown_images
from app.services.db_guard import guard_write_request


def get_dashboard_stats() -> dict:
    """Get dashboard statistics."""
    return {
        "block_count": Block.query.count(),
        "lecture_count": Lecture.query.count(),
        "exam_count": PreviousExam.query.count(),
        "question_count": Question.query.count(),
        "unclassified_count": Question.query.filter_by(is_classified=False).count(),
        "recent_exams": [
            {
                "id": e.id,
                "title": e.title,
                "subject": e.subject,
                "year": e.year,
                "term": e.term,
                "question_count": e.question_count,
                "unclassified_count": e.unclassified_count,
            }
            for e in PreviousExam.query.order_by(PreviousExam.created_at.desc())
            .limit(5)
            .all()
        ],
    }


def get_block_details(block_id: int) -> Optional[dict]:
    """Get block details with related data."""
    block = Block.query.get(block_id)
    if not block:
        return None

    return {
        "id": block.id,
        "name": block.name,
        "description": block.description,
        "order": block.order,
        "lecture_count": block.lecture_count,
        "question_count": block.question_count,
        "created_at": block.created_at.isoformat() if block.created_at else None,
        "updated_at": block.updated_at.isoformat() if block.updated_at else None,
    }


def create_block(name: str, description: str, order: int) -> Block:
    """Create a new block."""
    block = Block(name=name, description=description, order=order)
    db.session.add(block)
    db.session.commit()
    return block


def update_block(
    block_id: int, name: str, description: str, order: int
) -> Optional[Block]:
    """Update an existing block."""
    block = Block.query.get(block_id)
    if not block:
        return None
    block.name = name
    block.description = description
    block.order = order
    db.session.commit()
    return block


def delete_block(block_id: int) -> bool:
    """Delete a block."""
    block = Block.query.get(block_id)
    if not block:
        return False
    db.session.delete(block)
    db.session.commit()
    return True


def get_lecture_details(lecture_id: int) -> Optional[dict]:
    """Get lecture details with related data."""
    lecture = Lecture.query.get(lecture_id)
    if not lecture:
        return None

    return {
        "id": lecture.id,
        "block_id": lecture.block_id,
        "folder_id": lecture.folder_id,
        "parent_id": lecture.parent_id,
        "name": lecture.name,
        "order": lecture.order,
        "description": lecture.description,
        "professor": lecture.professor,
        "question_count": lecture.question_count,
        "created_at": lecture.created_at.isoformat() if lecture.created_at else None,
        "updated_at": lecture.updated_at.isoformat() if lecture.updated_at else None,
    }


def create_lecture(
    block_id: int,
    folder_id: Optional[int],
    parent_id: Optional[int],
    name: str,
    order: int,
    description: str,
    professor: Optional[str],
) -> Lecture:
    """Create a new lecture."""
    lecture = Lecture(
        block_id=block_id,
        folder_id=folder_id,
        parent_id=parent_id,
        name=name,
        order=order,
        description=description,
        professor=professor,
    )
    db.session.add(lecture)
    db.session.commit()
    return lecture


def update_lecture(
    lecture_id: int,
    block_id: int,
    folder_id: Optional[int],
    parent_id: Optional[int],
    name: str,
    order: int,
    description: str,
    professor: Optional[str],
) -> Optional[Lecture]:
    """Update an existing lecture."""
    lecture = Lecture.query.get(lecture_id)
    if not lecture:
        return None
    lecture.block_id = block_id
    lecture.folder_id = folder_id
    lecture.parent_id = parent_id
    lecture.name = name
    lecture.order = order
    lecture.description = description
    lecture.professor = professor
    db.session.commit()
    return lecture


def delete_lecture(lecture_id: int) -> bool:
    """Delete a lecture."""
    lecture = Lecture.query.get(lecture_id)
    if not lecture:
        return False
    db.session.delete(lecture)
    db.session.commit()
    return True


def get_exam_details(exam_id: int) -> Optional[dict]:
    """Get exam details with related data."""
    exam = PreviousExam.query.get(exam_id)
    if not exam:
        return None

    return {
        "id": exam.id,
        "block_id": exam.block_id,
        "folder_id": exam.folder_id,
        "title": exam.title,
        "subject": exam.subject,
        "year": exam.year,
        "professor": exam.professor,
        "order": exam.order,
        "description": exam.description,
        "question_count": exam.question_count,
        "created_at": exam.created_at.isoformat() if exam.created_at else None,
        "updated_at": exam.updated_at.isoformat() if exam.updated_at else None,
    }


def create_exam(
    block_id: int,
    folder_id: Optional[int],
    title: str,
    subject: str,
    year: int,
    professor: Optional[str],
    order: int,
    description: Optional[str],
) -> PreviousExam:
    """Create a new exam."""
    exam = PreviousExam(
        block_id=block_id,
        folder_id=folder_id,
        title=title,
        subject=subject,
        year=year,
        professor=professor,
        order=order,
        description=description,
    )
    db.session.add(exam)
    db.session.commit()
    return exam


def update_exam(
    exam_id: int,
    block_id: int,
    folder_id: Optional[int],
    title: str,
    subject: str,
    year: int,
    professor: Optional[str],
    order: int,
    description: Optional[str],
) -> Optional[PreviousExam]:
    """Update an existing exam."""
    exam = PreviousExam.query.get(exam_id)
    if not exam:
        return None
    exam.block_id = block_id
    exam.folder_id = folder_id
    exam.title = title
    exam.subject = subject
    exam.year = year
    exam.professor = professor
    exam.order = order
    exam.description = description
    db.session.commit()
    return exam


def delete_exam(exam_id: int) -> bool:
    """Delete an exam and its assets."""
    return delete_exam_with_assets(exam_id)


def get_question_details(question_id: int) -> Optional[dict]:
    """Get question details with choices."""
    question = Question.query.get(question_id)
    if not question:
        return None

    return {
        "id": question.id,
        "exam_id": question.exam_id,
        "number": question.number,
        "question_text": question.question_text,
        "choices": [
            {
                "id": c.id,
                "text": c.text,
                "is_correct": c.is_correct,
            }
            for c in question.choices
        ],
        "explanation": question.explanation,
        "is_classified": question.is_classified,
        "lecture_id": question.lecture_id,
        "question_type": question.question_type,
        "image_url": question.image_url,
        "created_at": question.created_at.isoformat() if question.created_at else None,
        "updated_at": question.updated_at.isoformat() if question.updated_at else None,
    }


def update_question(
    question_id: int,
    question_text: str,
    explanation: str,
    is_classified: bool,
    lecture_id: Optional[int],
    question_type: Optional[str],
) -> Optional[Question]:
    """Update a question."""
    question = Question.query.get(question_id)
    if not question:
        return None
    question.question_text = question_text
    question.explanation = explanation
    question.is_classified = is_classified
    question.lecture_id = lecture_id
    question.question_type = question_type
    db.session.commit()
    return question


def update_question_choices(
    question_id: int,
    choices_data: List[dict],
) -> Optional[Question]:
    """Update question choices."""
    question = Question.query.get(question_id)
    if not question:
        return None

    Question.query.filter_by(id=question_id).update({"choices": []})
    db.session.commit()

    for choice_data in choices_data:
        choice = Choice(
            question_id=question_id,
            text=choice_data.get("text"),
            is_correct=choice_data.get("is_correct", False),
        )
        db.session.add(choice)

    db.session.commit()
    return question


def delete_question(question_id: int) -> bool:
    """Delete a question."""
    question = Question.query.get(question_id)
    if not question:
        return False
    db.session.delete(question)
    db.session.commit()
    return True


def process_question_markdown(
    question_id: int,
    markdown_content: str,
    upload_folder: Optional[str],
) -> tuple[str, Optional[str]]:
    """Process markdown content for a question and extract image filename."""
    from app.services.file_paths import get_upload_folder

    if upload_folder is None:
        upload_folder = get_upload_folder()
    else:
        upload_folder = get_upload_folder(admin="admin" in upload_folder)

    return strip_markdown_images(markdown_content, upload_folder)
