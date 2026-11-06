# -*- coding: utf-8 -*-
"""[요약] 보고서용 요약 — 앞 단계 산출물을 모아 표와 문장 초안 재료를 한 파일로 정리한다.

새로 계산하는 값은 데이터 개요(리뷰 수·기간·평점)뿐이고, 나머지는 앞 단계 CSV 를 읽어 옮긴다.
앞 단계 결과가 없으면 그 절은 '미실행'으로 표시하고 넘어간다.

출력  output/new_sites/summary/분석결과_요약.md
      output/new_sites/summary/데이터개요.csv
      output/new_sites/summary/그림_연도별_리뷰수.png
      output/new_sites/산출물_목록.csv  (output/new_sites/ 아래 모든 파일과 행 수 — 제출 목록 대조용)

실행
    python src/new_sites/summary.py
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from common import config, read_csv, rel, setup_font, write_csv

OUT = config.OUT_SUMMARY
L: list[str] = []


def h(t):
    L.append(f"\n## {t}\n")


def table(df: pd.DataFrame, fmt: dict | None = None):
    fmt = fmt or {}
    cols = list(df.columns)
    L.append("| " + " | ".join(map(str, cols)) + " |")
    L.append("|" + "|".join("---:" if pd.api.types.is_numeric_dtype(df[c]) else "---" for c in cols) + "|")
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if c in fmt and pd.notna(v):
                cells.append(fmt[c].format(v))
            elif isinstance(v, float):
                cells.append("" if pd.isna(v) else f"{v:,.2f}")
            else:
                cells.append(str(v))
        L.append("| " + " | ".join(cells) + " |")
    L.append("")


def overview():
    h("1. 수집 데이터 개요")
    if not config.DATASET.exists():
        L.append("미실행 — build_dataset.py 를 먼저 실행한다.")
        return
    d = read_csv(config.DATASET)
    d["본문"] = d["body"].fillna("").str.strip().ne("")
    g = d.groupby(["place", "platform"]).agg(
        리뷰=("reviewId", "size"), 본문있음=("본문", "sum"), 시작=("date", "min"), 끝=("date", "max"),
        평균평점=("rating", "mean")).reset_index()
    tot = d.groupby("place").agg(리뷰=("reviewId", "size"), 본문있음=("본문", "sum"),
                                 시작=("date", "min"), 끝=("date", "max"),
                                 평균평점=("rating", "mean")).reset_index().assign(platform="계")
    ov = pd.concat([g, tot], ignore_index=True).sort_values(["place", "platform"])
    write_csv(ov, OUT / "데이터개요.csv")
    L.append(f"수집 기간 기준: {config.DATE_START} ~ {config.DATE_END or '(DATE_END 미고정)'} · "
             f"총 {len(d):,}건 (본문 있음 {int(d['본문'].sum()):,}건). 평균평점은 별점이 있는 리뷰만 "
             "(네이버는 대부분 별점이 없다).\n")
    table(ov[["place", "platform", "리뷰", "본문있음", "시작", "끝", "평균평점"]])
    L.append("※ 34개소 분석의 인접 관광지(비교용): "
             + ", ".join(f"{k} ↔ {v}" for k, v in config.COMPARE_PLACES.items()) + "\n")

    plt = setup_font()
    d["연도"] = pd.to_datetime(d["date"]).dt.year
    y = d.groupby(["연도", "place"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    y.plot(kind="bar", ax=ax, color=["#2a78d6", "#e3912b"][: y.shape[1]], width=0.75)
    ax.set_xlabel("")
    ax.set_ylabel("리뷰 수")
    ax.set_title("연도별 리뷰 수", loc="left")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if config.DATE_END is None or str(d["date"].max())[:4] == str(datetime.now().year):
        ax.text(0.99, 0.97, f"{d['date'].max()[:4]}년은 수집일까지 일부", transform=ax.transAxes,
                ha="right", va="top", fontsize=9, color="#555555")
    fig.tight_layout()
    fig.savefig(OUT / "그림_연도별_리뷰수.png", dpi=150)
    plt.close(fig)


def keywords():
    h("2. 주요 키워드")
    f = config.OUT_KEYWORD / "관광지별_frequency_top20.csv"
    if not f.exists():
        L.append("미실행 — keywords.py.")
        return
    fr = read_csv(f)
    tf = read_csv(config.OUT_KEYWORD / "관광지별_tfidf_top20.csv")
    bi = read_csv(config.OUT_KEYWORD / "관광지별_bigram_top20.csv")
    for p in config.TARGET_NAMES:
        a = fr[fr.place == p].head(10)
        b = tf[tf.place == p].head(10)
        c = bi[bi.place == p].head(10)
        if a.empty:
            continue
        L.append(f"**{p}**\n")
        t = pd.DataFrame({"순위": range(1, 11)})
        t["빈도 키워드"] = [f"{k} ({v})" for k, v in zip(a.keyword, a.frequency)] + [""] * (10 - len(a))
        t["TF-IDF 키워드"] = [f"{k} ({v:.3f})" for k, v in zip(b.keyword, b.tfidf_score)] + [""] * (10 - len(b))
        t["Bigram"] = [f"{k} ({v})" for k, v in zip(c.bigram, c["count"])] + [""] * (10 - len(c))
        table(t)
    tg = config.OUT_KEYWORD / "네이버_키워드리뷰_집계.csv"
    if tg.exists():
        t = read_csv(tg)
        for p in config.TARGET_NAMES:
            x = t[t.place == p].head(8)
            if len(x):
                L.append(f"- {p} 네이버 키워드 리뷰 상위: " +
                         ", ".join(f"'{r.tag}' {r['count']}건({r.언급비율:.0%})" for _, r in x.iterrows()))
        L.append("")
    L.append("TF-IDF 는 34개소 분석의 21개소 문서에 새 2개소를 더한 23개 문서로 계산했다 "
             "(임실군 다른 관광지와 비교한 특징어).\n")


def association():
    h("3. 키워드 연관관계")
    f = config.OUT_ASSOC / "연관관계_분석결과.csv"
    if not f.exists():
        L.append("미실행 — association.py.")
        return
    r = read_csv(f)
    for p in config.TARGET_NAMES:
        x = r[(r.scope == p) & (r.antecedent_size == 1)].sort_values("lift", ascending=False)
        # A⇒B 와 B⇒A 중 하나만 남긴다
        x = x.assign(k=x.apply(lambda q: tuple(sorted([q.antecedent, q.consequent])), axis=1))
        x = x.drop_duplicates("k").head(10)
        if x.empty:
            L.append(f"- {p}: 관광지 단위 규칙 없음 (리뷰 수가 적거나 임계값 미달)\n")
            continue
        L.append(f"**{p}** (트랜잭션 {int(x.n_transactions.iloc[0])}건, 향상도 상위)\n")
        table(x[["antecedent", "consequent", "support", "confidence", "lift", "count_both"]]
              .rename(columns={"antecedent": "A", "consequent": "B", "support": "지지도",
                               "confidence": "신뢰도", "lift": "향상도", "count_both": "동시출현"}),
              {"지지도": "{:.3f}", "신뢰도": "{:.2f}", "향상도": "{:.2f}"})
    L.append(f"그림: `{rel(config.OUT_ASSOC)}/그림_{{관광지}}_키워드네트워크.png`\n")


def sentiment():
    h("4. 감성분석")
    f = config.OUT_SENT / "관광지별_문장감성_최종.csv"
    if not f.exists():
        L.append("미실행 — sentiment.py ... merge.")
        return
    s = read_csv(f)
    rv = read_csv(config.OUT_SENT / "관광지별_리뷰감성_최종.csv")
    base_s = read_csv(config.BASE_SENT_SENTENCE)
    base_r = read_csv(config.BASE_SENT_REVIEW)
    rows = []
    for p in config.TARGET_NAMES:
        a = s[s.place == p]
        b = rv[rv.place == p]
        if a.empty:
            continue
        a, b = a.iloc[0], b.iloc[0]
        rows.append({"관광지": p, "문장": int(a["계"]), "긍정": a["긍정비율"], "부정": a["부정비율"],
                     "리뷰": int(b["계"]), "긍정리뷰": b["긍정비율"], "부정리뷰": b["부정비율"],
                     "혼합리뷰": b["혼합"] / b["계"]})
    for p in list(config.COMPARE_PLACES.values()) + ["34개소 전체"]:
        bs = base_s if p == "34개소 전체" else base_s[base_s.place == p]
        br = base_r if p == "34개소 전체" else base_r[base_r.place == p]
        if bs.empty:
            continue
        vs, vr = bs["label"].value_counts(), br["리뷰감성"].value_counts()
        rows.append({"관광지": f"(비교) {p}", "문장": len(bs), "긍정": vs.get("긍정", 0) / len(bs),
                     "부정": vs.get("부정", 0) / len(bs), "리뷰": len(br),
                     "긍정리뷰": vr.get("긍정", 0) / len(br), "부정리뷰": vr.get("부정", 0) / len(br),
                     "혼합리뷰": vr.get("혼합", 0) / len(br)})
    pct = {c: "{:.1%}" for c in ["긍정", "부정", "긍정리뷰", "부정리뷰", "혼합리뷰"]}
    table(pd.DataFrame(rows), pct)
    L.append("문장 비율은 리뷰 문장의 구성이지 방문객 비율이 아니다. 중립은 평가어가 없는 문장이다 "
             "(34개소 보고서 3장·6.6과 같은 해석 원칙). 30문장 미만 관광지의 비율은 경향만 본다.\n")
    v = config.OUT_SENT / "검증_34개소" / "채점_run1.json"
    if v.exists():
        j = json.loads(v.read_text(encoding="utf-8"))
        L.append(f"- 방법 검증: 34개소 사람 검증셋 본 TEST {j['본_TEST']['n']}문장에서 "
                 f"macro-F1 **{j['본_TEST']['macro_f1']:.3f}** (정확도 {j['본_TEST']['accuracy']:.3f}), "
                 f"보강셋 부정 재현율 {j['보강_부정재현율']['recall']:.3f}. "
                 f"34개소(ChatGPT 웹 UI) 0.906 · 0.82~0.91, 다수 클래스 기준선 0.579. 모델 `{j['model']}`.")
    else:
        L.append("- 방법 검증: 미실행 — `sentiment.py validate` (34개소 검증셋 재채점).")
    r = config.OUT_SENT / "runs" / "재현성.json"
    if r.exists():
        j = json.loads(r.read_text(encoding="utf-8"))
        L.append(f"- 재현성: 독립 2회 실행 불일치 {j['불일치']}/{j['문장']} = {j['불일치율']:.2%}, "
                 f"κ {j['kappa']:.3f}, 긍↔부 뒤집힘 {j['긍부_뒤집힘']}건 (34개소 4.20% · κ 0.936).")
    b = config.OUT_SENT / "블라인드검증_결과.json"
    if b.exists():
        j = json.loads(b.read_text(encoding="utf-8"))
        L.append(f"- 새 데이터 블라인드 표본 {j['n']}문장: 정확도 {j['accuracy']:.3f} · macro-F1 {j['macro_f1']:.3f}.")
    L.append(f"\n그림: `{rel(config.OUT_SENT)}/그림_관광지별_감성구성.png`\n")


def factors():
    h("5. 만족·불만 요인")
    f = config.OUT_FACTOR / "관광지별_요인집계.csv"
    if not f.exists():
        L.append("미실행 — satisfaction.py.")
        return
    t = read_csv(f)
    ex = read_csv(config.OUT_FACTOR / "요인별_대표원문.csv") if \
        (config.OUT_FACTOR / "요인별_대표원문.csv").exists() else pd.DataFrame()
    allb = t[t.place == "34개소 전체"].set_index("category")
    for p in config.TARGET_NAMES:
        x = t[t.place == p]
        if x.empty:
            continue
        cmp_ = t[t.place == config.COMPARE_PLACES.get(p, "")].set_index("category")
        n = int(x["분석리뷰"].iloc[0])
        L.append(f"**{p}** (본문 있는 리뷰 {n}건)\n")
        y = x[(x["만족리뷰"] + x["불만리뷰"]) > 0].sort_values("순만족", ascending=False).copy()
        y["34개소 만족"] = y["category"].map(allb["만족비율"])
        y["34개소 불만"] = y["category"].map(allb["불만비율"])
        if len(cmp_):
            y[f"{config.COMPARE_PLACES[p]} 불만"] = y["category"].map(cmp_["불만비율"])
        cols = ["category", "만족리뷰", "만족비율", "불만리뷰", "불만비율", "34개소 만족", "34개소 불만"] + \
            ([f"{config.COMPARE_PLACES[p]} 불만"] if len(cmp_) else [])
        table(y[cols].rename(columns={"category": "요인"}),
              {c: "{:.1%}" for c in cols if "비율" in c or "만족" in c[-2:] or "불만" in c[-2:]
               if c not in ("만족리뷰", "불만리뷰")})
        if len(ex):
            for kind in ("만족", "불만"):
                e = ex[(ex.place == p) & (ex.구분 == kind)].sort_values("언급리뷰", ascending=False)
                for cat, g in list(e.groupby("category", sort=False))[:3]:
                    L.append(f"- {kind} · {cat}: " + " / ".join(f"“{s}”" for s in g["원문"].head(2)))
            L.append("")
    L.append("비율의 분모는 본문이 있는 리뷰 수이고, 한 리뷰가 여러 요인을 언급할 수 있다. "
             f"그림: `{rel(config.OUT_FACTOR)}/그림_{{관광지}}_만족불만요인.png`\n")


def inventory():
    rows = []
    for p in sorted(config.OUT.rglob("*")):
        if p.is_file():
            n = ""
            if p.suffix == ".csv":
                try:
                    n = len(read_csv(p))
                except Exception:  # noqa: BLE001
                    n = "?"
            rows.append({"파일": str(p.relative_to(config.OUT)), "행수": n})
    write_csv(pd.DataFrame(rows), config.OUT / "산출물_목록.csv")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    L.append("# 추가 관광지 2개소 온라인 리뷰 분석 — 결과 요약\n")
    L.append(f"생성 {datetime.now():%Y-%m-%d %H:%M} · `src/new_sites/summary.py` · "
             f"대상: {', '.join(config.TARGET_NAMES)}"
             + (" · **시험 실행(가짜 데이터)**" if config.DEMO else "") + "\n")
    L.append(f"이 파일은 보고서 작성용 재료다. 수치는 모두 {rel(config.OUT)}/ 의 CSV 에서 옮겼다.\n")
    overview()
    keywords()
    association()
    sentiment()
    factors()
    (OUT / "분석결과_요약.md").write_text("\n".join(L), encoding="utf-8")
    inventory()
    print(f"저장: {rel(OUT / '분석결과_요약.md')}")


if __name__ == "__main__":
    main()
