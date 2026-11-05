"""온라인 언급량·비중 지표.

지표 A  전체 누적 언급량: 네이버 검색 API total (기간 지정 불가, 유사도 매칭 기반 근사치)
지표 B  최근 게시 속도: 최신순 최대 1,099건의 작성일로 계산한 '일평균 게시물 수' 및 월별 건수
지표 C  전북 관광 게시물 내 언급 비중: '전북 여행' 류 게시물 표본에서 각 시군이 언급된 게시물 비율
"""
from __future__ import annotations

import re

import pandas as pd


def share_table(totals: pd.DataFrame) -> pd.DataFrame:
    """totals: columns [region, channel, query, total] → 시군×채널 합계와 비중(%)."""
    t = totals.groupby(["region", "channel"])["total"].sum().unstack("channel").fillna(0)
    t["합계"] = t.sum(axis=1)
    share = (t / t.sum(axis=0) * 100).add_suffix("_비중(%)")
    out = pd.concat([t, share], axis=1).sort_values("합계", ascending=False)
    out["순위"] = range(1, len(out) + 1)
    return out.round(2)


def posting_rate(items: pd.DataFrame, end_date: str) -> pd.DataFrame:
    """items: normalize_item() 결과(date 有). region·channel 별 최근 게시 속도.

    1,099건 상한 때문에 인기 지역은 짧은 기간만 담긴다 → 기간 길이로 나눈 '일평균'으로 비교.
    한 시군에 검색어가 여러 개이므로, 모든 검색어가 빠짐없이 담긴 공통 구간
    (= 검색어별 가장 오래된 작성일 중 가장 늦은 날짜 ~ end_date)에서 중복 제거한 게시물 수를 센다.
    capped=False 이면 1,099건 상한에 걸리지 않은 것(=해당 검색어의 전수).
    """
    d = items.dropna(subset=["date"]).copy()
    d["date"] = pd.to_datetime(d["date"])
    end = pd.Timestamp(end_date)
    d = d[d["date"] <= end]
    rows = []
    for (region, ch), g in d.groupby(["region", "channel"]):
        per_q = g.groupby("query").agg(n=("link", "size"), oldest=("date", "min"))
        capped = bool((per_q["n"] >= 1099).any())
        window_from = per_q["oldest"].max() if capped else per_q["oldest"].min()
        w = g[g["date"] >= window_from].drop_duplicates("link")
        days = (end - window_from).days + 1
        rows.append({"region": region, "channel": ch, "n_posts": len(w), "window_from": window_from.date(),
                     "window_to": end.date(), "days": days, "posts_per_day": round(len(w) / days, 3), "capped": capped})
    return pd.DataFrame(rows).sort_values(["channel", "posts_per_day"], ascending=[True, False]).reset_index(drop=True)


class RegionMatcher:
    """게시물 텍스트에서 언급된 시군을 찾는다 (키워드 사전의 '본문 인정 표현'·'본문 제외 표현').

    - 모든 시군의 표현을 하나의 정규식으로 묶어 긴 표현부터 맞춘다. 그래서 임실의 '전주샹그릴라'가
      전주의 표현보다 먼저 잡혀 임실로 센다.
    - '본문 제외 표현'(예: '전주 대비', '마라톤 완주')은 매칭 전에 지운다.
    """

    def __init__(self, regions: dict[str, list[str]], excludes: dict[str, list[str]] | None = None):
        self.order = list(regions)
        self.alias_to_region: dict[str, str] = {}
        for r, aliases in regions.items():
            for al in aliases:
                prev = self.alias_to_region.setdefault(al, r)
                if prev != r:
                    raise ValueError(f"표현 '{al}' 이 {prev} 와 {r} 에 모두 있습니다")
        alts = sorted(self.alias_to_region, key=len, reverse=True)
        self.pattern = re.compile("|".join(map(re.escape, alts))) if alts else None
        ex = sorted({e for es in (excludes or {}).values() for e in es}, key=len, reverse=True)
        self.exclude = re.compile("|".join(map(re.escape, ex))) if ex else None

    def __call__(self, text: str) -> list[str]:
        t = text or ""
        if self.exclude is not None:
            t = self.exclude.sub(" ", t)
        if self.pattern is None:
            return []
        found = {self.alias_to_region[m.group(0)] for m in self.pattern.finditer(t)}
        return [r for r in self.order if r in found]


def regional_mention_share(posts: pd.DataFrame, regions: dict[str, list[str]],
                           excludes: dict[str, list[str]] | None = None) -> pd.DataFrame:
    """전북 관광 게시물 표본에서 시군별 언급 게시물 수와 비중.

    - 언급률(%)       = 해당 시군 언급 게시물 / 전체 표본 게시물
    - 언급 점유율(%)  = 해당 시군 언급 횟수 / 모든 시군 언급 횟수 합 (한 게시물이 여러 시군 언급 가능)
    """
    match = RegionMatcher(regions, excludes)
    p = posts.drop_duplicates("link").copy()
    p["text"] = p["title"].fillna("") + " " + p["description"].fillna("")
    p["regions"] = p["text"].map(match)
    n = len(p)
    ex = p.explode("regions").dropna(subset=["regions"])
    cnt = ex.groupby("regions")["link"].nunique().reindex(list(regions), fill_value=0)
    out = pd.DataFrame({"언급_게시물수": cnt})
    out["언급률(%)"] = (out["언급_게시물수"] / n * 100).round(2) if n else 0
    tot = out["언급_게시물수"].sum()
    out["언급_점유율(%)"] = (out["언급_게시물수"] / tot * 100).round(2) if tot else 0
    out = out.sort_values("언급_게시물수", ascending=False)
    out["순위"] = range(1, len(out) + 1)
    out.attrs["n_posts"] = n
    return out


def co_mentioned_regions(posts: pd.DataFrame, regions: dict[str, list[str]], target: str = "임실",
                         excludes: dict[str, list[str]] | None = None) -> pd.Series:
    """target 이 언급된 게시물에서 함께 언급된 시군(연계 관광 동선 파악용)."""
    match = RegionMatcher(regions, excludes)
    texts = (posts["title"].fillna("") + " " + posts["description"].fillna("")).tolist()
    co = pd.Series([r for t in texts for rs in [match(t)] if target in rs for r in rs if r != target], dtype="object")
    return co.value_counts()


def filter_topic_posts(posts: pd.DataFrame, topic_excludes: dict[str, list[str]], must_terms: list[str]) -> pd.DataFrame:
    """임실 관련 게시물 정제: (1) 주제어별 '거를 글' 표현이 있는 글 제거, (2) 임실 관련 표현이 없는 글 제거."""
    p = posts.copy()
    text = p["title"].fillna("") + " " + p["description"].fillna("")
    keep = pd.Series(True, index=p.index)
    if "topic" in p.columns:
        for topic, ex in topic_excludes.items():
            if ex:
                bad = (p["topic"] == topic) & text.str.contains("|".join(map(re.escape, ex)), regex=True)
                keep &= ~bad
    if must_terms:
        keep &= text.str.contains("|".join(map(re.escape, must_terms)), regex=True)
    return p[keep]
