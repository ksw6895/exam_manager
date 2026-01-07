"""PDF에서 강의 키워드 추출 서비스

강의 노트(PDF)를 업로드하면 Gemini API를 사용하여
해당 강의의 핵심 키워드를 자동으로 추출합니다.
"""
import json
import re
from typing import List, Optional

from flask import current_app

# PDF 파싱
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

# Google GenAI SDK
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    """PDF 파일에서 텍스트 추출
    
    Args:
        pdf_path: PDF 파일 경로
        
    Returns:
        추출된 텍스트 (실패 시 None)
    """
    if not PDFPLUMBER_AVAILABLE:
        raise RuntimeError("pdfplumber가 설치되지 않았습니다. pip install pdfplumber")
    
    text_content = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    text_content.append(f"--- Page {i+1} ---\n{text}")
                    
        return "\n".join(text_content)
    except Exception as e:
        current_app.logger.error(f"PDF 텍스트 추출 실패: {e}")
        return None


def extract_keywords_with_gemini(text_content: str, lecture_title: str = "") -> List[str]:
    """Gemini API를 사용하여 강의 키워드 추출
    
    Args:
        text_content: PDF에서 추출한 텍스트
        lecture_title: 강의 제목 (컨텍스트 제공용)
        
    Returns:
        추출된 키워드 리스트
    """
    if not GENAI_AVAILABLE:
        raise RuntimeError("google-genai가 설치되지 않았습니다.")
    
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다.")
    
    client = genai.Client(api_key=api_key)
    model_name = current_app.config.get('GEMINI_MODEL_NAME', 'gemini-2.0-flash-lite')
    
    # 프롬프트 설계
    context = f"강의명: {lecture_title}\n\n" if lecture_title else ""
    
    prompt = f"""당신은 의학 강의 노트 분석 전문가입니다.
아래 제공된 강의 노트 텍스트를 분석하여, 이 강의의 내용을 가장 잘 대표하는 **'핵심 키워드' 15~20개**를 추출해주세요.

## 중요 목표
이 키워드들은 나중에 **"시험 문제가 이 강의에 속하는지 판별하는 기준"**으로 사용될 것입니다.
따라서 너무 일반적인 단어(예: 치료, 진단, 병원)보다는, **이 강의에서만 다루는 구체적인 질병명, 해부학적 구조, 약물명, 생리학적 기전** 등을 우선적으로 추출하세요.

## 지시사항
1. 한국어와 영어가 혼용된 경우, 가장 널리 쓰이는 표기를 사용하세요. (가능하면 병기)
2. 중요도 순으로 나열하세요.
3. 반드시 아래와 같은 **JSON 리스트 형식**으로만 출력하세요. 다른 말은 하지 마세요.

Example Output:
["심방세동", "Warfarin", "P-wave", "뇌졸중 예방", "CHA2DS2-VASc"]

## {context}강의 노트 내용:
{text_content[:80000]}
"""
    
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        
        # JSON 파싱 (마크다운 코드블록 제거)
        result_text = response.text.strip()
        result_text = re.sub(r'```json\s*', '', result_text)
        result_text = re.sub(r'```\s*', '', result_text)
        
        # JSON 배열 추출
        json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if json_match:
            keywords = json.loads(json_match.group())
            return keywords
        
        return []
        
    except json.JSONDecodeError as e:
        current_app.logger.error(f"키워드 JSON 파싱 실패: {e}")
        return []
    except Exception as e:
        current_app.logger.error(f"Gemini API 요청 실패: {e}")
        raise


def process_pdf_and_extract_keywords(pdf_path: str, lecture_title: str = "") -> dict:
    """PDF 업로드 처리 및 키워드 추출 통합 함수
    
    Args:
        pdf_path: 업로드된 PDF 파일 경로
        lecture_title: 강의 제목
        
    Returns:
        {
            'success': bool,
            'keywords': List[str],
            'text_length': int,
            'error': str (실패 시)
        }
    """
    try:
        # 1. PDF 텍스트 추출
        text_content = extract_text_from_pdf(pdf_path)
        
        if not text_content:
            return {
                'success': False,
                'keywords': [],
                'error': 'PDF에서 텍스트를 추출할 수 없습니다.'
            }
        
        # 2. 키워드 추출
        keywords = extract_keywords_with_gemini(text_content, lecture_title)
        
        return {
            'success': True,
            'keywords': keywords,
            'text_length': len(text_content)
        }
        
    except Exception as e:
        return {
            'success': False,
            'keywords': [],
            'error': str(e)
        }
