# -*- coding: utf-8 -*-
"""`혼합` 267문장 층화 표본 40건 판정용 파일 생성

무엇을 하려는 것인가
  전수 결과에서 모델이 `혼합`이라 답한 267문장(4.7%)은 라벨이 아니라 **모델의 회피**다.
  이 연구의 사람 지침에는 애초에 `혼합` 이라는 범주가 없다 — 지배적 입장으로 단일
  판정하고, 독립된 두 평가가 있을 때만 절로 쪼갠다(지침 판정순서 1).

  267건을 전수로 쪼개면 지침보다 공격적인 규칙을 전체의 4.7%에만 적용하게 되어
  나머지 95.3%, 그리고 macro-F1 0.906의 근거였던 사람 라벨 698문장과 기준이 어긋난다.
  그래서 **쪼개는 것이 아니라 판정한다.** 40건만 지침대로 판정해서 267건 전체의
  구성비를 추정하면, 부정 비율을 4.7pp 범위가 아니라 약 1.3pp 폭으로 낼 수 있다.

  근거: 검증셋에서 모델이 `혼합` 이라 한 12문장을 사람은 긍정 8 · 부정 4 · 분할 0 으로
  판정했다. 12건은 너무 적어서 그대로 쓸 수 없다. 그래서 40건을 다시 본다.

입력 — 읽기만 한다.
  output/sentiment/fullscale/전수_문장라벨.csv          5,685문장. 그중 label=='혼합' 인 267건이 모집단
  input/sentiment/labeling/검증셋_본_라벨링용.xlsx      `지침요약` 시트를 그대로 복사한다 (같은 기준을 쓴다)

출력 — output/sentiment/mixed_audit/
  혼합40_판정용.xlsx    사람이 채운다
  혼합40_표본.csv       추출 결과 + 층 정보. 추정 스크립트가 읽는다

설계
  - **층화**: 플랫폼 x 관광지그룹(붕어섬 · 치즈테마파크 · 출렁다리 · 기타).
    267건 중 상위 3곳이 218건(82%)이고 플랫폼별 부정률 차이가 크다(구글 20.1% vs 네이버 10.9%).
    단순 무작위로 뽑으면 이 구성이 표본에서 흔들려 추정치가 같이 흔들린다.
    모집단 10건 미만인 층은 같은 플랫폼의 `기타` 로 합친다 — 층이 1~2건이면
    층 내 분산을 추정할 수 없어 신뢰구간이 오히려 나빠진다.
  - **비례배분 + 최대잉여법**으로 40건을 나눈다. 층별 추출확률이 다르므로
    추정할 때 반드시 가중치(N_h/n_h)를 쓴다 — `혼합40_표본.csv` 의 `가중치` 열.
  - **문맥을 같이 보여준다.** 같은 리뷰의 다른 문장 없이는 판정이 달라진다
    (`src/sentiment/labeling/build_relabel.py` 와 같은 이유).
  - **모델 예측을 시트에 넣지 않는다.** 40건 전부 모델이 `혼합` 이라 한 것이라는 사실은
    판정지침에 밝히되, "모델이 혼합이라 했으니 쪼개야 한다" 로 읽히면 측정하려던
    것을 측정하지 못한다. 그래서 지침 맨 위에 경고로 넣는다.
  - **순서를 섞는다.** 관광지·플랫폼이 뭉쳐 있으면 구간별로 기준이 드리프트한다.

실행:  python src/sentiment/mixed_audit/build_mixed_audit.py
"""
import sys
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

SEED = 20260824      # 확정. 바꾸지 않는다
N = 40
MIN_STRATUM = 10     # 모집단이 이보다 작은 층은 같은 플랫폼 `기타` 로 합친다
TOP3 = ["붕어섬생태공원", "임실치즈테마파크", "옥정호출렁다리"]

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_IN, SENT_OUT  # noqa: E402
# 기록용 코드다. 사람이 판정한 표는 input/sentiment/mixed_audit/ 에 있고,
# 다시 돌리면 빈 판정표가 output/sentiment/mixed_audit/ 에 새로 생긴다.
OUT_DIR = SENT_OUT / "mixed_audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_XLSX = OUT_DIR / "혼합40_판정용.xlsx"
OUT_CSV = OUT_DIR / "혼합40_표본.csv"

COLS = ["판정_id", "unit_id", "place", "platform", "sent", "문맥",
        "판정", "분할_앞", "분할_뒤", "분할_경계", "hold", "note"]
WIDTHS = [9, 13, 16, 9, 58, 58, 10, 10, 10, 40, 7, 26]

