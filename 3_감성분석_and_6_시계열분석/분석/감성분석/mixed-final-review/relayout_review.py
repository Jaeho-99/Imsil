# -*- coding: utf-8 -*-
"""`혼합227_최종검토용.xlsx` 의 열 순서·서식만 현재 규칙으로 다시 맞춘다 — 값은 그대로

무엇을 하려는 것인가
  사람이 오른쪽 끝의 `사람_판정` 을 채울 때 판정 대상 문장(`sent`)이 화면에서 사라지면
  227행 내내 좌우로 왕복해야 한다. 그래서 `sent` 를 세 번째 열로 옮기고
  `검토_id · unit_id · sent` 를 틀고정한다.

  열 순서와 서식은 `build_final_review.py` 의 `COLS` · `WIDTHS` · `style_review_sheet()`
  하나만 본다. 규칙이 두 군데로 갈라지면 파일을 다시 만들 때마다 화면이 달라진다.

  **값은 한 칸도 바꾸지 않는다.** 이미 채워 넣은 `사람_판정` 도 그대로 옮겨 온다.
  옮기기 전후로 모든 열의 값이 같은지 대조하고, 다르면 저장하지 않고 멈춘다.

  `검토` 시트의 값과 `판정지침` 시트를 다시 쓴다. `판정지침` 은 사람이 채우는 곳이 아니라
  `build_final_review.py` 의 `GUIDE` 에서 통째로 생성되는 안내문이라, 지침이 바뀌면
  여기서 같이 갱신한다. `지침요약` · `이미판정40` 은 건드리지 않는다.

실행:  ../../.venv/Scripts/python.exe mixed-final-review/relayout_review.py
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_final_review import COLS, FREEZE, GUIDE, style_review_sheet  # noqa: E402

HERE = Path(__file__).resolve().parent
XLSX = HERE / "혼합227_최종검토용.xlsx"
BACKUP_DIR = HERE / "백업"


def fail(msg):
    sys.exit(f"[중단] {msg}")


def main():
    if not XLSX.exists():
        fail("혼합227_최종검토용.xlsx 가 없다.")

    before = pd.read_excel(XLSX, sheet_name="검토", dtype=str).fillna("")
    missing = [c for c in COLS if c not in before.columns]
    extra = [c for c in before.columns if c not in COLS]
    if missing or extra:
        fail(f"열 구성이 다르다.\n     빠짐: {missing}\n     남음: {extra}")
    if list(before.columns) == COLS:
        print("이미 현재 열 순서다. 서식만 다시 입힌다.")

    filled = (before["사람_판정"] != "").sum()
    after = before.reindex(columns=COLS)

    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / stamp
    dest.mkdir(exist_ok=True)
    shutil.copy2(XLSX, dest / XLSX.name)

    try:
        wb = load_workbook(XLSX)
    except PermissionError:
        fail(f"{XLSX.name} 를 열 수 없다. Excel 에서 닫고 다시 실행한다.")

    ws = wb["검토"]
    # 시트를 비우고 새 순서로 다시 쓴다. 서식이 옛 열에 남지 않게 통째로 지운다.
    wb.remove(ws)
    ws = wb.create_sheet("검토", 0)
    ws.append(COLS)
    for row in after.itertuples(index=False):
        ws.append([v if v != "" else None for v in row])
    style_review_sheet(ws, len(after))

    # 판정지침은 GUIDE 에서 생성되는 안내문이다. 사람 입력이 없으므로 통째로 다시 쓴다.
    if "판정지침" in wb.sheetnames:
        wb.remove(wb["판정지침"])
    wg = wb.create_sheet("판정지침", 1)
    for line in GUIDE:
        wg.append([line])
    wg.column_dimensions["A"].width = 100
    for i in (1, 3, 4, 5, 6, 7):
        wg.cell(row=i, column=1).font = Font(bold=True)

    try:
        wb.save(XLSX)
    except PermissionError:
        fail(f"{XLSX.name} 에 쓸 수 없다. Excel 에서 닫고 다시 실행한다.")

    # 값이 한 칸도 안 바뀌었는지 다시 읽어서 대조한다
    check = pd.read_excel(XLSX, sheet_name="검토", dtype=str).fillna("")
    if list(check.columns) != COLS:
        fail("저장된 열 순서가 의도와 다르다.")
    for c in COLS:
        if list(check[c]) != list(before[c]):
            fail(f"`{c}` 열의 값이 바뀌었다 — 백업/{stamp}/ 에서 되돌린다.")

    print(f"열 재배치 완료 — {len(after)}행 · {len(COLS)}열, 값 전부 동일함을 확인")
    print(f"  순서: {' | '.join(COLS[:6])} | …")
    print(f"  틀고정: {FREEZE} (검토_id · unit_id · sent 는 오른쪽으로 스크롤해도 남는다)")
    print(f"  이미 채운 사람_판정 {filled}건 보존됨")
    print(f"  판정지침 시트도 현재 GUIDE 로 다시 썼다 ({len(GUIDE)}줄)")
    print(f"  백업: 백업/{stamp}/{XLSX.name}")


if __name__ == "__main__":
    main()
