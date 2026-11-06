# -*- coding: utf-8 -*-
"""②번 방법 채점 — 공개 사전학습 모델 무학습 적용 (6단계)

전제 (전부 결과 보기 전에 고정됨)
  모델        daekeun-ml/koelectra-small-v3-nsmc   (D-1, `docs/sentiment/0001-D4-3방법-조사.md`)
  라벨 방향   index 1 = 긍정                        (`src/sentiment/pilot/model2_smoke.py` 실측)
  중립 밴드   [0.05, 0.95]                          (`docs/sentiment/사전등록_임계값.md` 결정 기록)
  주 지표     macro-F1 · 보조 부정 재현율            (2강 확정)
  선택 규칙   부정 재현율 0.50 미만 탈락 → macro-F1 최고 → 0.03 이내면 재현성 높은 쪽 (3강 사전 등록)

채점 표본 — **두 세트를 합치지 않는다.**
  TEST 본   382문장  무작위 표본. macro-F1 · 정확도 · 클래스 분포는 여기서만 낸다
  TEST 보강 166문장  구글 별점 1~3점 그물. **부정 재현율의 주 측정 도구**
  CAL 150문장은 임계값을 고르는 데 썼으므로 채점에서 뺀다.

출력
  output/sentiment/evaluation/②번_결과.md
  output/sentiment/evaluation/②번_예측.csv     문장별 p_pos · 예측 (③번과 대조할 때 쓴다)

실행:  python src/sentiment/evaluation/run_model2.py
"""
from datetime import datetime
import sys
from pathlib import Path

import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL = "daekeun-ml/koelectra-small-v3-nsmc"
POS_IDX = 1
T = 0.05                 # 사전 등록으로 고정. 이 파일에서 바꾸지 않는다
LABELS = ["긍정", "부정", "중립"]
MAXLEN, BATCH = 128, 32

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_OUT  # noqa: E402
OUT = SENT_OUT / "evaluation"
OUT.mkdir(parents=True, exist_ok=True)

main = pd.read_csv(SENT_OUT / "labeling" / "확정" / "검증셋_본_확정.csv", encoding="utf-8-sig")
aug = pd.read_csv(SENT_OUT / "labeling" / "확정" / "검증셋_보강_확정.csv", encoding="utf-8-sig")
test_main = main[main["split"] == "TEST"].reset_index(drop=True)
test_aug = aug[aug["split"] == "TEST"].reset_index(drop=True)
assert len(test_main) == 382 and len(test_aug) == 166, f"{len(test_main)} / {len(test_aug)}"

tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSequenceClassification.from_pretrained(MODEL)
model.eval()


def p_pos(texts):
    chunks = []
    with torch.no_grad():
        for i in range(0, len(texts), BATCH):
            enc = tok(texts[i:i + BATCH], truncation=True, max_length=MAXLEN,
                      padding=True, return_tensors="pt")
            chunks.append(torch.softmax(model(**enc).logits, dim=-1))
    return torch.cat(chunks).numpy()[:, POS_IDX]


def label_of(x):
    return "중립" if T <= x <= 1 - T else ("긍정" if x > 0.5 else "부정")


for d in (test_main, test_aug):
    d["p_pos"] = p_pos(d["sent"].astype(str).tolist())
    d["pred"] = d["p_pos"].map(label_of)

pd.concat([test_main, test_aug])[
    ["unit_id", "set", "review_id", "place", "platform", "sent", "label", "p_pos", "pred"]
].to_csv(OUT / "②번_예측.csv", index=False, encoding="utf-8-sig")


def scores(d):
    pred, gold = d["pred"], d["label"]
    per = {}
    for c in LABELS:
        tp = int(((pred == c) & (gold == c)).sum())
        fp = int(((pred == c) & (gold != c)).sum())
        fn = int(((pred != c) & (gold == c)).sum())
        P = tp / (tp + fp) if tp + fp else 0.0
        R = tp / (tp + fn) if tp + fn else 0.0
        F = 2 * P * R / (P + R) if P + R else 0.0
        per[c] = dict(P=P, R=R, F1=F, n_gold=int((gold == c).sum()), n_pred=int((pred == c).sum()))
    macro = sum(v["F1"] for v in per.values()) / len(LABELS)
    acc = float((pred == gold).mean())
    base = float(gold.value_counts(normalize=True).max())
    return macro, acc, base, per


