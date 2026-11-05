"""검색어 트렌드 정규화.

네이버 데이터랩은 요청당 5개 그룹, 요청 내 최대값=100 인 상대값만 준다.
14개 시군을 한 척도로 비교하려면 모든 요청에 같은 '기준(anchor) 그룹'을 넣고
기준 그룹의 합이 같아지도록 각 요청의 값을 재조정한다(anchor chaining).
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd


def datalab_to_long(resp: dict, request_id: int | str = 0) -> pd.DataFrame:
    rows = []
    for res in resp.get("results", []):
        for d in res.get("data", []):
            rows.append({"request_id": request_id, "group": res["title"], "period": d["period"], "ratio": float(d["ratio"])})
    df = pd.DataFrame(rows, columns=["request_id", "group", "period", "ratio"])
    df["period"] = pd.to_datetime(df["period"])
    return df


def plan_anchor_batches(groups: list[str], anchor: str, per_request: int = 5) -> list[list[str]]:
    """anchor 를 매 요청에 포함하고 나머지를 (per_request-1)개씩 나눈 배치 목록."""
    others = [g for g in groups if g != anchor]
    k = per_request - 1
    return [[anchor, *others[i : i + k]] for i in range(0, len(others), k)]


def chain_by_anchor(df: pd.DataFrame, anchor: str) -> pd.DataFrame:
    """요청별 값을 anchor 그룹 합 기준으로 같은 척도로 맞춘다. 결과는 anchor 전체 기간 평균=100.

    df: datalab_to_long() 결과를 여러 요청 concat 한 것.
    """
    out = []
    for rid, sub in df.groupby("request_id"):
        a = sub.loc[sub["group"] == anchor, "ratio"]
        if a.empty or a.sum() == 0:
            raise ValueError(f"request {rid} 에 anchor '{anchor}' 값이 없습니다")
        scale = 100.0 / a.mean()
        s = sub.copy()
        s["index"] = s["ratio"] * scale
        out.append(s)
    res = pd.concat(out)
    # anchor 는 모든 요청에 같은 값(=같은 척도)으로 나오므로 하나만 남긴다
    first = res["request_id"].iloc[0]
    res = res[(res["group"] != anchor) | (res["request_id"] == first)]
    return res.drop(columns=["ratio"]).reset_index(drop=True)


def calibrate_absolute(
    rel: pd.DataFrame, group_volume_last_month: dict[str, float], ref_period: str
) -> pd.DataFrame:
    """상대지수를 검색광고 API 의 '최근 30일 검색수'로 환산한 추정 월간 검색수.

    rel: columns [group, period, index] (월 단위)
    group_volume_last_month: 그룹명 -> 해당 그룹 키워드들의 최근 30일 검색수 합
    ref_period: 검색광고 조회 시점에 해당하는 월(예: '2026-10-01')
    추정값 = index(t) * volume / index(ref_period). 근사치이므로 보고서에는 '추정'으로 표기.
    """
    ref = pd.Timestamp(ref_period)
    out = []
    for g, sub in rel.groupby("group"):
        if g not in group_volume_last_month:
            continue
        base = sub.loc[sub["period"] == ref, "index"]
        if base.empty or base.iloc[0] == 0:
            continue
        s = sub.copy()
        s["est_monthly_searches"] = s["index"] / base.iloc[0] * group_volume_last_month[g]
        out.append(s)
    return pd.concat(out).reset_index(drop=True) if out else pd.DataFrame()


def yearly_summary(rel: pd.DataFrame, value_col: str = "index") -> pd.DataFrame:
    s = rel.assign(year=rel["period"].dt.year).groupby(["group", "year"])[value_col].mean().unstack("year")
    return s.round(2)


def peak_months(rel: pd.DataFrame, top: int = 3, value_col: str = "index") -> pd.DataFrame:
    return (
        rel.sort_values(value_col, ascending=False)
        .groupby("group")
        .head(top)
        .sort_values(["group", value_col], ascending=[True, False])
        .reset_index(drop=True)
    )


def seasonality(rel: pd.DataFrame, value_col: str = "index") -> pd.DataFrame:
    """그룹별 월(1~12) 평균 / 연평균 → 1 보다 크면 성수기."""
    t = rel.assign(month=rel["period"].dt.month)
    m = t.groupby(["group", "month"])[value_col].mean()
    return (m / m.groupby("group").transform("mean")).unstack("month").round(2)


def concat(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(list(frames), ignore_index=True)
