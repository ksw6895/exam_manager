# Exam Manager

로컬에서 기출 시험 PDF를 파싱해 문제를 저장하고, 강의/블록 단위로 분류하며 연습/채점까지 연결하는 웹 앱입니다.

## TL;DR
- Flask(레거시 UI + JSON API) + Next.js(관리/연습 UI) + SQLite 단일 파일 DB
- 기본 포트: Flask 5000 / Local admin 5001 / Next.js 3000
- Python 3.10+ / Node.js 18+ 필요
- 실행/설정 상세: `docs/README.md`

## Ops Quick Commands
- Dev sync (prod -> dev + migrations + FTS rebuild):
  ```bash
  python scripts/clone_db.py --db data/exam.db --out data/dev.db
  python scripts/run_migrations.py --db data/dev.db && python scripts/init_fts.py --db data/dev.db --rebuild
  ```
- Prod apply (optional backup + migrations + FTS rebuild):
  ```bash
  python scripts/backup_db.py --db data/exam.db --keep 30
  python scripts/run_migrations.py --db data/exam.db && python scripts/init_fts.py --db data/exam.db --rebuild
  ```
- Read-only: `DB_READ_ONLY=1`
- Retrieval mode: `RETRIEVAL_MODE=bm25` / `RETRIEVAL_MODE=hybrid` (when implemented)
- AI auto apply: `AI_AUTO_APPLY=false` / `AI_AUTO_APPLY=true`
- Ops playbook: `docs/ops.md`

## Example Commands (5)
```bash
python scripts/clone_db.py --db data/exam.db --out data/dev.db
python scripts/run_migrations.py --db data/dev.db
python scripts/init_fts.py --db data/dev.db --rebuild
python scripts/backup_db.py --db data/exam.db --keep 30
DB_READ_ONLY=1 python run.py
```

## 데이터 손상 방지 원칙
- 모든 변경 전 백업
- migrations만으로 스키마 변경
- prod에서 실험 금지(항상 dev에서 먼저)

## UI 분리 현황 (Next.js vs Legacy)
### Next.js (현재 주 관리 화면)
- 블록/강의/시험 CRUD
- PDF 업로드 → 시험/문항 생성
- 문제 편집 (이미지 업로드 포함)
- 미분류 큐(일괄 분류/이동/초기화) + AI 분류 시작/적용
- 시험/문항 read-only 뷰

### Legacy Flask UI (아직 필요)
- 강의 상세 화면 (문제 리스트 + 정답 토글)
- 강의 노트 업로드/인덱싱(FTS)
- AI 분류 상세 미리보기 화면
- 일부 연습(Practice) 흐름 및 세션 기록 화면

## 주요 기능 (코드 기준)
- 블록/강의/기출시험 CRUD (`app/routes/manage.py`, `app/routes/api_manage.py`)
- PDF 업로드 → 문제/선지/정답 파싱 + 이미지 저장 (`app/services/pdf_parser.py`)
- PDF 크롭 이미지 생성 (PyMuPDF, `app/services/pdf_cropper.py`)
- 문제 분류/일괄 분류 (`app/routes/exam.py`, `/manage/questions/*`)
- Gemini 기반 AI 분류(배치) + 적용 (`app/routes/ai.py`, `app/services/ai_classifier.py`)
- 강의 노트 업로드 및 FTS 인덱싱 (`app/services/lecture_indexer.py`)
- 연습 모드(Flask 템플릿) + Next.js 연습 UI (`app/routes/practice.py`, `app/routes/api_practice.py`, `next_app/`)
- Local admin 모드 (별도 DB + experimental PDF parser, `run_local_admin.py`)

## 기술 스택
- Frontend: Flask Jinja 템플릿(`app/templates`), Next.js 16.1.1(`next_app`), React 19.2.3, Tailwind CSS 3.4.17, MUI
- Backend: Python, Flask, Flask-SQLAlchemy, python-dotenv, pdfplumber, PyMuPDF, pandas, Pillow, google-genai, tenacity, scikit-learn, numpy
- DB: SQLite (`data/exam.db`, `data/admin_local.db`)
- AI: Google Gemini (google-genai)