def table(per, L):
    L.append("| 클래스 | 정밀도 | 재현율 | F1 | 정답 수 | 예측 수 |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for c in LABELS:
        v = per[c]
        L.append(f"| {c} | {v['P']:.3f} | {v['R']:.3f} | **{v['F1']:.3f}** | {v['n_gold']} | {v['n_pred']} |")


def confusion(d, L):
    cm = pd.crosstab(d["label"], d["pred"]).reindex(index=LABELS, columns=LABELS, fill_value=0)
    L.append("| 사람 / 모델 | " + " | ".join(LABELS) + " | 계 |")
    L.append("|---|" + "---:|" * (len(LABELS) + 1))
    for c in LABELS:
        L.append(f"| **{c}** | " + " | ".join(str(cm.loc[c, x]) for x in LABELS) + f" | {cm.loc[c].sum()} |")
    L.append("| **계** | " + " | ".join(str(cm[x].sum()) for x in LABELS) + f" | {len(d)} |")


m_macro, m_acc, m_base, m_per = scores(test_main)
a_macro, a_acc, a_base, a_per = scores(test_aug)

L = []
L.append("# ②번 방법 결과 — 공개 사전학습 모델 무학습 적용\n")
L.append(f"실행 {datetime.now():%Y-%m-%d %H:%M} · 모델 `{MODEL}` · 중립 밴드 `[{T}, {1 - T}]` (사전 등록)\n")
L.append("> 두 표본의 수치를 합치지 않는다. 전체 성능은 본 검증셋, 부정 재현율은 보강셋에서 읽는다.\n")

L.append(f"## 1. TEST 본 {len(test_main)}문장 — 전체 성능\n")
L.append("| 항목 | 값 |")
L.append("|---|---|")
L.append(f"| **macro-F1 (주 지표)** | **{m_macro:.3f}** |")
L.append(f"| 정확도 | {m_acc:.3f} |")
L.append(f"| 다수 클래스 기준선 | {m_base:.3f} (전부 긍정으로 찍었을 때) |")
L.append(f"| 정확도 − 기준선 | {m_acc - m_base:+.3f} |")
L.append("")
table(m_per, L)
L.append("\n### 혼동표 (행 = 사람, 열 = 모델)\n")
confusion(test_main, L)

L.append(f"\n## 2. TEST 보강 {len(test_aug)}문장 — 부정 재현율\n")
L.append("구글 별점 1~3점 리뷰로만 그물을 쳤다. **네이버는 별점이 없어 포함되지 않는다** — 구글 편향 수치다.\n")
L.append("| 항목 | 값 |")
L.append("|---|---|")
L.append(f"| **부정 재현율 (보조 지표)** | **{a_per['부정']['R']:.3f}** ({a_per['부정']['n_gold']}건 중 "
         f"{int(round(a_per['부정']['R'] * a_per['부정']['n_gold']))}건) |")
L.append(f"| 부정 정밀도 | {a_per['부정']['P']:.3f} |")
L.append(f"| 참고 · 본 검증셋에서의 부정 재현율 | {m_per['부정']['R']:.3f} ({m_per['부정']['n_gold']}건 중 "
         f"{int(round(m_per['부정']['R'] * m_per['부정']['n_gold']))}건) |")
L.append("")
table(a_per, L)
L.append("\n### 혼동표 (행 = 사람, 열 = 모델)\n")
confusion(test_aug, L)

L.append("\n## 3. 사전 등록된 선택 규칙 대조\n")
r = a_per["부정"]["R"]
L.append("| 규칙 | 결과 |")
L.append("|---|---|")
L.append(f"| 1순위 · 부정 재현율 0.50 미만이면 탈락 | 보강셋 {r:.3f} → **{'통과' if r >= .50 else '탈락'}** |")
L.append(f"| 2순위 · macro-F1 최고 | {m_macro:.3f} (③번 나온 뒤 비교) |")
L.append("| 3순위 · 0.03 이내면 재현성 높은 쪽 | ③번 나온 뒤 판정 |")
if r < .50:
    L.append("\n**②번은 1순위 규칙에서 탈락했다.** 규칙대로 macro-F1을 보고 되살리지 않는다. "
             "탈락 사실 자체를 결과로 보고한다.\n")

L.append("\n## 4. 중립은 어떻게 되었나\n")
neu_pred_main = int((test_main["pred"] == "중립").sum())
L.append(f"- TEST 본에서 중립 예측 **{neu_pred_main}건** / 사람 중립 {m_per['중립']['n_gold']}건 · "
         f"중립 F1 **{m_per['중립']['F1']:.3f}**")
L.append("- 사전 등록에 미리 적어 둔 대로다: NSMC는 별점 5~8점(중립대)을 빼고 만든 데이터라 "
         "**이 모델은 중립을 학습한 적이 없다.** 임계값은 없는 능력을 사후에 흉내 내는 장치이고, "
         "여기 나온 중립 성능이 그 장치의 한계다. 버그가 아니라 예측된 결과다.\n")

(OUT / "②번_결과.md").write_text("\n".join(L), encoding="utf-8")

print(f"[TEST 본 {len(test_main)}]  macro-F1 {m_macro:.3f}  정확도 {m_acc:.3f}  기준선 {m_base:.3f}")
for c in LABELS:
    v = m_per[c]
    print(f"   {c}: P {v['P']:.3f}  R {v['R']:.3f}  F1 {v['F1']:.3f}  (정답 {v['n_gold']} / 예측 {v['n_pred']})")
print(pd.crosstab(test_main.label, test_main.pred).to_string())
print(f"\n[TEST 보강 {len(test_aug)}]  부정 재현율 {a_per['부정']['R']:.3f}  부정 정밀도 {a_per['부정']['P']:.3f}")
print(pd.crosstab(test_aug.label, test_aug.pred).to_string())
print(f"\n선택 규칙 1순위(부정 재현율 >= 0.50): {'통과' if r >= .5 else '탈락'}")
print(f"\n-> {OUT / '②번_결과.md'}")
