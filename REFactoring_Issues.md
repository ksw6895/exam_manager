# 리팩토링 백로그 (Issue 템플릿 모음)

> 아래 항목을 그대로 GitHub Issue로 복사해 사용하세요.  
> 원칙: **이슈 1개 = PR 1개**, 기능 변경 금지(명시된 경우 제외).

---

## 공통 Issue 템플릿

**배경/문제**
- (현 상태의 비효율/중복/결합도를 간단히 설명)

**목표**
- (리팩토링으로 얻고 싶은 구조적 개선을 1~2줄)

**범위 (Scope)**
- 포함: (파일/모듈)
- 제외: (하지 말아야 할 것)

**수용 기준 (Acceptance Criteria)**
- [ ] 외부 동작/응답 형식 유지
- [ ] `python -m compileall app scripts run.py run_local_admin.py` 통과
- [ ] docs/refactoring/checklists.md 중 관련 수동 스모크 항목 최소 2개 확인
- [ ] PR 설명에 변경 요약 + 검증 로그 포함

**참고**
- 관련 문서/코드 링크

---

## Issue 0 — 리팩토링 가드레일: “검증 스크립트” 추가

**배경/문제**
- 테스트가 충분하지 않은 상태에서 대규모 리팩토링을 하면 회귀 탐지가 늦어짐.

**목표**
- “리팩토링 안전망”으로 사용할 최소 검증 커맨드를 스크립트화하고 문서화.

**범위**
- 포함: `scripts/verify_repo.py`(또는 `scripts/verify.sh`), `docs/refactoring/README.md` 또는 `README.md`
- 제외: 기능 변경, DB 스키마 변경

**수용 기준**
- [ ] compileall + (가능하면) dev DB 마이그레이션/FTS 커맨드를 한 번에 실행 가능
- [ ] 실패 시 원인 메시지가 명확
- [ ] README에 “리팩토링 전에 이것부터 돌려라” 섹션 추가

---

## Issue 1 — 라우트 슬림화 1: manage/api_manage 경계 정리

**배경/문제**
- 라우트에 로직이 섞이면 중복/회귀가 증가하고 Next/Legacy 동작이 벌어질 수 있음.

**목표**
- 라우트는 요청/응답 변환만, 로직은 service로 이동.

**범위**
- 포함: `app/routes/manage.py`, `app/routes/api_manage.py`, 관련 service(신설 가능)
- 제외: API 응답 구조 변경, UI 변경

**수용 기준**
- [ ] 라우트에서 “DB 쿼리/비즈니스 로직”이 대부분 제거됨
- [ ] 기존 엔드포인트 동작 유지 (수동 스모크 2개 이상)

---

## Issue 2 — PDF 파싱 계층 정리: pdf_parser vs pdf_parser_experimental

**배경/문제**
- `pdf_parser.py` / `pdf_parser_experimental.py`가 분기/중복이 커지면 유지보수 어려움.

**목표**
- 파서 인터페이스를 만들고 모드를 “어댑터”로 분리해 중복 제거.

**범위**
- 포함: `app/services/pdf_parser.py`, `app/services/pdf_parser_experimental.py`, `app/routes/parse_pdf_questions.py` 등
- 제외: 파싱 결과 포맷 변경(동일 PDF 기준 결과가 크게 달라지면 안 됨)

**수용 기준**
- [ ] `PDF_PARSER_MODE=experimental/legacy` 토글이 한 지점에서만 결정됨
- [ ] 파서 공통 처리(전처리/후처리)가 중복 없이 재사용됨
- [ ] 샘플 PDF 1건 비교(수동) 체크리스트에 기록

---

## Issue 3 — 분류 파이프라인 경계 확립: ai_classifier/retrieval/context_expander

**배경/문제**
- 분류 파이프라인 관련 로직이 여러 파일에 흩어져 있으면 변경 영향 범위가 커짐.

**목표**
- “문제 1개 분류” 유스케이스(진입점)를 서비스로 고정하고, 단계별 인터페이스(검색/확장/판단)를 분리.

**범위**
- 포함: `app/services/ai_classifier.py`, `app/services/retrieval.py`, `app/services/context_expander.py`, `app/services/query_transformer.py`
- 제외: threshold/모드 기본값 변경, 품질 튜닝(리팩토링만)

**수용 기준**
- [ ] `classify_*` 혹은 `run_*` 형태의 단일 진입점 함수/클래스가 생김
- [ ] 검색/확장/판단 단계가 명확히 분리되고 호출 순서가 코드에서 한눈에 보임
- [ ] 기존 평가 스크립트(`scripts/evaluate_evalset.py`)가 그대로 동작

