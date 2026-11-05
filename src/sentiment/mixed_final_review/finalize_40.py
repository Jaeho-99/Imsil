# -*- coding: utf-8 -*-
"""혼합 표본 감사(`mixed_audit`) 40건의 최종 판정과 분할 조각을 한 파일로 확정한다

무엇을 하려는 것인가
  40건의 판정은 `input/sentiment/mixed_audit/혼합40_판정용.xlsx` 에 있고(긍정 18 · 부정 7 · 분할 15),
  분할 조각은 그 파일에 없어서 `혼합40_분할경계_확정용.xlsx` 에서 사람이 따로 확정했다.
  둘이 흩어져 있으면 병합할 때마다 두 파일을 맞춰 읽어야 하고, 아래 A23 같은
  판정 변경이 어디에도 안 남는다. 그래서 **병합이 읽을 파일 하나**로 합친다.

  판정을 새로 만들지 않는다. 이미 사람이 정한 값을 모으고, 아래 OVERRIDE 에 적힌
  변경만 반영한다.

판정 변경 기록 — OVERRIDE
  A23 `좋아요 가격이 비싼데 색다른 체험 좋아요` 는 원래 `분할`(부정 -> 긍정) 이었다.
  그런데 원문이 `좋아요`(긍정)로 시작해 라벨 순서와 어긋나고, 부정이 문장 **가운데**
  박혀 있어 연속 절단으로는 부정 조각을 떼어낼 수 없다. 어순을 바꾸면 조각을 만들 수는
  있으나 `조각1 + 조각2 == 원문` 규칙이 이 한 행에서만 깨진다.
  지침이 이 형태를 이미 결정해 두었으므로(사실+평가: `입장료 3000원이지만 돈이
  아깝지 않았어요` -> 긍정) **긍정 단일로 되돌린다.** 2026-08-26, 사람 결정.

  그 결과 40건 구성은 긍정 19 · 부정 7 · 분할 14 가 된다.
  `input/` 의 원본은 고치지 않는다. 변경은 여기에만 남는다.

입력 — 읽기만 한다.
  input/sentiment/mixed_audit/혼합40_판정용.xlsx                 `판정` 시트 (판정 · 분할_앞 · 분할_뒤)
  input/sentiment/mixed_final_review/혼합40_분할경계_확정용.xlsx  사람이 확정한 조각 원문
  output/sentiment/fullscale/전수_문장라벨.csv                   원문 대조

출력 — output/sentiment/mixed_final_review/
  혼합40_최종.csv                병합(merge_final.py)이 읽을 파일. 40행
  혼합40_분할경계_확정용.xlsx     input/ 의 확정용 표에 `최종 판정` 열을 더한 사본 (다른 값은 그대로)

실행:  python src/sentiment/mixed_final_review/finalize_40.py
"""
import sys
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_IN, SENT_OUT  # noqa: E402
OUT_DIR = SENT_OUT / "mixed_final_review"           # 검토표 작업본 (input/ 의 확정본은 건드리지 않는다)
OUT_DIR.mkdir(parents=True, exist_ok=True)
SRC = SENT_IN / "mixed_audit" / "혼합40_판정용.xlsx"
BND = SENT_IN / "mixed_final_review" / "혼합40_분할경계_확정용.xlsx"      # 사람이 확정한 분할 경계
BND_OUT = OUT_DIR / BND.name                    # 위 표에 `최종 판정` 열을 더한 사본
FULL = SENT_OUT / "fullscale" / "전수_문장라벨.csv"
OUT = OUT_DIR / "혼합40_최종.csv"

# 판정_id: (바뀐 판정, 사유)  — input/ 원본의 `판정` 을 여기서만 덮어쓴다
OVERRIDE = {
    "A23": ("긍정",
            "원문이 `좋아요`로 시작해 라벨 순서(부정->긍정)와 어긋나고 부정이 문장 가운데 있어 "
            "연속 절단으로 부정 조각을 떼어낼 수 없다. 지침의 `사실+평가` 형에 해당해 "
            "긍정 단일로 되돌림 (2026-08-26 사람 결정)"),
}

EXPECT_N = 40


def fail(msg):
    sys.exit(f"[중단] {msg}")


def squash(s):
    return "".join(str(s).split())


