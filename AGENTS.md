# AGENTS.md — Exam Manager 리팩토링/개발 에이전트 가이드

> 이 문서는 Codex/에이전트가 이 레포에서 작업할 때 반드시 따라야 하는 “프로젝트 헌법”입니다.
> 목표: **작고 안전한 변경(작은 PR)**, **동작 보존**, **회귀 방지**.

---

## 0) 이 프로젝트 한 줄 요약
로컬에서 시험 PDF를 파싱해 문제를 저장하고, 강의/블록 단위로 분류하며 연습/채점까지 연결하는 웹 앱.  
스택: **Flask(레거시 UI + JSON API) + Next.js(관리/연습 UI) + SQLite 단일 DB**

---

## 1) 절대 규칙 (Hard Rules)

### 1.1 리팩토링 PR 원칙
- **리팩토링 PR에는 기능 변경을 섞지 않습니다.**
- 한 PR은 **하나의 목적**만 (예: “retrieval 모듈 분리”, “라우트 슬림화”).
- PR당 변경량을 작게 유지 (권장: **300~600 LOC 이하**).
- “어디서 무엇을 바꿨는지” 리뷰 가능하도록 커밋 메시지/PR 설명을 구체적으로 작성.

### 1.2 DB/마이그레이션 규칙
- 스키마 변경은 반드시 `migrations/*.sql`로만 반영합니다.
- `data/exam.db`, `data/admin_local.db`는 작업 전 백업을 전제로 합니다.
- `DB_READ_ONLY=1` 모드 동작이 깨지지 않아야 합니다.

### 1.3 API 호환성
- Next.js가 의존하는 **API 응답 구조를 임의로 변경하지 않습니다.**
- 응답 변경이 필요하면:  
  (1) 기존 필드 유지 + 새 필드 추가 → (2) 프론트 반영 → (3) 제거(추후) 순서.

### 1.4 AI/분류 파이프라인 규칙
- 분류/리트리벌의 “품질/threshold/모드 기본값”을 리팩토링 PR에서 바꾸지 않습니다.
- `RETRIEVAL_MODE` 등 환경변수 의미를 임의로 변경하지 않습니다.
- 캐시 파일/아티팩트(`data/cache`, `reports/`)는 git에 커밋하지 않습니다.

---

## 2) 디렉터리/모듈 경계 (Architecture Boundaries)

### Backend (Flask)
- `app/routes/` : HTTP 라우트 (요청/응답 변환, 인증/권한, 에러 처리)
- `app/services/` : 핵심 로직 (PDF 파싱, 분류, 검색, 인덱싱, 캐시 등)
- `app/models.py` : DB 모델 (SQLAlchemy)
- `config.py` : 설정/환경변수

**규칙:** 라우트는 얇게, 로직은 서비스에. (docs/refactoring/checklists.md 참고)

### Frontend (Next.js)
- `next_app/` : Next.js App Router UI
**규칙:** 백엔드 리팩토링 이슈에서 프론트 수정은 “명시된 경우에만”.

### Ops / Scripts
- `scripts/` : DB 복제/백업/마이그레이션/FTS/평가/튜닝 스크립트
- `docs/ops.md` : 운영 플레이북
- `docs/refactoring/*` : 리팩토링 체크리스트/규칙

---

## 3) 개발/검증 커맨드 (Agent must run)

> 아래는 “가능한 범위에서” 수행하고, PR 설명에 실행 로그(요약)를 남깁니다.

### 3.1 Python 환경
```bash
python -m compileall app scripts run.py run_local_admin.py
```

### 3.2 DB/Ops (개발 DB 기준)
```bash
python scripts/clone_db.py --db data/exam.db --out data/dev.db
python scripts/run_migrations.py --db data/dev.db
python scripts/init_fts.py --db data/dev.db --rebuild
```

### 3.3 서버 기동 스모크 (선택, 가능하면)
```bash
python run.py
# 또는
python run_local_admin.py
```

### 3.4 Next.js 스모크 (프론트 변경이 있을 때만)
```bash
cd next_app
npm install
npm run dev
```

---

## 4) 리팩토링 작업 방식 (How we work)

### 4.1 작업 단위
- “이슈 1개 = PR 1개”를 기본으로 합니다.
- 각 PR은 반드시:
  - 변경 이유 (Why)
  - 변경 요약 (What)
  - 검증 방법 (How verified)
  를 포함합니다.

### 4.2 금지 패턴
- 서비스 로직을 라우트에서 직접 구현
- 동일 DB 쿼리 중복/산재
- “편의상” 임의의 전역 상태 추가 (싱글톤 캐시 등) — 꼭 필요하면 명시하고 격리
- 무분별한 설정 키 추가 (config 난립) — 먼저 기존 키/플래그 재사용 가능성 검토

### 4.3 안전 체크 (리팩토링 후 수동 확인 포인트)
- docs/refactoring/checklists.md 의 “작업 후 체크리스트” 최소 항목을 확인합니다.
- 특히 아래는 회귀가 잦습니다:
  - PDF 업로드 → 문제 생성
  - 미분류 큐/일괄 분류
  - AI 분류 시작/상태/적용
  - 강의 노트 업로드/FTS 인덱싱
  - Practice 흐름 (Legacy/Next 모두)

---

## 5) 코딩 컨벤션 (권장)

- 함수/클래스는 “입력/출력”을 명확히 합니다. (가능하면 dataclass 사용)
- 서비스는 “순수 로직” + “인프라 어댑터(파일/DB/외부 API)”를 분리합니다.
- 예외는 라우트까지 흘러가더라도, 사용자 메시지/로그 메시지를 분리합니다.
- 파일 이동/리네임은 별도 PR로 분리하는 것이 리뷰에 유리합니다.

---

## 6) 에이전트가 PR을 올릴 때 포함해야 할 것 (PR Template)

- 목적: (한 문장)
- 변경 범위: (파일/모듈)
- 비범위: (하지 않은 것)
- 검증:
  - `python -m compileall ...` ✅/❌
  - (가능하면) dev DB 마이그레이션/FTS ✅/❌
  - 수동 스모크 수행 여부 ✅/❌
- 리스크/롤백:
  - 영향을 받는 기능
  - 롤백 방법 (마지막 정상 커밋/백업 복구 등)

---
