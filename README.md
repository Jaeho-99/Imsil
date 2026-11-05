# 임실군 관광 빅데이터 분석

연세대학교 산업공학과 권상진 교수 연구팀 · 전북연구원/임실군 의뢰

| 과업 | 내용 | 코드 |
|---|---|---|
| 추가 분석 1 | 임실군 관광 온라인 언급량·비중, 네이버/Google 검색어 트렌드, 주요 키워드 및 연관관계 | `src/imsil_buzz`, `scripts/01~05` |
| 추가 분석 2 | 성수산·오수의견국민여가캠핑장 리뷰 분석 (지난 34개 관광지 분석 코드 재활용) | (예정) |

## 추가 분석 1: 온라인 언급·검색 키워드

### 무엇을 재는가

| 지표 | 출처 | 값의 성격 | 산출 파일 |
|---|---|---|---|
| A. 누적 언급량·비중 | 네이버 검색 API(블로그·카페·뉴스) `total` | 검색결과 문서 수, 기간 지정 불가(근사치) | `A_mention_totals.csv` |
| B. 최근 게시 속도 | 네이버 검색 API 최신순 최대 1,099건의 작성일 | 일평균 게시물 수(블로그·뉴스) | `B_posting_rate.csv`, `B_monthly_posts.csv` |
| C. 전북 관광 게시물 내 언급 비중 | '전북 여행' 류 게시물 표본에서 시군명·대표 관광지명 매칭 | 언급률(%)·언급 점유율(%) | `C_jeonbuk_mention_share*.csv`, `C_imsil_co_regions.csv` |
| 검색 트렌드(네이버) | 데이터랩 검색어트렌드(웹 다운로드) | 상대지수(요청 내 최대=100) → 임실 기준 재척도화 | `M_datalab_*.csv` |
| 절대 검색수·연관검색어 | 네이버 검색광고 키워드도구(웹 다운로드) | 최근 30일 PC/모바일 검색수(절대값) | `M_search_keywords*.csv` |
| 검색 트렌드(Google) | Google Trends(웹 다운로드) | 상대지수 0~100 | `M_google_*.csv` |
| 게시물 키워드·연관관계 | 임실 관련 게시물 제목+요약문 → Kiwi | 빈도, 문서빈도, TF-IDF, 연관규칙(지지도·신뢰도·향상도), 네트워크 중심성 | `K_post_*.csv`, `R_*.csv` |

> 언급량(A·B·C)은 **게시물을 쓴 사람**의 관심, 검색 트렌드는 **검색한 사람**의 관심이다. 두 지표는 단위와 모집단이 달라 직접 더하거나 비교하지 않고 따로 해석한다.

### 실행 방법

언급량·게시물은 네이버 검색 API(무료 키)로, 검색 추이·연관 키워드는 웹 다운로드 파일로 받는다(2026-11-05 결정).

```bash
pip install -r requirements.txt
cp .env.example .env                                   # NAVER_CLIENT_ID / SECRET (검색 API)

# 0) 키워드 범위 확인: 검색어별 최신 글 20건 확인표 → '맞음' 열에 O/X 표시 → 요약
python scripts/00_keyword_check_sheet.py make
python scripts/00_keyword_check_sheet.py summarize data/manual/keyword_check/확인표_YYYYMMDD_blog.csv

# 1) 수집일 하루에: 검색 API 수집 + 웹 다운로드 파일을 data/manual/ 에 저장
python scripts/01_collect_naver_search.py              # → data/raw/online_buzz/YYYYMMDD/ (약 1,900회 호출)

# 2) 분석 · 기록
python scripts/05_analyze.py                           # → data/processed/online_buzz/YYYYMMDD/
python scripts/06_record_collection.py --processed     # → data/수집기록.csv (파일별 SHA-256)
python scripts/06_record_collection.py --verify        # 다른 PC 에서 같은 원본·결과인지 확인
pytest -q
```

- 검색어·시군 별칭·거를 글은 [`config/키워드사전_v1.csv`](config/키워드사전_v1.csv) 한 파일에서 정한다(상태가 '확정'·'참고'인 행만 수집에 쓴다).
- 웹 다운로드 파일의 형식과 파일명 규칙은 [`data/manual/README.md`](data/manual/README.md), Claude Code 작업 규칙은 [`CLAUDE.md`](CLAUDE.md).
- `scripts/02~04` 는 데이터랩·검색광고·Google Trends 를 API 로 받는 선택 경로다(네이버 개발자센터와 NAVER Cloud API HUB 를 `.env` 의 `NAVER_BACKEND` 로 고른다).

### 폴더 구조

```
src/imsil_buzz/
  settings.py          기간·경로 설정, 키워드 사전에서 검색어 목록 생성
  keyword_dict.py      config/키워드사전_v*.csv 로더
  naver.py             네이버 검색·데이터랩 클라이언트
  searchad.py          네이버 검색광고 키워드도구 클라이언트
  manual.py            웹 다운로드 파일 로더(데이터랩, 검색광고 키워드도구, Google Trends, 언급 건수·게시물 표)
  google_trends.py     pytrends 수집 / Google Trends CSV 로더
  analysis/
    mentions.py        지표 A·B·C
    trends.py          데이터랩 anchor 재척도화, 절대량 환산, 계절성
    keywords.py        Kiwi 전처리, 빈도·TF-IDF
    association.py     연관규칙, 동시출현 네트워크, 검색 연관어 네트워크
config/                키워드 사전
scripts/00~06          확인표 → 수집 → 분석 → 수집기록
data/manual/         웹에서 내려받은 원본 (README.md 에 형식)
data/raw|processed
tests/                 네트워크 없이 도는 테스트
```
