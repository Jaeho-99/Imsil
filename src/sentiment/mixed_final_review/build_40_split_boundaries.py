# -*- coding: utf-8 -*-
"""혼합 표본 감사(`mixed_audit`) 40건 중 판정=분할 인 15건의 분할 경계 초벌 — 사람이 확정한다

무엇을 하려는 것인가
  `input/sentiment/mixed_audit/혼합40_판정용.xlsx` 의 40건은 판정이 이미 끝나 있다(긍정 18 · 부정 7 · 분할 15).
  그런데 분할 15건의 `분할_경계` 열이 **15건 전부 비어 있다.** 당시 목적은 267건의
  구성비를 추정하는 것이어서 `분할_앞`·`분할_뒤` 라벨만 있으면 됐고, 조각 원문은 쓸 일이
  없었다. 이제 전수 데이터에 `-b` 행을 실제로 만들려니 자를 지점이 없다.

  이 스크립트는 **자를 지점만** 초벌로 제안한다.
  `판정`(분할) 과 `분할_앞`·`분할_뒤` 라벨은 사람이 이미 정한 값이므로 건드리지 않는다.

방법 — 원문을 한 지점에서만 자른다
  각 행마다 `앵커`(조각1의 마지막 부분)를 지정하고
      조각1 = 원문[: 앵커끝]      조각2 = 원문[앵커끝 :]
  로 자른다. 이러면 `조각1 + 조각2 == 원문` 이 구조적으로 보장된다.
  앵커가 원문에 없거나 두 번 이상 나오면 그 자리에서 멈춘다.
  **원문 표현을 그대로 옮긴다. 새로 쓰거나 다듬지 않는다.**

  자를 지점은 이미 정해진 `앞 라벨 -> 뒤 라벨` 순서에 맞춘다. 그 순서와 맞출 수 없거나
  분할 판정 자체를 다시 볼 필요가 있으면 **억지로 자르지 않고 `재검토 필요`로 표시**한다.

입력 — 읽기만 한다. `input/` 은 절대 쓰지 않는다.
  input/sentiment/mixed_audit/혼합40_판정용.xlsx   `판정` 시트
  output/sentiment/fullscale/전수_문장라벨.csv       원문이 전수와 같은지 대조

출력 — output/sentiment/mixed_final_review/
  혼합40_분할경계_확정용.xlsx   사람이 `사람 확정 분할1/2` 를 채운다
                               (채운 확정본은 input/sentiment/mixed_final_review/ 에 있다)

실행:  python src/sentiment/mixed_final_review/build_40_split_boundaries.py
"""
import sys
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_IN, SENT_OUT  # noqa: E402
OUT_DIR = SENT_OUT / "mixed_final_review"           # 검토표 작업본 (input/ 의 확정본은 건드리지 않는다)
OUT_DIR.mkdir(parents=True, exist_ok=True)
SRC = SENT_IN / "mixed_audit" / "혼합40_판정용.xlsx"
FULL = SENT_OUT / "fullscale" / "전수_문장라벨.csv"
OUT = OUT_DIR / "혼합40_분할경계_확정용.xlsx"     # 빈 확정용 표 (사람이 채운 표는 input/ 에 있다)

EXPECT_SPLIT = 15

COLS = ["ID", "unit_id", "원문", "기존 앞 라벨", "기존 뒤 라벨",
        "제안 분할1", "제안 분할2", "재검토 필요 여부",
        "사람 확정 분할1", "사람 확정 분할2", "메모"]
WIDTHS = [7, 13, 60, 12, 12, 46, 46, 13, 46, 46, 54]

