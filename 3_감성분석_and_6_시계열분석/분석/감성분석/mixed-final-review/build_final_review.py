# -*- coding: utf-8 -*-
"""`혼합` 267건 중 아직 사람이 보지 않은 227건 — 최종 검토용 파일 생성

무엇을 하려는 것인가
  전수 결과에서 모델이 `혼합` 이라 답한 267문장은 라벨이 아니라 모델의 회피다.
  사람 지침에는 애초에 `혼합` 범주가 없다 — 지배적 입장으로 단일 판정하고,
  독립된 두 평가가 있을 때만 절로 쪼갠다(`-b` 행).

  267건 중 40건은 `mixed-audit/` 에서 이미 사람이 판정했다(긍정 18 · 부정 7 · 분할 15).
  그 40건은 267건 전체의 구성비를 **추정**하기 위한 층화 표본이었다.
  이번에는 추정으로 끝내지 않고 **남은 227건을 개별 판정해서 라벨을 확정**한다.
  전수 데이터 전체의 라벨 단위를 사람 지침과 같게 맞추기 위한 후처리다.

  이 스크립트는 그 판정을 하지 않는다. 판정할 판을 깔기만 한다.

문맥 — 이 파일의 핵심 규칙
  판정 대상 문장만 떼어 놓으면 생략된 주어·지시어('거기', '그것')를 풀 수 없어
  판정이 흔들린다. 그래서 **같은 `review_id` 안의 바로 이전 문장과 바로 다음 문장**을
  참고용으로 같이 준다.

  문맥은 **의미 해석용 참고자료일 뿐이다.** 감성 라벨은 반드시 판정 대상 문장 자체에
  표현된 평가로 정한다. 주변 문장의 긍정·부정을 대상 문장으로 옮기지 않는다.
      이전 `경치는 정말 좋았습니다.` / 대상 `주차 공간은 많이 부족합니다.`  -> 부정
      이전 `주차하기가 정말 힘들었습니다.` / 대상 `오후 2시에 방문했습니다.` -> 중립

  순서 기준: 같은 `review_id` 안에서 **`sent_no` 를 정수로 정렬한 순서**.
  `sent_no` 는 리뷰마다 1..n_sent 의 연속 정수이고, 사람이 절로 쪼갠 `-b` 행도
  이 번호 체계 안에 이미 편입되어 있다(예: BOOST-0119=4 / BOOST-0119-b=5 / BOOST-0120=6).
  즉 정수 정렬 순서가 곧 현재 분석 단위의 행 순서다. 실행할 때마다 그 전제를 확인한다.
  없는 문맥은 빈칸으로 둔다. 지어내지 않고 다른 리뷰에서 가져오지 않는다.
  원문은 자르거나 다듬지 않고 그대로 옮긴다.

  (2026-08-25 수정) 이전 판은 `sent_no` 를 문자열로 정렬해서 문장이 10개 이상인 리뷰에서
  순서가 1,10,11,...,2 로 뒤집혔다. 227건 중 4건이 그 영향을 받았다.
  지금은 `순번` (sent_no 의 정수형) 으로 정렬한다.

입력 — 읽기만 한다. 절대 쓰지 않는다.
  ../fullscale/전수_문장라벨.csv      5,685문장. 그중 label=='혼합' 267건이 모집단
  ../mixed-audit/혼합40_표본.csv      이미 판정이 끝난 40건의 unit_id (제외 대상)
  ../mixed-audit/혼합40_판정용.xlsx   위 40건과 일치하는지 교차 확인 + 판정 결과 참고 시트
  ../labeling/검증셋_본_라벨링용.xlsx `지침요약` 시트를 그대로 복사한다 (같은 기준을 쓴다)

출력 — mixed-final-review/ 안에만 쓴다. 덮어쓰기 전에 백업/ 으로 원본을 옮겨 둔다.
  혼합227_최종검토용.xlsx   사람이 채운다. `검토` / `판정지침` / `지침요약` / `이미판정40` 시트
  혼합227_대상.csv          227건의 불변 스냅샷. 문맥 검증의 기준값이기도 하다
  gpt_초벌_양식.csv         ChatGPT 초벌 판정을 받아올 빈 양식 (문맥 포함)

설계
  - **GPT 열과 사람 열을 분리한다.** GPT_* 는 초벌, 사람_* 이 최종이다. 한 칸에 덮어쓰면
    나중에 "사람이 GPT를 어디서 뒤집었는가" 를 셀 수 없다. 그 수치가 이 작업의 신뢰도다.
  - **GPT 가 보는 문맥과 사람이 보는 문맥을 같게 맞춘다.** `이전_문장` · `다음_문장` 이
    양쪽에 똑같이 들어간다. 서로 다른 정보를 보고 판정하면 둘을 비교할 수 없다.
  - **`리뷰전체` 는 사람에게만 추가로 준다.** 사람이 최종 결정권자이므로 더 볼 수 있게
    남겨 둔다(문장 4개 이상인 리뷰 38건에서만 인접 2문장과 다르다). GPT 양식에는 넣지 않는다.
  - **분할은 조각 원문과 조각 라벨을 둘 다 받는다.** 분할 판정은 `-b` 행을 만드는 일이라
    조각 원문 없이는 행을 만들 수 없고, 조각 라벨 없이는 그 행에 붙일 label 이 없다.
  - **모델 라벨은 전부 `혼합` 이므로 값 자체에는 정보가 없다.** 그래도 열로 남긴다 —
    이 227건이 어디서 왔는지 파일만 보고 알 수 있어야 한다.
  - **순서를 섞는다.** 관광지·플랫폼이 뭉쳐 있으면 구간별로 기준이 드리프트한다.
    SEED 는 고정이므로 다시 실행해도 `검토_id` -> `unit_id` 대응은 그대로다. 그것도 확인한다.
  - **이미 판정한 40건을 참고 시트로 같이 넣는다.** 같은 모집단에서 나온 기준선이다.

실행:  ../../.venv/Scripts/python.exe mixed-final-review/build_final_review.py
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

SEED = 20260825          # 확정. 바꾸지 않는다
EXPECT_POP = 267         # 모델이 `혼합` 이라 한 전체
EXPECT_DONE = 40         # mixed-audit 에서 이미 판정한 표본
EXPECT_TODO = 227        # 267 - 40

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT_XLSX = HERE / "혼합227_최종검토용.xlsx"
OUT_CSV = HERE / "혼합227_대상.csv"
OUT_FORM = HERE / "gpt_초벌_양식.csv"
BACKUP_DIR = HERE / "백업"

CTX_COLS = ["이전_문장", "다음_문장"]
GPT_COLS = ["GPT_판정", "GPT_분할1", "GPT_분할1_라벨", "GPT_분할2", "GPT_분할2_라벨"]
HUMAN_COLS = ["사람_판정", "사람_분할1", "사람_분할1_라벨", "사람_분할2", "사람_분할2_라벨"]

# GPT 초벌 양식 — 이 순서 그대로 받는다
FORM_COLS = ["검토_id", "unit_id", "이전_문장", "sent", "다음_문장"] + GPT_COLS

# 사람이 채우는 xlsx `검토` 시트
#
# `sent` 를 세 번째 열에 둔다. 사람이 오른쪽 끝의 `사람_판정` 을 채울 때 판정 대상 문장이
# 화면에서 사라지면 227행을 스크롤로 왕복해야 한다. 그래서 검토_id · unit_id · sent 까지
# 세 열을 틀고정한다(freeze_panes="D2"). 문맥 세 열은 sent 바로 오른쪽에 붙여 두어
# 왼쪽 화면에서는 `대상 -> 이전 -> 다음 -> 리뷰전체` 가 한눈에 이어지게 한다.
COLS = (["검토_id", "unit_id", "sent",
         "이전_문장", "다음_문장", "리뷰전체", "place", "platform", "기존_모델라벨"]
        + GPT_COLS + HUMAN_COLS + ["검토상태", "검토메모"])
WIDTHS = [9, 13, 55,
          40, 40, 48, 15, 8, 10,
          10, 32, 11, 32, 11,
          10, 32, 11, 32, 11,
          10, 26]
FREEZE = "D2"        # 검토_id · unit_id · sent 를 고정한다

CAT4 = "긍정,부정,중립,분할"
CAT3 = "긍정,부정,중립"
STATUS = "미검토,확정,수정,보류"

GUIDE = [
    "혼합 227건 최종 검토 — 남은 전건",
    "",
    "(!) 이 227문장은 전부 모델이 `혼합` 이라고 답한 문장이다.",
    "(!) 그 사실은 이 문장을 쪼개야 한다는 뜻이 아니다. 모델이 판단을 회피한 것일 수도 있다.",
    "(!) 같은 모집단에서 먼저 판정한 40건은 긍정 18 · 부정 7 · 분할 15 였다.",
    "(!) 즉 다수는 분할 대상이 아니라 지배적 입장으로 단일 판정되는 문장이다.",
    "(!) 그 40건은 `이미판정40` 시트에 그대로 들어 있다. 새 기준을 만들지 말고 저기에 맞춘다.",
    "",
    "무엇을 하려는 것인가",
    "  267건 중 40건은 이미 끝났고, 남은 227건을 개별 판정해서 라벨을 확정한다.",
    "  추정이 아니라 확정이다. 227칸을 다 채우면 `혼합` 이라는 범주가 데이터에서 사라진다.",
    "  목적은 전수 분석 데이터의 라벨 단위를 사람 지침과 같게 맞추는 것이다.",
    "",
    "판정 대상은 `sent` 열 하나뿐이다 — 문맥은 참고자료다",
    "  `이전_문장` · `다음_문장` 은 같은 리뷰의 바로 앞·뒤 문장이다(회색).",
    "  `리뷰전체` 는 그 리뷰의 모든 문장이고 `▶` 가 판정 대상이다(회색). 사람만 본다.",
    "  문맥은 대상 문장의 생략된 주어·지시어('거기', '그것', '이 가격')를 풀기 위한 것이다.",
    "",
    "  (!) 주변 문장의 감성을 대상 문장으로 옮기지 않는다. 라벨은 `sent` 안에 실제로",
    "      표현된 평가로만 정한다.",
    "      이전 `경치는 정말 좋았습니다.` / 대상 `주차 공간은 많이 부족합니다.`  -> 부정",
    "      이전 `주차하기가 정말 힘들었습니다.` / 대상 `오후 2시에 방문했습니다.` -> 중립",
    "      뒤 문장이 `그래도 또 오고 싶어요` 여도 대상이 불만이면 대상은 부정이다.",
    "",
    "  문맥 칸이 비어 있으면 그 자리에 문장이 없다는 뜻이다(리뷰의 첫 문장 · 마지막 문장 ·",
    "  한 문장짜리 리뷰). 227건 중 문맥이 아예 없는 문장이 117건이다. 지어내지 않는다.",
    "",
    "판정 범주는 네 개뿐이다 — 긍정 / 부정 / 중립 / 분할",
    "  `혼합` · `애매` · `모름` 은 쓰지 않는다. 그 범주를 없애려고 하는 작업이다.",
    "  두 번 읽어도 안 정해지면 `검토상태` 를 보류 로 두고 넘어간다. 이때는 사람_판정 에",
    "  현재 가장 그럴듯한 값을 적어 둔다. 전부 끝낸 다음 보류만 모아서 다시 본다.",
    "",
    "판정 순서 — `지침요약` 시트와 동일하다. 여기서는 그 중 1번만 다시 적는다.",
    "  1. 한 문장 안에 명시적 긍정과 명시적 부정이 둘 다 있으면 그 자리에서 절로 나눈다.",
    "     '-지만/-으나' 가 있다는 이유만으로는 쪼개지 않는다. 한쪽이 사실 진술이면 그대로 둔다.",
    "  나머지(중립 · 강도 무시 · 상투어)와 이미 결정된 경계 사례는 `지침요약` 시트를 본다.",
    "  판단이 갈리면 지침요약의 경계 사례가 우선한다. 새 규칙을 여기서 만들지 않는다.",
    "",
    "쪼개지 않는 것으로 이미 정해진 유형 — 이 227건에 특히 많다",
    "  외부 요인('날이 더워서', '비가 와서', '수위가 낮아', '사람이 많아')",
    "     -> 관광지에 대한 평가가 아니다. 지배적 입장으로 단일 판정한다.",
    "     예: `더운거 빼고 좋음` -> 긍정 (검증셋 사람 판정)",
    "  반사실 아쉬움('맑았으면 더 좋았을텐데', '~였으면 좋았을')",
    "     -> 지금 있는 것에 대한 불만이 아니다. 뒤쪽 실제 평가를 따른다.",
    "  사실 + 평가('입장료 3000원이지만 돈이 아깝지 않았어요') -> 긍정, 쪼개지 않음",
    "  개선 요구('~해주면 좋겠어요') -> 부정 (단일). 지금 없는 것을 요구하고 있는가로 판별.",
    "",
    "칸 채우는 법 — 동의하면 `확정` 만 누르면 된다",
    "",
    "  GPT_* 는 ChatGPT 초벌 판정이다. **덮어쓰지 않는다.** 그 값이 남아 있어야",
    "  나중에 사람이 어디서 몇 건을 뒤집었는지 셀 수 있다. 그 수치가 이 작업의 근거다.",
    "",
    "  (!) GPT 판정에 동의하면 `검토상태` 를 `확정` 으로만 바꾸고 `사람_*` 은 비워 둔다.",
    "      같은 값을 227번 다시 적을 필요가 없다. 특히 분할 건은 조각 원문을 옮겨 적다가",
    "      틀리기 쉬운데, GPT 조각은 이미 원문과 정확히 일치함이 검증돼 있다.",
    "",
    "  검토상태   사람_판정      최종 라벨이 되는 값",
    "  ------------------------------------------------------------------",
    "  확정       비움           GPT_판정 (분할이면 GPT_분할1/2 와 그 라벨)",
    "  확정       채움           사람_판정 — 단 GPT_판정 과 같아야 한다",
    "  수정       채움 (필수)    사람_판정 (분할이면 사람_분할1/2 도 채운다)",
    "  보류       채움 (필수)    사람_판정 — 잠정값. 전부 끝낸 뒤 다시 본다",
    "  미검토     —              아직 정해지지 않았다",
    "",
    "  `확정` 은 `읽고 나서 동의했다` 는 뜻이다. 안 읽은 행은 `미검토` 로 남겨 둔다.",
    "  둘을 구분해야 몇 건을 실제로 사람이 봤는지 나중에 말할 수 있다.",
    "  GPT 와 다르게 판정했으면 `확정` 이 아니라 `수정` 이다. 그래야 뒤집은 건수가 잡힌다.",
    "",
    "  뒤집을 때만 채우는 칸",
    "    사람_판정        긍정 / 부정 / 중립 / 분할  (드롭다운)",
    "    사람_분할1       판정=분할 일 때만. **앞 조각의 원문을 그대로 붙여넣는다.**",
    "    사람_분할1_라벨  앞 조각의 라벨 (긍정 / 부정 / 중립)",
    "    사람_분할2       판정=분할 일 때만. **뒤 조각의 원문을 그대로 붙여넣는다.**",
    "    사람_분할2_라벨  뒤 조각의 라벨 (긍정 / 부정 / 중립)",
    "    검토메모         자유. 판단이 애매했던 이유를 남기면 지침 보완에 쓴다.",
    "",
    "  분할 -> 단일 로 되돌릴 때는 사람_판정 만 적고 사람_분할* 은 비워 둔다.",
    "",
    "  분할은 `sent` 안에서만 쪼갠다. 이전·다음 문장은 이미 다른 행이므로 끌어오지 않는다.",
    "  분할1 + 분할2 를 이어 붙이면 `sent` 원문이 되어야 한다. 말을 지어내거나 다듬지 않는다.",
    "  기존 사람 분할 행과 같은 구조를 만드는 것이다 — 앞 조각은 원래 unit_id 를 그대로 쓰고",
    "  뒤 조각이 `<unit_id>-b` 가 된다 (예: MAIN-0094 / MAIN-0094-b).",
    "",
    "작업 요령",
    "  - 시작 전에 `지침요약` 과 `이미판정40` 시트를 처음부터 끝까지 읽는다.",
    "  - 세션을 나눌 때마다 위 두 시트를 다시 읽는다. 227건은 한 번에 끝나지 않는다.",
    "  - 처음 30문장은 마지막에 다시 검토한다(기준이 굳기 전에 매긴 라벨).",
    "  - 지침을 바꿔야 하면 라벨링을 멈추고 지침서를 먼저 고친 뒤 앞으로 돌아가 맞춘다.",
    "  - GPT 판정에 끌려가는 것을 경계한다. 원문과 문맥을 먼저 읽고 나서 GPT 칸을 본다.",
    "",
    "전체 지침서: reference/0001-라벨링-지침서.html",
]


def fail(msg):
    sys.exit(f"[중단] {msg}")


def backup_existing():
    """덮어쓰기 전에 현재 산출물을 백업/<타임스탬프>/ 로 복사해 둔다."""
    targets = [p for p in (OUT_XLSX, OUT_CSV, OUT_FORM) if p.exists()]
    if not targets:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for p in targets:
        shutil.copy2(p, dest / p.name)
    return dest


def style_review_sheet(ws, nrows):
    """`검토` 시트의 열 너비 · 틀고정 · 색 · 드롭다운을 입힌다.

    `relayout_review.py` 도 이 함수를 불러 쓴다. 서식 규칙이 두 군데로 갈라지면
    파일을 다시 만들 때마다 화면이 달라진다.
    """
    head = {c: i for i, c in enumerate(COLS, start=1)}
    for i, width in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = FREEZE          # 검토_id · unit_id · sent 는 스크롤해도 남는다
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDDDDD")
    for c in CTX_COLS + ["리뷰전체"]:                     # 참고 문맥 = 회색
        ws.cell(row=1, column=head[c]).fill = PatternFill("solid", fgColor="BFBFBF")
    ws.cell(row=1, column=head["sent"]).fill = PatternFill("solid", fgColor="FFF2CC")
    for c in GPT_COLS:                                    # GPT 초벌 = 노랑
        ws.cell(row=1, column=head[c]).fill = PatternFill("solid", fgColor="FFE59A")
    for c in HUMAN_COLS + ["검토상태", "검토메모"]:         # 사람 최종 = 초록
        ws.cell(row=1, column=head[c]).fill = PatternFill("solid", fgColor="C6E0B4")

    # 판정 대상은 굵게 + 좌우 굵은 테두리, 참고 문맥은 회색 이탤릭 — 한눈에 갈린다
    grey = Font(color="808080", italic=True)
    edge = Side(style="medium")
    for row in ws.iter_rows(min_row=2, max_row=nrows + 1):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
        for name in CTX_COLS + ["리뷰전체"]:
            row[head[name] - 1].font = grey
        tgt = row[head["sent"] - 1]
        tgt.font = Font(bold=True)
        tgt.fill = PatternFill("solid", fgColor="FFFDF0")
        tgt.border = Border(left=edge, right=edge)

    last = nrows + 1
    dv4 = DataValidation(type="list", formula1=f'"{CAT4}"', allow_blank=True)
    dv3 = DataValidation(type="list", formula1=f'"{CAT3}"', allow_blank=True)
    dvs = DataValidation(type="list", formula1=f'"{STATUS}"', allow_blank=True)
    for dv in (dv4, dv3, dvs):
        ws.add_data_validation(dv)
    for c in ("GPT_판정", "사람_판정"):
        col = get_column_letter(head[c])
        dv4.add(f"{col}2:{col}{last}")
    for c in ("GPT_분할1_라벨", "GPT_분할2_라벨", "사람_분할1_라벨", "사람_분할2_라벨"):
        col = get_column_letter(head[c])
        dv3.add(f"{col}2:{col}{last}")
    col = get_column_letter(head["검토상태"])
    dvs.add(f"{col}2:{col}{last}")


def main():
    full = pd.read_csv(ROOT / "fullscale" / "전수_문장라벨.csv",
                       encoding="utf-8-sig", dtype=str)
    full["순번"] = full["sent_no"].astype(int)

    # 문맥의 전제: sent_no 가 리뷰마다 1..n_sent 의 연속 정수여야 인접 문장을 정의할 수 있다.
    for rid, g in full.groupby("review_id"):
        if sorted(g["순번"]) != list(range(1, len(g) + 1)) or int(g["n_sent"].iloc[0]) != len(g):
            fail(f"리뷰 {rid} 의 sent_no 가 1..n_sent 연속이 아니다 — 인접 문장을 정의할 수 없다.")

    pop = full[full["label"] == "혼합"].copy()
    if len(pop) != EXPECT_POP:
        fail(f"`혼합` 이 {len(pop)}건이다 — {EXPECT_POP}건을 기대했다. "
             "전수 결과가 다시 만들어진 것인지 확인한다.")

    done = pd.read_csv(ROOT / "mixed-audit" / "혼합40_표본.csv",
                       encoding="utf-8-sig", dtype=str)
    done_ids = set(done["unit_id"])
    if len(done_ids) != EXPECT_DONE:
        fail(f"이미 판정한 표본이 {len(done_ids)}건이다 — {EXPECT_DONE}건을 기대했다.")

    audit = pd.read_excel(ROOT / "mixed-audit" / "혼합40_판정용.xlsx", sheet_name="판정")
    if set(audit["unit_id"].astype(str)) != done_ids:
        fail("혼합40_표본.csv 와 혼합40_판정용.xlsx 의 unit_id 가 다르다.")
    missing = done_ids - set(pop["unit_id"])
    if missing:
        fail(f"이미 판정한 40건 중 {len(missing)}건이 267건 안에 없다: {sorted(missing)[:5]}")

    todo = pop[~pop["unit_id"].isin(done_ids)].copy()
    if len(todo) != EXPECT_TODO:
        fail(f"남은 건수가 {len(todo)}건이다 — {EXPECT_TODO}건을 기대했다.")

    # ---------- 문맥 ----------
    # 같은 review_id 안에서 sent_no 정수 정렬. 바로 앞 = _n-1, 바로 뒤 = _n+1.
    by_review = {rid: g.sort_values("순번") for rid, g in full.groupby("review_id")}
    at = {(r.review_id, r.순번): r.sent
          for r in full[["review_id", "sent", "순번"]].itertuples()}

    def prev_sent(row):
        return at.get((row.review_id, row.순번 - 1), "")

    def next_sent(row):
        return at.get((row.review_id, row.순번 + 1), "")

    def whole_review(row):
        g = by_review[row.review_id]
        if len(g) == 1:
            return "(리뷰에 이 문장 하나뿐)"
        return "\n".join(("▶ " if u == row.unit_id else "   ") + str(s)
                         for u, s in zip(g.unit_id, g.sent))

    todo["이전_문장"] = [prev_sent(r) for r in todo.itertuples()]
    todo["다음_문장"] = [next_sent(r) for r in todo.itertuples()]
    todo["리뷰전체"] = [whole_review(r) for r in todo.itertuples()]

    # 문맥이 규칙대로 만들어졌는지 그 자리에서 다시 검산한다
    same_review = {rid: set(g["sent"]) for rid, g in by_review.items()}
    for r in todo.itertuples():
        g = by_review[r.review_id]
        want_p = at.get((r.review_id, r.순번 - 1), "")
        want_x = at.get((r.review_id, r.순번 + 1), "")
        if r.이전_문장 != want_p or r.다음_문장 != want_x:
            fail(f"{r.unit_id}: 인접 문장이 규칙과 다르다.")
        for c in (r.이전_문장, r.다음_문장):
            if c and c not in same_review[r.review_id]:
                fail(f"{r.unit_id}: 문맥이 같은 리뷰의 문장이 아니다.")
        if (r.순번 == 1) != (r.이전_문장 == ""):
            fail(f"{r.unit_id}: 첫 문장인데 이전 문맥이 있거나, 아닌데 비어 있다.")
        if (r.순번 == len(g)) != (r.다음_문장 == ""):
            fail(f"{r.unit_id}: 마지막 문장인데 다음 문맥이 있거나, 아닌데 비어 있다.")

    todo = todo.sample(frac=1, random_state=SEED).reset_index(drop=True)
    todo["검토_id"] = [f"M{i:03d}" for i in range(1, len(todo) + 1)]
    todo["기존_모델라벨"] = todo["label"]

    # 다시 만들어도 검토_id -> unit_id 대응이 그대로인지 (SEED 고정의 의미)
    if OUT_CSV.exists():
        old = pd.read_csv(OUT_CSV, encoding="utf-8-sig", dtype=str)
        new_map = dict(zip(todo["검토_id"], todo["unit_id"]))
        if dict(zip(old["검토_id"], old["unit_id"])) != new_map:
            fail("검토_id -> unit_id 대응이 이전 스냅샷과 달라졌다. SEED 나 모집단이 바뀌었다.")
        if list(old["sent"]) != list(todo["sent"]):
            fail("대상 문장이 이전 스냅샷과 달라졌다.")

    dest = backup_existing()

    todo[["검토_id", "unit_id", "review_id", "place", "platform", "sent_no", "n_sent",
          "이전_문장", "sent", "다음_문장", "기존_모델라벨"]].to_csv(
        OUT_CSV, index=False, encoding="utf-8-sig")

    form = todo.reindex(columns=FORM_COLS)
    form[GPT_COLS] = ""
    form.to_csv(OUT_FORM, index=False, encoding="utf-8-sig")

    sheet = todo.reindex(columns=COLS)
    sheet[GPT_COLS + HUMAN_COLS] = ""
    sheet["검토상태"] = "미검토"
    sheet["검토메모"] = ""

    guide = pd.read_excel(ROOT / "labeling" / "검증셋_본_라벨링용.xlsx",
                          sheet_name="지침요약", header=None)
    ref40 = audit[["판정_id", "unit_id", "place", "platform", "sent",
                   "판정", "분할_앞", "분할_뒤", "분할_경계"]].copy()

    try:
        writer = pd.ExcelWriter(OUT_XLSX, engine="openpyxl")
    except PermissionError:
        fail(f"{OUT_XLSX.name} 를 쓸 수 없다. Excel 에서 열려 있으면 닫고 다시 실행한다.")

    with writer as w:
        sheet.to_excel(w, sheet_name="검토", index=False)
        pd.DataFrame(GUIDE).to_excel(w, sheet_name="판정지침", index=False, header=False)
        guide.to_excel(w, sheet_name="지침요약", index=False, header=False)
        ref40.to_excel(w, sheet_name="이미판정40", index=False)

        style_review_sheet(w.sheets["검토"], len(sheet))

        wg = w.sheets["판정지침"]
        wg.column_dimensions["A"].width = 100
        for i in (1, 3, 4, 5, 6, 7):
            wg.cell(row=i, column=1).font = Font(bold=True)

        wr = w.sheets["이미판정40"]
        for i, width in enumerate([9, 13, 16, 9, 58, 8, 8, 8, 40], start=1):
            wr.column_dimensions[get_column_letter(i)].width = width
        for c in wr[1]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="DDDDDD")
        for row in wr.iter_rows(min_row=2, max_row=len(ref40) + 1):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")

    both = ((todo.이전_문장 != "") & (todo.다음_문장 != "")).sum()
    p_only = ((todo.이전_문장 != "") & (todo.다음_문장 == "")).sum()
    n_only = ((todo.이전_문장 == "") & (todo.다음_문장 != "")).sum()
    none = ((todo.이전_문장 == "") & (todo.다음_문장 == "")).sum()

    print(f"모집단 `혼합` {len(pop)}건 · 이미 판정 {len(done_ids)}건 -> 남은 {len(todo)}건")
    print(f"  이미 판정 40건 구성: {audit['판정'].value_counts().to_dict()}")
    print(f"  플랫폼 {todo.platform.value_counts().to_dict()}")
    print(f"  관광지 상위 {todo.place.value_counts().head(4).to_dict()}")
    print(f"\n문맥 (같은 review_id 의 바로 앞·뒤 문장)")
    print(f"  둘 다 있음 {both} · 이전만 {p_only} · 다음만 {n_only} · 없음 {none}"
          f"  합 {both + p_only + n_only + none}")
    print(f"  리뷰 {todo.review_id.nunique()}개 · 한 문장짜리 리뷰 "
          f"{(todo.리뷰전체 == '(리뷰에 이 문장 하나뿐)').sum()}건")
    if dest:
        print(f"\n이전 산출물 백업: 백업/{dest.name}/")
    print(f"출력: {OUT_XLSX.name} · {OUT_CSV.name} · {OUT_FORM.name}")
    print("다음: gpt_초벌_양식.csv 로 ChatGPT 초벌 판정을 받은 뒤 apply_gpt_draft.py")


if __name__ == "__main__":
    main()
