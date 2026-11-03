# -*- coding: utf-8 -*-
"""[6단계] 만족·불만 요인 — 34개소 코드(analyze_satisfaction.py)를 그대로 실행하고 관광지별로 집계

1) 추출: 4_연관관계분석_and_5_만족-불만요인분석/analyze_satisfaction.py 를 고치지 않고 입력·출력만 바꾼다.
   시스템 프롬프트·12개 요인 카테고리·출력 스키마·모델(config.FACTOR_MODEL)이 34개소와 같으므로
   두 결과를 같은 표에 놓을 수 있다. 중단되면 다시 실행할 때 끝난 리뷰는 건너뛴다(원 스크립트 기능).

2) 집계 (이 스크립트에서 새로 계산)
   관광지 × 요인 카테고리별로 만족·불만을 언급한 리뷰 수와 비율(분모: 본문이 있는 리뷰).
   '순만족' = 만족 언급 리뷰 비율 − 불만 언급 리뷰 비율.
   같은 요인이 34개소 전체·인접 관광지에서는 어땠는지 나란히 놓는다.
   보고서 인용용으로 요인별 대표 원문(span)을 뽑는다.

출력  output/4_만족불만요인/리뷰별_만족불만요인_분석결과.csv   (34개소 같은 이름 파일과 같은 컬럼)
      output/4_만족불만요인/관광지별_요인집계.csv
      output/4_만족불만요인/요인별_대표원문.csv
      output/4_만족불만요인/그림_{관광지}_만족불만요인.png

실행
    python scripts/s6_satisfaction.py --dry-run     # API 없이 대상 수만 확인
    python scripts/s6_satisfaction.py               # 추출 + 집계 (API)
    python scripts/s6_satisfaction.py --aggregate-only
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

import pandas as pd

from common import Checks, config, read_csv, rel, setup_font, write_csv

CATS12 = ["경관·볼거리", "체험·활동", "산책·휴식공간", "편의시설", "관리·청결", "접근·주차",
          "인적서비스", "음식·특산품", "요금·가성비", "안내·운영", "혼잡·대기", "자연·기상조건"]
OUT_CSV = config.OUT_FACTOR / "리뷰별_만족불만요인_분석결과.csv"


def extract(args):
    cmd = [sys.executable, str(config.FACTOR_DIR / "analyze_satisfaction.py"),
           "--input", str(config.PREPROCESSED), "--output", str(OUT_CSV),
           "--model", config.FACTOR_MODEL, "--effort", config.FACTOR_EFFORT]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    print("실행: analyze_satisfaction.py", " ".join(cmd[3:]).replace(str(config.REPO) + "/", ""))
    subprocess.run(cmd, check=True, cwd=config.FACTOR_DIR)


def factor_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in df.itertuples():
        try:
            fs = json.loads(r.factors_json).get("factors", []) if isinstance(r.factors_json, str) else []
        except json.JSONDecodeError:
            fs = []
        for f in fs:
            rows.append({"place": r.place, "reviewId": r.reviewId, "category": f.get("category"),
                         "sentiment": f.get("sentiment"), "span": f.get("span"), "opinion": f.get("opinion")})
    return pd.DataFrame(rows, columns=["place", "reviewId", "category", "sentiment", "span", "opinion"])


def place_table(df: pd.DataFrame, fr: pd.DataFrame, places) -> pd.DataFrame:
    out = []
    for p in places:
        n = int(((df["place"] == p) & (df["analyzed"].astype(str) == "True")).sum())
        f = fr[fr["place"] == p]
        for c in CATS12:
            pos = f[(f.category == c) & (f.sentiment == "POS")]["reviewId"].nunique()
            neg = f[(f.category == c) & (f.sentiment == "NEG")]["reviewId"].nunique()
            out.append({"place": p, "category": c, "분석리뷰": n, "만족리뷰": pos, "불만리뷰": neg,
                        "만족비율": pos / n if n else 0, "불만비율": neg / n if n else 0,
                        "순만족": (pos - neg) / n if n else 0})
    return pd.DataFrame(out)


def examples(fr: pd.DataFrame, k=3) -> pd.DataFrame:
    rows = []
    for (p, c, s), g in fr[fr.sentiment.isin(["POS", "NEG"])].groupby(["place", "category", "sentiment"]):
        g = g.assign(L=g["span"].str.len()).sort_values("L", ascending=False)
        for span in g.drop_duplicates("span")["span"].head(k):
            rows.append({"place": p, "category": c, "구분": "만족" if s == "POS" else "불만",
                         "언급리뷰": g["reviewId"].nunique(), "원문": span})
    return pd.DataFrame(rows)


def plot(tab: pd.DataFrame):
    plt = setup_font()
    for p in config.TARGET_NAMES:
        t = tab[tab.place == p]
        if t.empty or t["분석리뷰"].iloc[0] == 0:
            continue
        t = t.assign(tot=t["만족리뷰"] + t["불만리뷰"]).sort_values("tot")
        t = t[t.tot > 0]
        fig, ax = plt.subplots(figsize=(9, 0.45 * len(t) + 1.6))
        ax.barh(t["category"], t["만족비율"], color="#2a78d6", label="만족 언급")
        ax.barh(t["category"], -t["불만비율"], color="#d6452a", label="불만 언급")
        for i, r in enumerate(t.itertuples()):
            if r.만족리뷰:
                ax.text(r.만족비율 + 0.005, i, f"{r.만족리뷰}", va="center", fontsize=9)
            if r.불만리뷰:
                ax.text(-r.불만비율 - 0.005, i, f"{r.불만리뷰}", va="center", ha="right", fontsize=9)
        m = max(t["만족비율"].max(), t["불만비율"].max()) * 1.25
        ax.set_xlim(-m, m)
        ax.axvline(0, color="#555555", lw=0.8)
        ticks = ax.get_xticks()
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{abs(x):.0%}" for x in ticks])
        ax.set_xlabel(f"언급 리뷰 비율 (분모: 본문 있는 리뷰 {int(t['분석리뷰'].iloc[0])}건, 막대 끝 숫자 = 리뷰 수)")
        ax.set_title(f"{p} 요인별 만족·불만", loc="left")
        ax.legend(ncol=2, loc="lower right", bbox_to_anchor=(1.0, 1.0), frameon=False)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        fig.tight_layout()
        fig.savefig(config.OUT_FACTOR / f"그림_{p}_만족불만요인.png", dpi=150)
        plt.close(fig)


def aggregate():
    ck = Checks("만족·불만 요인 집계")
    ck("요인 추출 결과 존재", OUT_CSV.exists(), rel(OUT_CSV))
    df = read_csv(OUT_CSV, dtype={"reviewId": str})
    status = df["run_status"].value_counts().to_dict()
    bad = {k: v for k, v in status.items() if k not in ("ok", "skipped: 본문 없음")}
    ck("추출 실패 없음", not bad, f"상태 {status}", fatal=False)
    fr = factor_rows(df)

    base = read_csv(config.BASE_FACTOR, dtype={"reviewId": str})
    bfr = factor_rows(base)
    cmp_places = [v for v in config.COMPARE_PLACES.values()]
    tab = place_table(df, fr, config.TARGET_NAMES)
    tab_cmp = place_table(base, bfr, cmp_places)
    base_all = place_table(base.assign(place="34개소 전체"), bfr.assign(place="34개소 전체"), ["34개소 전체"])
    full = pd.concat([tab, tab_cmp, base_all], ignore_index=True)
    write_csv(full, config.OUT_FACTOR / "관광지별_요인집계.csv")
    write_csv(examples(fr), config.OUT_FACTOR / "요인별_대표원문.csv")
    plot(tab)
    ck("관광지별 요인 집계", len(tab) > 0, f"{len(tab)}행 (비교 {len(tab_cmp) + len(base_all)}행 별도)")

    for p in config.TARGET_NAMES:
        t = tab[tab.place == p]
        if t.empty:
            continue
        sat = t.sort_values("만족리뷰", ascending=False).head(3)
        dis = t.sort_values("불만리뷰", ascending=False).head(3)
        print(f"\n  [{p}] 분석 리뷰 {int(t['분석리뷰'].iloc[0])}건")
        print("    만족 상위: " + " · ".join(f"{r.category} {r.만족리뷰}건({r.만족비율:.0%})" for r in sat.itertuples()))
        print("    불만 상위: " + " · ".join(f"{r.category} {r.불만리뷰}건({r.불만비율:.0%})" for r in dis.itertuples()))
    print(f"\n저장: {rel(config.OUT_FACTOR)}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--aggregate-only", action="store_true")
    args = ap.parse_args()
    config.OUT_FACTOR.mkdir(parents=True, exist_ok=True)
    if not args.aggregate_only:
        extract(args)
    if not args.dry_run:
        aggregate()


if __name__ == "__main__":
    main()
