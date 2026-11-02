# -*- coding: utf-8 -*-
"""②번 중립 임계값 t 결정 — 사전 등록 절차 그대로 실행 (5단계)

사전 등록: `사전등록_임계값.md` (등록 2026-08-21, 성능 수치 확인 전)
  규칙 1. ②번 모델을 **CAL 150문장에만** 돌린다
  규칙 2. 밴드 [t, 1-t] 를 중립으로 한다 (0 < t < 0.5)
  규칙 3. t 를 0.01 간격으로 훑어 **CAL macro-F1 최대**인 값을 채택.
          동률이면 **t 가 작은 쪽**(밴드가 좁은 쪽)
  규칙 5. 이후 t 를 바꾸지 않는다. TEST 를 본 뒤의 변경은 금지

이 스크립트는 TEST 를 읽지 않는다. 읽으면 규칙 1 위반이다.

방향: `pilot/model2_smoke.py` 실측으로 index 1 = 긍정 확정 (CAL 극성 124문장 정확도 0.879)

출력
  calibration/임계값_결정결과.md   결정된 t · macro-F1 곡선(부록용) · 혼동표
  calibration/CAL_예측.csv         CAL 문장별 p_pos (재현용)

실행:  ../../.venv/Scripts/python.exe calibration/decide_threshold.py
"""
from datetime import datetime
from pathlib import Path

import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL = "daekeun-ml/koelectra-small-v3-nsmc"
POS_IDX = 1          # 스모크 테스트 실측. 추측 아님
LABELS = ["긍정", "부정", "중립"]
MAXLEN, BATCH = 128, 32

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

main = pd.read_csv(ROOT / "labeling" / "확정" / "검증셋_본_확정.csv", encoding="utf-8-sig")
cal = main[main["split"] == "CAL"].reset_index(drop=True)
assert len(cal) == 150, f"CAL {len(cal)}행"

tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSequenceClassification.from_pretrained(MODEL)
model.eval()

texts = cal["sent"].astype(str).tolist()
chunks = []
with torch.no_grad():
    for i in range(0, len(texts), BATCH):
        enc = tok(texts[i:i + BATCH], truncation=True, max_length=MAXLEN,
                  padding=True, return_tensors="pt")
        chunks.append(torch.softmax(model(**enc).logits, dim=-1))
p = torch.cat(chunks).numpy()
cal["p_pos"] = p[:, POS_IDX]
cal[["unit_id", "place", "platform", "sent", "label", "p_pos"]].to_csv(
    HERE / "CAL_예측.csv", index=False, encoding="utf-8-sig")


def predict(t):
    return cal["p_pos"].map(lambda x: "중립" if t <= x <= 1 - t else ("긍정" if x > 0.5 else "부정"))


def scores(pred, gold):
    per = {}
    for c in LABELS:
        tp = ((pred == c) & (gold == c)).sum()
        fp = ((pred == c) & (gold != c)).sum()
        fn = ((pred != c) & (gold == c)).sum()
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per[c] = dict(P=prec, R=rec, F1=f1, n_gold=int((gold == c).sum()),
                      n_pred=int((pred == c).sum()))
    macro = sum(v["F1"] for v in per.values()) / len(LABELS)
    return macro, (pred == gold).mean(), per


gold = cal["label"]
rows = []
for i in range(1, 50):
    t = i / 100
    pred = predict(t)
    macro, acc, per = scores(pred, gold)
    rows.append(dict(t=t, macro=macro, acc=acc,
                     n_neu=int((pred == "중립").sum()),
                     f1_pos=per["긍정"]["F1"], f1_neg=per["부정"]["F1"],
                     f1_neu=per["중립"]["F1"], rec_neg=per["부정"]["R"]))
curve = pd.DataFrame(rows)

