"""Google Trends 수집.

Google Trends 는 공식 공개 API 가 없다(2025-07 발표된 공식 API 는 신청자 대상 alpha).
따라서 두 경로를 둔다.

1) collect_with_pytrends(): 비공식 라이브러리 pytrends(2025-04 아카이브, 설치·동작은 함)로 자동 수집.
   429(요청 과다)가 잦으므로 호출 간격을 길게 두고, 실패하면 2)로 대체한다.
2) load_manual_csv(): trends.google.com 에서 '다운로드(CSV)' 한 파일을 data/manual/google_trends/ 에 두고 읽는다.
   재현성을 위해 다운로드 일자·조건(기간, 지역, 카테고리)을 파일명에 남긴다.
   예) 20261109_KR_2022-01-01_2026-10-31_임실.csv

값은 0~100 상대지수이고 같은 요청 안의 검색어끼리만 비교 가능하다.
검색량이 임계치 미만이면 0 으로 표시되므로, 지역 단위 소규모 검색어(성수산 등)는 결측이 많을 수 있다.
"""
from __future__ import annotations

import csv
import io
import time
from pathlib import Path

import pandas as pd

_TIME_HEADERS = {"week", "month", "day", "time", "주", "월", "일", "시간", "날짜"}


def _to_num(v: str) -> float:
    v = (v or "").strip()
    if v.startswith("<"):
        return 0.5  # '<1' 은 0과 1 사이 → 0.5 로 표기
    return float(v) if v else float("nan")


def load_manual_csv(path: str | Path) -> pd.DataFrame:
    """Google Trends 웹 화면에서 내려받은 '시간 흐름에 따른 관심도' CSV를 long 형식으로 읽는다."""
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    # 구버전 CSV 는 'Category: ...' + 빈 줄 뒤에 헤더가 온다 → 시간 컬럼 헤더 줄을 찾는다
    for i, line in enumerate(lines):
        first = line.split(",")[0].strip().lower()
        if first in _TIME_HEADERS:
            break
    else:
        raise ValueError(f"Google Trends CSV 헤더를 찾지 못했습니다: {path}")
    rows = list(csv.reader(io.StringIO("\n".join(lines[i:]))))
    header, body = rows[0], [r for r in rows[1:] if r]
    out = []
    for r in body:
        for col, val in zip(header[1:], r[1:]):
            term = col.split(":")[0].strip()  # '임실: (대한민국)' → '임실'
            out.append({"period": r[0], "term": term, "value": _to_num(val)})
    df = pd.DataFrame(out)
    df["period"] = pd.to_datetime(df["period"])
    df["source_file"] = Path(path).name
    return df


def collect_with_pytrends(
    terms: list[str],
    start: str,
    end: str,
    geo: str = "KR",
    sleep: float = 20.0,
    retries: int = 4,
) -> dict[str, pd.DataFrame]:
    """pytrends 로 관심도 추이·연관검색어·지역별 관심도를 수집. 검색어는 요청당 최대 5개."""
    from pytrends.request import TrendReq  # 선택 의존성

    if len(terms) > 5:
        raise ValueError("Google Trends 는 요청당 5개 검색어까지 비교 가능")
    py = TrendReq(hl="ko-KR", tz=-540)
    timeframe = f"{start} {end}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            py.build_payload(terms, timeframe=timeframe, geo=geo)
            iot = py.interest_over_time()
            time.sleep(sleep)
            related = py.related_queries()
            time.sleep(sleep)
            region = py.interest_by_region(resolution="REGION", inc_low_vol=True)
            break
        except Exception as e:  # 429 등
            last_err = e
            time.sleep(sleep * (2**attempt))
    else:
        raise RuntimeError(f"pytrends 수집 실패(수동 CSV 다운로드로 대체하세요): {last_err}")

    iot_long = (
        iot.drop(columns=[c for c in ["isPartial"] if c in iot.columns])
        .reset_index()
        .melt(id_vars="date", var_name="term", value_name="value")
        .rename(columns={"date": "period"})
    )
    rel_rows = []
    for term, d in (related or {}).items():
        for kind in ("top", "rising"):
            df = (d or {}).get(kind)
            if df is not None:
                for _, r in df.iterrows():
                    rel_rows.append({"term": term, "kind": kind, "query": r["query"], "value": r["value"]})
    return {
        "interest_over_time": iot_long,
        "related_queries": pd.DataFrame(rel_rows),
        "interest_by_region": region.reset_index(),
    }
