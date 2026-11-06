# 임실군 관광 온라인 언급·검색 키워드 분석

전북연구원·임실군청 추가 요청(2026-11) 중 **1. 임실군 관광 관련 온라인 언급 및 주요 키워드 분석**의 코드와 데이터입니다.
코드는 `src/online_buzz/`, 사람이 만들거나 내려받은 입력은 `input/online_buzz/`, 결과는 `output/online_buzz/`에 있습니다.

| 항목 | 내용 |
|---|---|
| 분석 기간 | 2022-01-01 ~ 2026-10-31 (`src/online_buzz/settings.py`의 `START_DATE`·`END_DATE`) |
| 수집일 | 2026-11-07 하루에 몰아서 받습니다. 분석은 저장된 원본만 읽고 API를 다시 부르지 않습니다 |
| 비교 범위 | 전북특별자치도 14개 시군 |
| 데이터 | 네이버 검색 API(블로그·카페·뉴스) + 웹에서 내려받은 데이터랩·검색광고 키워드도구·Google Trends |
| 검색어 범위 | [`input/online_buzz/키워드사전_v1.csv`](../input/online_buzz/키워드사전_v1.csv) |
| 최종 제출 | 2026-11-14 |

## 무엇을 재는가

| 지표 | 출처 | 값의 성격 | 결과 파일 |
|---|---|---|---|
| A. 누적 언급량·비중 | 검색 API `total` (블로그·카페·뉴스) | 수집일 기준 누적 검색결과 수. 기간 지정 불가 | `A_mention_totals.csv` |
| B. 최근 게시 속도 | 검색 API 최신순 최대 1,099건의 작성일 | 일평균 게시물 수(블로그·뉴스, 카페는 작성일이 없음) | `B_posting_rate.csv`, `B_monthly_posts.csv` |
| C. 전북 관광 게시물 안의 언급 비중 | '전북 여행'류 게시물 표본의 제목·요약에서 시군 표현 매칭 | 언급률(%)·점유율(%) | `C_jeonbuk_mention_share*.csv`, `C_imsil_co_regions.csv` |
| 네이버 검색 추이 | 데이터랩 검색어트렌드(웹 다운로드) | 조회 안 최대값=100인 상대값 → 임실 평균=100으로 맞춤 | `M_datalab_*.csv` |
| 절대 검색수·연관검색어 | 검색광고 키워드도구(웹 다운로드) | 조회일 기준 최근 30일 PC·모바일 검색수 | `M_searchad_keywords_long.csv`, `M_search_keywords_*.csv` |
| Google 검색 추이 | Google Trends(웹 다운로드) | 0~100 상대값. 소규모 검색어는 0이 많아 보조 지표 | `M_google_*.csv` |
| 게시물 키워드·연관관계 | 임실 관련 게시물 제목+요약 → Kiwi | 빈도·문서빈도·TF-IDF, 연관규칙(지지도 ≥0.01, 신뢰도 ≥0.20, 향상도 >1), 네트워크 중심성 | `K_post_*.csv`, `R_*.csv` |

- **언급 건수와 검색 트렌드는 다른 지표입니다.** 언급량은 글을 쓴 사람의, 검색 트렌드는 검색한 사람의 관심입니다. 단위와 모집단이 달라 합치거나 같은 축에 놓지 않고 따로 해석한 뒤 둘의 격차를 시사점으로 씁니다.
- 검색 API `total`은 '언급 건수'가 아니라 '검색 결과 수(수집일 기준 누적)'로 적습니다.
- 데이터랩·Google Trends 값은 서로 다른 조회 파일끼리 바로 비교하지 않고, 공통 기준 주제어(임실)로 맞춘 뒤에만 비교합니다(`analysis/trends.py`의 `chain_by_anchor`).
- 전처리와 키워드·연관관계 기준은 34개소 리뷰 분석과 같습니다. Kiwi 형태소 분석(NNG·NNP·VV·VA, 동사·형용사는 '~다'), '없다·아쉽다·비싸다' 같은 불만 표현은 불용어로 지우지 않습니다.

## 준비

```bash
pip install -r requirements-online_buzz.txt
```