best = curve["macro"].max()
ties = curve[curve["macro"] >= best - 1e-12]
T = float(ties["t"].min())          # 규칙 3: 동률이면 t 작은 쪽
pred = predict(T)
macro, acc, per = scores(pred, gold)
cm = pd.crosstab(gold, pred).reindex(index=LABELS, columns=LABELS, fill_value=0)

stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
L = []
L.append("# 중립 임계값 t 결정 결과\n")
L.append(f"실행 {stamp} · 모델 `{MODEL}` · 표본 **CAL {len(cal)}문장** · TEST 미열람\n")
L.append(f"방향은 `pilot/model2_smoke.py` 실측: **index {POS_IDX} = 긍정**\n")
L.append("## 결정\n")
L.append("| 항목 | 값 |")
L.append("|---|---|")
L.append(f"| **채택된 t** | **{T:.2f}** — 중립 밴드 `[{T:.2f}, {1 - T:.2f}]` |")
L.append(f"| 동률 t 개수 | {len(ties)} ({', '.join(f'{x:.2f}' for x in ties['t'])}) — 규칙 3에 따라 최솟값 채택 |")
L.append(f"| CAL macro-F1 | {macro:.3f} |")
L.append(f"| CAL 정확도 | {acc:.3f} |")
L.append(f"| CAL 중립 예측 수 | {int((pred == '중립').sum())} / {len(cal)} (사람 중립 {int((gold == '중립').sum())}) |")
L.append("\n**이 수치는 성능이 아니다.** CAL은 임계값을 고르는 데 쓴 표본이므로 보고서 본문에 싣지 않는다.\n")

L.append("## 채택된 t 에서의 CAL 클래스별 (부록용)\n")
L.append("| 클래스 | 정밀도 | 재현율 | F1 | 정답 수 | 예측 수 |")
L.append("|---|---:|---:|---:|---:|---:|")
for c in LABELS:
    v = per[c]
    L.append(f"| {c} | {v['P']:.3f} | {v['R']:.3f} | {v['F1']:.3f} | {v['n_gold']} | {v['n_pred']} |")

L.append("\n### 혼동표 (행 = 사람, 열 = 모델)\n")
L.append("| 사람 / 모델 | " + " | ".join(LABELS) + " | 계 |")
L.append("|---|" + "---:|" * (len(LABELS) + 1))
for c in LABELS:
    L.append(f"| **{c}** | " + " | ".join(str(cm.loc[c, d]) for d in LABELS) + f" | {cm.loc[c].sum()} |")
L.append("| **계** | " + " | ".join(str(cm[d].sum()) for d in LABELS) + f" | {len(cal)} |")

L.append("\n## 임계값별 곡선 — **부록 전용**\n")
L.append("본문에 실으면 '제일 좋은 값을 고른 것 아니냐'로 읽힌다. 사전 등록 '보고 방식' 참조.\n")
L.append("| t | 밴드 | macro-F1 | 정확도 | 중립예측 | F1 긍정 | F1 부정 | F1 중립 | 재현율 부정 |")
L.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|")
for r in curve.itertuples():
    mark = " **←채택**" if abs(r.t - T) < 1e-9 else ""
    L.append(f"| {r.t:.2f}{mark} | [{r.t:.2f}, {1 - r.t:.2f}] | {r.macro:.3f} | {r.acc:.3f} | "
             f"{r.n_neu} | {r.f1_pos:.3f} | {r.f1_neg:.3f} | {r.f1_neu:.3f} | {r.rec_neg:.3f} |")

(HERE / "임계값_결정결과.md").write_text("\n".join(L), encoding="utf-8")

print(f"채택 t = {T:.2f}  (동률 {len(ties)}개)  CAL macro-F1 {macro:.3f}  정확도 {acc:.3f}")
print(f"중립 예측 {int((pred == '중립').sum())} / {len(cal)}  (사람 중립 {int((gold == '중립').sum())})")
print(curve.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
print(f"\n-> {HERE / '임계값_결정결과.md'}\n-> {HERE / 'CAL_예측.csv'}")
