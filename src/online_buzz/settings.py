"""추가 분석 1 (온라인 언급·검색 키워드) — 공통 설정

기간·경로·채널을 이 파일 한 곳에서 정한다. 검색어·시군 별칭·거를 글은 키워드 사전
(input/online_buzz/키워드사전_v*.csv)에서 읽는다. 레포 공통 경로(input/·output/)는 src/paths.py 를 따른다.
값을 바꾼 경우 보고서의 '데이터 수집 기준' 표도 함께 갱신할 것.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 경로 — 코드는 src/online_buzz/, 사람이 만든·내려받은 파일은 input/online_buzz/, 코드가 만든 파일은 output/online_buzz/
# ---------------------------------------------------------------------------
SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
try:  # 레포 공통 경로 (src/paths.py)
    import paths as _paths

    REPO_ROOT, INPUT, OUTPUT = _paths.ROOT, _paths.INPUT, _paths.OUTPUT
except ModuleNotFoundError:  # src/paths.py 가 아직 없는 브랜치에서도 같은 위치를 쓴다
    REPO_ROOT = SRC.parent
    INPUT, OUTPUT = REPO_ROOT / "input", REPO_ROOT / "output"

ENV_FILE = REPO_ROOT / ".env"                  # NAVER_CLIENT_ID / NAVER_CLIENT_SECRET (git 제외)
DICT_DIR = INPUT / "online_buzz"               # 키워드 사전. 다른 사전은 환경변수 IMSIL_KEYWORD_DICT 로 지정

# 아래 두 폴더는 테스트에서 환경변수로 임시 폴더로 바꾼다
BUZZ_IN = Path(os.getenv("IMSIL_BUZZ_IN", INPUT / "online_buzz"))
BUZZ_OUT = Path(os.getenv("IMSIL_BUZZ_OUT", OUTPUT / "online_buzz"))

MANUAL_DIR = BUZZ_IN                           # 웹 다운로드 원본: naver_datalab/, naver_searchad/, google_trends/
CHECK_IN = BUZZ_IN / "keyword_check"           # 사람이 '맞음' 열을 채운 확인표 (링크가 있어 git 제외)
RAW_DIR = BUZZ_OUT / "raw"                     # 검색 API 원본 (블로그 링크에 작성자 ID 가 있어 git 제외)
PROCESSED_DIR = BUZZ_OUT                       # 결과표: output/online_buzz/<수집일 또는 manual_YYYYMMDD>/
CHECK_OUT = BUZZ_OUT / "keyword_check"         # 빈 확인표(git 제외)와 확인결과·판정표(커밋)
COLLECTION_LOG = BUZZ_OUT / "수집기록.csv"

# ---------------------------------------------------------------------------
# 분석 기간
# ---------------------------------------------------------------------------
# 지난 34개 관광지 리뷰 분석과 동일하게 2022-01-01부터.
# 데이터랩은 2016-01-01부터 조회 가능하므로 장기 추세가 필요하면 TREND_LONG_START 사용.
START_DATE = "2022-01-01"
END_DATE = "2026-10-31"
TREND_LONG_START = "2016-01-01"

# ---------------------------------------------------------------------------
# 검색어·별칭·거를 글: input/online_buzz/키워드사전_v*.csv (가장 높은 버전)에서 읽는다.
# 환경변수 IMSIL_KEYWORD_DICT 로 다른 사전을 지정할 수 있다.
# ---------------------------------------------------------------------------
from . import keyword_dict as _kd  # noqa: E402

KEYWORD_DICT_FILE = _kd.default_path()
KEYWORDS = _kd.load(KEYWORD_DICT_FILE)

# 전북특별자치도 14개 시군: 시군 -> 본문 인정 표현 (지표 C), 본문 제외 표현
JEONBUK_REGIONS: dict[str, list[str]] = _kd.regions(KEYWORDS)
JEONBUK_REGION_EXCLUDES: dict[str, list[str]] = _kd.region_excludes(KEYWORDS)
# 시군별 언급량 조회 (시군, 검색어) — 지표 A·B
REGION_QUERIES: list[tuple[str, str]] = _kd.region_queries(KEYWORDS)
# 전북 관광 게시물 표본 검색어 — 지표 C 의 분모
JEONBUK_TOURISM_QUERIES: list[str] = _kd.jeonbuk_queries(KEYWORDS)

# 데이터랩 주제어 묶음 (그룹당 최대 20개, 요청당 5그룹) — 모든 요청에 기준어(anchor)를 넣는다
TREND_ANCHOR = _kd.anchor(KEYWORDS)
REGION_TREND_GROUPS: dict[str, list[str]] = _kd.trend_groups(KEYWORDS, ("지역",))
IMSIL_TREND_GROUPS: dict[str, list[str]] = {
    TREND_ANCHOR: REGION_TREND_GROUPS.get(TREND_ANCHOR, []),
    **_kd.trend_groups(KEYWORDS, ("관광지", "축제", "특산물")),
}

# 검색광고 키워드도구 시드
SEARCHAD_SEEDS: list[str] = _kd.searchad_seeds(KEYWORDS)

# 임실 관련 게시물 수집 (주제어, 검색어) 와 주제어별 거를 글
IMSIL_POST_QUERIES: list[tuple[str, str]] = _kd.post_queries(KEYWORDS)
TOPIC_EXCLUDES: dict[str, list[str]] = _kd.topic_excludes(KEYWORDS)
# 임실 관련 글 판정 표현
IMSIL_TERMS: list[str] = _kd.imsil_terms(KEYWORDS)

# Google Trends
GOOGLE_GEO = "KR"
GOOGLE_GEO_JEONBUK = "KR-45"  # ISO 3166-2: 전북특별자치도(구 전라북도)
# 키워드 사전 범위 규칙을 따른다('붕어섬'·'옥정호' 단독은 쓰지 않음). 요청당 5개까지.
GOOGLE_TERMS = ["임실 여행", "임실치즈테마파크", "옥정호 출렁다리", "임실N치즈축제", "임실치즈"]

# ---------------------------------------------------------------------------
# 네이버 검색 API 채널
# ---------------------------------------------------------------------------
# cafearticle 은 응답에 작성일이 없으므로 기간 집계에서는 제외되고 total 만 쓴다.
NAVER_SEARCH_CHANNELS = ["blog", "cafearticle", "news"]
NAVER_SEARCH_MAX_START = 1000  # API 제한: start <= 1000, display <= 100  → 질의당 최대 1,099건