GUIDE = [
    "혼합 267건 판정 — 40건 층화 표본",
    "",
    "(!) 이 40문장은 전부 모델이 `혼합` 이라고 답한 문장이다.",
    "(!) 그 사실은 이 문장을 쪼개야 한다는 뜻이 아니다. 모델이 판단을 회피한 것일 수도 있다.",
    "(!) 검증셋에서 모델이 혼합이라 한 12문장 중 사람이 실제로 쪼갠 것은 0건이었고,",
    "(!) 8건은 그냥 긍정, 4건은 그냥 부정이었다. 지침 그대로 판정하면 된다.",
    "",
    "무엇을 재려는 것인가",
    "  267건이 사람 기준으로 긍정 / 부정 / 중립 / 분할 로 각각 몇 %인지.",
    "  이 40건의 구성비로 267건 전체를 추정하고, 전체 부정 비율의 범위를 좁힌다.",
    "  그러므로 판정을 '반반이니 분할' 쪽으로 몰면 추정치가 그만큼 위로 틀어진다.",
    "",
    "판정 순서 — `지침요약` 시트와 동일하다. 여기서는 그 중 1번만 다시 적는다.",
    "  1. 한 문장 안에 명시적 긍정과 명시적 부정이 둘 다 있으면 그 자리에서 절로 나눈다.",
    "     '-지만/-으나' 가 있다는 이유만으로는 쪼개지 않는다. 한쪽이 사실 진술이면 그대로 둔다.",
    "  나머지(중립 · 강도 무시 · 상투어 · hold)와 이미 결정된 경계 사례는 `지침요약` 시트를 본다.",
    "  판단이 갈리면 지침요약의 경계 사례가 우선한다. 새 규칙을 여기서 만들지 않는다.",
    "",
    "쪼개지 않는 것으로 이미 정해진 유형 — 267건에 특히 많다",
    "  외부 요인('날이 더워서', '비가 와서', '수위가 낮아', '사람이 많아')",
    "     -> 관광지에 대한 평가가 아니다. 지배적 입장으로 단일 판정한다.",
    "     예: `더운거 빼고 좋음` -> 긍정 (검증셋 사람 판정)",
    "  반사실 아쉬움('맑았으면 더 좋았을텐데', '~였으면 좋았을')",
    "     -> 지금 있는 것에 대한 불만이 아니다. 뒤쪽 실제 평가를 따른다.",
    "  사실 + 평가('입장료 3000원이지만 돈이 아깝지 않았어요') -> 긍정, 쪼개지 않음",
    "  개선 요구('~해주면 좋겠어요') -> 부정 (단일). 지금 없는 것을 요구하고 있는가로 판별.",
    "",
    "칸 채우는 법",
    "  판정      긍정 / 부정 / 중립 / 분할   (드롭다운. 40칸 전부 채운다)",
    "  분할_앞   판정=분할 일 때만. 앞 조각의 라벨",
    "  분할_뒤   판정=분할 일 때만. 뒤 조각의 라벨",
    "  분할_경계 판정=분할 일 때만. **앞 조각의 원문을 그대로 붙여넣는다.**",
    "            나중에 요인 분석에서 이 조각을 실제로 만들 때 쓴다.",
    "  hold      두 번 읽어도 안 정해지면 Y. 전부 끝낸 뒤 모아서 처리한다.",
    "  note      자유. 판단이 애매했던 이유를 남기면 지침 보완에 쓴다.",
    "",
    "작업 요령",
    "  - 40건은 한 번에 끝낸다. 나누면 기준이 드리프트해서 40건짜리 표본에는 치명적이다.",
    "  - 시작 전에 `지침요약` 시트를 처음부터 끝까지 읽는다.",
    "  - 다 채운 뒤: input/sentiment/mixed_audit/ 에 둔다. 다음 단계는 src/sentiment/mixed_final_review/ (267건 전수 확정).",
    "",
    "전체 지침서: docs/sentiment/0001-라벨링-지침서.html",
]


def allocate(sizes, n):
    """비례배분 + 최대잉여법. {층: 배정수} 를 돌려준다."""
    total = sum(sizes.values())
    raw = {k: v * n / total for k, v in sizes.items()}
    base = {k: int(v) for k, v in raw.items()}
    rest = n - sum(base.values())
    for k in sorted(raw, key=lambda k: (-(raw[k] - base[k]), k))[:rest]:
        base[k] += 1
    return base