- Python 3.11 이상. `kiwipiepy`는 34개소 분석과 같은 0.23.2로 고정했습니다. 버전이 다르면 형태소 분석 결과가 달라집니다.
- 레포 최상위의 `.env`(git에 올라가지 않음)에 네이버 검색 API 키를 넣습니다. 키는 [developers.naver.com](https://developers.naver.com)에서 애플리케이션을 등록하고 '검색' API를 추가하면 무료로 받습니다(하루 25,000회, 이번 수집은 약 1,900회).

```bash
NAVER_BACKEND=developers     # NAVER Cloud API HUB 에서 받은 키라면 apihub
NAVER_CLIENT_ID=발급받은_ID
NAVER_CLIENT_SECRET=발급받은_Secret

# 선택 단계(03_collect_searchad_keywords.py)를 쓸 때만
SEARCHAD_API_KEY=
SEARCHAD_SECRET_KEY=
SEARCHAD_CUSTOMER_ID=
```

## 실행 순서

명령은 모두 **레포 최상위에서** 실행합니다.

### 0. 검색어 범위 확인 (수집 전)

```bash
python src/online_buzz/00_keyword_check_sheet.py make
#   → output/online_buzz/keyword_check/확인표_YYYYMMDD_blog.csv 를 input/online_buzz/keyword_check/ 로 복사해 '맞음' 열에 O/X
python src/online_buzz/00_keyword_check_sheet.py summarize input/online_buzz/keyword_check/확인표_YYYYMMDD_blog.csv
#   → output/online_buzz/keyword_check/확인결과_*.csv (검색어별 20건 중 맞은 수), 판정_*.csv (글별 O/X)
```

20건 중 X가 3건을 넘는 검색어는 키워드 사전에서 좁힌 새 버전(v2…)을 만들고 비고에 날짜와 이유를 적습니다.

### 1. 수집 (2026-11-07)

```bash
python src/online_buzz/01_collect_naver_search.py    # → output/online_buzz/raw/YYYYMMDD/
```

같은 날 데이터랩·키워드도구·Google Trends 화면에서 파일을 내려받아 `input/online_buzz/`의 각 폴더에 넣습니다.
폴더별 형식과 파일명 규칙은 [input/online_buzz/README.md](../input/online_buzz/README.md)에 있습니다.

`02_collect_naver_datalab.py`·`03_collect_searchad_keywords.py`·`04_collect_google_trends.py`는 같은 자료를 API로 받는 선택 경로입니다. 요청이 있을 때만 씁니다.

### 2. 분석

```bash
python src/online_buzz/05_analyze.py                 # → output/online_buzz/YYYYMMDD/ (API 원본이 없으면 manual_YYYYMMDD/)
```

있는 원본만 분석하고 없는 단계는 건너뜁니다. `--snapshot YYYYMMDD`로 특정 수집일의 원본을 고를 수 있습니다.

### 3. 수집 기록

```bash
python src/online_buzz/06_record_collection.py --processed   # → output/online_buzz/수집기록.csv
python src/online_buzz/06_record_collection.py --verify      # 다른 PC 에서 같은 원본·결과인지 확인
```

파일마다 크기·SHA-256·키워드 사전 버전·git 커밋을 남깁니다. API 원본은 git에 올리지 않지만 지문은 이 기록으로 커밋되므로, 원본을 따로 전달받은 사람은 `--verify`로 같은 파일인지 확인할 수 있습니다.

### 테스트

```bash
python -m pytest -q src/online_buzz/tests
```

네트워크 없이 가짜 API 응답으로 수집 → 분석 전체 흐름, 웹 다운로드 파일 로더, 키워드 사전 범위 규칙, 작성자 정보가 git에 올라가지 않는지를 확인합니다.

## 작성자 정보 처리

레포가 공개이므로 작성자를 알아볼 수 있는 정보는 커밋하지 않습니다.

| 파일 | 담긴 것 | 처리 |
|---|---|---|
| `output/online_buzz/raw/` | 블로그 링크(작성자 ID 포함), 제목·요약 | git 제외. 블로그 닉네임(`bloggername`)은 수집할 때부터 저장하지 않습니다 |
| `output/online_buzz/keyword_check/확인표_*.csv`, `input/online_buzz/keyword_check/` | 블로그 링크, 제목·요약 | git 제외 |
| `output/online_buzz/keyword_check/판정_*.csv` | 검색어·순번·작성일·O/X | 커밋 (링크·제목 없음) |
| `output/online_buzz/<수집일>/` | 집계표, 게시물별 토큰 | 커밋. 게시물은 가명 `post_id`(P000001…)로만 가리키고 링크·출처 열을 두지 않습니다 |

제출용 원본 데이터셋을 만들 때도 수집 원본을 그대로 내지 않고 링크·출처 열을 뺀 사본을 씁니다(`utils.drop_private`).

## 폴더 구성

```
src/online_buzz/
  settings.py              기간·경로·채널. 검색어 목록은 키워드 사전에서 만든다
  keyword_dict.py          키워드 사전 로더
  naver.py                 네이버 검색·데이터랩 클라이언트 (개발자센터, NAVER Cloud API HUB)
  searchad.py              검색광고 키워드도구 클라이언트 (선택)
  manual.py                웹 다운로드 파일 로더 (데이터랩, 키워드도구, Google Trends)
  google_trends.py         pytrends 수집(선택) / Google Trends CSV 로더
  snapshot.py              수집일별 원본 폴더
  utils.py                 .env 읽기, HTML 정리, JSONL, 작성자 정보 열 제거
  analysis/
    mentions.py            지표 A·B·C, 시군 판정(RegionMatcher)
    trends.py              데이터랩 기준어 재척도화, 절대량 환산(추정), 계절성
    keywords.py            Kiwi 전처리, 빈도·TF-IDF
    association.py         연관규칙, 동시출현 네트워크, 검색 연관어 네트워크
  00_keyword_check_sheet.py ~ 06_record_collection.py   확인표 → 수집 → 분석 → 수집기록
  tests/                   네트워크 없이 도는 테스트
input/online_buzz/         키워드 사전, 웹 다운로드 원본, 채운 확인표(git 제외)
output/online_buzz/
  raw/YYYYMMDD/            검색 API 원본 (git 제외)
  keyword_check/           확인표(git 제외), 확인결과·판정(커밋)
  YYYYMMDD/ · manual_YYYYMMDD/   결과표
  수집기록.csv
```