# 판정_id: (앵커 = 조각1의 끝. None 이면 자르지 않는다, 재검토여부, 메모)
CUT = {
    "A02": ("유료여서 아쉽", "N", ""),
    "A05": ("입구 정체가 많이 되며", "N",
            "`입구 정체` 는 혼잡(외부 요인)이지만 사람이 이미 부정으로 판정했으므로 그대로 둔다"),
    "A11": ("참 좋은데", "N", ""),
    "A16": ("가공비가조금비싼듯하다.", "N", "`하지만` 부터 조각2"),
    "A17": ("운영하는데", "N",
            "앞 조각의 `주중에는 시설이 문을 닫습니다` 는 운영 정보에 가깝지만 사람 판정(부정)을 유지했다"),
    "A20": ("비쌌지만", "N", ""),
    "A21": ("재방문 강추", "N", ""),
    "A22": ("산책로 좋아요", "N", ""),
    "A23": (None, "Y",
            "원문이 `좋아요`(긍정)로 시작해 라벨 순서(부정->긍정)와 어긋난다. "
            "한 지점에서 잘라서는 앞 조각을 부정으로 만들 수 없다 — 긍정·부정·긍정 3조각 구조다. "
            "선택지: (1) 라벨 순서를 긍정->부정 으로 바꾸고 `좋아요 가격이 비싼데` / `색다른 체험 좋아요` "
            "(2) 지침의 `사실+평가` 형(`입장료 3000원이지만 돈이 아깝지 않았어요` -> 긍정)으로 보아 긍정 단일로 되돌린다"),
    "A27": ("예쁘게 구며놓아 좋아요", "N", "`단 주차공간이` 부터 조각2"),
    "A28": ("주차대란 힘듦", "Y",
            "자르는 것 자체는 자연스럽다. 다만 `사람이 많이 밀림`은 혼잡(외부 요인)이고 "
            "`그것만 빼면 ~ 좋은거같아요` 는 지침의 `빼고 좋음` 형이다"
            "(검증셋 사람 판정: `더운거 빼고 좋음` -> 긍정). 분할이 아니라 긍정 단일이 맞을 수 있다. "
            "분할을 유지하기로 하면 제안한 조각을 그대로 쓰면 된다"),
    "A31": ("좋았지만", "N", "뒤 조각은 개선 요구 -> 부정. 지침과 일치한다"),
    "A32": ("아쉬웠는데", "N", ""),
    "A37": ("걸어서는 힘듬)", "Y",
            "괄호까지 조각1에 넣어 잘랐고 각 조각의 지배적 입장은 라벨과 맞는다. 다만 평가가 넷이라 "
            "조각마다 반대 성분이 남는다 — 조각1 안에 `걸어서는 힘듬`(부정), "
            "조각2 안에 `유모차는 끌 수 있는데`(긍정). 이 경계로 확정할지 확인이 필요하다"),
    "A40": ("무서웠고..;;", "N",
            "앞은 명확히 부정, 뒤는 길지만 전부 긍정 방향이라 한 조각으로 둔다"),
}


def fail(msg):
    sys.exit(f"[중단] {msg}")


def squash(s):
    return "".join(str(s).split())


