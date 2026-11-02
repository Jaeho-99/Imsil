# -*- coding: utf-8 -*-
"""재라벨 50문장 -> Cohen's κ (4단계)

입력 — 읽기만 한다.
  labeling/재라벨/재라벨_50문장.xlsx   2차 라벨 (사용자가 채운 것)
  labeling/재라벨/재라벨_매핑.csv      재라벨_id -> unit_id
  labeling/확정/검증셋_본_확정.csv     1차 라벨 (원본)

출력
  labeling/재라벨/재라벨_결과.md       κ · 혼동표 · 불일치 50건 중 전체 목록
  labeling/재라벨/불일치.csv           불일치 문장만 (문맥 포함)

설계
  - κ 는 **같은 사람이 시간을 두고 다시 매긴 것**이므로 intra-rater(재현성)다.
    보고서에 rater 2명의 합의도로 쓰지 않는다.
  - 1차 라벨은 절대 덮어쓰지 않는다. 이 스크립트는 원본을 읽기만 한다.
  - 신뢰구간은 부트스트랩(문장 단위 복원추출 10,000회) 백분위수로 낸다.
    n=50 이라 정규근사 SE 보다 이쪽이 정직하다.

실행:  ../../.venv/Scripts/python.exe labeling/kappa.py
"""
import random
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RL = HERE / "재라벨"
LABELS = ["긍정", "부정", "중립"]
B = 10000
SEED = 20260823

# ---------- 읽기 ----------
new = pd.read_excel(RL / "재라벨_50문장.xlsx", sheet_name="재라벨")
mapping = pd.read_csv(RL / "재라벨_매핑.csv", encoding="utf-8-sig")
old = pd.read_csv(HERE / "확정" / "검증셋_본_확정.csv", encoding="utf-8-sig")

new["label"] = new["label"].astype(str).str.strip()
blank = new[~new["label"].isin(LABELS)]
if len(blank):
    raise SystemExit(f"라벨이 비었거나 값이 이상한 행 {len(blank)}개: "
                     f"{blank['재라벨_id'].tolist()}")

df = (mapping
      .merge(new[["재라벨_id", "sent", "문맥", "label", "note"]], on="재라벨_id")
      .merge(old[["unit_id", "place", "platform", "sent_no", "n_sent", "label"]],
             on="unit_id", suffixes=("_2차", "_1차")))
assert len(df) == len(mapping) == 50, f"결합 후 {len(df)}행 — 매핑이 어긋났다"

a = df["label_1차"]
b = df["label_2차"]
n = len(df)

# ---------- κ ----------
def kappa(x, y):
    po = (x == y).mean()
    pe = sum((x == c).mean() * (y == c).mean() for c in LABELS)
    return (po - pe) / (1 - pe), po, pe


k, po, pe = kappa(a, b)

rng = random.Random(SEED)
idx = list(range(n))
boot = []
for _ in range(B):
    s = [rng.choice(idx) for _ in idx]
    xa, xb = a.iloc[s].reset_index(drop=True), b.iloc[s].reset_index(drop=True)
    try:
        kb, _, _ = kappa(xa, xb)
    except ZeroDivisionError:
        continue
    boot.append(kb)
boot.sort()
lo, hi = boot[int(0.025 * len(boot))], boot[int(0.975 * len(boot)) - 1]

# 클래스별 κ (해당 클래스 vs 나머지)
per = {}
for c in LABELS:
    x, y = (a == c).map({True: c, False: "기타"}), (b == c).map({True: c, False: "기타"})
    po_c = (x == y).mean()
    pe_c = sum((x == v).mean() * (y == v).mean() for v in [c, "기타"])
    per[c] = ((po_c - pe_c) / (1 - pe_c)) if pe_c < 1 else float("nan")

cm = pd.crosstab(a, b).reindex(index=LABELS, columns=LABELS, fill_value=0)

dis = df[a != b].copy()
dis_out = dis[["재라벨_id", "unit_id", "place", "platform",
               "sent", "label_1차", "label_2차", "문맥", "note"]]
