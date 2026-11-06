# -*- coding: utf-8 -*-
"""[연관관계] 키워드 연관관계 — 연관규칙(34개소 코드 그대로) + 동시출현 네트워크

1) 연관규칙
   src/association/analyze_association.py 를 고치지 않고 입력·출력만 바꿔 실행한다.
   리뷰 1건 = 트랜잭션 1개, 지지도·신뢰도·향상도 계산 방식과 기본 임계값이 34개소와 같다.
   관광지 단위 규칙이 핵심이므로 --by-place 로 돌리고, 리뷰 수가 적은 관광지도 포함되게
   --min-place-transactions 만 낮춘다(스크립트 기본 100, 34개소 보고서 결과는 50 → 여기 기본 20).
   LLM 키워드 정규화(동의어 통합·기능어 제거)는 34개소와 같이 켜는 것이 기본이다.

2) 동시출현 네트워크 (보고서 그림용)
   관광지별 빈도 상위 키워드 사이에 '한 리뷰에 함께 나온 리뷰 수'를 가중치로 하는 연결망을 그린다.
   연결 강도는 동시출현 수와 Jaccard 계수를 함께 낸다. 배치는 seed 를 고정해 매번 같게 그린다.

입력  output/new_sites/keyword/추가관광지_리뷰데이터_키워드전처리완료.csv (keywords.py 결과)
출력  output/new_sites/association/연관관계_분석결과.csv
      output/new_sites/association/동시출현_엣지.csv, 동시출현_노드.csv
      output/new_sites/association/그림_{관광지}_키워드네트워크.png

실행
    python src/new_sites/association.py            # LLM 정규화 포함 (API 키 필요)
    python src/new_sites/association.py --no-llm   # API 없이
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from collections import Counter
from itertools import combinations

import pandas as pd

from common import Checks, config, read_csv, rel, setup_font, write_csv

TOP_N = 30          # 네트워크에 올릴 키워드 수
MIN_EDGE = 3        # 이 리뷰 수 미만으로 함께 나온 쌍은 선을 긋지 않는다
SEED = 20261102


def run_rules(no_llm: bool, min_tx: int):
    out = config.OUT_ASSOC / "연관관계_분석결과.csv"
    cmd = [sys.executable, str(config.ASSOC_SCRIPT),
           "--input", str(config.KEYWORD_DATA), "--output", str(out),
           "--by-place", "--min-place-transactions", str(min_tx)]
    if no_llm:
        cmd.append("--no-llm")
    print("실행:", " ".join(rel(c) if "/" in c else c for c in cmd[1:]))
    subprocess.run(cmd, check=True, cwd=config.REPO)
    return out


def network(df: pd.DataFrame):
    nodes, edges = [], []
    for place in config.TARGET_NAMES:
        tx = [set(t) for t in df.loc[df["place"] == place, "keyword_tokens_final"] if t]
        if not tx:
            continue
        freq = Counter(k for t in tx for k in t)
        top = [k for k, _ in freq.most_common(TOP_N)]
        pair = Counter()
        for t in tx:
            pair.update(combinations(sorted(k for k in t if k in top), 2))
        for k in top:
            nodes.append({"place": place, "keyword": k, "리뷰수": freq[k], "리뷰비율": freq[k] / len(tx)})
        for (a, b), c in pair.items():
            if c >= MIN_EDGE:
                edges.append({"place": place, "source": a, "target": b, "동시출현": c,
                              "jaccard": c / (freq[a] + freq[b] - c), "리뷰수": len(tx)})
    return pd.DataFrame(nodes), pd.DataFrame(edges)


def draw(nodes: pd.DataFrame, edges: pd.DataFrame):
    import networkx as nx
    plt = setup_font()
    for place in nodes["place"].unique():
        n = nodes[nodes.place == place]
        e = edges[edges.place == place] if len(edges) else edges
        g = nx.Graph()
        for r in n.itertuples():
            g.add_node(r.keyword, size=r.리뷰수)
        for r in e.itertuples():
            g.add_edge(r.source, r.target, weight=r.동시출현)
        g.remove_nodes_from([k for k in list(g) if g.degree(k) == 0])
        if not g.number_of_nodes():
            continue
        pos = nx.spring_layout(g, seed=SEED, k=1.2 / max(1, g.number_of_nodes()) ** 0.5, weight="weight")
        w = [g[a][b]["weight"] for a, b in g.edges]
        wmax = max(w) if w else 1
        sizes = [g.nodes[k]["size"] for k in g]
        smax = max(sizes)
        fig, ax = plt.subplots(figsize=(10, 9))
        nx.draw_networkx_edges(g, pos, ax=ax, width=[0.5 + 4 * x / wmax for x in w],
                               edge_color="#9aa7b8", alpha=0.6)
        nx.draw_networkx_nodes(g, pos, ax=ax, node_size=[200 + 2200 * s / smax for s in sizes],
                               node_color="#9cc3f0", edgecolors="#2a78d6", alpha=0.95)
        nx.draw_networkx_labels(g, pos, ax=ax, font_size=11, font_color="#111111",
                                font_family=plt.rcParams["font.family"])
        ax.set_title(f"{place} 키워드 동시출현 네트워크 (상위 {TOP_N}개 · {MIN_EDGE}회 이상 동시출현)")
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(config.OUT_ASSOC / f"그림_{place}_키워드네트워크.png", dpi=150)
        plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true", help="LLM 키워드 정규화 없이 계산")
    ap.add_argument("--min-place-transactions", type=int, default=20)
    args = ap.parse_args()

    ck = Checks("키워드 연관관계")
    ck("키워드 전처리 데이터 존재", config.KEYWORD_DATA.exists(), rel(config.KEYWORD_DATA))
    config.OUT_ASSOC.mkdir(parents=True, exist_ok=True)

    out = run_rules(args.no_llm, args.min_place_transactions)
    rules = read_csv(out)
    scopes = rules["scope"].value_counts().to_dict() if len(rules) else {}
    ck("연관규칙 산출", len(rules) > 0, f"범위별 규칙 수 {scopes}", fatal=False)
    for p in config.TARGET_NAMES:
        ck(f"{p} 관광지 단위 규칙", p in scopes,
           "" if p in scopes else "유효 트랜잭션이 --min-place-transactions 미만이거나 규칙 없음", fatal=False)

    df = read_csv(config.KEYWORD_DATA)
    df["keyword_tokens_final"] = df["keyword_tokens_final"].map(ast.literal_eval)
    nodes, edges = network(df)
    write_csv(nodes, config.OUT_ASSOC / "동시출현_노드.csv")
    write_csv(edges, config.OUT_ASSOC / "동시출현_엣지.csv")
    draw(nodes, edges)
    ck("동시출현 네트워크", len(nodes) > 0, f"노드 {len(nodes)} · 엣지 {len(edges)}")

    for p in config.TARGET_NAMES:
        top = rules[rules["scope"] == p].sort_values("lift", ascending=False).head(5) if len(rules) else []
        if len(top):
            print(f"\n  [{p}] 향상도 상위 규칙")
            for r in top.itertuples():
                print(f"    {r.antecedent} ⇒ {r.consequent}  (지지도 {r.support:.3f}, "
                      f"신뢰도 {r.confidence:.2f}, 향상도 {r.lift:.2f}, {r.count_both}건)")
    print(f"\n저장: {rel(config.OUT_ASSOC)}/")


if __name__ == "__main__":
    main()
