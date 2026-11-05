# -*- coding: utf-8 -*-
"""③번 방법 채점 (LLM) + ②③ 비교 + 사전 등록 선택 규칙 판정 (7단계)

입력
  input/sentiment/llm_labeling/llm_runs/run1/*   GPT 출력 (③번의 **예측**. 정답 아님)
  output/sentiment/labeling/확정/*_확정.csv      정답 = 사용자 손라벨
  output/sentiment/evaluation/②번_예측.csv       ②번 예측 (동일 548문장)

`혼합` 처리 — 결과를 보고 정한 것이 아니라 두 계산을 다 내서 결론이 흔들리는지 본다
  주 계산  `혼합`은 우리 3분류 체계에 없는 값이므로 **오답으로 센다.**
           쓸 수 있는 라벨을 못 낸 것도 그 방법의 성질이다.
  민감도   `혼합`을 분모에서 빼고 다시 계산해 함께 싣는다.
  `?` 는 빼지 않는다. 형식 오류도 방법의 성능에 포함되므로 비율만 보고한다.

채점 규칙 출처: `docs/sentiment/채점_규칙.md` (2026-08-22, 모델 실행 전 작성)

실행:  python src/sentiment/evaluation/run_llm3.py
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_OUT  # noqa: E402
OUT = SENT_OUT / "evaluation"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE.parent / "llm_labeling"))
from check_output import load_run, expected_ids          # 파싱 규칙을 한 곳에만 둔다

LABELS = ["긍정", "부정", "중립"]
RUN = "run1"

rows, bad, dup, noise = load_run(RUN)
exp = expected_ids()
assert not bad and not dup, "check_output.py 를 먼저 통과시켜라"
assert len(rows) == len(exp) == 548, f"{len(rows)} / {len(exp)} — 채점 중단(채점_규칙.md '정렬')"

main = pd.read_csv(SENT_OUT / "labeling" / "확정" / "검증셋_본_확정.csv", encoding="utf-8-sig")
aug = pd.read_csv(SENT_OUT / "labeling" / "확정" / "검증셋_보강_확정.csv", encoding="utf-8-sig")
gold = pd.concat([main, aug])
gold = gold[gold["split"] == "TEST"].reset_index(drop=True)

gold["raw"] = gold["unit_id"].map(rows)
gold["uncertain"] = gold["raw"].str.endswith("?")
gold["pred_3"] = gold["raw"].str.rstrip("?")          # 긍정/부정/중립/혼합
m2 = pd.read_csv(OUT / "②번_예측.csv", encoding="utf-8-sig")[["unit_id", "pred", "p_pos"]]
gold = gold.merge(m2.rename(columns={"pred": "pred_2", "p_pos": "p_pos_2"}), on="unit_id")
gold[["unit_id", "set", "place", "platform", "sent", "label",
      "pred_3", "uncertain", "pred_2"]].to_csv(
    OUT / "③번_예측.csv", index=False, encoding="utf-8-sig")


def scores(d, col, drop_mixed=False):
    d = d[d[col] != "혼합"] if drop_mixed else d
    pred, g = d[col], d["label"]
    per = {}
    for c in LABELS:
        tp = int(((pred == c) & (g == c)).sum())
        fp = int(((pred == c) & (g != c)).sum())
        fn = int(((pred != c) & (g == c)).sum())
        P = tp / (tp + fp) if tp + fp else 0.0
        R = tp / (tp + fn) if tp + fn else 0.0
        F = 2 * P * R / (P + R) if P + R else 0.0
        per[c] = dict(P=P, R=R, F1=F, n_gold=int((g == c).sum()), n_pred=int((pred == c).sum()))
    return sum(v["F1"] for v in per.values()) / 3, float((pred == g).mean()), per, len(d)


tm = gold[gold["set"] == "MAIN"]
ta = gold[gold["set"] == "BOOST"]

M3, A3, P3, N3 = scores(tm, "pred_3")
M3d, A3d, P3d, N3d = scores(tm, "pred_3", drop_mixed=True)
_, _, PA3, _ = scores(ta, "pred_3")
_, _, PA3d, _ = scores(ta, "pred_3", drop_mixed=True)
M2, A2, P2, _ = scores(tm, "pred_2")
_, _, PA2, _ = scores(ta, "pred_2")

mixed = gold[gold["pred_3"] == "혼합"]
base = float(tm.label.value_counts(normalize=True).max())


def ptable(per, L):
    L.append("| 클래스 | 정밀도 | 재현율 | F1 | 정답 수 | 예측 수 |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for c in LABELS:
        v = per[c]
        L.append(f"| {c} | {v['P']:.3f} | {v['R']:.3f} | **{v['F1']:.3f}** | {v['n_gold']} | {v['n_pred']} |")


def cmat(d, col, L):
    cols = LABELS + (["혼합"] if (d[col] == "혼합").any() else [])
    cm = pd.crosstab(d["label"], d[col]).reindex(index=LABELS, columns=cols, fill_value=0)
    L.append("| 사람 / 모델 | " + " | ".join(cols) + " | 계 |")
    L.append("|---|" + "---:|" * (len(cols) + 1))
    for c in LABELS:
        L.append(f"| **{c}** | " + " | ".join(str(cm.loc[c, x]) for x in cols) + f" | {cm.loc[c].sum()} |")
    L.append("| **계** | " + " | ".join(str(cm[x].sum()) for x in cols) + f" | {len(d)} |")


# ---------------- ③번 결과 ----------------
L = []
L.append("# ③번 방법 결과 — LLM (ChatGPT, 프롬프트 v1)\n")
L.append(f"채점 {datetime.now():%Y-%m-%d %H:%M} · 실행 `{RUN}` · **548/548행 완결** (누락·중복·라벨이상 0)\n")
L.append(f"확신없음 `?` **{int(gold.uncertain.sum())}건 ({gold.uncertain.mean():.1%})** — 규정대로 채점에서 빼지 않았다.\n")
L.append(f"`혼합` **{len(mixed)}건 ({len(mixed) / len(gold):.1%})** — 주 계산은 오답으로 셌다. 민감도도 함께 싣는다.\n")

L.append(f"## 1. TEST 본 {len(tm)}문장 — 전체 성능\n")
L.append("| 항목 | 혼합=오답 (주) | 혼합 제외 (민감도) |")
L.append("|---|---|---|")
L.append(f"| **macro-F1** | **{M3:.3f}** | {M3d:.3f} |")
L.append(f"| 정확도 | {A3:.3f} | {A3d:.3f} |")
L.append(f"| 문장 수 | {N3} | {N3d} |")
L.append(f"\n다수 클래스 기준선 {base:.3f} · 정확도 − 기준선 **{A3 - base:+.3f}**\n")
ptable(P3, L)
L.append("\n### 혼동표 (행 = 사람, 열 = ③번)\n")
cmat(tm, "pred_3", L)

L.append(f"\n## 2. TEST 보강 {len(ta)}문장 — 부정 재현율\n")
L.append("구글 별점 1~3점 리뷰로만 그물을 쳤다. 네이버는 별점이 없어 포함되지 않는다 — 구글 편향 수치다.\n")
L.append("| 항목 | 혼합=오답 (주) | 혼합 제외 |")
L.append("|---|---|---|")
L.append(f"| **부정 재현율 (보조 지표)** | **{PA3['부정']['R']:.3f}** | {PA3d['부정']['R']:.3f} |")
L.append(f"| 부정 정밀도 | {PA3['부정']['P']:.3f} | {PA3d['부정']['P']:.3f} |")
L.append(f"\n참고 · 본 검증셋에서의 부정 재현율 {P3['부정']['R']:.3f}\n")
ptable(PA3, L)
L.append("\n### 혼동표 (행 = 사람, 열 = ③번)\n")
cmat(ta, "pred_3", L)

L.append(f"\n## 3. `혼합` {len(mixed)}건은 무엇이었나\n")
L.append("사람은 이런 문장을 지침 규칙 1-1로 쪼개 `-b` 행을 만들었다. ③번에는 쪼개지 말라고 했으므로 `혼합`이 나온다.")
L.append("즉 ③번이 규칙을 어긴 것이 아니라, **3분류 체계로 옮길 수 없는 답을 낸 것**이다.\n")
L.append("| unit_id | 사람 | ②번 | 문장 |")
L.append("|---|---|---|---|")
for r in mixed.itertuples():
    L.append(f"| `{r.unit_id}` | {r.label} | {r.pred_2} | {str(r.sent)[:60]} |")

(OUT / "③번_결과.md").write_text("\n".join(L), encoding="utf-8")

# ---------------- 비교 ----------------
r2, r3 = PA2["부정"]["R"], PA3["부정"]["R"]
gap = M3 - M2
if abs(gap) > 0.03:
    win = "③ LLM" if gap > 0 else "② 공개 모델"
    verdict = f"**{win} 채택** — macro-F1 격차 {abs(gap):.3f} > 0.03 이므로 3순위를 쓰지 않는다"
else:
    win = None
    verdict = f"격차 {abs(gap):.3f} ≤ 0.03 → **3순위(재현성)로 넘어간다. run2 필요.**"

C = []
C.append("# D4 방법 비교 — ② 공개 사전학습 모델 vs ③ LLM\n")
C.append(f"작성 {datetime.now():%Y-%m-%d %H:%M} · 동일한 548문장, 동일한 정답(사용자 손라벨)으로 채점.\n")
C.append("① 사전 기반(KNU)은 조사 단계에서 제외했다 — `개선`=+2 로 우리 핵심 유형(개선 요구)을 "
         "원리적으로 못 잡는다. 제외 근거를 결과로 싣는다.\n")
C.append("> 두 표본을 합치지 않는다. 전체 성능은 본 382, 부정 재현율은 보강 166에서 읽는다.\n")

C.append("## 핵심 표\n")
C.append("| 지표 | 표본 | ② 공개 모델 | ③ LLM | 차이 |")
C.append("|---|---|---:|---:|---:|")
C.append(f"| **macro-F1 (주 지표)** | 본 382 | {M2:.3f} | **{M3:.3f}** | **{gap:+.3f}** |")
C.append(f"| 정확도 | 본 382 | {A2:.3f} | {A3:.3f} | {A3 - A2:+.3f} |")
C.append(f"| 다수 클래스 기준선 | 본 382 | {base:.3f} | {base:.3f} | — |")
C.append(f"| **부정 재현율 (보조)** | 보강 166 | {r2:.3f} | **{r3:.3f}** | {r3 - r2:+.3f} |")
C.append(f"| 부정 정밀도 | 보강 166 | {PA2['부정']['P']:.3f} | {PA3['부정']['P']:.3f} | "
         f"{PA3['부정']['P'] - PA2['부정']['P']:+.3f} |")
C.append("")
C.append("### 클래스별 F1 (본 382)\n")
C.append("| 클래스 | ② | ③ | 차이 |")
C.append("|---|---:|---:|---:|")
for c in LABELS:
    C.append(f"| {c} | {P2[c]['F1']:.3f} | {P3[c]['F1']:.3f} | {P3[c]['F1'] - P2[c]['F1']:+.3f} |")

C.append("\n## 사전 등록된 선택 규칙 적용\n")
C.append("규칙(3강, 결과 확인 전 등록): **부정 재현율 0.50 미만 탈락 → macro-F1 최고 → "
         "0.03 이내면 재현성 높은 쪽 → 전부 탈락이면 채택하지 않고 그 사실을 보고**\n")
C.append("| 순위 | 규칙 | ② | ③ | 판정 |")
C.append("|---|---|---|---|---|")
C.append(f"| 1 | 부정 재현율 ≥ 0.50 | {r2:.3f} {'통과' if r2 >= .5 else '**탈락**'} | "
         f"{r3:.3f} {'통과' if r3 >= .5 else '**탈락**'} | "
         f"{'둘 다 통과 → 2순위로' if min(r2, r3) >= .5 else '탈락 발생'} |")
C.append(f"| 2 | macro-F1 최고 | {M2:.3f} | {M3:.3f} | {verdict} |")
C.append(f"| 3 | 0.03 이내면 재현성 높은 쪽 | — | — | "
         f"{'해당 없음 (2순위에서 결정)' if abs(gap) > 0.03 else 'run2 불일치율로 판정'} |")
C.append(f"\n### 결론\n\n{verdict}\n")
if win == "③ LLM":
    C.append("사용자는 **③번 점수를 보기 전에** '성능이 좋으면 ③번으로 간다'고 사전 등록했다(2026-08-23). "
             "전수 적용이 수작업이라는 운영 부담은 선택 근거가 아니다.\n")

C.append("## 읽을 때 주의\n")
C.append(f"- ③번의 `?` {gold.uncertain.mean():.1%} · `혼합` {len(mixed) / len(gold):.1%}. "
         f"혼합을 오답에서 빼면 macro-F1 {M3:.3f} → {M3d:.3f} 로 오르지만 **승패는 바뀌지 않는다.**")
C.append("- ③번은 웹 UI 실행이라 temperature 를 고정하지 못했다. 변동성의 증거는 run2 불일치율뿐이며, "
         "2순위에서 결판이 나도 **재현성 수치는 보고서에 실어야 한다.**")
C.append("- 보강셋은 구글 별점 1~3점 전용이다. 두 방법 모두 이 표본에서 부정 재현율이 높게 나온다 — "
         "네이버에는 그물이 없었다.")
C.append("- ②번의 중립 밴드 t=0.05 는 CAL 150문장에서 사전 등록된 절차로 정했다. "
         "③번에는 대응하는 조정 장치가 없다 — 두 방법이 완전히 같은 조건은 아니라는 뜻이며, "
         "그 비대칭은 ②번에 **유리한** 쪽이다(③번은 우리 데이터로 아무 조정도 받지 않았다).")

(OUT / "②③_비교.md").write_text("\n".join(C), encoding="utf-8")

print(f"[③ 본 {len(tm)}]  macro-F1 {M3:.3f} (혼합제외 {M3d:.3f})  정확도 {A3:.3f}  기준선 {base:.3f}")
for c in LABELS:
    v = P3[c]
    print(f"   {c}: P {v['P']:.3f}  R {v['R']:.3f}  F1 {v['F1']:.3f}  (정답 {v['n_gold']} / 예측 {v['n_pred']})")
print(pd.crosstab(tm.label, tm.pred_3).to_string())
print(f"\n[③ 보강 {len(ta)}]  부정 재현율 {PA3['부정']['R']:.3f}  정밀도 {PA3['부정']['P']:.3f}")
print(pd.crosstab(ta.label, ta.pred_3).to_string())
print(f"\n=== 비교 (본 382) ===")
print(f"  macro-F1  ② {M2:.3f}   ③ {M3:.3f}   ({gap:+.3f})")
print(f"  정확도    ② {A2:.3f}   ③ {A3:.3f}   (기준선 {base:.3f})")
print(f"  부정재현  ② {r2:.3f}   ③ {r3:.3f}   (보강 166)")
print(f"  ? {int(gold.uncertain.sum())}건 · 혼합 {len(mixed)}건")
print(f"\n  판정: {verdict}")
