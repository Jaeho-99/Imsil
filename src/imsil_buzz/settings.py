"""분석 대상 지역·키워드·기간 설정.

이 파일만 수정하면 수집 범위를 바꿀 수 있도록 모든 상수를 모아 두었다.
값을 바꾼 경우 보고서의 '데이터 수집 기준' 표도 함께 갱신할 것.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# 경로
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("IMSIL_DATA_DIR", REPO_ROOT / "data"))  # 테스트 시 임시 폴더로 바꿀 수 있음
RAW_DIR = DATA_DIR / "raw" / "online_buzz"
PROCESSED_DIR = DATA_DIR / "processed" / "online_buzz"
MANUAL_DIR = DATA_DIR / "manual"

# ---------------------------------------------------------------------------
# 분석 기간
# ---------------------------------------------------------------------------
# 지난 34개 관광지 리뷰 분석과 동일하게 2022-01-01부터.
# 데이터랩은 2016-01-01부터 조회 가능하므로 장기 추세가 필요하면 TREND_LONG_START 사용.
START_DATE = "2022-01-01"
END_DATE = "2026-10-31"
TREND_LONG_START = "2016-01-01"

# ---------------------------------------------------------------------------
# 검색어·별칭·거를 글: config/키워드사전_v*.csv (가장 높은 버전)에서 읽는다.
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
GOOGLE_TERMS = ["임실", "임실 여행", "임실치즈테마파크", "옥정호", "붕어섬"]

# ---------------------------------------------------------------------------
# 네이버 검색 API 채널
# ---------------------------------------------------------------------------
# cafearticle 은 응답에 작성일이 없으므로 기간 집계에서는 제외되고 total 만 쓴다.
NAVER_SEARCH_CHANNELS = ["blog", "cafearticle", "news"]
NAVER_SEARCH_MAX_START = 1000  # API 제한: start <= 1000, display <= 100  → 질의당 최대 1,099건
