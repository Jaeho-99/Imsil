# -*- coding: utf-8 -*-
"""
검증셋 라벨링 파일 생성 (2강 7절 설계)

  본 검증셋   : 리뷰 300건 무작위(플랫폼 층화) -> 문장 단위로 분해
  부정 보강셋 : 구글 별점 1~3점 리뷰 70건 추가 (본 검증셋과 중복 없음)

설계상 지켜야 할 것
  - 라벨링 파일에는 rating을 넣지 않는다(앵커링 방지). 별점은 _대조표에만 보관하고
    라벨링이 끝난 뒤 review_id로 다시 붙인다.
  - 순서는 무작위로 섞되, 같은 리뷰의 문장은 붙여 둔다(문맥 없이 라벨할 수 없기 때문).
  - 부정 보강셋의 '그물'로 별점만 쓴다. 부정어 키워드로 뽑으면 사전 기반 방식의
    재현율을 인위적으로 부풀리게 되므로 절대 쓰지 않는다.
  - 두 세트의 수치는 합치지 않는다.

실행:  ../../.venv/Scripts/python.exe build_labeling_set.py

주의: 지금 다시 돌리면 문장부호 조각 6개가 사라져 unit_id가 밀린다.
     라벨링 중인 xlsx와 어긋나므로, 라벨링이 끝나기 전에는 실행하지 않는다.
"""
import re
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from textsplit import split_sentences  # 문장 분리는 여기 한 곳에서만 정의한다

SEED = 20260820
HERE = Path(__file__).resolve().parent
SRC = HERE.parent.parent / "data" / "임실군_관광지_리뷰데이터_1차전처리.csv"

N_MAIN = 300          # 본 검증셋 리뷰 수
N_BOOST = 70          # 부정 보강셋 리뷰 수
BOOST_MAX_RATING = 3  # 구글 별점 1~3점을 '그물'로 사용

BOILER = {
    "좋아요", "좋습니다", "좋네요", "좋았어요", "넘좋아요", "너무좋아요", "아주좋아요",
    "완전좋아요", "조아요", "좋아용", "굿", "굳", "굿굿", "굿굿굿", "최고", "만족합니다",
    "멋져요", "괜찮아요", "좋아", "좋았습니다", "좋음",
}


def norm(s: str) -> str:
    return re.sub(r"[\s.!~^,?]+", "", s)


def load():
    df = pd.read_csv(SRC, encoding="utf-8-sig")
    df["body"] = df["body"].fillna("").astype(str).str.strip()
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df = df[df["body"] != ""].copy()
    # reviewId가 비거나 중복일 때를 대비한 안정적인 키
    df = df.reset_index(drop=True)
    df["review_id"] = df["reviewId"].fillna("").astype(str)
    blank = df["review_id"] == ""
    df.loc[blank, "review_id"] = "ROW" + df.index[blank].astype(str)
    dup = df["review_id"].duplicated(keep=False)
    df.loc[dup, "review_id"] = df.loc[dup, "review_id"] + "_" + df.index[dup].astype(str)
    return df


def sample_main(df):
    """플랫폼 비율에 비례해 리뷰 300건. 관광지별 층화는 하지 않는다 —
    실제 분포를 그대로 추정하는 것이 본 검증셋의 목적이기 때문."""
    n_g = round(N_MAIN * (df.platform == "구글").sum() / len(df))
    n_n = N_MAIN - n_g
    g = df[df.platform == "구글"].sample(n_g, random_state=SEED)
    n = df[df.platform == "네이버"].sample(n_n, random_state=SEED)
    return pd.concat([g, n])


def sample_boost(df, exclude_ids):
    pool = df[(df.platform == "구글") & (df.rating <= BOOST_MAX_RATING)
              & (~df.review_id.isin(exclude_ids))]
    return pool.sample(min(N_BOOST, len(pool)), random_state=SEED)


