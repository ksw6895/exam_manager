from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Optional

from flask import current_app
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app import db
from app.models import QuestionQuery

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


PROMPT_TEMPLATE = """역할: 너는 의학 강의록 검색을 돕는 “검색 쿼리 생성기”다.

규칙:
- 절대 정답을 말하지 마라.
- 절대 선지 번호(1~5)나 특정 선택지를 고르지 마라.
- “다음 중 옳은 것은/틀린 것은” 같은 시험 문구는 제거하라.
- 강의록에서 찾아야 할 “핵심 개념/기전/진단 포인트/감별” 중심으로 작성하라.
- 의학 용어는 가능한 한 원어(영문 약어 포함)로도 병기하라.
- 출력은 아래 형식 그대로.

출력 형식:
[KEYWORDS]
- (핵심 키워드 4~7개, 각 2~5단어)

[LECTURE_STYLE_QUERY]
(강의록에서 그대로 찾을 법한 서술형 1~2문장)

[NEGATIVE_KEYWORDS]
- (검색에 방해되는 시험 문구/일반어 3~6개)

문제:
<<<
{question_text}
>>>
"""


SECTION_PATTERN = re.compile(
    r"\[KEYWORDS\](.*?)\[LECTURE_STYLE_QUERY\](.*?)\[NEGATIVE_KEYWORDS\](.*)",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class QueryTransformation:
    keywords: List[str]
    lecture_style_query: str
    negative_keywords: List[str]


def _normalize_list(lines: List[str]) -> List[str]:
    cleaned: List[str] = []
    for line in lines:
        item = line.strip()
        if not item:
            continue
        if item.startswith("-"):
            item = item[1:].strip()
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned


def _parse_bullets(section: str) -> List[str]:
    if not section:
        return []
    lines = [line for line in section.strip().splitlines() if line.strip()]
    return _normalize_list(lines)


def parse_transformation(text: str) -> Optional[QueryTransformation]:
    match = SECTION_PATTERN.search(text or "")
    if not match:
        return None
    keywords_raw, lecture_raw, negative_raw = match.groups()

    keywords = _parse_bullets(keywords_raw)
    negative_keywords = _parse_bullets(negative_raw)

    lecture_lines = [line.strip() for line in lecture_raw.splitlines() if line.strip()]
    lecture_style_query = " ".join(lecture_lines).strip()

    if not lecture_style_query:
        return None

    return QueryTransformation(
        keywords=keywords,
        lecture_style_query=lecture_style_query,
        negative_keywords=negative_keywords,
    )


def _limit_items(items: List[str], max_items: int) -> List[str]:
    if max_items <= 0:
        return items
    return items[:max_items]


def _prompt_version() -> str:
    return current_app.config.get("HYDE_PROMPT_VERSION", "hyde_v1")


def _model_name() -> str:
    return current_app.config.get("HYDE_MODEL_NAME") or current_app.config.get(
        "GEMINI_MODEL_NAME", "gemini-2.0-flash-lite"
    )


def _max_keywords() -> int:
    return int(current_app.config.get("HYDE_MAX_KEYWORDS", 7))


def _max_negative() -> int:
    return int(current_app.config.get("HYDE_MAX_NEGATIVE", 6))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((Exception,)),
)
def _call_gemini(question_text: str) -> QueryTransformation:
    if not GENAI_AVAILABLE:
        raise RuntimeError("google-genai package is not installed.")

    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)
    prompt = PROMPT_TEMPLATE.format(question_text=question_text)

    response = client.models.generate_content(
        model=_model_name(),
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.8,
            max_output_tokens=400,
        ),
    )
    text = (response.text or "").strip()
    parsed = parse_transformation(text)
    if not parsed:
        raise RuntimeError("Failed to parse query transformation output.")

    parsed.keywords = _limit_items(parsed.keywords, _max_keywords())
    parsed.negative_keywords = _limit_items(parsed.negative_keywords, _max_negative())
    return parsed


def _fetch_cached(question_id: int, prompt_version: str) -> Optional[QueryTransformation]:
    try:
        row = QuestionQuery.query.filter_by(
            question_id=question_id, prompt_version=prompt_version
        ).first()
    except Exception:
        return None
    if not row:
        return None
    try:
        keywords = json.loads(row.keywords_json or "[]")
    except json.JSONDecodeError:
        keywords = []
    try:
        negative_keywords = json.loads(row.negative_keywords_json or "[]")
    except json.JSONDecodeError:
        negative_keywords = []

    return QueryTransformation(
        keywords=keywords or [],
        lecture_style_query=row.lecture_style_query or "",
        negative_keywords=negative_keywords or [],
    )


def get_query_payload(
    question_id: int,
    question_text: str,
    *,
    allow_generate: bool = False,
) -> Optional[QueryTransformation]:
    if not question_id or not question_text:
        return None

    prompt_version = _prompt_version()
    cached = _fetch_cached(question_id, prompt_version)
    if cached:
        return cached

    if not allow_generate:
        return None

    try:
        generated = _call_gemini(question_text)
    except Exception as exc:
        current_app.logger.warning("HyDE query generation failed: %s", exc)
        return None

    row = QuestionQuery(
        question_id=question_id,
        prompt_version=prompt_version,
        lecture_style_query=generated.lecture_style_query,
        keywords_json=json.dumps(generated.keywords, ensure_ascii=False),
        negative_keywords_json=json.dumps(generated.negative_keywords, ensure_ascii=False),
    )
    try:
        db.session.add(row)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning("HyDE query cache save failed: %s", exc)
        return generated

    return generated
