# 임실군 관광 빅데이터 분석 — Claude Code 작업 안내

연세대학교 산업공학과 권상진 교수 연구팀이 전북연구원·임실군청에 제출하는 분석이다. 레포 전체 설명은 `README.md`.
2026-11 추가 요청 두 건의 최종 제출: 2026-11-14(토). 산출물 = 결과보고서(A4 10쪽 이상, 한국어) + 전체 코드 + 원본·최종 데이터셋. 재현성이 중요하다.

| 과업 | 코드 | 문서 |
|---|---|---|
| 추가 분석 1 — 임실군 관광 온라인 언급·검색 키워드 | `src/online_buzz/` | `docs/online_buzz.md` |
| 추가 분석 2 — 성수산·오수의견국민여가캠핑장 리뷰 | `src/new_sites/` | `docs/new_sites.md` |

## 레포 공통 규칙

- 코드는 `src/<단계>/`, 코드가 만들지 않는 파일(웹에서 내려받은 원본, 사람이 판정한 표, 손으로 만든 규칙표)은 `input/<단계>/`, 코드가 만든 파일은 `output/<단계>/`. 스크립트는 `input/` 을 읽기만 한다(예외: 판정 입력 도구 `src/satisfaction/annotation/add.py`).
- 명령은 레포 최상위에서 `python src/<단계>/<스크립트>.py`. 경로는 `src/paths.py` 와 단계별 설정 파일(`src/online_buzz/settings.py` 등)에서 정한다.
- **원본 파일은 수정하지 않는다.** 정리·변환은 코드로 하고, 노트북이나 일회성 셀 대신 `src/` 스크립트로 남겨 다시 실행할 수 있게 한다.
- **공개 레포다.** 작성자 닉네임·ID·프로필 주소가 든 수집 원본은 커밋하지 않는다(`.gitignore`, 폴더별 `.gitignore`). 결과표는 가명 ID 만 쓴다. API 키는 `.env` 에만 둔다.
- 브랜치는 Git-Flow(`docs/Branch.md`): 기능 브랜치는 `develop` 에서 따고 `develop` 으로 PR 을 연다. `main` 은 배포용이다.
- 커밋 메시지는 `type: 제목`(`docs/Commit.md`): feat·fix·docs·style·refactor·test·chore 소문자, 제목 50자 이내, 마침표 없음, 한글 가능.
- 숫자를 보고서에 쓰기 전에 산출 CSV 에서 직접 확인한다. 추정치(예: 상대지수의 절대량 환산)는 '추정'으로 표기한다.

## 추가 분석 1 — 온라인 언급·검색 키워드 (`src/online_buzz/`)

- 전북 관광 온라인 게시물에서 임실군 언급 건수와 상대 비중
- 네이버 데이터랩·Google Trends 검색어 트렌드로 주요 검색 키워드 도출
- 주요 키워드 간 연관관계
- 온라인 관심 특성과 시사점

### 데이터 흐름 (언급량·게시물만 검색 API, 나머지는 웹 다운로드)

2026-11-05 결정: 비용 없이 다시 받을 수 있어야 해서 **언급량과 게시물만 네이버 검색 API**로 받고,
데이터랩·검색광고 키워드도구·Google Trends 는 웹에서 내려받은 파일을 `input/online_buzz/` 에 넣는다(형식: `input/online_buzz/README.md`).
수집은 하루(2026-11-07)에 몰아서 하고, 분석은 저장된 원본만 읽는다.

```
input/online_buzz/키워드사전_v*.csv                          ← 검색어·별칭·거를 글 (가장 높은 버전을 씀)
python src/online_buzz/00_keyword_check_sheet.py make       → output/online_buzz/keyword_check/확인표_*.csv
    (사람이 input/online_buzz/keyword_check/ 로 복사해 '맞음' 열 표시)
python src/online_buzz/00_keyword_check_sheet.py summarize <확인표>   → output/online_buzz/keyword_check/확인결과_*.csv, 판정_*.csv
python src/online_buzz/01_collect_naver_search.py           → output/online_buzz/raw/YYYYMMDD/  (검색 API, .env 키 필요, git 제외)
input/online_buzz/{naver_datalab,naver_searchad,google_trends}/   ← 웹 다운로드 원본(손대지 않음)
python src/online_buzz/05_analyze.py                        → output/online_buzz/<YYYYMMDD 또는 manual_YYYYMMDD>/
python src/online_buzz/06_record_collection.py --processed  → output/online_buzz/수집기록.csv (파일별 SHA-256, 사전 버전, 커밋)
python -m pytest -q src/online_buzz/tests                   ← 코드 수정 후 항상 실행
```

