"""키워드 연관관계 분석.

(1) 게시물 키워드 연관규칙: 게시물 1건 = 트랜잭션. 지난 리뷰 분석과 같은 지지도·신뢰도·향상도 기준.
(2) 동시출현 네트워크: 키워드 쌍의 동시출현 수 + 향상도로 엣지를 만들고 중심성으로 핵심어를 찾는다.
(3) 검색 연관키워드 네트워크: 검색광고 API 의 시드→연관키워드 관계(검색 수요 측면).
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations

import pandas as pd


def pair_rules(token_lists: list[list[str]], min_support: float = 0.01, min_confidence: float = 0.2,
               top_vocab: int = 200) -> pd.DataFrame:
    """1:1 연관규칙(A→B). 계산량을 줄이려 문서빈도 상위 top_vocab 단어만 사용."""
    tx = [set(ts) for ts in token_lists if ts]
    n = len(tx)
    if n == 0:
        return pd.DataFrame(columns=["antecedent", "consequent", "support", "confidence", "lift", "n_co"])
    item_cnt = Counter(w for t in tx for w in t)
    vocab = {w for w, _ in item_cnt.most_common(top_vocab)}
    pair_cnt: Counter = Counter()
    for t in tx:
        for a, b in combinations(sorted(t & vocab), 2):
            pair_cnt[(a, b)] += 1
    rows = []
    for (a, b), c in pair_cnt.items():
        sup = c / n
        if sup < min_support:
            continue
        for x, y in ((a, b), (b, a)):
            conf = c / item_cnt[x]
            if conf < min_confidence:
                continue
            lift = conf / (item_cnt[y] / n)
            rows.append({"antecedent": x, "consequent": y, "support": round(sup, 4),
                         "confidence": round(conf, 4), "lift": round(lift, 3), "n_co": c})
    out = pd.DataFrame(rows, columns=["antecedent", "consequent", "support", "confidence", "lift", "n_co"])
    return out.sort_values(["lift", "support"], ascending=False).reset_index(drop=True)


def cooccurrence_edges(token_lists: list[list[str]], top_vocab: int = 80, min_co: int = 5) -> pd.DataFrame:
    tx = [set(ts) for ts in token_lists if ts]
    n = len(tx)
    item_cnt = Counter(w for t in tx for w in t)
    vocab = {w for w, _ in item_cnt.most_common(top_vocab)}
    pair_cnt: Counter = Counter()
    for t in tx:
        for a, b in combinations(sorted(t & vocab), 2):
            pair_cnt[(a, b)] += 1
    rows = [
        {"source": a, "target": b, "weight": c, "lift": round(c * n / (item_cnt[a] * item_cnt[b]), 3)}
        for (a, b), c in pair_cnt.items() if c >= min_co
    ]
    return pd.DataFrame(rows, columns=["source", "target", "weight", "lift"]).sort_values("weight", ascending=False)


def centrality(edges: pd.DataFrame) -> pd.DataFrame:
    import networkx as nx

    g = nx.Graph()
    for r in edges.itertuples():
        g.add_edge(r.source, r.target, weight=r.weight)
    if g.number_of_nodes() == 0:
        return pd.DataFrame()
    deg = nx.degree_centrality(g)
    btw = nx.betweenness_centrality(g, weight=None)
    try:  # scipy 없이 동작하는 거듭제곱법
        eig = nx.eigenvector_centrality(g, weight="weight", max_iter=1000)
    except nx.PowerIterationFailedConvergence:
        eig = {k: float("nan") for k in g}
    try:
        from networkx.algorithms.community import greedy_modularity_communities

        comm = {w: i for i, c in enumerate(greedy_modularity_communities(g, weight="weight")) for w in c}
    except Exception:
        comm = {}
    out = pd.DataFrame({"degree": deg, "betweenness": btw, "eigenvector": eig})
    out["community"] = pd.Series(comm)
    return out.round(4).sort_values("degree", ascending=False).rename_axis("keyword").reset_index()


def search_keyword_network(rel: pd.DataFrame) -> pd.DataFrame:
    """rel: columns [seed, keyword, monthly_total] → 시드-연관키워드 엣지. 둘 이상 시드에 걸친 키워드는 '교차 관심어'."""
    r = rel[rel["seed"].str.replace(" ", "") != rel["keyword"].str.replace(" ", "")]
    n_seeds = r.groupby("keyword")["seed"].nunique().rename("n_seeds")
    return r.merge(n_seeds, on="keyword").sort_values(["n_seeds", "monthly_total"], ascending=False)