---

## Issue 4 — 캐시/아티팩트 정책 정리: classifier_cache + data/cache

**배경/문제**
- 캐시 파일 경로/포맷이 난립하면 브랜치/환경별 재현성이 떨어짐.

**목표**
- 캐시 경로 규칙과 키 스키마를 문서화하고 코드에서 한 곳으로 통일.

**범위**
- 포함: `app/services/classifier_cache.py`, `data/cache/*` 사용처, `config.py`
- 제외: 캐시 의미 변경(히트율/정확도 튜닝)

**수용 기준**
- [ ] 캐시 경로가 환경변수/설정으로 일관되게 제어됨
- [ ] 캐시 키가 “모델/모드/버전”을 포함하여 충돌 위험이 낮음
- [ ] `.gitignore`에 캐시/리포트가 확실히 제외됨(필요 시 보강)

---

## Issue 5 — 설정(config) 구조화: retrieval/ai/pdf/ops 섹션 정리

**배경/문제**
- 설정 키가 흩어지면 운영/디버깅 난이도가 올라감.

**목표**
- config를 “의미 단위 섹션”으로 정리하고, 기본값/환경변수 매핑을 문서화.

**범위**
- 포함: `config.py`, `.env.example`, docs 관련
- 제외: 기본 동작 변경(기본값 바꾸지 않기)

**수용 기준**
- [ ] 설정이 retrieval/ai/pdf/ops 등 섹션으로 정리됨
- [ ] README/ops 문서에 핵심 플래그 표가 추가됨

---

## Issue 6 — DB 접근 경계: commit/transaction 경계 일관화

**배경/문제**
- 서비스 곳곳에서 `db.session.commit()`이 난립하면 부분 실패 시 일관성이 깨질 수 있음.

**목표**
- “커밋은 어디서 하는가” 원칙을 정하고(라우트 vs 서비스), 단계적으로 통일.

**범위**
- 포함: 대표 서비스 1~2개부터 (예: `practice_service.py`, `exam_cleanup.py`, `migrations.py` 등 중 선택)
- 제외: 광범위한 전면 수정(한 PR에서 다 하지 않기)

**수용 기준**
- [ ] 선택한 범위에서 commit 경계가 일관됨
- [ ] 실패 시 롤백/에러 처리 흐름이 명확해짐

---

## Issue 7 — 스크립트 정리: scripts가 제품 코드 “해킹 import”하지 않게

**배경/문제**
- scripts가 내부 구현에 직접 의존하면 리팩토링 때마다 스크립트가 깨짐.

**목표**
- 스크립트는 공용 엔트리포인트(서비스 함수/CLI)를 호출하도록 정리.

**범위**
- 포함: `scripts/*.py` 중 1~2개 대표 선정 (예: `dump_retrieval_features.py`, `build_embeddings.py`)
- 제외: 스크립트 기능 변경(출력 포맷 유지)

**수용 기준**
- [ ] 스크립트가 내부 모듈의 private 함수/전역에 덜 의존
- [ ] 실행 방법이 README/ops 문서에 남음

---

## Issue 8 — 파일/이미지 처리 경계: markdown_images/pdf_cropper 정리

**배경/문제**
- 업로드 경로/파일명 규칙이 깨지면 과거 데이터가 조회 불가해지는 위험이 큼.

**목표**
- 파일 경로 규칙(저장 위치/이름/확장자)을 상수/헬퍼로 통일하고, 서비스 간 중복 제거.

**범위**
- 포함: `app/services/markdown_images.py`, `app/services/pdf_cropper.py`, 관련 라우트
- 제외: 저장 경로/이름 규칙 변경(기존 데이터 호환 유지)

**수용 기준**
- [ ] 경로 생성 로직이 단일 헬퍼로 통일
- [ ] 기존 업로드/편집 화면이 깨지지 않음(수동 스모크)

---

## Issue 9 — Next.js/Legacy 경계 문서화 + “무엇이 어디에 있는지” 지도 만들기

**배경/문제**
- 기능이 Next/Legacy로 분산되어 있어 새로 합류한 사람이 길을 잃기 쉬움.

**목표**
- “기능 → 화면/라우트/API/서비스” 매핑 문서를 추가.

**범위**
- 포함: `docs/architecture/overview.md` 또는 새 문서 `docs/architecture/map.md`
- 제외: 코드 변경(문서만)

**수용 기준**
- [ ] 주요 기능 8~12개에 대해 엔드포인트/파일이 연결된 표가 존재
- [ ] README에서 해당 문서를 링크

---