`src/online_buzz/02~04`(데이터랩·검색광고·Google Trends API)는 선택이다. 사용자가 요청하지 않으면 실행하지 않는다.
API 호출은 수집일에만 한다. 분석 중에 API 를 다시 부르지 않는다.

### 작업 규칙

- 검색어·시군 별칭·거를 글은 `input/online_buzz/키워드사전_v*.csv` 에서만 바꾼다. 바꾸면 새 버전(v2, v3…) 파일로 만들고 비고에 날짜와 이유를 적는다. 기간 등 나머지 설정은 `src/online_buzz/settings.py`. 분석 기간 기본값 2022-01-01~2026-10-31.
- 새 파일 형식을 읽어야 하면 `src/online_buzz/manual.py` 에 로더를 추가하고, 그 파일의 앞부분을 본뜬 작은 예시로 `src/online_buzz/tests/` 에 테스트를 추가한다.
- 블로그 닉네임(`bloggername`)은 수집하지 않는다. 블로그 링크에는 작성자 ID 가 있으므로 `output/online_buzz/raw/` 와 확인표는 커밋하지 않고, 결과표·제출본에서는 `link`·`source` 열을 빼고(`utils.drop_private`) 가명 `post_id` 로 가리킨다.
- 그림: matplotlib, 한글 폰트 지정(Malgun Gothic/AppleGothic/NanumGothic), 300dpi PNG 를 `output/online_buzz/<폴더>/fig/` 에 저장.

### 지표 해석 원칙

- **언급 건수 ≠ 검색 트렌드.** 언급량은 글을 쓴 사람, 검색 트렌드는 검색한 사람의 관심이다. 단위·모집단이 달라 합치거나 같은 축에 놓지 않고 따로 해석한 뒤 둘의 격차(검색은 많은데 후기가 적은 관광지 등)를 시사점으로 쓴다.
- 데이터랩·Google Trends 값은 조회 안 최대값=100 인 상대값이다. 서로 다른 조회 파일은 공통 기준 주제어(anchor)로 맞춘 뒤에만 비교한다(`analysis/trends.py: chain_by_anchor`).
- 시군 비교의 분모는 전북특별자치도 14개 시군. 키워드 사전의 범위 규칙을 따른다: 짧거나 흔한 이름은 '임실'·시설명을 붙이고(도화지→도화지 도예문화원, 오수→오수의견), 다른 곳에도 있는 이름은 임실 쪽 장소를 붙인다(붕어섬→옥정호 붕어섬, 옥정호 단독은 참고). 본문 시군 판정에서 '전주'·'완주' 단독은 다른 뜻(전주 대비, 마라톤 완주)과 겹쳐 관광 맥락 표현만 인정하고, '전주샹그릴라CC'는 임실로 센다. '장수'는 '장수군'만.
- 검색 API `total` 은 '언급 건수'가 아니라 '검색 결과 수(수집일 기준 누적)'로 적는다. 같은 날 받은 값끼리만 비교한다.
- Google Trends 는 소규모 검색어가 0 으로 나올 수 있어 보조 지표로 쓴다.

### 지난 34개 관광지 분석과 맞출 방법론 (보고서 일관성)

- 전처리: URL·HTML·특수문자 제거 → Kiwi 0.23.2 형태소 분석(NNG, NNP, VV, VA; 동사·형용사 기본형 '~다') → 공통 불용어 + 대상별 불용어(최소 제거 원칙). '없다·아쉽다·비싸다' 같은 불만 표현은 남긴다. (`analysis/keywords.py`)
- 키워드: Frequency → TF-IDF(그룹별 문서 통합) 순서로 제시.
- 연관관계: 게시물 1건 = 트랜잭션, 최소 지지도 0.01, 최소 신뢰도 0.20, 향상도 > 1 (`analysis/association.py: pair_rules`), 보조로 동시출현 네트워크 중심성.

### 보고서 구성(안)

1. 분석 개요(목적, 데이터 출처·수집일·기간, 지표 정의, 언급량과 검색량의 차이)
2. 온라인 언급량: 14개 시군 대비 임실 비중·순위, 채널별 차이, 함께 언급되는 시군
3. 검색 트렌드: 시군 비교, 임실 관광지·축제별 추이, 계절성·축제 시기 급증, 기기·성별·연령 특성, Google 비교
4. 주요 키워드와 연관관계: 연관검색어, 게시물 키워드 빈도·TF-IDF, 연관규칙, 네트워크
5. 종합 시사점과 한계
