# 환경변수 가이드

이 프로젝트는 Flask용 `.env`와 Next.js용 `next_app/.env.local`을 분리해서 사용합니다.

## 구분 기준
- 필수: 프로덕션/보안상 반드시 설정해야 함 (로컬 개발은 기본값으로 동작 가능)
- 조건부: 해당 기능을 사용할 때만 필요
- 선택: 기본값이 있으나 필요 시 덮어쓰기 가능

## Flask (.env)
| 키 | 구분 | 설명 | 기본값/비고 |
| --- | --- | --- | --- |
| SECRET_KEY | 필수(프로덕션) | Flask 세션/보안 키 | 미설정 시 `dev-secret-key-change-in-production` |
| GEMINI_API_KEY | 조건부 | Gemini API 키 (AI 분류/텍스트 교정 사용 시) | 없음 |
| GEMINI_MODEL_NAME | 선택 | Gemini 모델명 | `gemini-2.0-flash-lite` |
| AUTO_CREATE_DB | 선택 | 앱 시작 시 `db.create_all()` 자동 실행 | DevelopmentConfig 기본 True |
| LOCAL_ADMIN_ONLY | 선택 | `/manage` 및 관련 API 로컬호스트 제한 | 값은 `1/true/yes/on` |
| LOCAL_ADMIN_DB | 선택 | local admin DB 경로 | 미설정 시 `data/admin_local.db` |
| PDF_PARSER_MODE | 선택 | PDF 파서 선택 (`legacy`/`experimental`) | 기본 `legacy` |
| FLASK_CONFIG | 선택 | 설정 프로파일 선택 | `default`, `development`, `production`, `local_admin` |

## Next.js (`next_app/.env.local`)
| 키 | 구분 | 설명 | 기본값/비고 |
| --- | --- | --- | --- |
| FLASK_BASE_URL | 필수 | Next.js 서버가 접근할 Flask base URL | 예: `http://127.0.0.1:5000` |
| NEXT_PUBLIC_SITE_URL | 선택 | SSR에서 사용할 Next.js base URL | 미설정 시 `http://localhost:3000` |
| NEXT_PUBLIC_APP_URL | 선택 | `NEXT_PUBLIC_SITE_URL` 대체값 | 미설정 시 `http://localhost:3000` |

## 최소 예시
### `.env`
```dotenv
SECRET_KEY=dev-secret-key-change-in-production
GEMINI_API_KEY=your_api_key_here
# GEMINI_MODEL_NAME=gemini-2.0-flash-lite
# AUTO_CREATE_DB=1
# LOCAL_ADMIN_ONLY=1
# LOCAL_ADMIN_DB=./data/admin_local.db
# PDF_PARSER_MODE=legacy
# FLASK_CONFIG=development
```

### `next_app/.env.local`
```dotenv
FLASK_BASE_URL=http://127.0.0.1:5000
# NEXT_PUBLIC_SITE_URL=http://localhost:3000
# NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## 참고
- `.env`는 `run.py`, `run_local_admin.py`에서 `python-dotenv`로 로드됩니다.
- AI 기능을 사용하지 않는다면 `GEMINI_API_KEY`는 생략해도 됩니다.
- `LOCAL_ADMIN_ONLY=1`이면 `/manage` 및 관련 API를 localhost에서만 접근할 수 있습니다.
- 환경변수 변경 후에는 Flask/Next.js 서버를 재시작해야 합니다.
