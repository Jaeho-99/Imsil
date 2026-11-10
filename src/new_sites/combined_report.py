# -*- coding: utf-8 -*-
"""[합산] 34개소 + 추가 2개소 — 보고서 리뷰 분석 절의 표·그림 숫자를 다시 낸다

34개소 보고서(리뷰 데이터 분석 절)의 표·그림을 추가 2개소(성수산·오수의견국민여가캠핑장)를 넣은 숫자로
다시 만든다. 판정은 새로 하지 않는다. 두 분석의 리뷰별 결과 파일을 행 단위로 합쳐 같은 방식으로 센다.

  34개소   output/satisfaction/리뷰별_만족불만요인_분석결과.csv           (5장 결과, 5,267행)
  추가     output/new_sites/satisfaction/리뷰별_만족불만요인_분석결과_요인기간.csv  (satisfaction.py merge 결과,
           config.FACTOR_DATE_END 까지)

두 파일은 열이 같다. 한 행이 수집 리뷰 하나이고, 본문이 없는 리뷰도 run_status='skipped: 본문 없음' 으로 들어 있다.

보고서 항목과 세는 방법
  그림 2-7 (요약본 그림 10)  연도별 수집 리뷰 수 · 만족도 분석 리뷰 수
        수집 = 행 수, 분석 = run_status 'ok' 이고 overall_sentiment 가 POS·NEU·NEG 인 행. 2022~2025년.
  그림 2-8 (요약본 그림 11)  연도별 긍정·중립·부정 리뷰 비율 — 분석 리뷰의 overall_sentiment. 2022~2025년.
  그림 2-9 · 요약본 표 2      만족·불만 요인 상위 5개 — 만족(또는 불만) 요인 건수 (아래 '요인 세는 단위'). '대상외' 제외.
  표 2-2 · 요약본 표 4        관광지별 분석 리뷰 수와 요인별 만족·불만 건수

  요인 세는 단위 (2026-11-10 결정)
    34개소   보고서 초안 그대로 (요인, 극성) 언급 수로 센다. 34개소 숫자는 기존 보고서와 같아야 한다.
    추가 2개소  리뷰 수로 센다. 한 리뷰에서 같은 요인을 여러 번 언급해도 1건이다. 오수의견국민여가캠핑장 리뷰는
             길어서(본문 중앙값 250자, 34개소 21자) 같은 요인을 거듭 언급하는 일이 많아, 언급 수로 세면
             요인 건수가 분석 리뷰 수보다 커진다. (34개소는 거듭 언급이 리뷰당 0.04건이라 두 방식 차이가 작다)
    합계     34개소 언급 수 + 추가 2개소 리뷰 수.
  그림 2-10                  계절별 긍정·중립·부정 리뷰 비율 (봄 3~5월, 여름 6~8월, 가을 9~11월, 겨울 12~2월). 2022~2025년.

기간
  연도별·계절별 항목은 두 분석 모두 2022~2025년만 센다.
  요인 리뷰 수와 관광지별 분석 리뷰 수는 34개소 보고서와 같이 2022년~2026년 8월 리뷰로 센다.
  34개소 결과 파일은 전체가 이 기간이다(FACTOR_YEARS_34 = None). 추가 2개소는 요인 기간 결과 파일
  (config.FACTOR_DATE_END = 2026-08-31 까지)을 쓴다.

재현 확인 (34개소만 셌을 때 보고서 초안과 같아야 하는 숫자 — 다르면 멈춘다. 입력 파일이 같은지 보는 검사다)
  수집 2022~2025년 1,192 · 1,817 · 1,238 · 730건, 분석 691 · 1,047 · 792 · 468건, 계절 합계 2,998건
  만족 1위 경관·볼거리 1,044건, 불만 1위 자연·기상조건 240건 (언급 수)

입력  output/satisfaction/리뷰별_만족불만요인_분석결과.csv
      output/new_sites/satisfaction/리뷰별_만족불만요인_분석결과_요인기간.csv
출력  output/new_sites/combined/
        연도별_리뷰수_감성.csv       그림 2-7·2-8 숫자 (34개소 · 추가 2개소 · 합계, 전년 대비 증감)
        요인별_리뷰수.csv           그림 2-9 숫자 (요인 × 만족·불만, 34개소 · 추가 · 합계, 순위)
        관광지별_요인리뷰수.csv      표 2-2 숫자 (관광지 × 요인 × 만족·불만)
        관광지별_주요요인.csv        표 2-2 한 줄 요약 (관광지별 분석 리뷰 수, 만족·불만 상위 3개)
        계절별_감성.csv             그림 2-10 숫자
        수치요약.md                 본문 문장에 들어가는 숫자 (증감률 등)
        그림2-7_연도별_리뷰분포.png
        그림2-8_연도별_감성분포.png
        그림2-9_주요요인.png
        그림2-10_계절별_감성비율.png

실행
    python src/new_sites/combined_report.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

import pandas as pd

from common import Checks, config, read_csv, rel, setup_font, write_csv

sys.path.insert(0, str(config.FACTOR_SCRIPT.parent))
import analyze_satisfaction as az  # noqa: E402  34개소 코드: 요인 카테고리

BASE_CSV = config.BASE_FACTOR
NEW_CSV = config.OUT_FACTOR / "리뷰별_만족불만요인_분석결과_요인기간.csv"
OUT = config.OUT / "combined"

YEARS = [2022, 2023, 2024, 2025]           # 연도별·계절별 항목 (두 분석 모두)
FACTOR_YEARS_34 = None                     # 34개소 요인 집계 기간. None = 결과 파일 전체 (2022년~2026년 8월, 34개소 보고서와 같다)
TOP_N = 5                                  # 그림 2-9 상위 요인 수
CATS = [c for c in az.CATEGORIES if c != "대상외"]
SENTS = [("POS", "긍정"), ("NEU", "중립"), ("NEG", "부정")]
SEASONS = ["봄", "여름", "가을", "겨울"]
GROUPS = ["34개소", "추가2개소", "합계"]

# 34개소만 셌을 때 보고서와 같아야 하는 숫자
EXPECT_34 = {
    "collected": {2022: 1192, 2023: 1817, 2024: 1238, 2025: 730},
    "analyzed": {2022: 691, 2023: 1047, 2024: 792, 2025: 468},
    "pos_top": ("경관·볼거리", 1044),
    "neg_top": ("자연·기상조건", 240),
    "season_total": 2998,
}

# 그림 색 — 34개소 보고서 그림과 같은 계열
C_COLLECT, C_ANALYZED = "#3D6AA2", "#F0A04B"
C_SENT = {"POS": "#3B7DC4", "NEU": "#A7B1BE", "NEG": "#E2735E"}
C_SEASON = {"POS": "#31846B", "NEU": "#D19A3B", "NEG": "#C65E5A"}   # src/satisfaction/plot_seasonal_sentiment.py
C_FACTOR = {"POS": "#3B7DC4", "NEG": "#E2735E"}


# ─────────────────────────────────────────────────────────────
# 읽기
# ─────────────────────────────────────────────────────────────
def parse_date(s: str):
    try:
        return datetime.strptime(str(s).strip(), "%Y.%m.%d")
    except ValueError:
        return None


def load(path, group: str) -> pd.DataFrame:
    df = read_csv(path, dtype=str, keep_default_na=False)
    df["group"] = group
    d = df["date"].map(parse_date)
    df["year"] = d.map(lambda x: x.year if x else None)
    df["month"] = d.map(lambda x: x.month if x else None)
    df["sent"] = df["overall_sentiment"].str.strip().str.upper()
    df["is_analyzed"] = (df["run_status"].str.strip() == "ok") & df["sent"].isin(["POS", "NEU", "NEG"])
    return df


def season_of(month: int) -> str:
    return SEASONS[(month % 12) // 3 - 1]   # 3~5 봄, 6~8 여름, 9~11 가을, 12~2 겨울


PER_REVIEW_GROUPS = ("추가2개소",)   # 리뷰 수로 세는 구분. 34개소는 언급 수 (보고서 초안과 같게)


def factor_rows(df: pd.DataFrame, per_review_groups=PER_REVIEW_GROUPS) -> pd.DataFrame:
    """factors_json 의 (요인, 극성) 한 쌍이 한 행 (= 언급 수). per_review_groups 에 든 구분은
    한 리뷰의 같은 (요인, 극성)을 한 행만 남긴다 (= 리뷰 수)."""
    rows = []
    for r in df[df["is_analyzed"]].itertuples():
        try:
            fs = json.loads(r.factors_json).get("factors", []) if r.factors_json else []
        except json.JSONDecodeError:
            fs = []
        for f in fs:
            rows.append({"group": r.group, "place": r.place, "reviewId": r.reviewId, "year": r.year,
                         "category": f.get("category"), "sentiment": f.get("sentiment")})
    out = pd.DataFrame(rows, columns=["group", "place", "reviewId", "year", "category", "sentiment"])
    dup = out.duplicated(["group", "reviewId", "category", "sentiment"]) & out["group"].isin(per_review_groups)
    return out[~dup]


def in_factor_period(df: pd.DataFrame) -> pd.DataFrame:
    """요인 집계에 쓰는 행 — 34개소는 FACTOR_YEARS_34, 추가 2개소는 요인 기간 결과 파일 전체."""
    if FACTOR_YEARS_34 is None:
        return df
    keep = (df["group"] != "34개소") | df["year"].isin(FACTOR_YEARS_34)
    return df[keep]


def with_total(parts: dict) -> dict:
    """{'34개소': df, '추가2개소': df} → '합계' 를 더한다."""
    parts = dict(parts)
    parts["합계"] = pd.concat(list(parts.values()), ignore_index=True)
    return parts


# ─────────────────────────────────────────────────────────────
# 집계
# ─────────────────────────────────────────────────────────────
def yearly(parts: dict) -> pd.DataFrame:
    rows = []
    for g in GROUPS:
        df = parts[g]
        for y in YEARS:
            dy = df[df["year"] == y]
            a = dy[dy["is_analyzed"]]
            row = {"구분": g, "연도": y, "수집리뷰": len(dy), "분석리뷰": len(a)}
            for code, label in SENTS:
                n = int((a["sent"] == code).sum())
                row[f"{label}"] = n
                row[f"{label}비율"] = round(100 * n / len(a), 1) if len(a) else None
            rows.append(row)
    t = pd.DataFrame(rows)
    for col in ("수집리뷰", "분석리뷰"):
        prev = t.groupby("구분")[col].shift(1)
        t[f"{col}_전년대비증감률"] = ((t[col] - prev) / prev * 100).round(1)
    return t


def factor_counts(fr: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for g in GROUPS:
        f = fr if g == "합계" else fr[fr["group"] == g]
        for code, label in (("POS", "만족"), ("NEG", "불만")):
            fc = f[f["sentiment"] == code]["category"].value_counts()
            ranked = sorted(CATS, key=lambda c: (-int(fc.get(c, 0)), CATS.index(c)))
            for rank, c in enumerate(ranked, 1):
                rows.append({"구분": g, "극성": label, "요인": c, "리뷰수": int(fc.get(c, 0)), "순위": rank})
    return pd.DataFrame(rows)


def place_factors(an: pd.DataFrame, fr: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    n_rev = an.groupby(["group", "place"]).size()
    long_rows, top_rows = [], []
    for (g, p), n in n_rev.sort_values(ascending=False).items():
        f = fr[(fr["group"] == g) & (fr["place"] == p)]
        top = {"구분": g, "관광지": p, "분석리뷰": int(n)}
        for code, label in (("POS", "만족"), ("NEG", "불만")):
            fc = f[f["sentiment"] == code]["category"].value_counts()
            for c in CATS:
                long_rows.append({"구분": g, "관광지": p, "분석리뷰": int(n), "극성": label,
                                  "요인": c, "리뷰수": int(fc.get(c, 0))})
            ranked = [c for c in sorted(CATS, key=lambda c: (-int(fc.get(c, 0)), CATS.index(c)))
                      if fc.get(c, 0)]
            for i in range(3):
                top[f"{label}{i + 1}"] = f"{ranked[i]}({int(fc[ranked[i]])})" if i < len(ranked) else ""
        top_rows.append(top)
    return pd.DataFrame(long_rows), pd.DataFrame(top_rows)


def seasonal(parts: dict) -> pd.DataFrame:
    rows = []
    for g in GROUPS:
        a = parts[g]
        a = a[a["is_analyzed"] & a["year"].isin(YEARS)]
        a = a.assign(season=a["month"].map(lambda m: season_of(int(m))))
        for s in SEASONS:
            ds = a[a["season"] == s]
            row = {"구분": g, "계절": s, "분석리뷰": len(ds)}
            for code, label in SENTS:
                n = int((ds["sent"] == code).sum())
                row[label] = n
                row[f"{label}비율"] = round(100 * n / len(ds), 1) if len(ds) else None
            rows.append(row)
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────
# 그림 — 보고서 그림과 내용·구성을 맞춘다 (제목·출처는 보고서 캡션으로 단다)
# ─────────────────────────────────────────────────────────────
def _clean(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#E3E6EA", linewidth=0.8)
    ax.set_axisbelow(True)


def plot_yearly_counts(plt, t: pd.DataFrame, path):
    t = t[t["구분"] == "합계"]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    x = range(len(YEARS))
    w = 0.36
    for off, col, color, label in ((-w / 2, "수집리뷰", C_COLLECT, "수집 리뷰"),
                                   (w / 2, "분석리뷰", C_ANALYZED, "만족도 분석에 사용된 리뷰")):
        bars = ax.bar([i + off for i in x], t[col], width=w, color=color, label=label)
        for b, v in zip(bars, t[col]):
            ax.annotate(f"{v:,}", (b.get_x() + b.get_width() / 2, b.get_height()), xytext=(0, 4),
                        textcoords="offset points", ha="center", va="bottom", fontsize=10)
    ax.set_xticks(list(x), [f"{y}년" for y in YEARS])
    ax.set_xlabel("연도")
    ax.set_ylabel("리뷰 수(건)")
    ax.set_ylim(0, max(t["수집리뷰"]) * 1.15)
    _clean(ax)
    ax.legend(ncol=2, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def plot_yearly_sentiment(plt, t: pd.DataFrame, path):
    t = t[t["구분"] == "합계"].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 5.6))
    x = list(range(len(YEARS)))
    bottom = [0.0] * len(YEARS)
    for code, label in SENTS:
        vals = [100 * r[label] / r["분석리뷰"] if r["분석리뷰"] else 0 for _, r in t.iterrows()]
        ax.bar(x, vals, bottom=bottom, width=0.62, color=C_SENT[code], label=label,
               edgecolor="white", linewidth=0.8)
        for i, v in enumerate(vals):
            if v >= 3:
                ax.text(i, bottom[i] + v / 2, f"{v:.1f}%", ha="center", va="center", fontsize=10,
                        color="white" if code != "NEU" else "#222222", fontweight="bold")
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(x, [str(y) for y in YEARS])
    ax.set_ylabel("비율(%)")
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 20), [f"{v}%" for v in range(0, 101, 20)])
    _clean(ax)
    ax.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def plot_factors(plt, fc: pd.DataFrame, path):
    f = fc[(fc["구분"] == "합계") & (fc["순위"] <= TOP_N)]
    fig, axes = plt.subplots(2, 1, figsize=(10, 8.4))
    for ax, (label, code, legend) in zip(axes, (("만족", "POS", "만족 요인"), ("불만", "NEG", "불만 요인"))):
        d = f[f["극성"] == label].sort_values("순위")
        bars = ax.bar(d["요인"], d["리뷰수"], width=0.55, color=C_FACTOR[code], label=legend)
        for b, v in zip(bars, d["리뷰수"]):
            ax.annotate(f"{v:,}", (b.get_x() + b.get_width() / 2, b.get_height()), xytext=(0, 3),
                        textcoords="offset points", ha="center", va="bottom", fontsize=10)
        ax.set_ylabel("리뷰 수(건)")
        ax.set_ylim(0, d["리뷰수"].max() * 1.18)
        _clean(ax)
        ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout(h_pad=2.5)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def plot_seasonal(plt, s: pd.DataFrame, path):
    s = s[s["구분"] == "합계"].set_index("계절").loc[SEASONS]
    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    w = 0.22
    for off, (code, label) in zip((-1, 0, 1), SENTS):
        pct = [r[f"{label}비율"] or 0 for _, r in s.iterrows()]
        bars = ax.bar([i + off * w for i in range(len(SEASONS))], pct, width=w,
                      color=C_SEASON[code], label=label)
        for b, p, n in zip(bars, pct, s[label]):
            if n:
                ax.annotate(f"{p:.1f}%\n({n:,}건)", (b.get_x() + b.get_width() / 2, b.get_height()),
                            xytext=(0, 5), textcoords="offset points", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(range(len(SEASONS)), [f"{k}\n(n={n:,})" for k, n in zip(SEASONS, s["분석리뷰"])])
    ax.set_ylabel("리뷰 수 비율 (%)")
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 20))
    _clean(ax)
    ax.legend(ncol=3, frameon=False, loc="upper right")
    fig.suptitle("임실군 전체 관광지의 계절별 긍정·중립·부정 리뷰 비율", fontsize=17, fontweight="bold", y=0.98)
    fig.tight_layout(rect=(0, 0.02, 1, 0.92))
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
# 수치 요약 (본문 문장용)
# ─────────────────────────────────────────────────────────────
def pct_change(a, b) -> str:
    if not a:
        return "비교 불가(전년 0건)"
    v = (b - a) / a * 100
    return f"{abs(v):.1f}% {'증가' if v > 0 else '감소'}"


def summary_md(t, fc, top, s, n_new_by_place) -> str:
    L = ["# 34개소 + 추가 2개소 합산 수치 요약", "",
         f"만든 코드: src/new_sites/combined_report.py · 만든 날: {datetime.now():%Y-%m-%d}", "",
         "추가 2개소 리뷰 수 (분석 기간 안): " + ", ".join(f"{p} {n}건" for p, n in n_new_by_place.items()), ""]
    for g in GROUPS:
        ty = t[t["구분"] == g].set_index("연도")
        L += [f"## 연도별 ({g})", "",
              "| 연도 | 수집 | 분석 | 긍정 | 중립 | 부정 |", "|---|---:|---:|---:|---:|---:|"]
        for y in YEARS:
            r = ty.loc[y]
            L.append(f"| {y} | {r['수집리뷰']:,} | {r['분석리뷰']:,} | {r['긍정비율']}% | {r['중립비율']}% | {r['부정비율']}% |")
        c, a = ty["수집리뷰"], ty["분석리뷰"]
        L += ["", f"- 수집 합계 {c.sum():,}건, 분석 합계 {a.sum():,}건",
              "- 수집 전년 대비: " + ", ".join(f"’{str(y)[2:]}년 {pct_change(c[y - 1], c[y])}" for y in YEARS[1:]),
              f"- 수집 ’22년 대비 ’25년: {pct_change(c[2022], c[2025])} ({abs(c[2025] - c[2022]):,}건)",
              "- 분석 전년 대비: " + ", ".join(f"’{str(y)[2:]}년 {pct_change(a[y - 1], a[y])}" for y in YEARS[1:]),
              f"- 분석 ’22년 대비 ’25년: {pct_change(a[2022], a[2025])} ({abs(a[2025] - a[2022]):,}건)"]
        p, n, u = ty["긍정비율"].fillna(0), ty["부정비율"].fillna(0), ty["중립비율"].fillna(0)
        L += [f"- 긍정 비율 범위 {p.min()}~{p.max()}%, 부정 비율 범위 {n.min()}~{n.max()}%",
              f"- ’25년 전년 대비: 긍정 {p[2025] - p[2024]:+.1f}%p, 부정 {n[2025] - n[2024]:+.1f}%p, 중립 {u[2025] - u[2024]:+.1f}%p", ""]
    for g in GROUPS:
        L += [f"## 만족·불만 요인 상위 {TOP_N} ({g})", ""]
        for label in ("만족", "불만"):
            d = fc[(fc["구분"] == g) & (fc["극성"] == label) & (fc["순위"] <= TOP_N + 1)]
            L.append(f"- {label}: " + ", ".join(f"{r.요인} {r.리뷰수:,}건" for r in d.itertuples()))
        L.append("")
    L += ["## 관광지별 주요 요인 (분석 리뷰 수 순)", "",
          "| 구분 | 관광지 | 분석 리뷰 | 만족 1 | 만족 2 | 만족 3 | 불만 1 | 불만 2 | 불만 3 |",
          "|---|---|---:|---|---|---|---|---|---|"]
    for r in top.head(12).itertuples():
        L.append(f"| {r.구분} | {r.관광지} | {r.분석리뷰:,} | {r.만족1} | {r.만족2} | {r.만족3} | {r.불만1} | {r.불만2} | {r.불만3} |")
    for r in top[(top["구분"] == "추가2개소")].itertuples():
        if r.Index >= 12:
            L.append(f"| {r.구분} | {r.관광지} | {r.분석리뷰:,} | {r.만족1} | {r.만족2} | {r.만족3} | {r.불만1} | {r.불만2} | {r.불만3} |")
    L.append("")
    for g in GROUPS:
        ss = s[s["구분"] == g].set_index("계절")
        tot = ss["분석리뷰"].sum()
        pos = ss["긍정"].sum()
        L += [f"## 계절별 ({g}) — 합계 {tot:,}건, 전체 긍정 {100 * pos / tot:.1f}%" if tot else f"## 계절별 ({g})", ""]
        for k in SEASONS:
            r = ss.loc[k]
            if r["분석리뷰"]:
                L.append(f"- {k} (n={r['분석리뷰']:,}): 긍정 {r['긍정비율']}%, 중립 {r['중립비율']}%, 부정 {r['부정비율']}%")
            else:
                L.append(f"- {k} (n=0): 리뷰 없음")
        L.append("")
    return "\n".join(L)


# ─────────────────────────────────────────────────────────────
def main():
    ck = Checks("34개소 + 추가 2개소 합산")
    ck("34개소 결과 파일", BASE_CSV.exists(), rel(BASE_CSV))
    ck("추가 2개소 결과 파일", NEW_CSV.exists(),
       rel(NEW_CSV) if NEW_CSV.exists() else f"{rel(NEW_CSV)} 없음 — satisfaction.py merge 를 먼저 실행")
    base, new = load(BASE_CSV, "34개소"), load(NEW_CSV, "추가2개소")
    ck("추가 2개소 장소명", set(new["place"]) <= set(config.TARGET_NAMES), f"{sorted(set(new['place']))}")
    ck("두 파일의 리뷰ID 겹침 없음", not set(base["reviewId"]) & set(new["reviewId"]))
    bad_dates = int(base["year"].isna().sum() + new["year"].isna().sum())
    ck("날짜 읽기", bad_dates == 0, f"읽지 못한 날짜 {bad_dates}건")
    lo, hi = config.DATE_START[:4], (config.factor_end() or "9999")[:4]
    ck("추가 2개소 기간", new["year"].between(int(lo), int(hi)).all(), f"{int(new['year'].min())}~{int(new['year'].max())}년")

    parts = with_total({"34개소": base, "추가2개소": new})
    t = yearly(parts)
    allrows = pd.concat([base, new], ignore_index=True)
    an = in_factor_period(allrows[allrows["is_analyzed"]])
    fr = factor_rows(an)
    fc = factor_counts(fr)
    long_pf, top = place_factors(an, fr)
    s = seasonal(parts)

    # 재현 확인 — 34개소만 센 숫자가 보고서와 같은가
    t34 = t[t["구분"] == "34개소"].set_index("연도")
    ck("재현: 34개소 연도별 수집 리뷰", t34["수집리뷰"].to_dict() == EXPECT_34["collected"], f"{t34['수집리뷰'].to_dict()}")
    ck("재현: 34개소 연도별 분석 리뷰", t34["분석리뷰"].to_dict() == EXPECT_34["analyzed"], f"{t34['분석리뷰'].to_dict()}")
    if FACTOR_YEARS_34 is None:
        m34 = fr[fr["group"] == "34개소"]
        top_of = lambda code: m34[m34["sentiment"] == code]["category"].value_counts().head(1)  # noqa: E731
        got = tuple((t.index[0], int(t.iloc[0])) for t in (top_of("POS"), top_of("NEG")))
        ck("재현: 34개소 만족·불만 1위 (언급 수)", got == (EXPECT_34["pos_top"], EXPECT_34["neg_top"]), f"{got}")
    s34 = int(s[s["구분"] == "34개소"]["분석리뷰"].sum())
    ck("재현: 34개소 계절별 합계", s34 == EXPECT_34["season_total"], f"{s34:,}건")

    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(t, OUT / "연도별_리뷰수_감성.csv")
    write_csv(fc, OUT / "요인별_리뷰수.csv")
    write_csv(long_pf, OUT / "관광지별_요인리뷰수.csv")
    write_csv(top, OUT / "관광지별_주요요인.csv")
    write_csv(s, OUT / "계절별_감성.csv")
    n_new = new.groupby("place").size().to_dict()
    (OUT / "수치요약.md").write_text(summary_md(t, fc, top, s, n_new), encoding="utf-8")

    plt = setup_font()
    plot_yearly_counts(plt, t, OUT / "그림2-7_연도별_리뷰분포.png")
    plot_yearly_sentiment(plt, t, OUT / "그림2-8_연도별_감성분포.png")
    plot_factors(plt, fc, OUT / "그림2-9_주요요인.png")
    plot_seasonal(plt, s, OUT / "그림2-10_계절별_감성비율.png")
    ck("그림 4개", all((OUT / n).exists() for n in ("그림2-7_연도별_리뷰분포.png", "그림2-8_연도별_감성분포.png",
                                                   "그림2-9_주요요인.png", "그림2-10_계절별_감성비율.png")))

    tt = t[t["구분"] == "합계"].set_index("연도")
    print("\n  합계 수집 " + " · ".join(f"{y} {tt.loc[y, '수집리뷰']:,}" for y in YEARS)
          + f" (계 {tt['수집리뷰'].sum():,})")
    print("  합계 분석 " + " · ".join(f"{y} {tt.loc[y, '분석리뷰']:,}" for y in YEARS)
          + f" (계 {tt['분석리뷰'].sum():,})")
    for label in ("만족", "불만"):
        d = fc[(fc["구분"] == "합계") & (fc["극성"] == label) & (fc["순위"] <= TOP_N)]
        print(f"  {label} 상위 {TOP_N}: " + ", ".join(f"{r.요인} {r.리뷰수:,}" for r in d.itertuples()))
    print(f"\n저장: {rel(OUT)}/  (숫자는 수치요약.md)")


if __name__ == "__main__":
    main()