## 디렉터리 구조 요약
- `app/`: Flask 앱 (routes/services/models/templates/static)
- `next_app/`: Next.js App Router UI
- `data/`: SQLite DB 및 백업
- `scripts/`: 마이그레이션/FTS 스크립트

## 실행 방법 (WSL)
WSL2 + Ubuntu 기준으로 작성했습니다. Windows 브라우저에서 `http://localhost:5000`으로 접속 가능합니다.

### 1) 기본 도구 설치
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 --version  # 3.10+ 권장
```

Node.js는 `nvm` 사용을 권장합니다.
```bash
# nvm 설치 (이미 설치되어 있다면 생략)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc

# Node 설치 (예: 20)
nvm install 20
nvm use 20
```

### 2) 프로젝트 설치
```bash
cd /home/ksw6895/Projects/exam_manager
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) 환경변수 설정
```bash
cp .env.example .env
```
`.env`에 Gemini API 키가 필요하면 `GEMINI_API_KEY`를 넣습니다.

Next.js용 `.env.local` 생성:
```bash
cat <<'EOT' > next_app/.env.local
FLASK_BASE_URL=http://127.0.0.1:5000
EOT
```

### 4) DB 초기화/마이그레이션 (처음 1회)
```bash
python scripts/init_db.py --db data/exam.db
python scripts/run_migrations.py --db data/exam.db
python scripts/init_fts.py --db data/exam.db --sync
```
- 강의 노트 인덱싱/AI 분류를 안 쓰면 `init_fts.py`는 나중에 실행해도 됩니다.
- local admin DB를 쓸 경우 `data/admin_local.db`를 대상으로 동일하게 실행하세요.

### 5) 서버 실행
Flask (관리 UI + API):
```bash
python run.py
```
접속: http://127.0.0.1:5000

Next.js (관리/연습 UI):
```bash
cd next_app
npm install
npm run dev
```
접속: http://localhost:3000/lectures

### 6) Local admin (실험용)
```bash
python run_local_admin.py
```
접속: http://127.0.0.1:5001/manage

## 실행 방법 (Windows)
PowerShell 기준으로 작성했습니다.

### 1) 기본 도구 설치
- Python 3.10+ 설치 후 `py` 명령 동작
- Node.js 18+ 설치 후 `node`/`npm` 사용 가능

