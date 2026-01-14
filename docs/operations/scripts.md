# 운영/스크립트 가이드

## 주의 사항
- 스크립트 실행 전 `data/exam.db` 백업을 권장합니다.
- `scripts/*`는 기본 설정(`data/exam.db`)을 기준으로 동작합니다.
- `scripts/*`는 `.env`를 자동 로드하지 않습니다. 필요하면 환경변수를 미리 export하세요.

## FTS 초기화/동기화
강의 노트 인덱싱(Phase 1)용 FTS5 테이블을 생성/동기화합니다.

```bash
python scripts/init_fts.py --sync
```

옵션:
- `--rebuild`: 기존 FTS 데이터를 비우고 재구축
- `--sync`: `lecture_chunks` 테이블과 동기화

## AI 분류 필드 마이그레이션
`questions` 테이블에 AI 관련 컬럼을 추가합니다.

```bash
python scripts/migrate_ai_fields.py
```

## 기타 유틸리티 (CLI)
아래 스크립트들은 Flask와 직접 연결되어 있지 않은 독립 유틸리티입니다.

### PDF -> CSV 변환
```bash
python app/routes/parse_pdf_questions.py input.pdf [output.csv]
```
- `output.csv` 미지정 시 `input.csv`로 저장
- 이미지가 `media/<pdf_stem>/` 하위로 저장됨

### PDF 문제 크롭 이미지 생성
```bash
python app/routes/crop.py --pdf input.pdf --out exam_crops
```
- `--tight-crop`을 주면 페이지 전체 대신 내용 중심으로 크롭
- 결과 이미지는 `--out` 디렉터리에 저장

## 데이터 위치 요약
- 기본 DB: `data/exam.db`
- local admin DB: `data/admin_local.db`
- 업로드 이미지/파일: `app/static/uploads/` (local admin은 `uploads_admin`)