def main():
    a = pd.read_excel(SRC, sheet_name="판정").fillna("")
    full = pd.read_csv(FULL, encoding="utf-8-sig", dtype=str)
    sent_of = dict(zip(full["unit_id"], full["sent"]))
    label_of = dict(zip(full["unit_id"], full["label"]))

    sp = a[a["판정"] == "분할"].copy()
    if len(sp) != EXPECT_SPLIT:
        fail(f"분할이 {len(sp)}건이다 — {EXPECT_SPLIT}건을 기대했다.")
    if set(sp["판정_id"]) != set(CUT):
        fail(f"분할 건 목록이 다르다.\n     표에만: {sorted(set(CUT) - set(sp['판정_id']))}"
             f"\n     원본에만: {sorted(set(sp['판정_id']) - set(CUT))}")

    rows = []
    for r in sp.itertuples():
        uid = r.unit_id
        if squash(sent_of.get(uid, "")) != squash(r.sent):
            fail(f"{r.판정_id}: 원문이 전수 데이터와 다르다.")
        if label_of.get(uid) != "혼합":
            fail(f"{r.판정_id}: 전수 label 이 `혼합` 이 아니다 ({label_of.get(uid)}).")

        anchor, warn, memo = CUT[r.판정_id]
        sent = str(r.sent)
        if anchor is None:
            p1 = p2 = ""
        else:
            n = sent.count(anchor)
            if n == 0:
                fail(f"{r.판정_id}: 앵커 {anchor!r} 가 원문에 없다.")
            if n > 1:
                fail(f"{r.판정_id}: 앵커 {anchor!r} 가 원문에 {n}번 나온다 — 자를 지점이 모호하다.")
            cut = sent.index(anchor) + len(anchor)
            p1, p2 = sent[:cut].strip(), sent[cut:].strip()
            if not p1 or not p2:
                fail(f"{r.판정_id}: 조각 하나가 빈다.")
            if squash(p1 + p2) != squash(sent):
                fail(f"{r.판정_id}: 조각을 이어 붙여도 원문이 아니다.")

        rows.append({
            "ID": r.판정_id, "unit_id": uid, "원문": sent,
            "기존 앞 라벨": r.분할_앞, "기존 뒤 라벨": r.분할_뒤,
            "제안 분할1": p1, "제안 분할2": p2,
            "재검토 필요 여부": warn,
            "사람 확정 분할1": "", "사람 확정 분할2": "", "메모": memo,
        })

    df = pd.DataFrame(rows, columns=COLS).sort_values("ID").reset_index(drop=True)

    with pd.ExcelWriter(OUT, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="분할경계", index=False)
        ws = w.sheets["분할경계"]
        head = {c: i for i, c in enumerate(COLS, start=1)}
        for i, width in enumerate(WIDTHS, start=1):
            ws.column_dimensions[get_column_letter(i)].width = width
        ws.freeze_panes = "D2"          # ID · unit_id · 원문 은 스크롤해도 남는다
        for c in ws[1]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="DDDDDD")
        for c in ("기존 앞 라벨", "기존 뒤 라벨"):      # 이미 정해진 값 = 회색
            ws.cell(row=1, column=head[c]).fill = PatternFill("solid", fgColor="BFBFBF")
        ws.cell(row=1, column=head["원문"]).fill = PatternFill("solid", fgColor="FFF2CC")
        for c in ("제안 분할1", "제안 분할2"):          # 초벌 = 노랑
            ws.cell(row=1, column=head[c]).fill = PatternFill("solid", fgColor="FFE59A")
        for c in ("사람 확정 분할1", "사람 확정 분할2", "메모"):   # 사람 = 초록
            ws.cell(row=1, column=head[c]).fill = PatternFill("solid", fgColor="C6E0B4")
        ws.cell(row=1, column=head["재검토 필요 여부"]).fill = PatternFill("solid", fgColor="F4B183")

        grey = Font(color="808080", italic=True)
        for row in ws.iter_rows(min_row=2, max_row=len(df) + 1):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
            row[head["원문"] - 1].font = Font(bold=True)
            for c in ("기존 앞 라벨", "기존 뒤 라벨", "메모"):
                row[head[c] - 1].font = grey
            if row[head["재검토 필요 여부"] - 1].value == "Y":
                row[head["재검토 필요 여부"] - 1].fill = PatternFill("solid", fgColor="F4B183")

        last = len(df) + 1
        dv = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
        ws.add_data_validation(dv)
        col = get_column_letter(head["재검토 필요 여부"])
        dv.add(f"{col}2:{col}{last}")

    n_warn = (df["재검토 필요 여부"] == "Y").sum()
    filled = df[df["제안 분할1"] != ""]
    print(f"분할 {len(df)}건 생성 -> {OUT.name}")
    print(f"  제안 조각을 넣은 행 {len(filled)}건 · 전부 `조각1+조각2 == 원문` 확인")
    print(f"  재검토 필요 {n_warn}건: {df.loc[df['재검토 필요 여부'] == 'Y', 'ID'].tolist()}")
    print(f"  원문·라벨은 input/ 원본 그대로다. 판정과 라벨은 건드리지 않았다.")


if __name__ == "__main__":
    main()