def main():
    a = pd.read_excel(SRC, sheet_name="판정").fillna("")
    b = pd.read_excel(BND, sheet_name="분할경계").fillna("")
    full = pd.read_csv(FULL, encoding="utf-8-sig", dtype=str)
    sent_of = dict(zip(full["unit_id"], full["sent"]))
    label_of = dict(zip(full["unit_id"], full["label"]))

    if len(a) != EXPECT_N:
        fail(f"판정 시트가 {len(a)}행이다 — {EXPECT_N}행을 기대했다.")
    unknown = set(OVERRIDE) - set(a["판정_id"])
    if unknown:
        fail(f"OVERRIDE 에 없는 판정_id: {sorted(unknown)}")

    bnd = {r.ID: r for r in b.itertuples()}
    rows, warn = [], []
    for r in a.itertuples():
        uid, pid = r.unit_id, r.판정_id
        if squash(sent_of.get(uid, "")) != squash(r.sent):
            fail(f"{pid}: 원문이 전수 데이터와 다르다.")
        if label_of.get(uid) != "혼합":
            fail(f"{pid}: 전수 label 이 `혼합` 이 아니다 ({label_of.get(uid)}).")

        verdict, why = r.판정, ""
        if pid in OVERRIDE:
            verdict, why = OVERRIDE[pid]
            if verdict == r.판정:
                fail(f"{pid}: OVERRIDE 가 원래 판정과 같다 — 지울 것.")

        p1 = l1 = p2 = l2 = ""
        if verdict == "분할":
            if pid not in bnd:
                fail(f"{pid}: 분할인데 분할경계 파일에 행이 없다.")
            g = bnd[pid]
            p1, p2 = str(g._9).strip(), str(g._10).strip()   # 사람 확정 분할1/2
            if not p1 or not p2:
                fail(f"{pid}: 분할인데 사람 확정 조각이 비어 있다.")
            if squash(p1 + p2) != squash(r.sent):
                fail(f"{pid}: 조각을 이어 붙여도 원문이 아니다.")
            l1, l2 = str(r.분할_앞).strip(), str(r.분할_뒤).strip()
            if l1 not in {"긍정", "부정", "중립"} or l2 not in {"긍정", "부정", "중립"}:
                fail(f"{pid}: 조각 라벨이 이상하다 ({l1} / {l2}).")
            if str(g._8).strip() == "Y":
                warn.append(pid)
        elif verdict not in {"긍정", "부정", "중립"}:
            fail(f"{pid}: 판정 {verdict!r} 이 허용 범주가 아니다.")

        rows.append({"판정_id": pid, "unit_id": uid, "place": r.place,
                     "platform": r.platform, "sent": r.sent,
                     "원래_판정": r.판정, "최종_판정": verdict,
                     "분할1": p1, "분할1_라벨": l1, "분할2": p2, "분할2_라벨": l2,
                     "판정변경_사유": why})

    d = pd.DataFrame(rows)
    d.to_csv(OUT, index=False, encoding="utf-8-sig")

    # 분할경계 xlsx 사본(output/)에 `최종 판정` 열을 더한다 — input/ 의 원본과 기존 값은 그대로 둔다
    before = pd.read_excel(BND, sheet_name="분할경계").fillna("")

    verdict_of = dict(zip(d["판정_id"], d["최종_판정"]))
    reason_of = dict(zip(d["판정_id"], d["판정변경_사유"]))
    try:
        wb = load_workbook(BND)
    except PermissionError:
        fail(f"{BND.name} 를 열 수 없다. Excel 에서 닫고 다시 실행한다.")
    ws = wb["분할경계"]
    head = {c.value: c.column for c in ws[1]}
    col = head.get("최종 판정") or ws.max_column + 1
    ws.cell(row=1, column=col).value = "최종 판정"
    ws.cell(row=1, column=col).font = Font(bold=True)
    ws.cell(row=1, column=col).fill = PatternFill("solid", fgColor="C6E0B4")
    ws.column_dimensions[get_column_letter(col)].width = 11
    for i in range(2, ws.max_row + 1):
        pid = ws.cell(row=i, column=head["ID"]).value
        v = verdict_of.get(pid, "")
        c = ws.cell(row=i, column=col)
        c.value = v
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if v != "분할":                       # 분할에서 빠진 행은 눈에 띄게
            c.fill = PatternFill("solid", fgColor="F4B183")
            m = ws.cell(row=i, column=head["메모"])
            if reason_of.get(pid) and reason_of[pid] not in str(m.value or ""):
                m.value = f"[확정] {reason_of[pid]}"
    try:
        wb.save(BND_OUT)
    except PermissionError:
        fail(f"{BND.name} 에 쓸 수 없다. Excel 에서 닫고 다시 실행한다.")

    after = pd.read_excel(BND_OUT, sheet_name="분할경계").fillna("")
    for c in before.columns:
        if c == "메모":
            continue
        if list(after[c]) != list(before[c]):
            fail(f"`{c}` 열의 값이 바뀌었다 — {BND_OUT.name} 를 지우고 다시 실행한다 (input/ 원본은 그대로다).")

    print(f"40건 최종 확정 -> {OUT.name}")
    print(f"  원래 판정 {a['판정'].value_counts().to_dict()}")
    print(f"  최종 판정 {d['최종_판정'].value_counts().to_dict()}")
    for pid, (v, _) in OVERRIDE.items():
        o = a.loc[a['판정_id'] == pid, '판정'].iloc[0]
        print(f"  판정 변경: {pid}  {o} -> {v}")
    n_sp = (d["최종_판정"] == "분할").sum()
    print(f"  분할 {n_sp}건 전부 `조각1+조각2 == 원문` 확인")
    if warn:
        print(f"  분할경계 파일에서 `재검토 필요=Y` 였으나 분할로 확정된 건: {warn}")
    print(f"  병합 시 -b 행 {n_sp}개 추가 예정")
    print("  input/ 원본은 건드리지 않았다. 변경은 output/sentiment/mixed_final_review/ 에만 남는다.")
    print(f"  `최종 판정` 열을 더한 사본: {BND_OUT.name}")


if __name__ == "__main__":
    main()
