# -*- coding: utf-8 -*-
"""레포의 모든 경로를 한 곳에 모은 파일 — 스크립트는 경로를 여기서 가져온다.

    input/   코드가 만들지 않는 파일
             통합 리뷰 데이터, 사람이 판정한 표, LLM 응답을 붙여 넣은 파일, 손으로 만든 규칙표
    output/  코드가 만든 파일. 앞 단계의 output 을 다음 단계가 읽는다.

경로는 이 파일의 위치로 계산하므로 어느 폴더에서 실행해도 같다.
스크립트 첫머리에서 아래처럼 불러온다.

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # src/ (하위 폴더면 parents[2])
    from paths import REVIEWS, TS_OUT
"""
from __future__ import annotations

import atexit
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # 레포 최상위
SRC = ROOT / "src"
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
ENV_FILE = ROOT / ".env"                            # ANTHROPIC_API_KEY (git 제외)
LOCAL = ROOT / ".local"                             # 이 컴퓨터에만 두는 파일: 로그인 프로필 등 (git 제외)

# ── 34개소 통합 리뷰 데이터 (비식별 처리본)
REVIEWS = INPUT / "임실군_관광지_리뷰데이터.csv"
REVIEWS_PRE = INPUT / "임실군_관광지_리뷰데이터_1차전처리.csv"

# ── 데이터 수집 — 작성자 정보가 들어 있어 naver/·google/ 은 git 에서 제외한다
COLLECT_OUT = OUTPUT / "collect"
NAVER_RAW = COLLECT_OUT / "naver"
GOOGLE_RAW = COLLECT_OUT / "google"

# ── 키워드 분석 (보고서 2장)
KEYWORD_OUT = OUTPUT / "keyword"
KEYWORD_DATA = KEYWORD_OUT / "리뷰데이터_키워드전처리완료.csv"

# ── 감성 분석 (보고서 3장)
SENT_IN = INPUT / "sentiment"
SENT_OUT = OUTPUT / "sentiment"
SENT_FINAL = SENT_OUT / "final"                    # 최종 문장·리뷰 감성 라벨

# ── 연관관계 분석 (4장) · 만족·불만 요인 분석 (5장)
ASSOC_OUT = OUTPUT / "association"
SATIS_IN = INPUT / "satisfaction"
SATIS_OUT = OUTPUT / "satisfaction"
SATIS_RESULT = SATIS_OUT / "리뷰별_만족불만요인_분석결과.csv"

# ── 시계열 분석 (6장)
TS_OUT = OUTPUT / "timeseries"

# ── 추가 관광지 2개소 (성수산 · 오수의견국민여가캠핑장)
NEW_IN = INPUT / "new_sites"
NEW_OUT = OUTPUT / "new_sites"


class _Tee:
    def __init__(self, stream, file):
        self._stream, self._file = stream, file

    def write(self, s):
        self._stream.write(s)
        self._file.write(s)
        return len(s)

    def flush(self):
        self._stream.flush()
        self._file.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def save_console(path: Path) -> None:
    """이후의 print 출력을 화면에 보이면서 파일에도 남긴다 (결과가 콘솔 출력뿐인 스크립트용)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "w", encoding="utf-8")
    screen = sys.stdout
    sys.stdout = _Tee(screen, f)

    def close():
        sys.stdout.flush()
        sys.stdout = screen
        f.close()

    atexit.register(close)
