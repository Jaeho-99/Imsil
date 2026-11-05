# -*- coding: utf-8 -*-
"""`혼합` 267건 사람 확정 결과를 전수 데이터에 반영한다 — 새 폴더에만 쓴다

무엇을 하려는 것인가
  전수 5,685문장 중 267건은 모델이 `혼합` 이라 답한 자리였다. 사람 지침에 없는 범주라
  관광지별 부정 비율 같은 지표를 하나의 수로 낼 수 없었고, 그동안은 40건 층화 표본으로
  **추정**해 왔다(`output/sentiment/mixed_audit/재배분율.json`).

  이제 267건 전부 사람이 판정했다. 추정을 걷어내고 실제 라벨로 바꾼다.
      227건  input/sentiment/mixed_final_review/혼합227_최종검토용.xlsx  (검토상태 기준으로 최종 판정 도출)
       40건  output/sentiment/mixed_final_review/혼합40_최종.csv

  `분할` 108건은 기존 사람 분할과 같은 구조로 `-b` 행을 만든다.
      FULL-01067        조각1  (원래 unit_id 유지)
      FULL-01067-b      조각2  (새 행)
  그 리뷰 안에서 `sent_no` 를 1..n 으로 다시 매기고 `n_sent` 도 새 값으로 바꾼다.
  기존 사람 분할 9건(`MAIN-0094` / `MAIN-0094-b` 등)이 쓰던 방식 그대로다.

  결과: 5,685 -> 5,793행. 문장 단위에서 `혼합` 이 사라진다.

무엇이 달라지나 — 읽는 사람이 알아야 할 것
  - 문장 라벨은 긍정 / 부정 / 중립 3범주가 된다. `부정_하한`·`부정_상한` 이라는 범위 표기와
    `보정_*` 열이 없어진다. 부정 비율이 **하나의 수**로 나온다.
  - 리뷰 단위의 `혼합` 은 그대로 남는다. 그건 모델의 회피가 아니라 한 리뷰 안에 긍정
    문장과 부정 문장이 같이 있다는 뜻이고, 애초에 문장->리뷰 집계에서 유도하는 값이다.
  - `output/sentiment/mixed_audit/재배분율.json` 의 추정치(전체 부정비율 18.18%)는 **더 이상 쓰지 않는다.**
    추정하려던 대상을 전건으로 세었기 때문이다.
  - 267건의 `출처` 는 `사람 재검토` 로 바꾼다. 값이 어디서 왔는지 파일만 보고 알 수 있어야 한다.

입력 — 읽기만 한다. `output/sentiment/fullscale/` 과 `input/` 은 절대 쓰지 않는다.
  output/sentiment/fullscale/전수_문장라벨.csv          5,685행
  혼합227_최종검토용.xlsx                 `검토` 시트
  혼합40_최종.csv                         finalize_40.py 산출

출력 — output/sentiment/final/ 에만 쓴다.
  전수_문장라벨_최종.csv        5,793행
  전수_리뷰라벨_최종.csv
  관광지별_문장감성_최종.csv
  관광지별_리뷰감성_최종.csv
  전수_결과_최종.md
  변경내역.csv                  267건이 무엇에서 무엇으로 바뀌었는지 · 새로 생긴 -b 행

실행:  python src/sentiment/mixed_final_review/merge_final.py
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_IN, SENT_OUT, SENT_FINAL  # noqa: E402
FS = SENT_OUT / "fullscale"
OUT = SENT_FINAL

SRC_FULL = FS / "전수_문장라벨.csv"
SRC_227 = SENT_IN / "mixed_final_review" / "혼합227_최종검토용.xlsx"   # 사람이 확정한 검토표
SRC_40 = SENT_OUT / "mixed_final_review" / "혼합40_최종.csv"

EXPECT_MIX = 267
SENT_CATS = ["긍정", "부정", "중립"]
REV_CATS = ["긍정", "부정", "중립", "혼합"]
ORIGIN = "사람 재검토"


def md_table(t, index_name):
    """DataFrame 을 마크다운 표로. tabulate 의존성을 만들지 않는다."""
    cols = list(t.columns)
    out = ["| " + " | ".join([index_name] + [str(c) for c in cols]) + " |",
           "|" + "---|" * (len(cols) + 1)]
    for idx, row in t.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            # 비율 열만 백분율로, 나머지는 건수로 출력한다.
            # iterrows() 는 행을 공통 dtype 으로 올려 버리므로 dtype 으로 판별하면
            # 건수까지 float 가 되어 백분율로 찍힌다 (1,479 -> 147900.0%).
            cells.append(f"{v:.1%}" if "비율" in str(c) else f"{int(round(float(v))):,}")
        out.append("| " + " | ".join([str(idx)] + cells) + " |")
    return "\n".join(out)


def fail(msg):
    sys.exit(f"[중단] {msg}")


def squash(s):
    return "".join(str(s).split())


def decisions():
    """267건의 최종 판정을 {unit_id: (판정, 조각1, 라벨1, 조각2, 라벨2, 출처설명)} 로 모은다."""
    x = pd.read_excel(SRC_227, sheet_name="검토", dtype=str).fillna("")
    d = {}
    for r in x.itertuples():
        if r.사람_판정:
            who, src = "사람", "사람 판정"
        elif r.검토상태 == "확정" and r.GPT_판정:
            who, src = "GPT", "GPT 초벌 확정"
        else:
            fail(f"{r.검토_id}: 최종 판정이 정해지지 않았다 (검토상태={r.검토상태!r}).")
        v = getattr(r, f"{who}_판정")
        p1 = getattr(r, f"{who}_분할1"); l1 = getattr(r, f"{who}_분할1_라벨")
        p2 = getattr(r, f"{who}_분할2"); l2 = getattr(r, f"{who}_분할2_라벨")
        d[r.unit_id] = (v, p1, l1, p2, l2, src)

    f = pd.read_csv(SRC_40, encoding="utf-8-sig", dtype=str).fillna("")
    for r in f.itertuples():
        if r.unit_id in d:
            fail(f"{r.unit_id}: 227건과 40건 양쪽에 있다.")
        src = "사람 판정(40건 표본)" + (" · 판정 변경" if r.판정변경_사유 else "")
        d[r.unit_id] = (r.최종_판정, r.분할1, r.분할1_라벨, r.분할2, r.분할2_라벨, src)
    return d


def main():
    full = pd.read_csv(SRC_FULL, encoding="utf-8-sig", dtype=str)
    full["순번"] = full["sent_no"].astype(int)
    mix = full[full["label"] == "혼합"]
    if len(mix) != EXPECT_MIX:
        fail(f"`혼합` 이 {len(mix)}건이다 — {EXPECT_MIX}건을 기대했다.")

    dec = decisions()
    if set(dec) != set(mix["unit_id"]):
        fail(f"판정 목록과 `혼합` 행이 다르다. 판정만 {len(set(dec) - set(mix.unit_id))}건 · "
             f"혼합만 {len(set(mix.unit_id) - set(dec))}건")
    if len(dec) != EXPECT_MIX:
        fail(f"판정이 {len(dec)}건이다.")

    # ---------- 행 만들기 ----------
    rows, log = [], []
    for r in full.itertuples():
        base = {"unit_id": r.unit_id, "review_id": r.review_id, "place": r.place,
                "platform": r.platform, "sent_no": r.순번, "n_sent": int(r.n_sent),
                "sent": r.sent, "label": r.label, "출처": r.출처}
        if r.unit_id not in dec:
            rows.append(base)
            continue

        v, p1, l1, p2, l2, src = dec[r.unit_id]
        if v == "분할":
            if not p1 or not p2:
                fail(f"{r.unit_id}: 분할인데 조각이 비었다.")
            if squash(p1 + p2) != squash(r.sent):
                fail(f"{r.unit_id}: 조각을 이어 붙여도 원문이 아니다.")
            if l1 not in SENT_CATS or l2 not in SENT_CATS:
                fail(f"{r.unit_id}: 조각 라벨이 이상하다 ({l1} / {l2}).")
            nid = f"{r.unit_id}-b"
            if nid in set(full["unit_id"]):
                fail(f"{nid}: 이미 있는 unit_id 다.")
            rows.append({**base, "sent": p1, "label": l1, "출처": ORIGIN})
            rows.append({**base, "unit_id": nid, "sent": p2, "label": l2, "출처": ORIGIN})
            log.append({"unit_id": r.unit_id, "place": r.place, "platform": r.platform,
                        "원문": r.sent, "이전_label": "혼합", "최종_판정": v,
                        "새_label": l1, "새_행_unit_id": nid, "새_행_label": l2,
                        "조각1": p1, "조각2": p2, "판정_출처": src})
        else:
            if v not in SENT_CATS:
                fail(f"{r.unit_id}: 판정 {v!r} 이 허용 범주가 아니다.")
            if p1 or p2:
                fail(f"{r.unit_id}: 분할이 아닌데 조각이 채워져 있다.")
            rows.append({**base, "label": v, "출처": ORIGIN})
            log.append({"unit_id": r.unit_id, "place": r.place, "platform": r.platform,
                        "원문": r.sent, "이전_label": "혼합", "최종_판정": v,
                        "새_label": v, "새_행_unit_id": "", "새_행_label": "",
                        "조각1": "", "조각2": "", "판정_출처": src})

    d = pd.DataFrame(rows)

    # ---------- 리뷰 안에서 sent_no 다시 매기기 ----------
    # -b 행은 원래 행 바로 뒤에 오게 정렬한다. 그 뒤 1..n 으로 번호를 다시 준다.
    d["_ord"] = d["unit_id"].str.endswith("-b").astype(int)
    d = d.sort_values(["review_id", "sent_no", "_ord"], kind="stable").drop(columns="_ord")
    d["sent_no"] = d.groupby("review_id").cumcount() + 1
    d["n_sent"] = d.groupby("review_id")["sent_no"].transform("max")
    d = d.reset_index(drop=True)

    # ---------- 검산 ----------
    n_split = sum(1 for v in dec.values() if v[0] == "분할")
    if len(d) != len(full) + n_split:
        fail(f"행 수가 {len(d)} 다 — {len(full) + n_split} 를 기대했다.")
    if (d["label"] == "혼합").any():
        fail("문장 라벨에 `혼합` 이 남아 있다.")
    if d["unit_id"].duplicated().any():
        fail("unit_id 가 중복된다.")
    if not set(d["label"]) <= set(SENT_CATS):
        fail(f"허용되지 않은 라벨: {set(d['label']) - set(SENT_CATS)}")
    for rid, g in d.groupby("review_id"):
        if sorted(g["sent_no"]) != list(range(1, len(g) + 1)):
            fail(f"리뷰 {rid} 의 sent_no 가 1..n 연속이 아니다.")
    # 손대지 않은 행은 라벨이 그대로여야 한다
    old = dict(zip(full["unit_id"], full["label"]))
    for r in d.itertuples():
        if r.unit_id in old and r.unit_id not in dec and r.label != old[r.unit_id]:
            fail(f"{r.unit_id}: 건드리지 않아야 할 행의 라벨이 바뀌었다.")

    OUT.mkdir(exist_ok=True)
    d[["unit_id", "review_id", "place", "platform", "sent_no", "n_sent",
       "sent", "label", "출처"]].to_csv(
        OUT / "전수_문장라벨_최종.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(log).to_csv(OUT / "변경내역.csv", index=False, encoding="utf-8-sig")

    # ---------- 리뷰 단위 ----------
    def review_label(g):
        s = set(g)
        if {"긍정", "부정"} <= s:
            return "혼합"
        if "긍정" in s:
            return "긍정"
        if "부정" in s:
            return "부정"
        return "중립"

    rev = (d.groupby(["review_id", "place", "platform"])["label"]
           .apply(review_label).reset_index(name="리뷰감성"))
    rev.to_csv(OUT / "전수_리뷰라벨_최종.csv", index=False, encoding="utf-8-sig")

    # ---------- 관광지별 ----------
    def agg(df, key, unit, cats):
        t = df.pivot_table(index=key, columns=unit, aggfunc="size", fill_value=0)
        for c in cats:
            if c not in t:
                t[c] = 0
        t = t[cats]
        t["계"] = t.sum(axis=1)
        t["부정비율"] = t["부정"] / t["계"]
        t["긍정비율"] = t["긍정"] / t["계"]
        return t.sort_values("부정비율", ascending=False)

    by_place = agg(d, "place", "label", SENT_CATS)
    by_place.insert(0, "사람확정문장",
                    d[d["출처"] == ORIGIN].groupby("place").size()
                    .reindex(by_place.index).fillna(0).astype(int))
    by_place.to_csv(OUT / "관광지별_문장감성_최종.csv", encoding="utf-8-sig")
    by_place_rev = agg(rev, "place", "리뷰감성", REV_CATS)
    by_place_rev.to_csv(OUT / "관광지별_리뷰감성_최종.csv", encoding="utf-8-sig")
    by_plat = agg(d, "platform", "label", SENT_CATS)

    # ---------- 보고서 ----------
    lg = pd.DataFrame(log)
    old_neg = (full["label"] == "부정").sum() / len(full)
    old_neg_hi = ((full["label"].isin(["부정", "혼합"])).sum()) / len(full)
    new_neg = (d["label"] == "부정").sum() / len(d)

    L = [f"# 전수 감성분석 결과 (최종) — 임실군 관광지 리뷰\n",
         f"작성 {datetime.now():%Y-%m-%d %H:%M}\n",
         "모델이 `혼합` 이라 답한 267문장을 **연구자가 전건 확인**하여 라벨을 확정한 판이다. "
         "문장 단위에서 `혼합` 이 사라졌고, 부정 비율이 범위가 아니라 하나의 수로 나온다.\n",
         "## 무엇이 달라졌나\n",
         "| | 이전 (`fullscale/`) | 최종 (이 폴더) |",
         "|---|---|---|",
         f"| 문장 수 | {len(full):,} | **{len(d):,}** (분할 {n_split}건의 `-b` 행 추가) |",
         f"| 문장 라벨 | 긍정·부정·중립·**혼합** | 긍정·부정·중립 |",
         f"| 부정 비율 | {old_neg:.1%} ~ {old_neg_hi:.1%} (범위) | **{new_neg:.1%}** |",
         f"| 근거 | 40건 표본으로 추정 | 267건 전건 확인 (LLM 초벌 검토 197 · 연구자 직접 판정 30 · 앞선 표본 40) |\n",
         "이전 단계에서 40건 표본으로 추정하던 값(전체 부정비율 18.18% [17.58, 18.78])은 "
         "**더 이상 쓰지 않는다.** 추정하려던 대상을 전건으로 세었다.\n",
         "## 267건이 어떻게 갈렸나\n",
         "| 최종 판정 | 건수 |", "|---|---:|"]
    for c, n in lg["최종_판정"].value_counts().items():
        L.append(f"| {c} | {n} |")
    L.append(f"| **합계** | **{len(lg)}** |\n")
    L.append("판정 출처\n")
    L.append("| 출처 | 건수 |")
    L.append("|---|---:|")
    for c, n in lg["판정_출처"].value_counts().items():
        L.append(f"| {c} | {n} |")
    L.append("")
    L.append("## 전체 문장 감성\n")
    L.append("| 라벨 | 문장 | 비율 |")
    L.append("|---|---:|---:|")
    for c in SENT_CATS:
        n = int((d["label"] == c).sum())
        L.append(f"| {c} | {n:,} | {n/len(d):.1%} |")
    L.append(f"| **합계** | **{len(d):,}** | |\n")
    L.append("## 플랫폼별 문장 감성\n")
    L.append(md_table(by_plat, "플랫폼") + "\n")
    L.append("## 관광지별 문장 감성 — 부정 비율 높은 순\n")
    L.append(md_table(by_place, "관광지") + "\n")
    L.append("## 관광지별 리뷰 감성\n")
    L.append("리뷰의 `혼합` 은 한 리뷰 안에 긍정 문장과 부정 문장이 같이 있다는 뜻이다. "
             "문장 단위의 `혼합` 과 다르다 — 이건 집계에서 유도하는 값이라 그대로 남는다.\n")
    L.append(md_table(by_place_rev, "관광지") + "\n")
    L.append("## 파일\n")
    L.append("| 파일 | 내용 |")
    L.append("|---|---|")
    L.append(f"| `전수_문장라벨_최종.csv` | 문장 {len(d):,}개 · 라벨 · 출처 |")
    L.append(f"| `전수_리뷰라벨_최종.csv` | 리뷰 {rev['review_id'].nunique():,}개 · 리뷰 단위 감성 |")
    L.append("| `관광지별_문장감성_최종.csv` | 관광지 × 라벨 교차표 + 부정/긍정 비율 |")
    L.append("| `관광지별_리뷰감성_최종.csv` | 관광지 × 리뷰감성 교차표 |")
    L.append("| `변경내역.csv` | 267건이 무엇에서 무엇으로 바뀌었는지 · 새로 생긴 `-b` 행 |")
    L.append("\n산출: `src/sentiment/mixed_final_review/merge_final.py` · "
             "원자료 `output/sentiment/fullscale/전수_문장라벨.csv`(수정하지 않음)")
    (OUT / "전수_결과_최종.md").write_text("\n".join(L), encoding="utf-8")

    print(f"{len(full):,}행 -> {len(d):,}행 (분할 {n_split}건의 -b 행 추가)")
    print(f"  문장 `혼합` {EXPECT_MIX} -> 0")
    print(f"  267건 판정: {lg['최종_판정'].value_counts().to_dict()}")
    print(f"  부정 비율: {old_neg:.1%}~{old_neg_hi:.1%} (범위) -> {new_neg:.1%} (확정)")
    print(f"  리뷰 {rev['review_id'].nunique():,}개 · 리뷰감성 {rev['리뷰감성'].value_counts().to_dict()}")
    print(f"\n출력 -> {OUT.name}/")
    for p in sorted(OUT.iterdir()):
        print(f"  {p.name}")
    print("\ninput/ 과 output/sentiment/fullscale/ 은 건드리지 않았다.")


if __name__ == "__main__":
    main()