def main():
    full = pd.read_csv(SENT_OUT / "fullscale" / "전수_문장라벨.csv",
                       encoding="utf-8-sig", dtype=str)
    pop = full[full["label"] == "혼합"].copy()
    if len(pop) == 0:
        sys.exit("혼합 문장이 없다 — 전수_문장라벨.csv 를 확인한다")

    # 층 만들기: 플랫폼 x 관광지그룹, 작은 층은 같은 플랫폼 `기타` 로 흡수
    grp = pop["place"].where(pop["place"].isin(TOP3), "기타")
    pop["층"] = pop["platform"] + "·" + grp
    small = [s for s, c in pop["층"].value_counts().items() if c < MIN_STRATUM]
    if small:
        pop["층"] = pop["층"].where(~pop["층"].isin(small),
                                   pop["platform"] + "·기타")
        print(f"모집단 {MIN_STRATUM}건 미만이라 합친 층: {', '.join(sorted(small))}")

    sizes = pop["층"].value_counts().to_dict()
    alloc = allocate(sizes, N)

    picks = [pop[pop["층"] == s].sample(k, random_state=SEED)
             for s, k in sorted(alloc.items())]
    pick = pd.concat(picks, ignore_index=True)
    pick["N_h"] = pick["층"].map(sizes)
    pick["n_h"] = pick["층"].map(alloc)
    pick["가중치"] = pick["N_h"] / pick["n_h"]

    # 같은 리뷰의 문장을 이어 붙이고 대상 문장에만 화살표를 단다 (모델 라벨은 넣지 않는다)
    by_review = {rid: g.sort_values("sent_no") for rid, g in full.groupby("review_id")}

    def context(row):
        g = by_review[row.review_id]
        if len(g) == 1:
            return "(리뷰에 이 문장 하나뿐)"
        return "\n".join(("▶ " if u == row.unit_id else "   ") + str(s)
                         for u, s in zip(g.unit_id, g.sent))

    pick["문맥"] = [context(r) for r in pick.itertuples()]
    pick = pick.sample(frac=1, random_state=SEED).reset_index(drop=True)
    pick["판정_id"] = [f"A{i:02d}" for i in range(1, len(pick) + 1)]

    pick[["판정_id", "unit_id", "review_id", "place", "platform",
          "층", "N_h", "n_h", "가중치", "sent"]].to_csv(
        OUT_CSV, index=False, encoding="utf-8-sig")

    sheet = pick.reindex(columns=COLS).fillna("")
    guide = pd.read_excel(SENT_IN / "labeling" / "검증셋_본_라벨링용.xlsx",
                          sheet_name="지침요약", header=None)

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as w:
        sheet.to_excel(w, sheet_name="판정", index=False)
        pd.DataFrame(GUIDE).to_excel(w, sheet_name="판정지침",
                                     index=False, header=False)
        guide.to_excel(w, sheet_name="지침요약", index=False, header=False)

        ws = w.sheets["판정"]
        for i, width in enumerate(WIDTHS, start=1):
            ws.column_dimensions[get_column_letter(i)].width = width
        ws.freeze_panes = "E2"
        for c in ws[1]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="DDDDDD")
        for ref in ("G1", "H1", "I1", "J1"):          # 사람이 채우는 칸
            ws[ref].fill = PatternFill("solid", fgColor="FFE59A")
        for row in ws.iter_rows(min_row=2, max_row=len(sheet) + 1):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")

        last = len(sheet) + 1
        dv4 = DataValidation(type="list", formula1='"긍정,부정,중립,분할"',
                             allow_blank=True)
        dv3 = DataValidation(type="list", formula1='"긍정,부정,중립"',
                             allow_blank=True)
        ws.add_data_validation(dv4)
        ws.add_data_validation(dv3)
        dv4.add(f"G2:G{last}")
        dv3.add(f"H2:I{last}")

        wg = w.sheets["판정지침"]
        wg.column_dimensions["A"].width = 100
        for i in (1, 3, 4, 5, 6):
            wg.cell(row=i, column=1).font = Font(bold=True)

    print(f"\n모집단 혼합 {len(pop)}문장 -> {len(pick)}문장 추출 (seed {SEED})")
    print(f"  리뷰 {pick.review_id.nunique()}개 · 문맥 있는 문장 "
          f"{(~pick.문맥.str.startswith('(')).sum()}건")
    print(f"  플랫폼 {pick.platform.value_counts().to_dict()}\n")
    tbl = (pd.DataFrame({"모집단 N_h": sizes, "표본 n_h": alloc})
             .assign(가중치=lambda t: (t["모집단 N_h"] / t["표본 n_h"]).round(2))
             .sort_index())
    print(tbl.to_string())
    print(f"\n출력: {OUT_XLSX.name} · {OUT_CSV.name}")
    print("다음: xlsx `판정` 시트 G열을 40칸 모두 채운 뒤 estimate_mixed.py")


if __name__ == "__main__":
    main()
