---
description: RAW STT 설교 원문을 무손실 정제하여 HYC-Roman 웹북에 추가 및 자동 빌드
---

# HYC-Roman 강해 설교 STT 정제 워크플로우

1. RAW STT 텍스트 100% 문장 보존 윤문 (`[음악]` 등 지문 100% 삭제, STT 오타/비문 보정)
2. 헬라어/히브리어 언급 시 괄호 속에 해당 용어(원어/음역) 병기 표기
3. 15개 소제목(`###`) 구조화 및 독서용 문단 나누기 (이탤릭체 `*text*`, `_text_` 사용 금지)
4. `sources/romans/Rom<Ch>-<StartV>-<EndV>.md` 원천 소스 저장
5. `corpus/manifest.json` 코퍼스 대장에 신규 세션 등록
6. `python3 tools/build.py && python3 harness.py` 웹북 빌드 및 검수 통과 확인