### 2) 프로젝트 설치
```powershell
cd C:\path\to\exam_manager
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3) 환경변수 설정
```powershell
copy .env.example .env
```
`.env`에 Gemini API 키가 필요하면 `GEMINI_API_KEY`를 넣습니다.

Next.js용 `.env.local` 생성:
```powershell
Set-Content -Path next_app\.env.local -Value "FLASK_BASE_URL=http://127.0.0.1:5000"
```

### 4) DB 초기화/마이그레이션 (처음 1회)
```powershell
python scripts\init_db.py --db data\exam.db
python scripts\run_migrations.py --db data\exam.db
python scripts\init_fts.py --db data\exam.db --sync
```
- 강의 노트 인덱싱/AI 분류를 안 쓰면 `init_fts.py`는 나중에 실행해도 됩니다.
- local admin DB를 쓸 경우 `data\admin_local.db`를 대상으로 동일하게 실행하세요.

### 5) 서버 실행
Flask (관리 UI + API):
```powershell
python run.py
```
접속: http://127.0.0.1:5000

Next.js (관리/연습 UI):
```powershell
cd next_app
npm install
npm run dev
```
접속: http://localhost:3000/lectures

### 6) Local admin (실험용)
```powershell
python run_local_admin.py
```
접속: http://127.0.0.1:5001/manage

### 7) Windows 실행 스크립트
- `launch_exam_manager.bat`
- `launch_exam_manager_local_admin.bat`

두 파일 모두 경로가 하드코딩되어 있으므로 본인 환경에 맞게 `cd /d` 경로를 수정해야 합니다.

## 환경변수(.env) 요약
자세한 설명은 `docs/setup/env.md`를 참고하세요.

### Flask (.env)
| 키 | 필수 | 설명 | 기본값/비고 |
| --- | --- | --- | --- |
| SECRET_KEY | 권장 | Flask 세션/보안 키 | 미설정 시 `dev-secret-key-change-in-production` |
| GEMINI_API_KEY | 조건부 | Gemini API 키 (AI 분류/텍스트 교정 사용 시) | 없음 |
| GEMINI_MODEL_NAME | 선택 | Gemini 모델명 | `gemini-2.0-flash-lite` |
| AUTO_CREATE_DB | 선택 | (deprecated) 앱 시작 시 `db.create_all()` 자동 실행 | 현재 사용 안 함 |
| LOCAL_ADMIN_ONLY | 선택 | `/manage` 및 관련 API 로컬호스트 제한 | 값은 `1/true/yes/on` |
| LOCAL_ADMIN_DB | 선택 | local admin DB 경로 | 미설정 시 `data/admin_local.db` |
| PDF_PARSER_MODE | 선택 | PDF 파서 선택 (`legacy`/`experimental`) | 기본 `legacy` |
| FLASK_CONFIG | 선택 | 설정 프로파일 선택 | `default`, `development`, `production`, `local_admin` |
| DB_READ_ONLY | 선택 | 쓰기 경로 차단 | 기본 False |
| RETRIEVAL_MODE | 선택 | 검색 모드 | 기본 `bm25` |
| AI_AUTO_APPLY | 선택 | AI 자동 반영 | 기본 False |
| AUTO_BACKUP_BEFORE_WRITE | 선택 | 쓰기 전 핫백업 수행 | 기본 False |
| AUTO_BACKUP_KEEP | 선택 | 백업 유지 개수 | 기본 30 |
| AUTO_BACKUP_DIR | 선택 | 백업 디렉터리 | 기본 `backups` |
| CHECK_PENDING_MIGRATIONS | 선택 | 앱 시작 시 미적용 마이그레이션 감지 | 기본 True |
| FAIL_ON_PENDING_MIGRATIONS | 선택 | 프로덕션에서 미적용 마이그레이션 있으면 중단 | 기본 False |
| ENFORCE_BACKUP_BEFORE_WRITE | 선택 | 프로덕션에서 백업 강제 | 기본 False |

### Next.js (`next_app/.env.local`)
| 키 | 필수 | 설명 |
| --- | --- | --- |
| FLASK_BASE_URL | 필수 | Next.js 서버가 접근할 Flask base URL |
| NEXT_PUBLIC_SITE_URL | 선택 | SSR에서 사용할 Next.js base URL |
| NEXT_PUBLIC_APP_URL | 선택 | `NEXT_PUBLIC_SITE_URL` 대체값 |

## 주요 라우트
### Next.js
- `/manage` (dashboard)
- `/manage/blocks`, `/manage/blocks/new`, `/manage/blocks/[id]/edit`
- `/manage/blocks/[id]/lectures`, `/manage/blocks/[id]/lectures/new`
- `/manage/lectures/[id]` (edit)
- `/manage/exams`, `/manage/exams/new`, `/manage/exams/[id]/edit`
- `/manage/exams/[id]` (exam detail + question list)
- `/manage/questions/[id]/edit` (question editor)
- `/manage/upload-pdf` (PDF -> exam/questions)
- `/exam` and `/exam/[id]` (read-only views)
- `/exam/unclassified` (bulk classify + AI flow)
- `/lectures`, `/practice/start`, `/practice/session/[sessionId]`

### Legacy Flask UI
- `/manage` (dashboard)
- `/manage/lecture/<id>` (강의 상세, 노트 업로드)
- `/exam` `/exam/<id>` `/exam/unclassified`
- `/practice` `/practice/lecture/<id>` `/practice/sessions`
- `/ai/classify/preview/<job_id>`

## JSON API 요약
### 관리/시험
- `/api/manage/*` (blocks/lectures/exams/questions/upload)
- `/api/exam/unclassified`
- `/manage/questions/move`, `/manage/questions/reset` (bulk 작업)

### 연습/세션
- `/api/practice/lectures`
- `/api/practice/lecture/<id>`
- `/api/practice/lecture/<id>/questions`
- `/api/practice/lecture/<id>/submit`
- `/api/practice/lecture/<id>/result`
- `/api/practice/sessions`, `/api/practice/sessions/<id>`

### AI
- `/ai/classify/start`
- `/ai/classify/status/<id>`
- `/ai/classify/result/<id>`
- `/ai/classify/apply`
- `/ai/classify/recent`
- `/ai/correct-text`

## Manual QA 체크리스트
- [ ] Blocks/Lectures CRUD (Next `/manage/blocks`)
- [ ] Exams CRUD + 상세 보기 (Next `/manage/exams`)
- [ ] PDF 업로드 → 문항/선지 생성 (Next `/manage/upload-pdf`)
- [ ] Question edit + 이미지 업로드 (Next `/manage/questions/[id]/edit`)
- [ ] Unclassified queue: 분류/이동/초기화 (Next `/exam/unclassified`)
- [ ] AI 분류: start/status/result/apply (Next `/exam/unclassified` 또는 Legacy preview)
- [ ] 강의 노트 업로드/인덱싱 (Legacy `/manage/lecture/<id>`)
- [ ] Practice 흐름 (Legacy `/practice/*`, Next `/lectures`)

## Lecture Note Indexing (FTS)
- `python scripts/init_fts.py --sync` 실행 후 FTS 테이블 생성
- 강의 상세 페이지(`/manage/lecture/<id>`)에서 PDF 업로드 → `lecture_chunks` 생성
- FTS 검색은 `lecture_chunks_fts`를 사용

## 운영 포인트
- `AUTO_CREATE_DB`는 deprecated (스키마 생성은 `scripts/init_db.py`로 수행)
- Local admin 모드는 `LOCAL_ADMIN_ONLY`로 localhost 접근만 허용
- PDF 파서 모드(`PDF_PARSER_MODE`)는 `legacy`/`experimental` 선택
- 업로드 최대 크기: 100MB (`config.py`의 `MAX_CONTENT_LENGTH`)
- 업로드 저장 위치: `app/static/uploads` (local admin은 `uploads_admin`)
- AI 분류 작업은 비동기 처리이므로 `/ai/classify/status/<id>`로 진행 확인

## 알려진 제약/갭
- Next.js Practice는 세션 생성 API가 없어 클라이언트 fallback 모드로 시작함
- 강의 노트 업로드/인덱싱 UI는 Legacy에서만 제공
- AI 분류 상세 미리보기 UI는 Legacy에서만 제공

## 문서
- 문서 인덱스: `docs/README.md`
- 실행/환경 설정: `docs/setup/wsl.md`, `docs/setup/windows.md`, `docs/setup/env.md`
- 아키텍처 요약: `docs/architecture/overview.md`
- 운영/스크립트: `docs/operations/scripts.md`
- 리팩토링 가이드(상세): `docs/refactoring/README.md`
- 리팩토링 체크리스트: `docs/refactoring/checklists.md`

## 트러블슈팅
- `ModuleNotFoundError` 발생: `pip install -r requirements.txt` 재실행
- AI 분류/텍스트 교정 실패: `google-genai` 설치 여부와 `GEMINI_API_KEY` 설정 확인
- Next.js 시작 시 `Missing or invalid FLASK_BASE_URL`: `next_app/.env.local` 확인
- PDF 업로드 후 문항이 0개: PDF 포맷 문제 가능 → `PDF_PARSER_MODE=experimental` 시도
- 업로드가 413으로 실패: `config.py`의 `MAX_CONTENT_LENGTH`(100MB) 확인
- Local admin 화면이 404: `LOCAL_ADMIN_ONLY` 활성화 시 localhost에서만 접근 가능
- 테이블이 생성되지 않음: `AUTO_CREATE_DB` 설정 또는 마이그레이션 스크립트 실행
- AI 분류 결과가 비어있음: FTS 초기화(`scripts/init_fts.py --sync`) 여부 확인

## TODO(확인 필요)
- 배포/운영 환경(호스팅, 프로세스 매니저, CI)은?
- 인증/권한(로그인) 기능이 필요한가?
- `importer.py` 사용 계획은?
