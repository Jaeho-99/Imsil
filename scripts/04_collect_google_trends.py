"""[수집 4] Google Trends.

기본: pytrends 로 자동 수집 → data/raw/online_buzz/<수집일>/google_*.csv
실패(429 등) 시: trends.google.com 에서 같은 조건으로 CSV 를 내려받아 data/manual/google_trends/ 에 저장하면
05_analyze.py 가 그 파일을 읽는다(파일명 규칙은 src/imsil_buzz/google_trends.py 참고).

조건: 대한민국 전체(KR)와 전북(KR-45) 두 지역, 기간 START_DATE~END_DATE, 카테고리 전체, 웹 검색.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from imsil_buzz import settings as S
from imsil_buzz.google_trends import collect_with_pytrends
from imsil_buzz.snapshot import new_snapshot


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
