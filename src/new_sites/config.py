# -*- coding: utf-8 -*-
"""추가 관광지 2개소 분석 — 공통 설정

분석 대상, 수집 기간, 불용어, 경로를 이 파일 한 곳에서 정한다.
src/new_sites/ 의 모든 스크립트가 이 파일을 읽으므로 값을 바꾸면 전 단계에 같이 반영된다.
레포 공통 경로(input/·output/)는 src/paths.py 에 있다.

수집 전에 채워야 하는 값
  - TARGETS[*]["naver_place_id"] : 네이버 지도 URL의 /place/{숫자} 부분 (2026-11-03 입력 완료)
  - PLATFORMS : 추가 관광지는 구글에 리뷰가 없어 네이버만 쓴다 (2026-11-05 결정).
수집 후에 고정해야 하는 값
  - DATE_END : 수집일 전날로 고정한다. 34개소 분석(2026-08-10)과 같은 방식이다.

API 를 쓰지 않는다 (2026-11-06)
  LLM 이 판정하는 단계(번역·문장 감성·만족·불만 요인)는 코드가 판정 대상을 output/ 에 내보내고,
  사람이 Claude Code 에서 지시문대로 판정해 결과를 input/new_sites/ 에 저장하면, 코드가 그 파일을 읽는다.
  34개소 분석도 같은 방식이었다(감성: ChatGPT 웹 UI, 요인: Claude Code 대화).
  지시문은 input/new_sites/claude_지시문/, 실행 순서는 docs/new_sites.md 에 있다.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/
import paths  # noqa: E402

REPO = paths.ROOT                                # 레포 최상위
HERE = Path(__file__).resolve().parent           # src/new_sites/

# 시험 실행 모드 — IMSIL_DEMO=1 이면 34개소 데이터의 인접 관광지 리뷰로 만든 가짜 수집 원본을
# output/_demo/ 아래에서 처리한다. 실제 input/·output/ 은 건드리지 않는다 (output/_demo/ 는 git 제외).
DEMO = os.environ.get("IMSIL_DEMO") == "1"
DEMO_DIR = paths.OUTPUT / "_demo"
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

# 분석에 쓰는 플랫폼. 구글을 넣으면 output/collect/google/ 의 같은 이름 수집 파일도 읽는다.
PLATFORMS = ["네이버"]

# 네이버 리뷰의 날짜로 쓸 필드. created(작성일)가 구글의 작성일과 같은 의미다.
NAVER_DATE_FIELD = "created"

# 가명 리뷰ID 시작 번호. 34개소 데이터(RV00001~RV05267)와 겹치지 않게 10001부터 쓴다.
REVIEW_ID_START = 10001

# ─────────────────────────────────────────────────────────────
# 경로
# ─────────────────────────────────────────────────────────────
# 수집 원본 — 작성자 정보 포함 → git 제외. 34개소 수집과 같은 폴더(output/collect/)를 쓴다.
RAW_NAVER = DEMO_DIR / "collect" / "naver" if DEMO else paths.NAVER_RAW   # {ID}_raw.json · {이름}_naver_reviews.csv
RAW_GOOGLE = DEMO_DIR / "collect" / "google" if DEMO else paths.GOOGLE_RAW
ID_MAP = RAW_NAVER / "추가관광지_리뷰ID_대응표.csv"   # 원본 ID ↔ 가명 ID (git 제외)

# 사람·Claude Code 가 만든 입력 (input/new_sites/). 코드는 읽기만 한다.
IN = DEMO_DIR / "input" if DEMO else paths.NEW_IN
MASK_RULES = IN / "비식별_치환목록.csv"                      # 실명으로 확인한 표현 → ○○○ (git 제외)
TRANSLATE_DONE = IN / "번역결과.csv"                         # 외국어 리뷰 번역 (Claude Code)
SENT_RUNS = IN / "sentiment" / "runs"                       # 문장 감성 판정 run1·run2 (Claude Code)
SENT_VAL_RUNS = IN / "sentiment" / "검증_34개소"              # 34개소 검증셋 판정 run1·run2 (Claude Code)
REVIEW_FILLED = IN / "사람검토표.xlsx"                       # 감성 사람 검토표 (채운 것)
FACTOR_ANN = IN / "satisfaction" / "annotations.jsonl"      # 만족·불만 요인 판정 (Claude Code)

OUT = DEMO_DIR / "new_sites" if DEMO else paths.NEW_OUT    # output/new_sites/
DATASET = OUT / "추가관광지_리뷰데이터.csv"                   # 통합 원본 (비식별)
PREPROCESSED = OUT / "추가관광지_리뷰데이터_1차전처리.csv"
TRANSLATE_TODO = OUT / "번역대상.csv"                       # 번역할 외국어 리뷰 (git 제외)
OUT_KEYWORD = OUT / "keyword"
KEYWORD_DATA = OUT_KEYWORD / "추가관광지_리뷰데이터_키워드전처리완료.csv"
OUT_ASSOC = OUT / "association"
OUT_SENT = OUT / "sentiment"
OUT_FACTOR = OUT / "satisfaction"
OUT_SUMMARY = OUT / "summary"
SENT_ARCHIVE = DEMO_DIR / "_감성_이전실행" if DEMO else paths.LOCAL / "new_sites_감성_이전실행"   # git 제외

# 34개소 분석 산출물 (비교·재사용)
BASE_DATASET = paths.REVIEWS
BASE_KEYWORD_DATA = paths.KEYWORD_DATA
BASE_SENT_REVIEW = paths.SENT_FINAL / "전수_리뷰라벨_최종.csv"
BASE_SENT_SENTENCE = paths.SENT_FINAL / "전수_문장라벨_최종.csv"
BASE_SENT_CHUNKS = paths.SENT_OUT / "llm_labeling" / "chunks"     # 34개소 검증셋 548문장 묶음
BASE_SENT_GOLD = paths.SENT_OUT / "labeling" / "확정"              # 34개소 사람 확정 라벨
BASE_SENT_RUNS = paths.SENT_IN / "llm_labeling" / "llm_runs"       # 34개소 검증셋 ChatGPT 판정 (시험 실행용)
BASE_FACTOR = paths.SATIS_RESULT
BASE_FACTOR_IN = paths.SATIS_IN                                    # 34개소 요인 판정 pending·annotations (시험 실행용)
PROMPT_V1 = paths.SENT_IN / "llm_labeling" / "프롬프트_v1.md"

# 34개소 코드 (고치지 않고 불러 쓴다)
SENT_SRC = paths.SRC / "sentiment"                       # textsplit.py, llm_labeling/check_output.py
COLLECT_SRC = paths.SRC / "collect"                      # naver_reviews.py
ASSOC_SCRIPT = paths.SRC / "association" / "analyze_association.py"
FACTOR_SCRIPT = paths.SRC / "satisfaction" / "analyze_satisfaction.py"

# ─────────────────────────────────────────────────────────────
# 키워드 분석 — 34개소 키워드 분석(src/keyword/keyword_analysis.py)과 같은 값
# ─────────────────────────────────────────────────────────────
TARGET_POS = {"NNG", "NNP", "VV", "VA"}
COMMON_STOPWORDS = {"곳", "장소", "여기", "하다", "되다", "있다", "가다", "오다", "보다",
                    "들다", "주다", "때", "것", "방문"}
ANALYSIS_STOPWORDS = {"좋다", "많다", "같다", "생각", "다녀오다", "나오다", "추천"}

# ─────────────────────────────────────────────────────────────
# 감성분석 — 34개소 전수 적용과 같은 조건 (프롬프트 v1, 150문장 묶음, 독립 2회 판정)
# ─────────────────────────────────────────────────────────────
SENT_CHUNK = 150                 # 34개소 전수 적용 묶음 크기와 같다
SENT_SEED = 20261102
SENT_UNIT_PREFIX = "ADD"         # 문장 unit_id: ADD-00001 (check_output.py 정규식과 호환)
