# -*- coding: utf-8 -*-
"""ChatGPT 초벌 판정 결과를 `혼합227_최종검토용.xlsx` 의 GPT_* 열에 채워 넣는다

무엇을 하려는 것인가
  ChatGPT 초벌 판정은 227행짜리 CSV 로 받는다(`gpt_초벌_양식.csv` 와 같은 열).
  그것을 사람이 xlsx 에 손으로 227번 옮겨 적으면 옮겨 적다가 틀린다.
  이 스크립트가 옮긴다. **GPT_* 열만 건드린다. 사람_* 과 검토상태·검토메모는 손대지 않는다.**

  이것은 라벨 확정이 아니다. 초벌을 자리에 앉히는 일일 뿐이고,
  최종 라벨은 사람이 `사람_판정` 열에 적는 값이다.

문맥 열은 입력 조건이지 답이 아니다
  양식에는 `이전_문장` · `sent` · `다음_문장` 이 들어 있다. 이것은 GPT 가 **읽으라고**
  준 값이지 고쳐서 돌려보내라고 준 값이 아니다. 세 열 중 하나라도 기준 스냅샷
  (`혼합227_대상.csv`)과 다르면 **반영하지 않고 멈춘다.** 문장이 바뀌었다면 GPT 가
  다른 문장을 판정했다는 뜻이고, 그 판정은 이 행의 라벨이 될 수 없다.

  줄바꿈·앞뒤 공백만 다른 경우까지 막고 싶지 않으면 `--공백무시` 를 준다.
  그래도 글자가 하나라도 다르면 여전히 멈춘다.

작업본 위치
  output/sentiment/mixed_final_review/ — build_final_review.py 가 만든 작업본에 쓴다.
  사람이 다 채운 확정본은 input/sentiment/mixed_final_review/ 에 있고, 이 스크립트는 그 파일을 건드리지 않는다.

입력
  input/sentiment/mixed_final_review/gpt_초벌_판정.csv (또는 인자로 준 경로)
      검토_id, unit_id, 이전_문장, sent, 다음_문장,
      GPT_판정, GPT_분할1, GPT_분할1_라벨, GPT_분할2, GPT_분할2_라벨
      - 227행 전부, `검토_id`·`unit_id` 가 대상 스냅샷과 순서까지 일치해야 한다
      - GPT_판정 은 긍정 / 부정 / 중립 / 분할 넷 중 하나. `혼합`·`애매`·`모름` 은 거부한다
      - 분할이 아니면 분할 칸 4개는 비운다. 분할이면 4개를 다 채운다
  혼합227_대상.csv          대조 기준 (건드리지 않는다)
  혼합227_최종검토용.xlsx    여기에 쓴다

출력
  혼합227_최종검토용.xlsx 를 제자리에서 갱신한다.
  덮어쓰기 전에 `백업/<타임스탬프>/` 로 원본을 복사해 둔다.

실행:  python src/sentiment/mixed_final_review/apply_gpt_draft.py [csv경로] [--공백무시]
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_IN, SENT_OUT  # noqa: E402
OUT_DIR = SENT_OUT / "mixed_final_review"           # 검토표 작업본 (input/ 의 확정본은 건드리지 않는다)
OUT_DIR.mkdir(parents=True, exist_ok=True)
XLSX = OUT_DIR / "혼합227_최종검토용.xlsx"
BASE_CSV = OUT_DIR / "혼합227_대상.csv"
BACKUP_DIR = OUT_DIR / "백업"

CTX_COLS = ["이전_문장", "다음_문장"]
FIXED_COLS = ["이전_문장", "sent", "다음_문장"]      # GPT 가 바꿔서는 안 되는 입력 조건
GPT_COLS = ["GPT_판정", "GPT_분할1", "GPT_분할1_라벨", "GPT_분할2", "GPT_분할2_라벨"]
CAT4 = {"긍정", "부정", "중립", "분할"}
CAT3 = {"긍정", "부정", "중립"}


def fail(msg):
    sys.exit(f"[중단] {msg}")


def squash(s):
    return "".join(str(s).split())


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    loose = "--공백무시" in sys.argv[1:]
    src = Path(args[0]) if args else SENT_IN / "mixed_final_review" / "gpt_초벌_판정.csv"

    if not src.exists():
        fail(f"{src.name} 가 없다. gpt_초벌_양식.csv 를 채워서 그 이름으로 두거나 경로를 인자로 준다.")
    if not XLSX.exists():
        fail("혼합227_최종검토용.xlsx 가 없다. build_final_review.py 를 먼저 실행한다.")

    gpt = pd.read_csv(src, encoding="utf-8-sig", dtype=str).fillna("")
    base = pd.read_csv(BASE_CSV, encoding="utf-8-sig", dtype=str).fillna("")

    need = ["검토_id", "unit_id"] + FIXED_COLS + GPT_COLS
    miss = [c for c in need if c not in gpt.columns]
    if miss:
        fail(f"열이 없다: {miss}\n     양식: {', '.join(need)}")

    gpt[need] = gpt[need].apply(lambda s: s.str.strip())

    # ---------- 행 정합성 ----------
    if len(gpt) != len(base):
        fail(f"{len(gpt)}행이다 — {len(base)}행을 기대했다.")
    if list(gpt["검토_id"]) != list(base["검토_id"]):
        fail("검토_id 의 순서나 구성이 대상 스냅샷과 다르다. 양식을 다시 받는다.")
    bad_uid = gpt.loc[gpt["unit_id"].values != base["unit_id"].values, "검토_id"].tolist()
    if bad_uid:
        fail(f"unit_id 가 대상과 다른 행: {bad_uid[:10]}")

    # ---------- 입력 조건(대상 문장 + 문맥) 이 그대로인가 ----------
    norm = squash if loose else (lambda s: str(s).strip())
    for c in FIXED_COLS:
        left = gpt[c].map(norm).values
        right = base[c].map(norm).values
        diff = gpt.loc[left != right, "검토_id"].tolist()
        if diff:
            i = gpt.index[gpt["검토_id"] == diff[0]][0]
            fail(f"`{c}` 가 기준 데이터와 다른 행 {len(diff)}건: {diff[:10]}\n"
                 f"     예) {diff[0]}\n"
                 f"       기준: {base.loc[i, c]!r}\n"
                 f"       받음: {gpt.loc[i, c]!r}\n"
                 "     문맥과 대상 문장은 읽으라고 준 입력이다. 고쳐서 돌려보내면 안 된다."
                 + ("" if loose else "\n     공백만 다른 것이면 --공백무시 로 다시 실행한다."))

    # ---------- 판정값 ----------
    bad = gpt.loc[~gpt["GPT_판정"].isin(CAT4), ["검토_id", "GPT_판정"]]
    if len(bad):
        fail("GPT_판정 이 긍정/부정/중립/분할 이 아닌 행이 있다 "
             "(`혼합`·`애매`·`모름` 은 쓰지 않는다):\n" + bad.head(10).to_string(index=False))

    is_split = gpt["GPT_판정"] == "분할"
    for c in ("GPT_분할1", "GPT_분할2"):
        empty = gpt.loc[is_split & (gpt[c] == ""), "검토_id"].tolist()
        if empty:
            fail(f"분할인데 {c} 가 비어 있다: {empty[:10]}")
    for c in ("GPT_분할1_라벨", "GPT_분할2_라벨"):
        wrong = gpt.loc[is_split & ~gpt[c].isin(CAT3), "검토_id"].tolist()
        if wrong:
            fail(f"분할인데 {c} 가 긍정/부정/중립 이 아니다: {wrong[:10]}")
    for c in GPT_COLS[1:]:
        dirty = gpt.loc[~is_split & (gpt[c] != ""), "검토_id"].tolist()
        if dirty:
            fail(f"분할이 아닌데 {c} 가 채워져 있다: {dirty[:10]}")

    # 조각을 이어 붙이면 대상 문장이 되어야 한다 — 문맥에서 끌어온 것도 여기서 걸린다
    joined = (gpt["GPT_분할1"] + gpt["GPT_분할2"]).map(squash)
    orig = base["sent"].map(squash)
    off = gpt.loc[is_split.values & (joined.values != orig.values), "검토_id"].tolist()
    if off:
        print(f"[경고] 분할 조각을 이어 붙여도 대상 문장과 다른 행 {len(off)}건: {off[:10]}")
        print("       조각을 다듬었거나 이전/다음 문장을 끌어왔을 수 있다. 사람 검토 때 이 행부터 본다.")

    # ---------- 반영 ----------
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
    head = {c.value: c.column for c in ws[1]}
    for i, row in enumerate(gpt.itertuples(index=False), start=2):
        if ws.cell(row=i, column=head["검토_id"]).value != row.검토_id:
            fail(f"{i}행의 검토_id 가 어긋난다 — xlsx 행 순서가 바뀌었다.")
        for c in GPT_COLS:
            ws.cell(row=i, column=head[c]).value = getattr(row, c) or None
    try:
        wb.save(XLSX)
    except PermissionError:
        fail(f"{XLSX.name} 에 쓸 수 없다. Excel 에서 닫고 다시 실행한다.")

    print(f"{src.name} -> {XLSX.name} `검토` 시트 GPT_* 열 {len(gpt)}행 반영"
          + ("  (공백 차이 무시)" if loose else ""))
    print(f"  구성: {gpt['GPT_판정'].value_counts().to_dict()}")
    print(f"  입력 조건 확인: 이전_문장 · sent · 다음_문장 227행 전부 기준과 일치")
    print(f"  백업: 백업/{stamp}/{XLSX.name}")
    print("\n다음: 사람이 227행의 `사람_판정` 을 채운다. GPT_* 는 덮어쓰지 않는다.")
    print("      진행 상황 점검: check_review.py")


if __name__ == "__main__":
    main()
