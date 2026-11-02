"""[수집 3] 네이버 검색광고 키워드도구: 임실 관광 연관검색어 + 최근 30일 절대 검색수.

생성 파일 (data/raw/online_buzz/<수집일>/)
  searchad_related_keywords.csv   seed, keyword, monthly_pc, monthly_mobile, monthly_total, ...
  searchad_group_volumes.csv      데이터랩 키워드 그룹(시군·임실 관광지)의 최근 30일 검색수 합 → 절대량 환산용

검색광고 수치는 '조회 시점 기준 최근 30일'이므로 수집일을 반드시 기록한다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from imsil_buzz import settings as S
from imsil_buzz.searchad import SearchAdClient
from imsil_buzz.snapshot import new_snapshot


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    a = ap.parse_args()
    cli = SearchAdClient.from_env()
    out = new_snapshot(a.snapshot)

    rows = []
    for seed in S.SEARCHAD_SEEDS:  # 시드별로 따로 호출해야 '어느 시드의 연관어인지'가 남는다
        for r in cli.keywordstool([seed]):
            rows.append({"seed": seed, **r})
    pd.DataFrame(rows).to_csv(out / "searchad_related_keywords.csv", index=False, encoding="utf-8-sig")

    # 그룹 검색수: 그룹 키워드를 5개씩 hint 로 넣고, 응답 중 hint 와 같은 키워드의 검색수만 합산
    groups: dict[str, list[str]] = dict(S.IMSIL_TREND_GROUPS)
    for region in S.JEONBUK_REGIONS:
        name = S.REGION_QUERY_NAME_OVERRIDE.get(region, region)
        groups[region] = [t.format(r=name) for t in S.REGION_QUERY_TEMPLATES]
    vol = []
    for g, kws in groups.items():
        want = {k.replace(" ", "") for k in kws}
        found = {}
        for i in range(0, len(kws), 5):
            for r in cli.keywordstool(kws[i : i + 5]):
                if r["keyword"].replace(" ", "") in want:
                    found[r["keyword"]] = r
        vol.append({"group": g, "n_keywords": len(found), "monthly_pc": sum(r["monthly_pc"] for r in found.values()),
                    "monthly_mobile": sum(r["monthly_mobile"] for r in found.values()),
                    "monthly_total": sum(r["monthly_total"] for r in found.values()),
                    "keywords": "|".join(found)})
    pd.DataFrame(vol).to_csv(out / "searchad_group_volumes.csv", index=False, encoding="utf-8-sig")
    print("saved ->", out)


if __name__ == "__main__":
    main()
