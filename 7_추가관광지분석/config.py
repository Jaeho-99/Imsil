# -*- coding: utf-8 -*-
"""추가 관광지 2개소 분석 — 공통 설정

분석 대상, 수집 기간, 불용어, 경로를 이 파일 한 곳에서 정한다.
모든 스크립트(scripts/*.py)가 이 파일을 읽으므로 값을 바꾸면 전 단계에 같이 반영된다.

수집 전에 채워야 하는 값
  - TARGETS[*]["naver_place_id"] : 네이버 지도 URL의 /place/{숫자} 부분 (2026-11-03 입력 완료)
  - 구글 장소는 1_데이터수집/구글/google_reviews.py 의 TARGETS 에 있다 (같은 이름으로 등록)
수집 후에 고정해야 하는 값
  - DATE_END : 수집일 전날로 고정한다. 34개소 분석(2026-08-10)과 같은 방식이다.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # 7_추가관광지분석/
REPO = ROOT.parent                               # 레포 최상위

# 시험 실행 모드 — IMSIL_DEMO=1 이면 34개소 데이터의 인접 관광지 리뷰로 만든 가짜 수집 원본을
# _demo/ 아래에서 처리한다. 실제 data/·output/ 은 건드리지 않는다 (_demo/ 는 git 제외).
DEMO = os.environ.get("IMSIL_DEMO") == "1"
WORK = ROOT / "_demo" if DEMO else ROOT
# 시험 실행에서 가짜 수집 원본으로 쓸 34개소 관광지 (리뷰가 넉넉한 곳)
DEMO_SOURCES = {"성수산": "사선대관광지", "오수의견국민여가캠핑장": "임실치즈마을"}

# ─────────────────────────────────────────────────────────────
# 분석 대상
# ─────────────────────────────────────────────────────────────
TARGETS = [
    {
        "name": "성수산",
        "naver_place_id": "13491702",      # m.place.naver.com/place/13491702
        # 키워드 분석에서 관광지명 자체를 빼는 불용어 (34개소 노트북의 place_specific_stopwords 방식)
        "place_stopwords": {"성수산", "임실"},
    },
    {
        "name": "오수의견국민여가캠핑장",
        "naver_place_id": "2006533162",    # m.place.naver.com/place/2006533162
        "place_stopwords": {"오수", "의견", "오수의견", "국민여가", "캠핑장",
                            "국민여가캠핑장", "임실"},
    },
]
TARGET_NAMES = [t["name"] for t in TARGETS]

# 34개소 분석에 이미 있는 인접 관광지 — 비교 기준으로만 쓰고 새 수집 대상에는 넣지 않는다.
COMPARE_PLACES = {
    "성수산": "성수산왕의숲자연휴양림",
    "오수의견국민여가캠핑장": "오수의견공원",
}

# ─────────────────────────────────────────────────────────────
# 수집 기간 — 34개소 분석과 같은 시작일
# ─────────────────────────────────────────────────────────────
DATE_START = "2022-01-01"
DATE_END = "2026-11-02"  # 첫 수집일(2026-11-03) 전날. 플랫폼마다 수집일이 달라도 같은 기간을 보도록 고정
                         # None 이면 상한 없이 쓰고 경고를 낸다.

# 네이버 리뷰의 날짜로 쓸 필드. created(작성일)가 구글의 작성일과 같은 의미다.
NAVER_DATE_FIELD = "created"

# 가명 리뷰ID 시작 번호. 34개소 데이터(RV00001~RV05267)와 겹치지 않게 10001부터 쓴다.
REVIEW_ID_START = 10001

# ─────────────────────────────────────────────────────────────
# 경로
# ─────────────────────────────────────────────────────────────
RAW_DIR = WORK / "data" / "raw"                  # 수집 원본 (작성자 정보 포함 → git 제외)
RAW_NAVER = RAW_DIR / "naver"
RAW_GOOGLE = RAW_DIR / "google"
ID_MAP = RAW_DIR / "리뷰ID_대응표.csv"           # 원본 ID ↔ 가명 ID (git 제외)

DATA_DIR = WORK / "data"
DATASET = DATA_DIR / "추가관광지_리뷰데이터.csv"             # 통합 원본 (비식별)
PREPROCESSED = DATA_DIR / "추가관광지_리뷰데이터_1차전처리.csv"
KEYWORD_DATA = DATA_DIR / "추가관광지_리뷰데이터_키워드전처리완료.csv"
TRANSLATE_TODO = DATA_DIR / "번역대상.csv"
TRANSLATE_DONE = DATA_DIR / "번역결과.csv"
MASK_RULES = DATA_DIR / "비식별_치환목록.csv"

OUT = WORK / "output"
OUT_KEYWORD = OUT / "1_키워드"
OUT_ASSOC = OUT / "2_연관관계"
OUT_SENT = OUT / "3_감성"
OUT_FACTOR = OUT / "4_만족불만요인"
OUT_SUMMARY = OUT / "5_요약"

# 34개소 분석 산출물 (비교·재사용)
BASE_KEYWORD_DATA = REPO / "2_키워드분석" / "리뷰데이터_키워드전처리완료.csv"
BASE_SENT_REVIEW = (REPO / "3_감성분석_and_6_시계열분석" / "분석" / "감성분석"
                    / "fullscale-final" / "전수_리뷰라벨_최종.csv")
BASE_SENT_SENTENCE = BASE_SENT_REVIEW.with_name("전수_문장라벨_최종.csv")
BASE_FACTOR = (REPO / "4_연관관계분석_and_5_만족-불만요인분석" / "output"
               / "리뷰별_만족불만요인_분석결과.csv")
SENT_DIR = REPO / "3_감성분석_and_6_시계열분석" / "분석" / "감성분석"
PROMPT_V1 = SENT_DIR / "llm-labeling" / "프롬프트_v1.md"
FACTOR_DIR = REPO / "4_연관관계분석_and_5_만족-불만요인분석"

# ─────────────────────────────────────────────────────────────
# 키워드 분석 — 34개소 노트북(2_키워드분석)과 같은 값
# ─────────────────────────────────────────────────────────────
TARGET_POS = {"NNG", "NNP", "VV", "VA"}
COMMON_STOPWORDS = {"곳", "장소", "여기", "하다", "되다", "있다", "가다", "오다", "보다",
                    "들다", "주다", "때", "것", "방문"}
ANALYSIS_STOPWORDS = {"좋다", "많다", "같다", "생각", "다녀오다", "나오다", "추천"}

# ─────────────────────────────────────────────────────────────
# LLM — 감성(프롬프트 v1)·요인 추출·번역
# ─────────────────────────────────────────────────────────────
# 요인 추출: 34개소와 같은 모델로 돌려야 두 결과를 나란히 놓을 수 있다.
FACTOR_MODEL = "claude-opus-5"           # analyze_satisfaction.py 기본값
FACTOR_EFFORT = "medium"
# 감성분류·번역: 프롬프트 v1을 API로 실행. 현재 모델은 temperature 를 받지 않으므로
# 34개소와 마찬가지로 독립 2회 실행의 불일치율로 변동성을 보고한다.
SENT_MODEL = "claude-opus-5-5"
SENT_EFFORT = "high"
SENT_CHUNK = 150                 # 34개소 전수 적용 묶음 크기와 같다
SENT_SEED = 20261102
SENT_UNIT_PREFIX = "ADD"         # 문장 unit_id: ADD-00001 (check_output.py 정규식과 호환)
