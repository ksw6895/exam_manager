# 리팩토링 체크리스트

리팩토링을 안전하게 진행하기 위한 점검 항목입니다. 작업 전/중/후로 나누어 체크하세요.

## 1) 작업 전 체크리스트
- [ ] `data/exam.db` 백업 완료 (필요 시 `data/admin_local.db`도 백업)
- [ ] `.env`와 `next_app/.env.local` 값 기록
- [ ] 현재 동작 기준선 확인 (PDF 업로드, 분류, AI, 연습)
- [ ] 이번 리팩토링 대상 파일/모듈 범위 확정
- [ ] API/DB 변경 여부 결정
- [ ] 강의 노트 사용 시 FTS 초기화 상태 확인 (`scripts/init_fts.py --sync`)

## 2) 작업 중 체크리스트
- [ ] 라우트는 요청/응답만 담당, 로직은 서비스로 이동
- [ ] 서비스 함수 입력/출력이 명확 (dict/dataclass)
- [ ] `db.session.commit()` 경계가 일관됨
- [ ] 동일 쿼리가 중복되지 않음
- [ ] 응답 포맷이 기존과 호환됨
- [ ] 업로드 경로/파일명 규칙이 변하지 않음
- [ ] 변경 범위가 커지면 작업을 분할

## 3) 작업 후 체크리스트 (필수)
- [ ] PDF 업로드 → 문제 생성 정상 (Next `/manage/upload-pdf`)
- [ ] 문제 분류(수동/일괄) 정상 (Next `/exam/unclassified`)
- [ ] AI 분류 시작/상태/적용 정상
- [ ] 강의 노트 업로드/인덱싱 정상 (Legacy `/manage/lecture/<id>`)
- [ ] Practice 흐름 정상 (Legacy `/practice/*`, Next `/lectures`)
- [ ] Next.js `/manage`, `/lectures` 렌더링 정상
- [ ] Local admin 실행 가능 (`run_local_admin.py`)
- [ ] 문서/README 반영 완료

## 4) 위험 신호
- 요청당 쿼리 수 급증 (페이지 로딩 느려짐)
- 업로드 이미지/파일 경로 불일치
- `PDF_PARSER_MODE` 변경 시 파싱 결과 차이 발생
- API 응답 구조 변경으로 프론트 오류 발생
- AI 분류 결과가 비어있거나 적용 실패

## 5) 복구 전략
- DB 백업 복구
- 마지막 정상 커밋/브랜치로 롤백
- API 변경 이력 문서화 후 단계적으로 적용
