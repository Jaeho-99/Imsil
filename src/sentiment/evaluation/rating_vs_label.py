# -*- coding: utf-8 -*-
"""별점 × 사람 감성라벨 교차표 (4단계)

1강 "별점은 감성이 아니다"의 실증 근거를 만든다.
별점을 정답으로 썼다면 어떤 일이 벌어졌을지를 숫자로 보인다.

입력 — 읽기만 한다.
  output/sentiment/labeling/확정/검증셋_본_확정.csv      532문장
  output/sentiment/labeling/확정/검증셋_보강_확정.csv    166문장
  input/sentiment/labeling/_대조표_별점포함_라벨링중_열지말것.csv   별점·날짜 (라벨링 끝났으므로 이제 연다)

출력
  output/sentiment/evaluation/별점_교차표.md

주의: 네이버는 별점이 없다. 별점 분석은 전부 구글 한정이다.
"""
import pandas as pd
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_IN, SENT_OUT  # noqa: E402
LAB_IN = SENT_IN / "labeling"
LAB_OUT = SENT_OUT / "labeling"
OUT = SENT_OUT / "evaluation"
OUT.mkdir(parents=True, exist_ok=True)
LABELS = ["긍정", "중립", "부정"]

main = pd.read_csv(LAB_OUT / "확정" / "검증셋_본_확정.csv", encoding="utf-8-sig")
boost = pd.read_csv(LAB_OUT / "확정" / "검증셋_보강_확정.csv", encoding="utf-8-sig")
ref = pd.read_csv(LAB_IN / "_대조표_별점포함_라벨링중_열지말것.csv", encoding="utf-8-sig")
ref = ref[["review_id", "rating"]].drop_duplicates("review_id")

out = []
def w(s=""): out.append(s)


def macro_f1(gold, pred):
    """클래스별 F1의 산술평균. 분모가 0이면 그 클래스 F1을 0으로 둔다."""
    f1s = {}
    for c in LABELS:
        tp = ((gold == c) & (pred == c)).sum()
        fp = ((gold != c) & (pred == c)).sum()
        fn = ((gold == c) & (pred != c)).sum()
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1s[c] = 2 * p * r / (p + r) if p + r else 0.0
    return sum(f1s.values()) / len(LABELS), f1s


def table(df, index, columns, title):
    t = pd.crosstab(df[index], df[columns])
    for c in LABELS:
        if c not in t:
            t[c] = 0
    t = t[LABELS]
    t["합계"] = t.sum(axis=1)
    w(f"### {title}\n")
    w("| " + index + " | " + " | ".join(LABELS) + " | 합계 | 부정 비율 |")
    w("|---" * (len(LABELS) + 3) + "|")
    for idx, row in t.iterrows():
        neg = row["부정"] / row["합계"] * 100 if row["합계"] else 0
        w(f"| {idx} | " + " | ".join(str(int(row[c])) for c in LABELS)
          + f" | {int(row['합계'])} | {neg:.1f}% |")
    w()
    return t


for name, df in (("본 검증셋", main), ("부정 보강셋", boost)):
    d = df.merge(ref, on="review_id", how="left")
    g = d[(d.platform == "구글") & d.rating.notna()].copy()
    g["rating"] = g.rating.astype(int)
    w(f"## {name}\n")
    w(f"문장 {len(d)} 중 구글 {len(g)} · 네이버 {len(d)-len(g)} (네이버는 별점 없음)\n")
    if not len(g):
        continue
    table(g, "rating", "label", "별점 × 문장 라벨 (문장 단위)")

    # 별점을 정답으로 썼다면
    m = {1: "부정", 2: "부정", 3: "중립", 4: "긍정", 5: "긍정"}
    g["별점라벨"] = g.rating.map(m)
    f1, per = macro_f1(g.label, g.별점라벨)
    acc = (g.label == g.별점라벨).mean()
    w(f"**별점을 정답으로 썼다면** (1–2→부정 · 3→중립 · 4–5→긍정, 구글 {len(g)}문장 기준)\n")
    w(f"- 사람 라벨과 일치: **{acc*100:.1f}%** · macro-F1 **{f1:.3f}**")
    w("- 클래스별 F1: " + " · ".join(f"{k} {v:.3f}" for k, v in per.items()) + "\n")

    # 리뷰 단위 — 별점 안에 반대 감성이 얼마나 섞여 있나
    rv = g.groupby(["review_id", "rating"]).label.agg(list).reset_index()
    rows = []
    for r in sorted(rv.rating.unique()):
        s = rv[rv.rating == r]
        rows.append((r, len(s),
                     sum("부정" in x for x in s.label) / len(s) * 100,
                     sum("긍정" in x for x in s.label) / len(s) * 100,
                     sum(len(set(x) & {"긍정", "부정"}) == 2 for x in s.label) / len(s) * 100))
    w("### 리뷰 안에 섞인 감성 (리뷰 단위)\n")
    w("| 별점 | 리뷰 | 부정 문장 포함 | 긍정 문장 포함 | 둘 다 포함 |")
    w("|---|---:|---:|---:|---:|")
    for r, n, neg, pos, both in rows:
        w(f"| {r}점 | {n} | {neg:.1f}% | {pos:.1f}% | {both:.1f}% |")
    w()

# 다수 클래스 기준선 — 파일럿 추정치(0.661)를 실제 라벨로 갱신
test = main[main.split == "TEST"]
base = test.label.value_counts(normalize=True).max()
w("## 다수 클래스 기준선 갱신\n")
w(f"| | 값 | 출처 |")
w(f"|---|---:|---|")
w(f"| 파일럿 추정 (LLM 라벨 62문장) | 0.661 | `learning-records/0004` |")
w(f"| **확정 (사람 라벨 TEST 본 {len(test)}문장)** | **{base:.3f}** | 이 문서 |")
w()
w(f"②·③이 정확도 {base:.3f}를 못 넘으면 2강 4순위 규칙(채택하지 않고 그 사실을 결과로 보고)이 발동한다.\n")

(OUT / "별점_교차표.md").write_text(
    "# 별점 × 감성라벨 교차표\n\n생성 2026-08-22 · 재현: `src/sentiment/evaluation/rating_vs_label.py`\n\n"
    + "\n".join(out), encoding="utf-8")
print("\n".join(out))
