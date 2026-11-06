# -*- coding: utf-8 -*-
"""전수 결과 병합 + 관광지별 집계 (11단계) — STEP 3 산출물

무엇을 합치나
  사람 라벨  698문장 (370리뷰) — 검증셋. **정답이므로 이쪽을 쓴다**
  ③번 예측  4,987문장 (2,838리뷰) — 나머지 전부
  합계      5,685문장 / 3,208리뷰

`혼합` 처리 — 한 문장에 긍정·부정이 둘 다 있어 3분류로 옮길 수 없는 답
  사람은 이런 문장을 절로 쪼개 `-b` 행을 만들었다. ③번에는 쪼개지 말라고 했으므로 `혼합`이 나온다.
  자동으로 쪼갤 방법이 없으므로 **버리지도 않고 한쪽으로 몰지도 않는다.**
  대신 부정 지표를 **범위**로 낸다.
      부정 비율 하한 = 부정 / 전체
      부정 비율 상한 = (부정 + 혼합) / 전체        ← 혼합에는 부정 성분이 반드시 들어 있다
  보고서에는 두 값을 다 싣고, 관광지 순위는 하한·상한 양쪽에서 확인한다.

리뷰 단위 감성 — 1강 확정: "'혼합'은 문장→리뷰 집계에서 유도한다"
  리뷰의 문장에 긍정과 부정이 함께 있으면 그 리뷰는 혼합. 문장 라벨이 `혼합`이어도 혼합.

실행:  python src/sentiment/fullscale/merge_fullscale.py [run이름]
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_IN, SENT_OUT  # noqa: E402
OUT_DIR = SENT_OUT / "fullscale"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RUNS = SENT_IN / "fullscale" / "llm_runs"     # LLM 판정 결과 (붙여 넣은 파일)
sys.path.insert(0, str(HERE.parent / "llm_labeling"))
from check_output import load_run

RUN = sys.argv[1] if len(sys.argv) > 1 else "run1"
CATS = ["긍정", "부정", "중립", "혼합"]

# 혼합 재배분율 — `mixed_audit/estimate_mixed.py (레포에 없음)` 가 사람 판정 40건으로 만든 파일.
# 여기서 수치를 지어내지 않는다. 파일이 없으면 보정 없이 하한~상한만 낸다.
AUDIT_PATH = SENT_OUT / "mixed_audit" / "재배분율.json"
AUDIT = json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else None

# ---------- ③번 예측 ----------
pred, bad, dup, _ = load_run(RUN, base=RUNS)
src = pd.read_csv(OUT_DIR / "문장목록.csv", encoding="utf-8-sig")
assert not bad and not dup, "check_fullscale.py 를 먼저 통과시켜라"
src["label"] = src["unit_id"].map(pred).str.rstrip("?")
assert src["label"].notna().all(), f"예측 누락 {src['label'].isna().sum()}건 — 채점 중단"
src["출처"] = "③번 예측"

# ---------- 사람 라벨 ----------
hum = pd.concat([pd.read_csv(SENT_OUT / "labeling" / "확정" / f, encoding="utf-8-sig")
                 for f in ["검증셋_본_확정.csv", "검증셋_보강_확정.csv"]])
hum = hum.rename(columns={"review_id": "review_id"})[
    ["unit_id", "review_id", "place", "platform", "sent_no", "n_sent", "sent", "label"]].copy()
hum["출처"] = "사람 라벨"
assert set(hum["review_id"]) & set(src["review_id"]) == set(), "라벨 리뷰가 전수에 섞여 들어갔다"

all_ = pd.concat([hum, src], ignore_index=True)
all_.to_csv(OUT_DIR / "전수_문장라벨.csv", index=False, encoding="utf-8-sig")

# ---------- 리뷰 단위 ----------
def review_label(g):
    s = set(g)
    if "혼합" in s or ({"긍정", "부정"} <= s):
        return "혼합"
    if "긍정" in s:
        return "긍정"
    if "부정" in s:
        return "부정"
    return "중립"


rev = (all_.groupby(["review_id", "place", "platform"])["label"]
       .apply(review_label).reset_index(name="리뷰감성"))
rev.to_csv(OUT_DIR / "전수_리뷰라벨.csv", index=False, encoding="utf-8-sig")


# ---------- 관광지별 ----------
def agg(df, key, unit, mix_by_plat=None):
    t = df.pivot_table(index=key, columns=unit, aggfunc="size", fill_value=0)
    for c in CATS:
        if c not in t:
            t[c] = 0
    t = t[CATS]
    t["계"] = t.sum(axis=1)
    t["부정_하한"] = t["부정"] / t["계"]
    t["부정_상한"] = (t["부정"] + t["혼합"]) / t["계"]
    t["긍정비율"] = t["긍정"] / t["계"]

    # 보정 — 혼합을 사람 판정 구성비대로 재배분한다.
    # 이전 판의 `분할추정`(혼합 = 긍정+부정 1:1 가정)은 폐기했다. 근거였던 '사람이 쪼갠
    # 9건이 9/9 긍정+부정' 은 **사람이 쪼개기로 결정한 것만 사후에 본 것**이라 선택편향이다.
    # 올바른 대조군은 '모델이 혼합이라 한 것을 사람이 어떻게 했나' 이고, 검증셋 12건 중
    # 사람이 실제로 쪼갠 것은 1건뿐이었다. 그래서 40건을 층화 추출해 직접 판정했다.
    if AUDIT is not None and mix_by_plat is not None:
        r = AUDIT["플랫폼별_건당증가"]
        add = lambda k: sum(mix_by_plat[p] * r[p][k] for p in r if p in mix_by_plat)
        den = t["계"] + add("분모")
        t["보정_분모"] = den
        t["보정_긍정"] = (t["긍정"] + add("긍정")) / den
        t["보정_부정"] = (t["부정"] + add("부정")) / den
        t["보정_중립"] = t["중립"] / den
        return t.sort_values("보정_부정", ascending=False)
    return t.sort_values("부정_하한", ascending=False)


def mix_split(df, key):
    """key 별 · 플랫폼별 `혼합` 문장 수. 재배분율이 플랫폼마다 다르므로 필요하다."""
    m = df[df["label"] == "혼합"]
    if key == "platform":
        t = m.groupby("platform").size()
        return pd.DataFrame({p: t.where(t.index == p, 0) for p in t.index}).fillna(0)
    return (m.groupby([key, "platform"]).size().unstack(fill_value=0)
            .reindex(df[key].unique()).fillna(0))


by_place = agg(all_, "place", "label", mix_split(all_, "place"))
by_place.insert(0, "사람라벨문장", all_[all_["출처"] == "사람 라벨"].groupby("place").size().reindex(by_place.index).fillna(0).astype(int))
by_place.to_csv(OUT_DIR / "관광지별_문장감성.csv", encoding="utf-8-sig")

by_place_rev = agg(rev, "place", "리뷰감성")
by_place_rev.to_csv(OUT_DIR / "관광지별_리뷰감성.csv", encoding="utf-8-sig")

by_plat = agg(all_, "platform", "label", mix_split(all_, "platform"))

# ---------- 보고서 ----------
n_mix = int((all_["label"] == "혼합").sum())
L = []
L.append("# 전수 감성분석 결과 — 임실군 관광지 리뷰\n")
L.append(f"작성 {datetime.now():%Y-%m-%d %H:%M} · 방법 ③ LLM (D4 비교에서 채택) · 실행 `{RUN}`\n")
L.append("| 구성 | 리뷰 | 문장 | 출처 |")
L.append("|---|---:|---:|---|")
L.append(f"| 검증셋 | {hum['review_id'].nunique()} | {len(hum)} | **사람 라벨(정답)** |")
L.append(f"| 나머지 | {src['review_id'].nunique()} | {len(src)} | ③번 예측 |")
L.append(f"| **합계** | **{all_['review_id'].nunique()}** | **{len(all_)}** | |")
L.append("\n검증셋 370리뷰는 사람이 직접 매긴 라벨을 그대로 썼다 — 예측보다 정확하기 때문이다.\n")

L.append("## 이 수치를 얼마나 믿을 수 있나\n")
L.append("| 근거 | 값 |")
L.append("|---|---|")
L.append("| ③번 macro-F1 (검증 본 382문장) | **0.906~0.914** (3회 실행) |")
L.append("| 부정 재현율 (보강 166문장) | **0.82~0.91** — 단일 값이 아니라 범위 |")
L.append("| 실행 간 불일치율 | 4.20% (κ 0.936) · 긍↔부 뒤집힘 0건 |")
L.append("| 라벨 기준 자체의 재현성 | 사람 κ 0.964 (50문장, 15시간 간격 → 상한값) |")
L.append("\n**소수점 둘째 자리까지 말하지 않는다.** 관광지별 부정 비율은 경향을 보는 값이지 "
         "정밀 측정값이 아니다.\n")

L.append(f"## `혼합` {n_mix}문장 ({n_mix / len(all_):.1%}) 을 어떻게 셌나\n")
L.append("한 문장에 긍정·부정이 둘 다 있어 3분류로 옮길 수 없는 답이다. 자동으로 쪼갤 방법이 없으므로 "
         "**버리지도, 한쪽으로 몰지도 않았다.**\n")
neg = int((all_["label"] == "부정").sum())
L.append("- **하한** = 부정 / 전체 ← 혼합을 전부 비부정으로 취급")
L.append("- **상한** = (부정 + 혼합) / 전체 ← 혼합에는 부정 성분이 반드시 들어 있다\n")
if AUDIT is None:
    L.append(f"> 전체 기준: 하한 **{neg / len(all_):.1%}** · 상한 **{(neg + n_mix) / len(all_):.1%}**\n")
    L.append("⚠ `output/sentiment/mixed_audit/재배분율.json` 이 없어 보정값을 내지 않았다. "
             "재배분율을 만든 `estimate_mixed.py` 는 레포에 남아 있지 않다 — "
             "최종 결과는 267건을 사람이 전수 확정한 `output/sentiment/final/` 을 쓴다.\n")
else:
    a, ci = AUDIT["구성"], AUDIT["전체_부정비율"]
    L.append(f"- **보정** ← 267건 중 **{AUDIT['표본']}건을 층화 무작위 추출해 사람이 지침대로 직접 판정**하고, "
             "그 구성비를 267건 전체에 적용한 값\n")
    L.append(f"> 전체 기준: 하한 **{neg / len(all_):.1%}** · "
             f"**보정 {ci['점추정']:.1%} (95% CI {ci['ci_low']:.1%}~{ci['ci_high']:.1%})** · "
             f"상한 **{(neg + n_mix) / len(all_):.1%}**\n")
    L.append(f"판정 결과 267건의 구성은 **긍정 {a['긍정']:.1%} · 부정 {a['부정']:.1%} · "
             f"중립 {a['중립']:.1%} · 분할 {a['분할']:.1%}** 였다. "
             f"즉 모델이 `혼합` 이라 한 것의 다수는 **분할 대상이 아니라 지배적 입장으로 단일 판정되는 문장**이다. "
             f"분할분을 반영하면 전체 문장 수가 {len(all_):,} → {len(all_) + n_mix * AUDIT['구성']['분할']:,.0f} 가 된다. "
             f"범위 폭이 {100 * n_mix / len(all_):.1f}pp → "
             f"{100 * (ci['ci_high'] - ci['ci_low']):.1f}pp 로 줄었다.\n")
    L.append("⚠ **이전 판의 `분할추정`(혼합 = 긍정+부정 1:1 가정, 전체 19.7%)은 폐기했다.** 근거였던 "
             "'사람이 쪼갠 9건이 9/9 모두 긍정+부정' 은 **사람이 쪼개기로 결정한 것만 사후에 본 것**이라 "
             "선택편향이었다. 올바른 대조군은 '모델이 혼합이라 한 것을 사람이 어떻게 했나' 이고, "
             "검증셋 12건 중 사람이 실제로 쪼갠 것은 **1건**뿐이었다.\n")
    L.append(f"⚠ 이 보정은 **모델이 `혼합` 으로 잡아낸 {n_mix}건에 대해서만** 유효하다. 모델이 긍정·부정으로 "
             "단정해 버린 진짜 혼합 문장은 여전히 미지수다. 또한 부정 재현율 0.82~0.91 에서 오는 "
             "불확실성(부정 문장 약 110건 폭)은 이 보정으로 줄어들지 않는다 — 그쪽이 더 큰 오차원이다.\n")
    L.append(f"> 산출 근거: `output/sentiment/mixed_audit/판정_결과.md` · "
             f"재배분율 `output/sentiment/mixed_audit/재배분율.json` "
             f"(표본 {AUDIT['표본']} · 층 {AUDIT['층']} · 부트스트랩 {AUDIT['부트스트랩']:,}회 · 시드 {AUDIT['시드']})\n")
L.append("⚠ **한계로 반드시 적을 것.** 검증셋에서 `혼합` 은 2.2% 였는데 전수에서는 "
         f"{(src['label'] == '혼합').mean():.1%} 다. 검증셋은 사람이 이미 혼합 문장 9개를 절로 쪼개 둔 "
         "뒤의 표본이라 혼합이 적게 나온다. 즉 **성능을 잰 표본이 전수보다 쉬웠을 수 있다** — "
         "macro-F1 0.906 은 전수에 대해 약간 낙관적인 값일 수 있다.\n")

L.append("## 문장 단위 전체 분포\n")
d1 = all_["label"].value_counts()
L.append("| 라벨 | 문장 | 비율 |")
L.append("|---|---:|---:|")
for c in CATS:
    L.append(f"| {c} | {int(d1.get(c, 0))} | {d1.get(c, 0) / len(all_):.1%} |")

L.append("\n## 리뷰 단위 분포\n")
d2 = rev["리뷰감성"].value_counts()
L.append("| 리뷰 감성 | 리뷰 | 비율 |")
L.append("|---|---:|---:|")
for c in CATS:
    L.append(f"| {c} | {int(d2.get(c, 0))} | {d2.get(c, 0) / len(rev):.1%} |")
L.append("\n리뷰 안에 긍정 문장과 부정 문장이 함께 있으면 **혼합**이다(1강 확정: 혼합은 집계에서 유도한다).\n")

has_adj = "보정_부정" in by_place.columns

L.append("## 플랫폼별\n")
if has_adj:
    L.append("| 플랫폼 | 문장 | 혼합 | 보정 긍정 | 보정 중립 | **보정 부정** | 부정 하한~상한 |")
    L.append("|---|---:|---:|---:|---:|---:|---|")
    for p, r in by_plat.iterrows():
        L.append(f"| {p} | {int(r['계'])} | {int(r['혼합'])} | {r['보정_긍정']:.1%} | "
                 f"{r['보정_중립']:.1%} | **{r['보정_부정']:.1%}** | "
                 f"{r['부정_하한']:.1%} ~ {r['부정_상한']:.1%} |")
    L.append("\n플랫폼마다 재배분율이 다르므로 관광지별 보정에도 그 관광지의 플랫폼 구성이 반영된다.\n")
else:
    L.append("| 플랫폼 | 문장 | 긍정 | 부정 | 중립 | 혼합 | 부정 하한~상한 |")
    L.append("|---|---:|---:|---:|---:|---:|---|")
    for p, r in by_plat.iterrows():
        L.append(f"| {p} | {int(r['계'])} | {int(r['긍정'])} | {int(r['부정'])} | {int(r['중립'])} | "
                 f"{int(r['혼합'])} | {r['부정_하한']:.1%} ~ {r['부정_상한']:.1%} |")

L.append(f"\n## 관광지별 — 문장 단위 ({'보정 부정' if has_adj else '부정 하한'} 높은 순)\n")
if has_adj:
    g_share = (all_[all_["platform"] == "구글"].groupby("place").size()
               .reindex(by_place.index).fillna(0) / by_place["계"])
    L.append("| 관광지 | 문장 | 긍정 | 부정 | 중립 | 혼합 | **보정 부정** | 보정 긍정 | 부정 하한~상한 | 구글 비중 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---|---:|")
    for p, r in by_place.iterrows():
        L.append(f"| {p} | {int(r['계'])} | {int(r['긍정'])} | {int(r['부정'])} | {int(r['중립'])} | "
                 f"{int(r['혼합'])} | **{r['보정_부정']:.1%}** | {r['보정_긍정']:.1%} | "
                 f"{r['부정_하한']:.1%} ~ {r['부정_상한']:.1%} | {g_share[p]:.0%} |")
else:
    L.append("| 관광지 | 문장 | 긍정 | 부정 | 중립 | 혼합 | 부정 하한~상한 | 긍정비율 |")
    L.append("|---|---:|---:|---:|---:|---:|---|---:|")
    for p, r in by_place.iterrows():
        L.append(f"| {p} | {int(r['계'])} | {int(r['긍정'])} | {int(r['부정'])} | {int(r['중립'])} | "
                 f"{int(r['혼합'])} | {r['부정_하한']:.1%} ~ {r['부정_상한']:.1%} | {r['긍정비율']:.1%} |")
L.append("\n⚠ **문장 수가 적은 관광지의 비율은 읽지 않는다.** 30문장 미만이면 한두 건에 순위가 뒤집힌다.\n")
small = by_place[by_place["계"] < 30]
if len(small):
    L.append(f"30문장 미만: {', '.join(f'{p}({int(n)})' for p, n in small['계'].items())}\n")

L.append("## 산출 파일\n")
L.append("| 파일 | 내용 |")
L.append("|---|---|")
L.append("| `전수_문장라벨.csv` | 문장 5,685개 · 라벨 · 출처(사람/③번) |")
L.append("| `전수_리뷰라벨.csv` | 리뷰 3,208개 · 리뷰 단위 감성 |")
L.append("| `관광지별_문장감성.csv` | 관광지 × 라벨 교차표 + 부정 하한/상한/보정 |")
L.append("| `관광지별_리뷰감성.csv` | 관광지 × 리뷰감성 교차표 |")
if AUDIT is not None:
    L.append("| `input/sentiment/mixed_audit/혼합40_판정용.xlsx` | 사람이 판정한 40문장 원본 |")
    L.append("| `output/sentiment/mixed_audit/판정_결과.md` | 혼합 재배분 추정 상세 + 신뢰구간 |")
    L.append("| `output/sentiment/mixed_audit/재배분율.json` | 이 문서의 보정값이 읽어 온 파일 |")

(OUT_DIR / "전수_결과.md").write_text("\n".join(L), encoding="utf-8")

print(f"문장 {len(all_)} (사람 {len(hum)} + ③번 {len(src)}) · 리뷰 {all_['review_id'].nunique()}")
print(f"문장 분포: " + " · ".join(f"{c} {int(d1.get(c, 0))}({d1.get(c, 0) / len(all_):.1%})" for c in CATS))
print(f"리뷰 분포: " + " · ".join(f"{c} {int(d2.get(c, 0))}({d2.get(c, 0) / len(rev):.1%})" for c in CATS))
print()
cols = ["계", "부정", "혼합", "부정_하한", "부정_상한"]
if "보정_부정" in by_place.columns:
    cols.insert(4, "보정_부정")
    print(f"혼합 보정: {AUDIT_PATH.name} 적용 (표본 {AUDIT['표본']}건) / "
          f"전체 부정 {AUDIT['전체_부정비율']['점추정']:.1%} "
          f"(95% CI {AUDIT['전체_부정비율']['ci_low']:.1%}~{AUDIT['전체_부정비율']['ci_high']:.1%})")
else:
    print(f"혼합 보정 없음 — {AUDIT_PATH} 가 없다 (만드는 estimate_mixed.py 는 이 레포에 없다)")
print(by_place[cols].head(12).to_string(float_format=lambda x: f"{x:.1%}"))
print(f"\n-> {OUT_DIR / '전수_결과.md'}")
