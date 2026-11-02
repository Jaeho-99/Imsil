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
| 검색 트렌드(네이버) | 데이터랩 검색어트렌드 | 상대지수(요청 내 최대=100) → 임실 기준 재척도화 | `T_*.csv` |
| 절대 검색수·연관검색어 | 네이버 검색광고 키워드도구 | 최근 30일 PC/모바일 검색수(절대값) | `K_search_keywords*.csv`, `T_estimated_searches.csv` |
| 검색 트렌드(Google) | Google Trends (pytrends 또는 수동 CSV) | 상대지수 0~100 | `G_*.csv` |
| 게시물 키워드·연관관계 | 임실 관련 게시물 제목+요약문 → Kiwi | 빈도, 문서빈도, TF-IDF, 연관규칙(지지도·신뢰도·향상도), 네트워크 중심성 | `K_post_*.csv`, `R_*.csv` |

> 언급량(A·B·C)은 **게시물을 쓴 사람**의 관심, 검색 트렌드는 **검색한 사람**의 관심이다. 두 지표는 단위와 모집단이 달라 직접 더하거나 비교하지 않고 따로 해석한다.

### 실행 방법 (기본: 웹에서 내려받은 CSV/XLSX)

```bash
pip install -r requirements.txt
# 1) 네이버 데이터랩·Google Trends 화면에서 내려받은 파일, 직접 정리한 언급 건수·게시물 표를
#    data/manual/ 아래에 넣는다 (형식·파일명 규칙: data/manual/README.md)
python scripts/05_analyze.py      # → data/processed/online_buzz/manual_YYYYMMDD/M_*.csv
pytest -q                         # 테스트
```

Claude Code 로 이어서 작업할 때의 규칙·방법론·보고서 구성은 [`CLAUDE.md`](CLAUDE.md) 에 정리했다.

<details><summary>선택: API 로 자동 수집하는 경우</summary>

```bash
cp .env.example .env        # 네이버 API 키, 검색광고 API 키 입력
python scripts/01_collect_naver_search.py       # 언급량·게시물 (약 1,900회 호출)
python scripts/02_collect_naver_datalab.py      # 검색어 트렌드
python scripts/03_collect_searchad_keywords.py  # 연관검색어·절대 검색수
python scripts/04_collect_google_trends.py      # pytrends
python scripts/05_analyze.py
```

원본은 `data/raw/online_buzz/YYYYMMDD/` 에 저장되고 `meta.json` 에 수집 시각과 조건이 남는다.
네이버 개발자센터와 NAVER Cloud API HUB 를 `.env` 의 `NAVER_BACKEND` 로 고른다.
</details>

- 수집 대상·기간·검색어·시군 별칭은 모두 `src/imsil_buzz/settings.py` 한 곳에서 바꾼다.

### 폴더 구조

```
src/imsil_buzz/
  settings.py          지역·검색어·기간 설정
  naver.py             네이버 검색·데이터랩 클라이언트
  searchad.py          네이버 검색광고 키워드도구 클라이언트
  manual.py            웹 다운로드 파일 로더(데이터랩 xlsx/csv, Google Trends, 언급 건수·게시물 표)
  google_trends.py     pytrends 수집 / Google Trends CSV 로더
  analysis/
    mentions.py        지표 A·B·C
    trends.py          데이터랩 anchor 재척도화, 절대량 환산, 계절성
    keywords.py        Kiwi 전처리, 빈도·TF-IDF
    association.py     연관규칙, 동시출현 네트워크, 검색 연관어 네트워크
scripts/01~05          수집 → 분석 순서대로 실행
data/manual/         웹에서 내려받은 원본 (README.md 에 형식)
data/raw|processed
tests/                 네트워크 없이 도는 테스트
```
