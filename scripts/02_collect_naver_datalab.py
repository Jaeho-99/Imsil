"""[수집 2] 네이버 데이터랩 검색어트렌드.

생성 파일 (data/raw/online_buzz/<수집일>/)
  datalab_regions_raw.json     14개 시군 '여행·가볼만한곳·관광' 그룹, 임실을 기준(anchor)으로 묶은 요청들
  datalab_imsil_raw.json       임실 관광지·축제별 키워드 그룹 (임실 관광(전체)를 anchor 로)
  datalab_imsil_segments.json  임실 관광(전체) 그룹의 기기·성별·연령대별 추이

모든 응답은 원본 그대로 저장하고, 정규화(anchor chaining)는 05_analyze.py 에서 한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from imsil_buzz import settings as S
from imsil_buzz.analysis.trends import plan_anchor_batches
from imsil_buzz.naver import NaverClient
from imsil_buzz.snapshot import new_snapshot

AGE_BANDS = {"10대": ["2"], "20대": ["3", "4"], "30대": ["5", "6"], "40대": ["7", "8"], "50대": ["9", "10"], "60대+": ["11"]}


def region_groups() -> dict[str, list[str]]:
    g = {}
    for region in S.JEONBUK_REGIONS:
        name = S.REGION_QUERY_NAME_OVERRIDE.get(region, region)
        g[region] = [t.format(r=name) for t in S.REGION_QUERY_TEMPLATES] + [t.format(r=name).replace(" ", "") for t in S.REGION_QUERY_TEMPLATES]
    return g


def run_batches(cli, groups, anchor, start, end, unit, **filters):
    out = []
    for i, batch in enumerate(plan_anchor_batches(list(groups), anchor)):
        resp = cli.datalab_search({k: groups[k] for k in batch}, start, end, unit, **filters)
        out.append({"request_id": i, "filters": filters, "response": resp})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=S.START_DATE)
    ap.add_argument("--end", default=S.END_DATE)
    ap.add_argument("--unit", default="month", choices=["date", "week", "month"])
    ap.add_argument("--snapshot")
    a = ap.parse_args()
    cli = NaverClient.from_env()
    out = new_snapshot(a.snapshot)

    def dump(name, obj):
        (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")

    dump("datalab_regions_raw.json", run_batches(cli, region_groups(), "임실", a.start, a.end, a.unit))
    # 장기 추세(2016~)도 같이 받아 둔다
    dump("datalab_regions_long_raw.json", run_batches(cli, region_groups(), "임실", S.TREND_LONG_START, a.end, "month"))
    dump("datalab_imsil_raw.json", run_batches(cli, S.IMSIL_TREND_GROUPS, "임실 관광(전체)", a.start, a.end, a.unit))
    # 일 단위(축제 전후 등 이벤트 분석용)
    dump("datalab_imsil_daily_raw.json", run_batches(cli, S.IMSIL_TREND_GROUPS, "임실 관광(전체)", a.start, a.end, "date"))

    seg = []
    base = {"임실 관광(전체)": S.IMSIL_TREND_GROUPS["임실 관광(전체)"]}
    for dev in ("pc", "mo"):
        seg.append({"segment": f"device={dev}", "response": cli.datalab_search(base, a.start, a.end, a.unit, device=dev)})
    for gen in ("m", "f"):
        seg.append({"segment": f"gender={gen}", "response": cli.datalab_search(base, a.start, a.end, a.unit, gender=gen)})
    for band, ages in AGE_BANDS.items():
        seg.append({"segment": f"age={band}", "response": cli.datalab_search(base, a.start, a.end, a.unit, ages=ages)})
    dump("datalab_imsil_segments.json", seg)
    print("saved ->", out)


if __name__ == "__main__":
    main()