def to_units(reviews, tag):
    """리뷰 -> 문장 단위 행. 리뷰 순서는 섞되 리뷰 내부 문장 순서는 유지."""
    order = reviews.sample(frac=1, random_state=SEED + 1)
    rows = []
    for _, r in order.iterrows():
        sents = split_sentences(r["body"])
        for i, s in enumerate(sents, start=1):
            rows.append({
                "unit_id": None,
                "set": tag,
                "review_id": r["review_id"],
                "sent_no": i,
                "n_sent": len(sents),
                "place": r["place"],
                "platform": r["platform"],
                "sent": s,
                "label": "",
                "is_boilerplate": "Y" if norm(s) in BOILER else "",
                "is_split": "",
                "hold": "",
                "note": "",
            })
    out = pd.DataFrame(rows)
    out["unit_id"] = [f"{tag}-{i:04d}" for i in range(1, len(out) + 1)]
    return out


def write_xlsx(units, path, title):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "라벨링"

    cols = list(units.columns)
    ws.append(cols)
    for _, r in units.iterrows():
        ws.append([r[c] for c in cols])

    head_fill = PatternFill("solid", fgColor="1A1A18")
    for c in range(1, len(cols) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True, color="FDFCF8")
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    widths = {"unit_id": 12, "set": 8, "review_id": 10, "sent_no": 7, "n_sent": 7,
              "place": 18, "platform": 9, "sent": 78, "label": 9,
              "is_boilerplate": 13, "is_split": 9, "hold": 7, "note": 24}
    for i, c in enumerate(cols, start=1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(c, 12)

    sent_col = get_column_letter(cols.index("sent") + 1)
    for row in ws.iter_rows(min_row=2, min_col=cols.index("sent") + 1,
                            max_col=cols.index("sent") + 1):
        row[0].alignment = Alignment(wrap_text=True, vertical="top")

    last = len(units) + 1
    def dv(colname, formula, prompt):
        letter = get_column_letter(cols.index(colname) + 1)
        v = DataValidation(type="list", formula1=formula, allow_blank=True,
                           showDropDown=False, promptTitle=colname, prompt=prompt)
        ws.add_data_validation(v)
        v.add(f"{letter}2:{letter}{last}")

    dv("label", '"긍정,부정,중립"', "규칙: 평가어 없으면 중립. 강도는 보지 않는다.")
    dv("is_boilerplate", '"Y"', "상투어 단독 문장이면 Y (자동으로 채워진 것도 확인할 것)")
    dv("is_split", '"Y"', "규칙 1-1로 이 문장을 쪼갰으면 Y")
    dv("hold", '"Y"', "두 번 읽어도 안 정해지면 Y. 끝난 뒤 모아서 처리")

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{last}"

    # 지침 요약 시트
    g = wb.create_sheet("지침요약")
    lines = [
        (title, True),
        ("", False),
        ("판정 순서", True),
        ("1. 한 문장 안에 명시적 긍정과 명시적 부정이 둘 다 있으면 그 자리에서 절로 나눈다 (is_split=Y).", False),
        ("   '-지만/-으나'가 있다는 이유만으로는 쪼개지 않는다. 한쪽이 사실 진술이면 그대로 둔다.", False),
        ("2. 평가어가 없으면 중립. 여기서 멈춘다. 작성자의 속마음을 추론하지 않는다.", False),
        ("3. 평가 방향만 본다. 강도는 보지 않는다 ('조금 아쉽네요'도 부정).", False),
        ("4. 상투어 단독이면 긍정 + is_boilerplate=Y.", False),
        ("5. 두 번 읽어도 안 정해지면 hold=Y. 전부 끝낸 뒤 모아서 한 번에 처리한다.", False),
        ("", False),
        ("이미 결정된 경계 사례", True),
        ("헛걸음(가 봤는데 못 들어감, 본인의 좌절된 방문 경험 서술)  ->  부정", False),
        ("개선 요구('~됐음 좋겠어요', '신경써주면 좋겠습니다')  ->  부정", False),
        ("   판별 질문: 지금 없는 것을 요구하고 있는가.", False),
        ("   재방문 의사('봄에 다시 오겠음') -> 긍정 / 관광지 평가가 아닌 소망('많이 놀러오시길') -> 중립", False),
        ("이중부정('나쁘지 않아요', '부족함이 없어요')  ->  긍정 (단어가 아니라 문장의 뜻을 본다)", False),
        ("운영 정보만 전달('월요일은 쉬어요', '3월까지 이용할 수 없음')  ->  중립", False),
        ("사실+평가('입장료 3000원이지만 돈이 아깝지 않았어요')  ->  긍정, 쪼개지 않음", False),
        ("약한 부정('그린이 조금 아쉽네요')  ->  부정", False),
        ("내용 없음('붕어섬출렁다리', '따뜻한 아메리카노가')  ->  중립", False),
        ("전언·인용('맛있다고해서 먹어봄')  ->  중립", False),
        ("외국어 리뷰  ->  같은 기준 적용, note에 표시", False),
        ("", False),
        ("작업 절차", True),
        ("- 2~3회 세션으로 나누고, 세션 시작 때마다 이 시트를 다시 읽는다.", False),
        ("- 처음 50문장은 마지막에 다시 검토한다(기준이 굳기 전에 매긴 라벨).", False),
        ("- 하루 뒤 무작위 50문장을 이전 라벨을 보지 않고 다시 라벨 -> Cohen's kappa.", False),
        ("- 지침을 바꿔야 하면 라벨링을 멈추고 지침서를 먼저 고친 뒤 앞으로 돌아가 맞춘다.", False),
        ("", False),
        ("전체 지침서: reference/0001-라벨링-지침서.html", False),
    ]
    for text, bold in lines:
        g.append([text])
        if bold:
            g.cell(row=g.max_row, column=1).font = Font(bold=True)
    g.column_dimensions["A"].width = 110

    wb.save(path)


def main():
    df = load()
    main_rv = sample_main(df)
    boost_rv = sample_boost(df, set(main_rv["review_id"]))

    u_main = to_units(main_rv, "MAIN")
    u_boost = to_units(boost_rv, "BOOST")

    HERE.mkdir(exist_ok=True)
    u_main.to_csv(HERE / "검증셋_본_라벨링용.csv", index=False, encoding="utf-8-sig")
    u_boost.to_csv(HERE / "검증셋_부정보강_라벨링용.csv", index=False, encoding="utf-8-sig")
    write_xlsx(u_main, HERE / "검증셋_본_라벨링용.xlsx", "본 검증셋 — 문장 단위 3분류")
    write_xlsx(u_boost, HERE / "검증셋_부정보강_라벨링용.xlsx", "부정 보강셋 — 문장 단위 3분류")

    # 별점·날짜는 라벨링이 끝난 뒤 결합할 대조표에만 보관한다
    key = pd.concat([main_rv.assign(set="MAIN"), boost_rv.assign(set="BOOST")])
    key[["set", "review_id", "reviewId", "place", "platform", "rating", "date", "visitCount", "body"]] \
        .to_csv(HERE / "_대조표_별점포함_라벨링중_열지말것.csv", index=False, encoding="utf-8-sig")

    for name, rv, u in [("본 검증셋", main_rv, u_main), ("부정 보강셋", boost_rv, u_boost)]:
        print(f"\n== {name} ==")
        print(f"  리뷰 {len(rv)}건 -> 문장 {len(u)}개 (리뷰당 {len(u)/len(rv):.2f})")
        print("  플랫폼:", rv["platform"].value_counts().to_dict())
        print(f"  상투어 자동표시: {(u.is_boilerplate=='Y').sum()}개")
        print(f"  관광지 {rv['place'].nunique()}곳, 상위 5곳:",
              rv["place"].value_counts().head(5).to_dict())
        if rv["rating"].notna().any():
            print("  (참고) 별점 분포:", rv["rating"].value_counts().sort_index().to_dict())


if __name__ == "__main__":
    main()