dis_out.to_csv(RL / "불일치.csv", index=False, encoding="utf-8-sig")

# ---------- 보고서 ----------
def band(v):
    return ("0.81~1.00 almost perfect" if v >= .81 else
            "0.61~0.80 substantial" if v >= .61 else
            "0.41~0.60 moderate" if v >= .41 else
            "0.21~0.40 fair" if v >= .21 else "0.20 이하 slight")


L = []
L.append("# 재라벨 결과 — Cohen's κ\n")
L.append(f"1차 라벨링 후 하루 이상 비우고 무작위 50문장 재라벨 (seed 20260822, 모집단 본 확정 {len(old)}문장).\n")
L.append("**같은 사람의 시점 간 재현성(intra-rater)**이다. 2인 합의도가 아니다.\n")
L.append("## 수치\n")
L.append("| 항목 | 값 |")
L.append("|---|---|")
L.append(f"| 문장 수 | {n} |")
L.append(f"| 일치 (Po) | {po:.3f} ({int(po * n)}/{n}) |")
L.append(f"| 우연 일치 기대 (Pe) | {pe:.3f} |")
L.append(f"| **Cohen's κ** | **{k:.3f}** |")
L.append(f"| 95% CI (부트스트랩 {B:,}회) | {lo:.3f} ~ {hi:.3f} |")
L.append(f"| Landis–Koch 구간 | {band(k)} |")
L.append("\n### 클래스별 κ (해당 클래스 vs 나머지)\n")
L.append("| 클래스 | κ | 1차 건수 | 2차 건수 |")
L.append("|---|---|---:|---:|")
for c in LABELS:
    L.append(f"| {c} | {per[c]:.3f} | {(a == c).sum()} | {(b == c).sum()} |")
L.append("\n## 혼동표 (행 = 1차, 열 = 2차)\n")
L.append("| 1차 / 2차 | " + " | ".join(LABELS) + " | 계 |")
L.append("|---|" + "---:|" * (len(LABELS) + 1))
for c in LABELS:
    L.append(f"| **{c}** | " + " | ".join(str(cm.loc[c, d]) for d in LABELS)
             + f" | {cm.loc[c].sum()} |")
L.append("| **계** | " + " | ".join(str(cm[d].sum()) for d in LABELS) + f" | {n} |")

L.append(f"\n## 불일치 {len(dis)}건\n")
if len(dis) == 0:
    L.append("없다.\n")
else:
    for r in dis.itertuples():
        L.append(f"### {r.재라벨_id} · `{r.unit_id}` · {r.place}({r.platform}) "
                 f"· {r.sent_no}/{r.n_sent}번째 문장")
        L.append(f"> {r.sent}\n")
        L.append(f"1차 **{r.label_1차}** → 2차 **{r.label_2차}**\n")
        ctx = str(r.문맥)
        if not ctx.startswith("("):
            L.append("문맥:\n```\n" + ctx + "\n```\n")

L.append("\n## 이 수치를 어디에 쓰는가\n")
L.append("- 검증셋이 1인 단독 라벨링이므로, 신뢰도 근거는 이 κ 하나뿐이다. 보고서 방법론에 그대로 싣는다.\n")
L.append("- **1차 라벨을 이 결과로 고치지 않는다.** 고치면 κ가 잰 대상이 사라진다.\n")
L.append("  불일치 문장에서 지침의 빈 구멍이 보이면, 지침서를 고치고 그 사실을 한계로 적는다.\n")

(RL / "재라벨_결과.md").write_text("\n".join(L), encoding="utf-8")

print(f"n={n}  Po={po:.3f}  Pe={pe:.3f}  kappa={k:.3f}  95%CI [{lo:.3f}, {hi:.3f}]  {band(k)}")
print("per-class kappa: " + "  ".join(f"{c}={per[c]:.3f}" for c in LABELS))
print(f"disagreements: {len(dis)}")
print(cm.to_string())
print(f"\n-> {RL / '재라벨_결과.md'}\n-> {RL / '불일치.csv'}")
