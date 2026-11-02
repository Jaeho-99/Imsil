# -*- coding: utf-8 -*-
"""③번 재현성 — run1 vs run2 (8단계)

무엇을 재는가
  1. **라벨 불일치율** — 두 실행이 같은 문장에 다른 라벨을 준 비율
  2. **실행 간 κ** — 사람의 재현성 κ(0.964)와 같은 자로 잰 값. 나란히 놓아야 비교가 된다
  3. **지표 변동** — run1/run2 각각으로 채점했을 때 macro-F1 이 얼마나 흔들리는가.
     불일치율보다 이쪽이 결론에 직접 걸린다. 라벨이 흔들려도 결론이 안 흔들리면 그것도 결과다
  4. 불일치가 **어느 경계에 몰리는가**

왜 이걸 보고하나
  웹 UI 실행이라 temperature 를 고정할 수 없었다(3강 재현성 요건 미충족).
  변동성의 증거가 이 수치들뿐이다. D4 선택은 2순위(macro-F1 격차 0.330)에서 이미 끝났으므로
  **이 수치는 선택 근거가 아니다.** 방법의 성질로 보고한다.

실행:  ../../.venv/Scripts/python.exe evaluation/재현성.py
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "llm-labeling"))
from check_output import load_run, expected_ids

LABELS = ["긍정", "부정", "중립"]
ALL4 = LABELS + ["혼합"]

# 인자: [A실행] [B실행].  기본은 run1 vs run2(재현성). 묶음 크기 실험은 run1 vs run_150.
RUN_A = sys.argv[1] if len(sys.argv) > 1 else "run1"
RUN_B = sys.argv[2] if len(sys.argv) > 2 else "run2"
IS_REPRO = (RUN_A, RUN_B) == ("run1", "run2")

r1, _, _, _ = load_run(RUN_A)
r2, _, _, _ = load_run(RUN_B)
exp = expected_ids()
assert len(r1) == len(r2) == len(exp) == 548

main = pd.read_csv(ROOT / "labeling" / "확정" / "검증셋_본_확정.csv", encoding="utf-8-sig")
aug = pd.read_csv(ROOT / "labeling" / "확정" / "검증셋_보강_확정.csv", encoding="utf-8-sig")
d = pd.concat([main, aug])
d = d[d["split"] == "TEST"].reset_index(drop=True)
d["p1"] = d["unit_id"].map(r1).str.rstrip("?")
d["p2"] = d["unit_id"].map(r2).str.rstrip("?")
d["q1"] = d["unit_id"].map(r1).str.endswith("?")
d["q2"] = d["unit_id"].map(r2).str.endswith("?")


def scores(df, col, drop_mixed=False):
    x = df[df[col] != "혼합"] if drop_mixed else df
    pred, g = x[col], x["label"]
    per = {}
    for c in LABELS:
        tp = int(((pred == c) & (g == c)).sum())
        fp = int(((pred == c) & (g != c)).sum())
        fn = int(((pred != c) & (g == c)).sum())
        P = tp / (tp + fp) if tp + fp else 0.0
        R = tp / (tp + fn) if tp + fn else 0.0
        per[c] = 2 * P * R / (P + R) if P + R else 0.0
        if c == "부정":
            rec_neg = R
    return sum(per.values()) / 3, float((pred == g).mean()), per, rec_neg


def kappa(x, y, cats):
    po = float((x == y).mean())
    pe = sum(float((x == c).mean()) * float((y == c).mean()) for c in cats)
    return (po - pe) / (1 - pe), po, pe


tm, ta = d[d["set"] == "MAIN"], d[d["set"] == "BOOST"]
m1, a1, f1_1, _ = scores(tm, "p1")
m2, a2, f1_2, _ = scores(tm, "p2")
_, _, _, rn1 = scores(ta, "p1")
_, _, _, rn2 = scores(ta, "p2")

k, po, pe = kappa(d["p1"], d["p2"], ALL4)
dis = d[d["p1"] != d["p2"]].copy()

pairs = (dis.groupby(["p1", "p2"]).size().sort_values(ascending=False))
neu_involved = int(((dis["p1"] == "중립") | (dis["p2"] == "중립")).sum())
mix_involved = int(((dis["p1"] == "혼합") | (dis["p2"] == "혼합")).sum())
flip = int((((dis["p1"] == "긍정") & (dis["p2"] == "부정")) |
            ((dis["p1"] == "부정") & (dis["p2"] == "긍정"))).sum())
q_any = d[(d["q1"]) | (d["q2"])]
q_dis = int((q_any["p1"] != q_any["p2"]).sum())

L = []
L.append("# ③번 재현성 — run1 vs run2\n")
L.append(f"작성 {datetime.now():%Y-%m-%d %H:%M} · 프롬프트 `v1` 동결 · 독립된 두 대화 · 동일 12묶음·동일 순서\n")
L.append("웹 UI 실행이라 temperature 를 고정할 수 없었다. **이 문서가 변동성의 유일한 증거다.**\n")

L.append("## 1. 라벨 불일치\n")
L.append("| 항목 | 값 |")
L.append("|---|---|")
L.append(f"| 문장 | {len(d)} |")
L.append(f"| **불일치** | **{len(dis)} / {len(d)} = {len(dis) / len(d):.2%}** |")
L.append(f"| 일치 (Po) | {po:.3f} |")
L.append(f"| **실행 간 κ** | **{k:.3f}** |")
L.append(f"| 참고 · 사람의 재현성 κ | 0.964 (50문장, 15.0시간 간격, 상한값) |")
L.append("\n같은 자로 재면 **사람 0.964 · LLM 두 실행 " + f"{k:.3f}**. "
         "사람 쪽은 50문장 표본이고 LLM 쪽은 548문장이므로 오차 폭이 다르다 — 순위를 매기는 데 쓰지 말고, "
         "두 값이 같은 자릿수라는 사실만 말한다.\n")

L.append("## 2. 지표는 얼마나 흔들리는가 — **결론에 직접 걸리는 것**\n")
L.append(f"| 지표 | 표본 | {RUN_A} | {RUN_B} | 폭 | 참고 · ②번 |")
L.append("|---|---|---:|---:|---:|---:|")
L.append(f"| **macro-F1** | 본 382 | {m1:.3f} | {m2:.3f} | {abs(m1 - m2):.3f} | 0.576 |")
L.append(f"| 정확도 | 본 382 | {a1:.3f} | {a2:.3f} | {abs(a1 - a2):.3f} | 0.668 |")
L.append(f"| 부정 재현율 | 보강 166 | {rn1:.3f} | {rn2:.3f} | {abs(rn1 - rn2):.3f} | 0.753 |")
L.append("")
L.append("### 클래스별 F1 (본 382)\n")
L.append(f"| 클래스 | {RUN_A} | {RUN_B} | 폭 |")
L.append("|---|---:|---:|---:|")
for c in LABELS:
    L.append(f"| {c} | {f1_1[c]:.3f} | {f1_2[c]:.3f} | {abs(f1_1[c] - f1_2[c]):.3f} |")
worst = min(m1, m2)
L.append(f"\n**라벨은 {len(dis) / len(d):.1%} 흔들렸지만 macro-F1 은 {abs(m1 - m2):.3f} 밖에 안 움직인다.** "
         f"둘 중 나쁜 쪽({worst:.3f})을 써도 ②번(0.576)과의 격차는 {worst - 0.576:.3f} 로, "
         f"사전 등록 임계 0.03 의 열 배가 넘는다. **D4 결론은 어느 실행을 쓰든 같다.**\n")

L.append("### ⚠ 그런데 보조 지표는 그렇지 않다 — 숨기지 말 것\n")
L.append(f"부정 재현율이 **{rn1:.3f} → {rn2:.3f} ({abs(rn1 - rn2):.3f})** 움직였다. "
         f"macro-F1 의 폭({abs(m1 - m2):.3f})의 **{abs(rn1 - rn2) / max(abs(m1 - m2), 1e-9):.0f}배**다.")
L.append(f"이유는 표본 크기다 — 보강셋의 부정은 {int((ta['label'] == '부정').sum())}문장뿐이라 "
         f"몇 문장만 중립·혼합 쪽으로 밀려도 비율이 크게 흔들린다.\n")
L.append("두 가지를 함께 말해야 정확하다.")
L.append(f"- 사전 등록 1순위 규칙(부정 재현율 ≥ 0.50)은 **두 실행 모두 통과**한다({min(rn1, rn2):.3f} ≥ 0.50). 선택은 안 바뀐다.")
L.append(f"- 그러나 **\"③번의 부정 재현율은 {max(rn1, rn2):.3f}\" 라고 한 숫자로 말하면 안 된다.** "
         f"실측 범위는 {min(rn1, rn2):.3f}~{max(rn1, rn2):.3f} 이고, 2회 실행으로는 이 범위조차 정확히 모른다.")
L.append("- 주 지표를 macro-F1 로 정한 2강 결정이 여기서 한 번 더 값을 한다. "
         "표본이 작은 클래스의 재현율은 그 자체로 불안정하다.\n")

L.append("## 3. 불일치는 어디에 몰렸나\n")
L.append("| 유형 | 건수 | 비율(불일치 중) |")
L.append("|---|---:|---:|")
L.append(f"| 중립이 한쪽에 낀 경우 | {neu_involved} | {neu_involved / len(dis):.0%} |")
L.append(f"| 혼합이 한쪽에 낀 경우 | {mix_involved} | {mix_involved / len(dis):.0%} |")
L.append(f"| **긍정 ↔ 부정 정반대** | **{flip}** | {flip / len(dis):.0%} |")
L.append("\n의미: 흔들림이 **경계(중립·혼합)에 몰려 있고 극성이 뒤집히는 일은 거의 없다.** "
         "'GPT가 매번 다른 소리를 한다'가 아니라 '애매한 문장에서만 흔들린다'로 읽는다.\n")
L.append("### 라벨 쌍별\n")
L.append(f"| {RUN_A} → {RUN_B} | 건수 |")
L.append("|---|---:|")
for (x, y), n in pairs.items():
    L.append(f"| {x} → {y} | {n} |")

L.append(f"\n### `?`(확신없음) 표시와의 관계\n")
L.append(f"어느 한쪽이라도 `?` 를 붙인 문장 {len(q_any)}건 중 **{q_dis}건이 실제로 불일치**했다 "
         f"({q_dis / len(q_any):.0%}). 전체 불일치율 {len(dis) / len(d):.1%} 과 견주면, "
         f"`?` 는 흔들릴 문장을 {'어느 정도 짚어낸다' if q_dis / len(q_any) > len(dis) / len(d) else '잘 짚어내지 못한다'}.\n")

L.append(f"## 4. 불일치 {len(dis)}건 전체\n")
L.append(f"| unit_id | 사람 | {RUN_A} | {RUN_B} | 문장 |")
L.append("|---|---|---|---|---|")
for r in dis.itertuples():
    t1 = r.p1 + ("?" if r.q1 else "")
    t2 = r.p2 + ("?" if r.q2 else "")
    L.append(f"| `{r.unit_id}` | {r.label} | {t1} | {t2} | {str(r.sent)[:55]} |")

q1s = set(d.loc[d["q1"], "unit_id"])
q2s = set(d.loc[d["q2"], "unit_id"])
m1s = set(d.loc[d["p1"] == "혼합", "unit_id"])
m2s = set(d.loc[d["p2"] == "혼합", "unit_id"])
exact = float(((d.p1 == d.p2) & (d.q1 == d.q2)).mean())

if IS_REPRO:
    L.append("\n## 한계 — 메모리·개인화를 끄지 않았다\n")
    L.append("run1·run2 모두 **새 대화에서 실행했으나 임시 채팅이 아니었고 메모리·개인화를 끄지 않았다.** "
             "따라서 run2 가 run1 의 맥락을 일부 참조했을 가능성을 배제할 수 없다.\n")
    L.append("**편향의 방향은 한쪽으로 정해져 있다.** 맥락이 새면 두 실행이 더 비슷해지므로 일치율은 "
             f"높아지고 불일치율은 낮아진다. 즉 **{len(dis) / len(d):.2%} 는 실제 변동성의 하한**이다. "
             "실제 변동성은 이보다 크면 컸지 작지 않다. 이 방향성 때문에 결론은 흔들리지 않는다 — "
             "변동성을 과소평가했을 뿐, ③번의 우위(macro-F1 격차 0.330)를 부풀리는 쪽이 아니다.\n")
    L.append("### 실제로 샜다고 보기 어려운 근거\n")
    L.append("| 관찰 | 값 | 베껴 왔다면 |")
    L.append("|---|---|---|")
    L.append(f"| 라벨 완전 일치(`?` 포함) | {exact:.2%} | 100% 에 가까워야 |")
    L.append(f"| **`?` 를 붙인 문장이 겹치는 수** | **{len(q1s & q2s)}건** "
             f"(run1 {len(q1s)} · run2 {len(q2s)}) | 대부분 겹쳐야 |")
    L.append(f"| `혼합` 판정 | 공통 {len(m1s & m2s)} · run1만 {len(m1s - m2s)} · "
             f"run2만 {len(m2s - m1s)} | 완전히 같아야 |")
    L.append("\n특히 **`?` 가 한 건도 겹치지 않았다.** 확신 없음 표시는 문장 내용보다 그때그때의 판단에 "
             "좌우되는 흔적인데, 두 실행이 완전히 다른 문장에 붙였다. 앞 실행의 답을 참조했다면 나오기 어려운 결과다.\n")
    L.append("> 보고서에는 이렇게 쓴다: 두 실행은 각각 새 대화에서 수행했으나 임시 채팅이 아니었으므로 "
             "맥락 유출 가능성을 완전히 배제하지 못한다. 다만 유출이 있었다면 불일치율이 낮아지는 방향이므로 "
             f"보고한 {len(dis) / len(d):.2%} 는 변동성의 하한으로 해석한다.\n")

    L.append("\n## 보고서에 쓸 문구\n")
    L.append("> ③번 방법은 웹 UI로 실행하여 temperature 를 고정할 수 없었다. 따라서 재현성은 프롬프트를 동결한 채 "
             f"독립된 두 대화에서 각각 실행하고 두 결과의 불일치율로 보고한다: "
             f"**{len(dis)}/{len(d)} = {len(dis) / len(d):.2%}** "
             f"(실행 간 κ {k:.3f}). 불일치의 {neu_involved / len(dis):.0%} 는 중립 경계에서 발생했고 "
             f"긍정·부정이 뒤집힌 사례는 {flip}건이었다. 두 실행으로 각각 채점한 macro-F1 은 "
             f"{min(m1, m2):.3f}~{max(m1, m2):.3f} 로 방법 선택 결론은 어느 실행을 쓰든 동일하나, "
             f"보강셋의 부정 재현율은 {min(rn1, rn2):.3f}~{max(rn1, rn2):.3f} 로 변동 폭이 컸다"
             f"(부정 {int((ta['label'] == '부정').sum())}문장의 소표본에서 측정한 값이기 때문이다). "
             f"따라서 부정 재현율은 단일 값이 아니라 범위로 해석한다.\n")
else:
    BASE_DIS, BASE_MACRO = 0.0420, 0.002      # run1 vs run2 기준선
    L.append("\n## 판정 — 조건 변경의 영향인가, 그냥 변동성인가\n")
    L.append("| 항목 | 이번 비교 | 재현성 기준선 (run1 vs run2) | 읽기 |")
    L.append("|---|---:|---:|---|")
    L.append(f"| 불일치율 | {len(dis) / len(d):.2%} | {BASE_DIS:.2%} | "
             f"{'기준선보다 큼 — 조건 영향 의심' if len(dis) / len(d) > BASE_DIS * 1.5 else '기준선 범위 — 영향 단정 못 함'} |")
    L.append(f"| macro-F1 폭 | {abs(m1 - m2):.3f} | {BASE_MACRO:.3f} | "
             f"{'기준선보다 큼' if abs(m1 - m2) > BASE_MACRO * 3 else '기준선 범위'} |")
    L.append(f"| 낮은 쪽 macro-F1 | {min(m1, m2):.3f} | 0.906 | "
             f"{'②번(0.576) 대비 우위 유지' if min(m1, m2) - 0.576 > 0.03 else '⚠ 우위 흔들림'} |")
    L.append("\n**판단 기준.** 두 실행의 차이가 재현성 기준선 안에 들면 조건 변경의 영향이 있다고 "
             "말할 수 없다 — 같은 조건으로 두 번 돌려도 그만큼은 흔들리기 때문이다. "
             "기준선을 뚜렷이 넘을 때만 조건 탓으로 돌린다.\n")
    L.append("**행 누락은 별개다.** `check_output.py` 가 548/548 을 확인하지 못하면 "
             "성능과 무관하게 그 묶음 크기는 쓰지 않는다.\n")

name = "③번_재현성.md" if IS_REPRO else f"③번_조건비교_{RUN_A}_vs_{RUN_B}.md"
(HERE / name).write_text("\n".join(L), encoding="utf-8")

print(f"불일치 {len(dis)}/{len(d)} = {len(dis) / len(d):.2%}   실행 간 κ {k:.3f} (Po {po:.3f})")
print(f"macro-F1  {RUN_A} {m1:.3f}  {RUN_B} {m2:.3f}  폭 {abs(m1 - m2):.3f}   (②번 0.576)")
print(f"정확도    {RUN_A} {a1:.3f}  {RUN_B} {a2:.3f}")
print(f"부정재현  {RUN_A} {rn1:.3f}  {RUN_B} {rn2:.3f}  (보강 166)")
print(f"중립 낀 불일치 {neu_involved}/{len(dis)} · 혼합 낀 {mix_involved} · 긍↔부 뒤집힘 {flip}")
print(f"? 붙은 {len(q_any)}건 중 불일치 {q_dis}건")
print(f"\n-> {HERE / name}")
