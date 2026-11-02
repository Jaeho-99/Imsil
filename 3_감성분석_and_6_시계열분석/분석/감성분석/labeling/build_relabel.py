# -*- coding: utf-8 -*-
"""재라벨용 파일 생성 (3단계) — Cohen's κ 측정용

입력 — 읽기만 한다.
  labeling/확정/검증셋_본_확정.csv        532문장 (1단계 산출물)
  labeling/검증셋_본_라벨링용.xlsx         지침요약 시트만 복사

출력 — labeling/재라벨/
  재라벨_50문장.xlsx    사용자가 채운다. 원래 라벨은 들어 있지 않다
  재라벨_매핑.csv       재라벨_id -> unit_id. **κ 계산 전까지 열지 않는다**

설계
  - 모집단은 본 확정 532문장. 보강셋은 별점 1~3 편향 표본이라 제외한다.
  - 순서를 새로 섞는다. 원래 순서면 앞뒤 문맥으로 그때 판단이 되살아난다.
  - unit_id를 파일에서 뺐다. 남겨 두면 원본과 대조할 수 있다.
  - 대신 **같은 리뷰의 다른 문장을 문맥 열로 보여준다.** 원래 라벨링 때는 같은 리뷰
    문장이 붙어 있어 문맥이 있었다. 문맥 없이 다시 매기면 조건이 달라져서 κ가
    재현성이 아니라 조건 차이를 재게 된다.

실행:  ../../.venv/Scripts/python.exe labeling/build_relabel.py
"""
import pandas as pd
from pathlib import Path
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

SEED = 20260822   # 확정. 바꾸지 않는다
N = 50

HERE = Path(__file__).resolve().parent
OUT = HERE / "재라벨"

src = pd.read_csv(HERE / "확정" / "검증셋_본_확정.csv", encoding="utf-8-sig")
pick = src.sample(N, random_state=SEED).copy()

# 같은 리뷰의 문장을 순서대로 이어 붙이고, 대상 문장에만 ▶ 를 단다
by_review = {rid: g.sort_values("sent_no") for rid, g in src.groupby("review_id")}


def context(row):
    g = by_review[row.review_id]
    if len(g) == 1:
        return "(리뷰에 이 문장 하나뿐)"
    return "\n".join(("▶ " if u == row.unit_id else "   ") + s
                     for u, s in zip(g.unit_id, g.sent))


pick["문맥"] = [context(r) for r in pick.itertuples()]
pick = pick.sample(frac=1, random_state=SEED).reset_index(drop=True)   # 한 번 더 섞는다
pick["재라벨_id"] = [f"R{i:02d}" for i in range(1, N + 1)]

OUT.mkdir(exist_ok=True)
pick[["재라벨_id", "unit_id"]].to_csv(OUT / "재라벨_매핑.csv", index=False, encoding="utf-8-sig")

sheet = pick[["재라벨_id", "place", "platform", "sent", "문맥"]].copy()
sheet["label"] = ""
sheet["note"] = ""

guide = pd.read_excel(HERE / "검증셋_본_라벨링용.xlsx", sheet_name="지침요약", header=None)

with pd.ExcelWriter(OUT / "재라벨_50문장.xlsx", engine="openpyxl") as w:
    sheet.to_excel(w, sheet_name="재라벨", index=False)
    guide.to_excel(w, sheet_name="지침요약", index=False, header=False)
    ws = w.sheets["재라벨"]
    for col, width in zip("ABCDEFG", (10, 16, 9, 60, 60, 10, 24)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDDDDD")
    for row in ws.iter_rows(min_row=2, max_row=N + 1):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    dv = DataValidation(type="list", formula1='"긍정,부정,중립"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"F2:F{N + 1}")

print(f"모집단 {len(src)}문장 -> {N}문장 추출 (seed {SEED})")
print(f"  리뷰 {pick.review_id.nunique()}개에서 나옴 · 문맥 있는 문장 {(~pick.문맥.str.startswith('(')).sum()}건")
print(f"  플랫폼 {pick.platform.value_counts().to_dict()}")
print(f"\n출력: {OUT}")
