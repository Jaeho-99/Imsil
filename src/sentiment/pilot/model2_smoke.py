# -*- coding: utf-8 -*-
"""②번 모델 스모크 테스트 — 라벨 방향(극성) 확인

왜 필요한가.
  `daekeun-ml/koelectra-small-v3-nsmc` 의 config.json 에는 라벨 이름이 없다
  (`id2label = {"0":"0","1":"1"}`). 어느 인덱스가 긍정인지 문서에 없으므로,
  **추측하고 돌리면 전 구간 부호가 뒤집힌 결과를 성능으로 착각한다.**
  그래서 본 실행 전에 방향부터 실측한다.

무엇으로 재는가.
  **CAL 150문장만** 쓴다. CAL은 사전 등록(`docs/sentiment/사전등록_임계값.md`)에서
  임계값 결정 전용으로 떼어 둔 표본이고, 성능 보고에 쓰지 않기로 되어 있다.
  TEST 548문장은 이 스크립트가 읽지 않는다.
  방향 판정은 긍정·부정 문장만 쓴다(중립은 2분류 모델이 낼 수 없는 답이라 무의미).

출력
  output/sentiment/pilot/model2_smoke_result.txt

실행:  python src/sentiment/pilot/model2_smoke.py
"""
import sys
from pathlib import Path

import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL = "daekeun-ml/koelectra-small-v3-nsmc"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_OUT  # noqa: E402
OUT = SENT_OUT / "pilot"
OUT.mkdir(parents=True, exist_ok=True)
MAXLEN = 128
BATCH = 32

out = []


def say(s=""):
    print(s)
    out.append(str(s))


# ---------- CAL 만 읽는다 ----------
main = pd.read_csv(SENT_OUT / "labeling" / "확정" / "검증셋_본_확정.csv", encoding="utf-8-sig")
cal = main[main["split"] == "CAL"].reset_index(drop=True)
assert (main["split"] == "TEST").sum() > 0 and len(cal) == 150, f"CAL {len(cal)}행 — 분할이 어긋났다"

say(f"# ②번 모델 스모크 테스트")
say(f"모델: {MODEL}")
say(f"표본: CAL {len(cal)}문장 (TEST 는 읽지 않았다)")
say(f"CAL 라벨 분포: {cal.label.value_counts().to_dict()}")
say()

# ---------- 모델 ----------
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSequenceClassification.from_pretrained(MODEL)
model.eval()

cfg = model.config
say("## config 의 라벨 정보")
say(f"  num_labels = {cfg.num_labels}")
say(f"  id2label   = {cfg.id2label}")
say(f"  label2id   = {cfg.label2id}")
say(f"  -> 라벨 이름이 없다. 아래 실측으로 방향을 정한다." if set(map(str, cfg.id2label.values())) <= {"0", "1", "LABEL_0", "LABEL_1"}
    else "  -> 라벨 이름이 있다. 실측과 대조한다.")
say()

texts = cal["sent"].astype(str).tolist()
probs = []
with torch.no_grad():
    for i in range(0, len(texts), BATCH):
        enc = tok(texts[i:i + BATCH], truncation=True, max_length=MAXLEN,
                  padding=True, return_tensors="pt")
        logits = model(**enc).logits
        probs.append(torch.softmax(logits, dim=-1))
probs = torch.cat(probs).numpy()
cal["p_idx1"] = probs[:, 1]

# ---------- 방향 판정 ----------
pol = cal[cal.label.isin(["긍정", "부정"])].copy()
pred_idx1 = pol["p_idx1"] >= 0.5

acc_A = (pred_idx1 == (pol.label == "긍정")).mean()   # 가정 A: index 1 = 긍정
acc_B = 1 - acc_A                                      # 가정 B: index 1 = 부정

say("## 방향 판정 (CAL 의 긍정·부정 문장만, 중립 제외)")
say(f"  대상 {len(pol)}문장 (긍정 {(pol.label == '긍정').sum()} · 부정 {(pol.label == '부정').sum()})")
say(f"  가정 A — index 1 = 긍정 : 정확도 {acc_A:.3f}")
say(f"  가정 B — index 1 = 부정 : 정확도 {acc_B:.3f}")
POS_IDX = 1 if acc_A >= acc_B else 0
say(f"  **판정: index {POS_IDX} = 긍정** (정확도 {max(acc_A, acc_B):.3f})")
if max(acc_A, acc_B) < 0.7:
    say("  ⚠ 이긴 쪽조차 0.70 미만이다. 방향 문제가 아니라 모델이 이 도메인에서 안 되는 것일 수 있다.")
say()

cal["p_pos"] = cal["p_idx1"] if POS_IDX == 1 else 1 - cal["p_idx1"]

# ---------- 확신도 분포 ----------
conf = cal["p_pos"].where(cal["p_pos"] >= .5, 1 - cal["p_pos"])
say("## 확신도 분포 — 사전 등록이 예측한 '0.99 쏠림'이 실제로 일어났는가")
say(f"  max(p, 1-p) 중앙값 {conf.median():.4f} · 평균 {conf.mean():.4f} · 최소 {conf.min():.4f}")
bins = [(.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, .95), (.95, .99), (.99, 1.01)]
say("  | 확신도 구간 | 문장 | 비율 |")
say("  |---|---:|---:|")
for lo, hi in bins:
    m = ((conf >= lo) & (conf < hi)).sum()
    say(f"  | {lo:.2f} ~ {hi if hi <= 1 else 1.0:.2f} | {m} | {m / len(conf):.1%} |")
say()
for t in (0.40, 0.45, 0.49):
    band = ((cal.p_pos > t) & (cal.p_pos < 1 - t)).sum()
    say(f"  밴드 [{t:.2f}, {1 - t:.2f}] 안에 드는 문장: {band} / {len(cal)} ({band / len(cal):.1%})")
say("  -> 밴드를 최대(t=0.49)로 벌려도 이만큼밖에 못 잡는다면, 중립은 임계값으로 만들어지지 않는다.")
say()

# ---------- 라벨별 p_pos ----------
say("## 사람 라벨별 p_pos")
say("  | 사람 라벨 | 문장 | p_pos 중앙값 | 25% | 75% |")
say("  |---|---:|---:|---:|---:|")
for c in ["긍정", "중립", "부정"]:
    g = cal[cal.label == c]["p_pos"]
    say(f"  | {c} | {len(g)} | {g.median():.3f} | {g.quantile(.25):.3f} | {g.quantile(.75):.3f} |")
say("  -> 중립의 사분위가 긍정·부정과 겹칠수록, 중립 밴드는 원리적으로 만들 수 없다.")
say()

# ---------- 육안 확인용 ----------
say("## 육안 확인 — 가장 확신한 10문장 (판정된 방향 적용)")
for c, g in (("긍정 쪽", cal.nlargest(5, "p_pos")), ("부정 쪽", cal.nsmallest(5, "p_pos"))):
    say(f"  [{c}]")
    for r in g.itertuples():
        say(f"    p_pos={r.p_pos:.4f}  사람={r.label}  {str(r.sent)[:60]}")
say()

(OUT / "model2_smoke_result.txt").write_text("\n".join(out), encoding="utf-8")
print(f"-> {OUT / 'model2_smoke_result.txt'}")
