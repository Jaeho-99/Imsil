"""[수집 4, 선택] Google Trends (pytrends).

기본 경로는 웹 다운로드(input/online_buzz/google_trends/)다. 이 스크립트는 요청할 때만 쓴다.
pytrends 로 자동 수집 → output/online_buzz/raw/<수집일>/google_*.csv
실패(429 등) 시: trends.google.com 에서 같은 조건으로 CSV 를 내려받아 input/online_buzz/google_trends/ 에 저장하면
05_analyze.py 가 그 파일을 읽는다(파일명 규칙은 input/online_buzz/README.md 참고).

조건: 대한민국 전체(KR)와 전북(KR-45) 두 지역, 기간 START_DATE~END_DATE, 카테고리 전체, 웹 검색.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/

from online_buzz import settings as S
from online_buzz.google_trends import collect_with_pytrends
from online_buzz.snapshot import new_snapshot


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    ap.add_argument("--sleep", type=float, default=20.0)
    a = ap.parse_args()
    out = new_snapshot(a.snapshot)
    for geo in (S.GOOGLE_GEO, S.GOOGLE_GEO_JEONBUK):
        res = collect_with_pytrends(S.GOOGLE_TERMS, S.START_DATE, S.END_DATE, geo=geo, sleep=a.sleep)
        for name, df in res.items():
            df.to_csv(out / f"google_{name}_{geo}.csv", index=False, encoding="utf-8-sig")
    print("saved ->", out)


if __name__ == "__main__":
    main()
