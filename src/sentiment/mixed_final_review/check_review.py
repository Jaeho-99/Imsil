# -*- coding: utf-8 -*-
"""`혼합227_최종검토용.xlsx` 의 진행 상황과 정합성을 점검한다 — 읽기 전용

무엇을 하려는 것인가
  227건을 사람이 채우는 동안, 그리고 다 채운 뒤에 "이 파일을 병합해도 되는가" 를 본다.
  아무것도 쓰지 않는다. 병합도 하지 않는다. 화면에 보고만 한다.

최종 라벨이 어떻게 정해지는가 — `검토상태` 가 기준이다
  사람이 GPT 초벌에 동의할 때마다 같은 값을 227번 다시 타이핑하게 하면,
  특히 분할 건의 조각 원문을 옮겨 적다가 틀린다(GPT 조각은 이미 원문과 일치함이 검증돼 있다).
  그래서 **동의하면 `검토상태` 만 `확정` 으로 두고 `사람_*` 은 비워 둔다.**

      검토상태   사람_판정    최종 라벨
      ────────────────────────────────────────────────────────────
      확정       비움         GPT_판정 (분할이면 GPT_분할1/2 와 그 라벨)
      확정       채움         사람_판정 — 단 GPT_판정 과 같아야 한다. 다르면 `수정` 이다
      수정       채움(필수)   사람_판정 (분할이면 사람_분할1/2 도 채운다)
      보류       채움(필수)   사람_판정 — 잠정값. 전부 끝낸 뒤 다시 본다
      미검토     —            아직 정해지지 않았다

  `확정` 은 "읽고 나서 동의했다" 는 뜻이다. 안 읽은 행은 `미검토` 로 남겨 둔다.
  둘을 구분할 수 있어야 나중에 몇 건을 실제로 사람이 봤는지 말할 수 있다.

무엇을 보는가
  1. 진행률 — 몇 건이 정해졌고 보류가 몇 건인가
  2. 범주 위반 — `혼합`·`애매`·`모름` 처럼 허용되지 않은 값이 들어갔는가
  3. 검토상태 정합성 — 위 표의 규칙을 어긴 행이 있는가
  4. 분할 정합성 — 분할인데 조각이 비었는가 / 조각을 이어 붙이면 대상 문장이 되는가
  5. 대상·문맥 훼손 — unit_id·원문·이전/다음 문장이 스냅샷과 그대로인가
  6. 문맥 규칙 — 전수 데이터로 문맥을 다시 계산해 227행을 대조한다
  7. 변경 추적 — 사람이 GPT 초벌을 어디서 몇 건 뒤집었는가 (혼동표)

실행:  python src/sentiment/mixed_final_review/check_review.py [xlsx경로]
  기본은 사람이 확정한 input/sentiment/mixed_final_review/혼합227_최종검토용.xlsx (merge_final.py 가 읽는 파일).
  채우는 중에는 작업본 output/sentiment/mixed_final_review/혼합227_최종검토용.xlsx 를 경로로 준다.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_IN, SENT_OUT  # noqa: E402
XLSX = (Path(sys.argv[1]) if len(sys.argv) > 1 else
        SENT_IN / "mixed_final_review" / "혼합227_최종검토용.xlsx")     # 기본: 사람이 확정한 검토표
BASE_CSV = SENT_IN / "mixed_final_review" / "혼합227_대상.csv"
FULL_CSV = SENT_OUT / "fullscale" / "전수_문장라벨.csv"

CTX_COLS = ["이전_문장", "다음_문장"]
CAT4 = {"긍정", "부정", "중립", "분할"}
CAT3 = {"긍정", "부정", "중립"}
STATUS = {"미검토", "확정", "수정", "보류"}
DECIDED = {"확정", "수정", "보류"}


def squash(s):
    return "".join(str(s).split())


def final_of(r):
    """행 하나의 최종 판정과 조각을 돌려준다. 아직 안 정해졌으면 판정이 빈 문자열."""
    if r["사람_판정"]:
        who = "사람"
    elif r["검토상태"] == "확정" and r["GPT_판정"]:
        who = "GPT"
    else:
        return "", "", "", "", "", ""
    return (r[f"{who}_판정"], r[f"{who}_분할1"], r[f"{who}_분할1_라벨"],
            r[f"{who}_분할2"], r[f"{who}_분할2_라벨"], who)


def main():
    if not XLSX.exists():
        sys.exit("혼합227_최종검토용.xlsx 가 없다. build_final_review.py 를 먼저 실행한다.")
    df = pd.read_excel(XLSX, sheet_name="검토", dtype=str).fillna("")
    base = pd.read_csv(BASE_CSV, encoding="utf-8-sig", dtype=str).fillna("")
    problems = 0

    fin = df.apply(final_of, axis=1, result_type="expand")
    fin.columns = ["최종_판정", "최종_분할1", "최종_분할1_라벨",
                   "최종_분할2", "최종_분할2_라벨", "출처"]
    d = pd.concat([df, fin], axis=1)

    print(f"== 대상 {len(df)}행 ==")

    # 1. 진행률
    done = (d["최종_판정"] != "").sum()
    print(f"\n[진행] 최종 판정이 정해진 행 {done}/{len(df)}건 "
          f"({done / len(df):.0%}) · 남은 {len(df) - done}건")
    print(f"       검토상태 {df['검토상태'].value_counts().to_dict()}")
    if done:
        print(f"       최종 라벨 출처 {d.loc[d['출처'] != '', '출처'].value_counts().to_dict()}"
              "  (GPT = 사람이 확정만 누른 행)")
        print(f"       최종 구성 {d.loc[d['최종_판정'] != '', '최종_판정'].value_counts().to_dict()}")
    hold = df.loc[df["검토상태"] == "보류", "검토_id"].tolist()
    if hold:
        print(f"       보류 {len(hold)}건: {hold[:15]}")

    # 2. 범주 위반
    for col, allowed in (("GPT_판정", CAT4), ("사람_판정", CAT4),
                         ("GPT_분할1_라벨", CAT3), ("GPT_분할2_라벨", CAT3),
                         ("사람_분할1_라벨", CAT3), ("사람_분할2_라벨", CAT3),
                         ("검토상태", STATUS)):
        bad = df.loc[(df[col] != "") & ~df[col].isin(allowed), ["검토_id", col]]
        if len(bad):
            problems += len(bad)
            print(f"\n[위반] {col} 에 허용되지 않은 값 {len(bad)}건")
            print(bad.head(10).to_string(index=False))

    # 3. 검토상태 정합성
    need = d.loc[d["검토상태"].isin(["수정", "보류"]) & (d["사람_판정"] == ""),
                 "검토_id"].tolist()
    if need:
        problems += len(need)
        print(f"\n[상태] `수정`·`보류` 인데 사람_판정 이 비었다 {len(need)}건: {need[:10]}")
        print("       동의해서 그대로 둔 것이면 `확정` 으로 바꾼다.")

    clash = d.loc[(d["검토상태"] == "확정") & (d["사람_판정"] != "")
                  & (d["사람_판정"] != d["GPT_판정"]), "검토_id"].tolist()
    if clash:
        problems += len(clash)
        print(f"\n[상태] `확정` 인데 사람_판정 이 GPT_판정 과 다르다 {len(clash)}건: {clash[:10]}")
        print("       뒤집은 것이므로 `수정` 이 맞다. 그래야 뒤집은 건수를 셀 수 있다.")

    blank = d.loc[(d["검토상태"] == "확정") & (d["사람_판정"] == "")
                  & (d["GPT_판정"] == ""), "검토_id"].tolist()
    if blank:
        problems += len(blank)
        print(f"\n[상태] `확정` 인데 GPT_판정 도 사람_판정 도 없다 {len(blank)}건: {blank[:10]}")

    stray = d.loc[(d["검토상태"] == "미검토") & (d["사람_판정"] != ""), "검토_id"].tolist()
    if stray:
        problems += len(stray)
        print(f"\n[상태] `미검토` 인데 사람_판정 이 채워져 있다 {len(stray)}건: {stray[:10]}")

    # 4. 분할 정합성 — GPT · 사람 · 그리고 실제로 쓰일 최종 조각
    for who in ("GPT", "사람", "최종"):
        v, p1, l1, p2, l2 = (f"{who}_판정", f"{who}_분할1", f"{who}_분할1_라벨",
                             f"{who}_분할2", f"{who}_분할2_라벨")
        split = d[v] == "분할"
        for c in (p1, l1, p2, l2):
            empty = d.loc[split & (d[c] == ""), "검토_id"].tolist()
            if empty:
                problems += len(empty)
                print(f"\n[분할] {who}: 분할인데 {c} 가 빔 {len(empty)}건: {empty[:10]}")
        for c in (p1, l1, p2, l2):
            dirty = d.loc[(d[v] != "") & ~split & (d[c] != ""), "검토_id"].tolist()
            if dirty:
                problems += len(dirty)
                print(f"\n[분할] {who}: 분할이 아닌데 {c} 가 채워짐 {len(dirty)}건: {dirty[:10]}")
        joined = (d[p1] + d[p2]).map(squash)
        off = d.loc[split & (joined != d["sent"].map(squash)), "검토_id"].tolist()
        if off:
            if who == "최종":
                problems += len(off)
            print(f"\n[분할] {who}: 조각을 이어 붙여도 대상 문장과 다름 {len(off)}건: {off[:10]}")
            print("       (조각을 다듬었거나 이전/다음 문장을 끌어왔는지 확인한다)")

    # 5. 대상·문맥 훼손
    aligned = list(df["검토_id"]) == list(base["검토_id"])
    if not aligned:
        problems += 1
        print("\n[훼손] 검토_id 의 순서나 구성이 스냅샷과 다르다. 행을 지우거나 정렬했는가.")
    else:
        for c in ["unit_id", "place", "platform", "sent"] + CTX_COLS:
            diff = df.loc[df[c].map(squash).values != base[c].map(squash).values,
                          "검토_id"].tolist()
            if diff:
                problems += len(diff)
                print(f"\n[훼손] {c} 가 스냅샷과 다른 행 {len(diff)}건: {diff[:10]}")
    bad_model = df.loc[df["기존_모델라벨"] != "혼합", "검토_id"].tolist()
    if bad_model:
        problems += len(bad_model)
        print(f"\n[훼손] 기존_모델라벨 이 `혼합` 이 아닌 행 {len(bad_model)}건: {bad_model[:10]}")

    # 6. 문맥 규칙 — 전수 데이터로 직접 다시 계산해서 대조한다
    if not FULL_CSV.exists():
        print("\n[문맥] 전수_문장라벨.csv 가 없어 문맥 재계산을 건너뛴다.")
    else:
        full = pd.read_csv(FULL_CSV, encoding="utf-8-sig", dtype=str)
        full["순번"] = full["sent_no"].astype(int)
        at = {(r.review_id, r.순번): r.sent
              for r in full[["review_id", "sent", "순번"]].itertuples()}
        size = full.groupby("review_id").size().to_dict()
        by_review = {rid: set(g["sent"]) for rid, g in full.groupby("review_id")}

        m = df[["검토_id"] + CTX_COLS + ["sent"]].merge(
            base[["검토_id", "review_id", "sent_no"]], on="검토_id", how="left")
        m["순번"] = m["sent_no"].astype(int)

        wrong = other_review = self_ctx = ghost = 0
        both = p_only = n_only = none = 0
        for r in m.itertuples():
            want_p = at.get((r.review_id, r.순번 - 1), "")
            want_x = at.get((r.review_id, r.순번 + 1), "")
            got_p, got_x = r.이전_문장, r.다음_문장
            if squash(got_p) != squash(want_p) or squash(got_x) != squash(want_x):
                wrong += 1
            for c in (got_p, got_x):
                if not c:
                    continue
                if c not in by_review[r.review_id]:
                    other_review += 1
                if squash(c) == squash(r.sent):
                    self_ctx += 1
            if got_p and r.순번 == 1:
                ghost += 1
            if got_x and r.순번 == size[r.review_id]:
                ghost += 1
            if got_p and got_x:
                both += 1
            elif got_p:
                p_only += 1
            elif got_x:
                n_only += 1
            else:
                none += 1

        problems += wrong + other_review + self_ctx + ghost
        print(f"\n[문맥] 같은 review_id 의 바로 앞·뒤 문장 규칙 재계산")
        print(f"       둘 다 {both} · 이전만 {p_only} · 다음만 {n_only} · 없음 {none}"
              f"  합 {both + p_only + n_only + none}")
        print(f"       규칙과 다른 행 {wrong} · 다른 리뷰에서 온 문맥 {other_review} · "
              f"자기 자신이 문맥 {self_ctx} · 없어야 할 문맥 {ghost}")
        if wrong == other_review == self_ctx == ghost == 0:
            print("       -> 227행 전부 규칙대로다.")

    # 7. 변경 추적
    seen = d[d["검토상태"].isin(DECIDED) & (d["GPT_판정"] != "") & (d["최종_판정"] != "")]
    if len(seen):
        same = (seen["GPT_판정"] == seen["최종_판정"]).sum()
        print(f"\n[추적] 사람이 본 {len(seen)}건 중 GPT 와 일치 {same}건 "
              f"({same / len(seen):.1%}) · 뒤집음 {len(seen) - same}건")
        print(pd.crosstab(seen["GPT_판정"], seen["최종_판정"],
                          rownames=["GPT"], colnames=["최종"]).to_string())
        flip = seen.loc[seen["GPT_판정"] != seen["최종_판정"],
                        ["검토_id", "unit_id", "GPT_판정", "최종_판정", "검토메모"]]
        if len(flip):
            print("\n뒤집힌 행 (앞 15건)")
            print(flip.head(15).to_string(index=False))
    else:
        print("\n[추적] 아직 사람이 본 행이 없다.")

    left = len(df) - done
    if left:
        print(f"\n=> 아직 병합할 수 없다. {left}건이 남았다 "
              "(동의하면 `검토상태` 를 `확정` 으로 두면 된다).")
    elif problems:
        print(f"\n=> 병합 불가. 문제 {problems}건을 먼저 고친다.")
    else:
        print("\n=> 227건 전부 정해졌고 정합성 문제 없음. 병합 단계로 넘어갈 수 있다.")
        print("   (병합 스크립트는 아직 없다. 이 폴더는 검토 준비까지만 다룬다.)")


if __name__ == "__main__":
    main()
