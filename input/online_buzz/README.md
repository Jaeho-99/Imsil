# input/online_buzz — 온라인 언급·검색 키워드 분석에서 사람이 만들거나 내려받은 입력

코드가 만들지 않는 파일만 둡니다. `src/online_buzz/`의 코드는 이 폴더를 읽기만 합니다.
언급량과 게시물은 사람이 세지 않고 네이버 검색 API로 받습니다(`src/online_buzz/01_collect_naver_search.py` → `output/online_buzz/raw/<수집일>/`).

| 위치 | 만드는 법 | 읽는 곳 | git |
|---|---|---|:-:|
| `키워드사전_v*.csv` | 검색어·시군 별칭·거를 글을 손으로 정합니다. 가장 높은 버전을 씁니다 | 모든 스크립트 (`settings.py`) | ○ |
| `naver_datalab/` | 네이버 데이터랩 검색어트렌드 화면에서 내려받은 원본 | `05_analyze.py` | ○ |
| `naver_searchad/` | 네이버 검색광고 키워드도구 화면에서 내려받은 원본 | `05_analyze.py` | ○ |
| `google_trends/` | Google Trends 화면에서 내려받은 CSV | `05_analyze.py` | ○ |
| `keyword_check/` | `00_keyword_check_sheet.py make`가 만든 `output/online_buzz/keyword_check/확인표_*.csv`를 여기로 복사해 '맞음' 열을 채웁니다 | `00_keyword_check_sheet.py summarize` | 제외 (블로그 링크에 작성자 ID, 제목·요약이 있음) |

내려받은 파일은 손대지 않고 넣은 뒤 레포 최상위에서 `python src/online_buzz/05_analyze.py`를 실행합니다.
결과는 `output/online_buzz/<API 수집일 또는 manual_YYYYMMDD>/`에 `M_`로 시작하는 이름으로 저장됩니다.
실행 순서 전체는 [docs/online_buzz.md](../../docs/online_buzz.md)에 있습니다.

**파일명 규칙**: `다운로드일_내용_조건.확장자` (예: `20261109_시군비교_월간_2022-2026__anchor=임실.xlsx`).
다운로드일과 조건(기간, 단위, 기기·성별·연령 필터)을 파일명에 남겨야 보고서에 수집 기준을 정확히 적을 수 있습니다.

## 키워드사전_v*.csv — 검색어 범위

- 검색어·시군 별칭·거를 글은 이 파일에서만 바꿉니다. 바꾸면 새 버전(v2, v3…) 파일을 만들고 비고에 날짜와 이유를 적습니다.
- '상태'가 `확정`·`참고`인 행만 수집에 씁니다. `후보`·`확인필요`는 확인표로 먼저 확인합니다.
- 다른 사전을 시험할 때는 환경변수 `IMSIL_KEYWORD_DICT`에 경로를 줍니다.

## naver_datalab/ — 네이버 데이터랩 검색어트렌드

- 출처: https://datalab.naver.com > 검색어트렌드 > 조회 후 '다운로드'(엑셀)
- 원본 .xlsx를 그대로 넣습니다. .csv로 저장한 것도 읽습니다.
- 한 번에 주제어 5개까지만 비교되고, 값은 '조회 안 최대값=100'인 상대값입니다.
  **5개가 넘는 그룹(예: 전북 14개 시군)을 한 척도로 비교하려면** 모든 조회에 같은 기준 주제어(임실)를 넣고
  파일명에 `__anchor=임실`을 붙입니다. `05_analyze.py`가 기준 주제어 평균=100으로 맞춘 `M_datalab_index_anchor-임실.csv`를 만듭니다.
- 권장 조회 세트. 주제어 이름과 넣는 검색어는 키워드 사전의 '주제어'·'넣는 검색어'를 그대로 씁니다('쓰는 곳'에 검색추이가 있는 행).
  1. 시군 비교: 주제어 = 임실 + 다른 시군 4개 (×4회), 월간, 2022-01~2026-10, `__anchor=임실`
  2. 임실 관광지·축제·특산물: 주제어 = 임실 + 다른 주제어 4개씩, `__anchor=임실`
  3. 같은 조회를 기기(PC/모바일)·성별·연령 필터별로 한 번씩 (파일명에 필터 명시)
  4. 축제 전후 분석용 일간 조회

## naver_searchad/ — 네이버 검색광고 키워드도구

- 출처: https://searchad.naver.com > 도구 > 키워드 도구 > 키워드 입력(최대 5개) 후 '다운로드'
- 원본을 그대로 넣고, 파일명에 넣은 키워드를 `__seed=`로 적습니다(여러 개는 `+`). 예) `20261107_키워드도구__seed=임실여행+임실가볼만한곳.xlsx`
- 값은 조회일 기준 최근 30일 검색수입니다. '< 10'은 5로 바꾸고 `censored_lt10` 열에 표시합니다.

## google_trends/ — Google Trends

- 출처: https://trends.google.co.kr > 탐색 > 지역 '대한민국'(또는 전북), 기간 지정 > 각 차트의 다운로드(CSV)
- '시간 흐름에 따른 관심도' CSV는 아무 이름으로, '관련 검색어' CSV는 파일명에 `related`를 넣습니다
  (예: `20261109_KR_임실_related.csv`).
- 소규모 검색어는 0으로 나올 수 있어 보조 지표로 씁니다.

## keyword_check/ — 검색어 정확도 확인표 (git 제외)

1. `python src/online_buzz/00_keyword_check_sheet.py make`가 빈 확인표를 `output/online_buzz/keyword_check/`에 만듭니다.
2. 그 파일을 이 폴더로 복사해 엑셀에서 '맞음' 열에 O(임실 관광 관련 글) 또는 X(엉뚱한 글)를 적습니다.
   `output/`에서 바로 고치면 `make`를 다시 돌릴 때 덮어써집니다.
3. `python src/online_buzz/00_keyword_check_sheet.py summarize input/online_buzz/keyword_check/확인표_<날짜>_blog.csv`
   → `output/online_buzz/keyword_check/`에 `확인결과_*.csv`(검색어별 맞은 수)와 `판정_*.csv`(글별 O/X, 링크·제목 없음)가 생깁니다.
   20건 중 X가 3건을 넘는 검색어는 키워드 사전에서 좁힙니다.
