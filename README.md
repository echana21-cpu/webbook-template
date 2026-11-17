# Sermon Webbook Template

마크다운(`.md`) 기반 강해 설교·성경 연구 원고를 **한글/영문 정적 웹북**으로 자동 빌드하는 범용 템플릿입니다.  
[koh-sermon.vercel.app](https://koh-sermon.vercel.app/)의 아키텍처를 기반으로, 누구든 자신의 설교·강의 코퍼스를 손쉽게 웹북으로 출판할 수 있도록 핵심 파이프라인과 샘플 데이터를 정리했습니다.

---

## 주요 기능

- **한글/영문 이중언어(Bilingual) 정적 웹북 빌드**: `sources/<book>/` 및 `sources/<book>_en/` 마크다운 원고를 `site/` 정적 HTML로 변환
- **개역개정(NKRV) 66권 성경 팝업 (RefPop)**: 본문 내 성경 구절(`창 6:5-9`, `마 5:3`, `롬 3:23` 등) 자동 인식 및 호버/클릭 팝업 지원
- **TKG 신학 지식 그래프 (`graph.html`)**: `D3.js` 기반 신학 개념·주장·관계 네트워크 시각화
- **원어 타이포그래피 & 서식**: 헬라어·히브리어 원어 표기, 굽은 따옴표 자동 변환, 대지/소대지/기도문 박스 렌더링
- **자동 검수 하네스 (`harness.py`)**: 매니페스트, 원천 파일, 빌드 결과, HTML 구조, 성경 팝업, 에셋 연결을 일괄 PASS/FAIL 검증
- **Vercel 즉시 배포**: `vercel.json` 설정으로 `site/` 정적 산출물 바로 배포 가능

---

## 디렉토리 구조

```text
webbook-template/
├── README.md                  # 프로젝트 안내 문서
├── harness.py                 # 전 구간 PASS/FAIL 검수 하네스
├── vercel.json                # Vercel 정적 배포 설정
├── bible/
│   └── NKRV/                  # 개역개정 66권 성경 JSON DB
├── corpus/
│   ├── manifest.json          # 설교 코퍼스 대장 (구약/신약, 한/영 경로)
│   ├── ontology.json          # TKG 신학 온톨로지 (개념/주장/관계)
│   └── lectures_data.json     # 주제별 강의 목록 (선택)
├── sources/                   # 샘플 마크다운 설교 원고 (OT/NT 한/영)
│   ├── genesis/
│   ├── genesis_en/
│   ├── matthew/
│   └── matthew_en/
├── templates/
│   └── modern_lectures.html   # 강의 자료실 리다이렉트 템플릿
├── tools/
│   ├── build.py               # 마크다운 -> 정적 HTML 웹북 빌드 스크립트
│   └── generate_modern_index.py # 모던 아카이브 index.html 생성기
└── site/                      # 빌드된 정적 웹북 산출물
    ├── index.html
    ├── graph.html
    └── assets/                # CSS, JS, D3.js
```

---

## 빠른 시작 (Quick Start)

Python 3.9+ 표준 라이브러리만으로 동작합니다 (별도 pip 패키지 설치 불필요).

```bash
# 1. 정적 웹북 빌드
python3 tools/build.py

# 2. 전 구간 하네스 검수
python3 harness.py

# 3. 로컬 브라우저로 확인
open site/index.html
open site/graph.html
```

---

## 새 설교 원고 추가 방법

1. `sources/<book>/` (한글) 및 `sources/<book>_en/` (영문, 선택)에 마크다운(`.md`) 원고 작성
2. `corpus/manifest.json`의 `sections` 배열에 새 섹션 등록
3. (선택) `corpus/ontology.json`에 핵심 신학 개념(`concepts`)과 주장(`claims`) 추가
4. 빌드 및 검수 실행:
   ```bash
   python3 tools/build.py && python3 harness.py
   ```
5. Vercel 배포:
   ```bash
   npx vercel --prod
   ```
