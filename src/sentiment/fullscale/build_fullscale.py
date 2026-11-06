# -*- coding: utf-8 -*-
"""전수 적용용 묶음 생성 — 이미 라벨된 리뷰는 뺀다 (9단계)

무엇을 만드나
  1차전처리 CSV 3,208건(텍스트 보유) 중 **사람이 이미 라벨한 370리뷰를 제외**한
  2,838리뷰 4,987문장을 150문장 묶음으로 자른다.

왜 빼는가
  그 370리뷰에는 사람 라벨 698개가 있다. 사람 라벨이 ③번 예측보다 정확하다
  (③번의 macro-F1 0.906~0.914 는 바로 그 라벨을 정답으로 삼아 잰 값이다).
  이미 정답이 있는 것을 다시 예측시킬 이유가 없고, 붙여넣을 분량도 준다.
  최종 집계에서 그 자리에는 **사람 라벨**을 넣는다(`merge_fullscale.py`).

조건 — `NOTES.md` '전수 적용 조건 (확정)' 과 같아야 한다
  묶음 150문장. 실측으로 승인됨(548문장 재실행: 행 누락 0 · macro-F1 0.914 ·
  run1 대비 불일치 3.65% < 재현성 기준선 4.20%). `output/sentiment/evaluation/③번_조건비교_run1_vs_run_150.md`

설계
  - 문장 분리는 `textsplit.py` 하나만 쓴다. 파이프라인 전체가 같은 분리기를 쓴다.
  - 같은 리뷰의 문장은 한 묶음 안에 둔다. 문맥 없이는 라벨할 수 없다.
  - **리뷰 순서를 섞는다(seed 20260823).** 관광지별로 묶이면 한 묶음이 한 장소로만 채워져
    기준이 그 장소에 맞춰 흐를 수 있다. 검증셋을 섞은 것과 같은 이유다.
  - 별점을 넣지 않는다. 검증셋에서 잰 성능과 같은 조건이어야 그 성능을 전수에 적용할 수 있다.

출력
  output/sentiment/fullscale/문장목록.csv        unit_id ↔ 리뷰·문장 대조표. 채점·병합의 기준
  output/sentiment/fullscale/chunks/전수_NN.txt   붙여넣을 묶음

실행:  python src/sentiment/fullscale/build_fullscale.py
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import REVIEWS_PRE, SENT_OUT  # noqa: E402
sys.path.insert(0, str(HERE.parent))
from textsplit import split_sentences

SEED = 20260823
TARGET = 150
CSV = REVIEWS_PRE
OUT_DIR = SENT_OUT / "fullscale"
OUT = OUT_DIR / "chunks"                         # LLM 에 넣을 묶음


def main():
    d = pd.read_csv(CSV, encoding="utf-8-sig")
    t = d[d["body"].notna() & (d["body"].astype(str).str.strip() != "")].copy()
    assert not t["reviewId"].duplicated().any(), "reviewId 가 유일하지 않다"

    labeled = set()
    for f in ["검증셋_본_확정.csv", "검증셋_보강_확정.csv"]:
        labeled |= set(pd.read_csv(SENT_OUT / "labeling" / "확정" / f,
                                   encoding="utf-8-sig")["review_id"])
    rest = t[~t["reviewId"].isin(labeled)].copy()

    rest = rest.sample(frac=1, random_state=SEED).reset_index(drop=True)

    rows = []
    for r in rest.itertuples():
        sents = split_sentences(str(r.body))
        for i, s in enumerate(sents, 1):
            rows.append(dict(review_id=r.reviewId, place=r.place, platform=r.platform,
                             sent_no=i, n_sent=len(sents), sent=s))
    df = pd.DataFrame(rows)
    df.insert(0, "unit_id", [f"FULL-{i:05d}" for i in range(1, len(df) + 1)])
    df.to_csv(OUT_DIR / "문장목록.csv", index=False, encoding="utf-8-sig")

    # 리뷰 경계를 넘지 않게 자른다
    groups, cur = [], []
    for _, g in df.groupby("review_id", sort=False):
        recs = g.to_dict("records")
        if cur and len(cur) + len(recs) > TARGET:
            groups.append(cur)
            cur = []
        cur.extend(recs)
    if cur:
        groups.append(cur)

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.txt"):
        old.unlink()
    for i, recs in enumerate(groups, 1):
        lines = [f"# 묶음 전수_{i:02d} · {len(recs)}문장 · 출력도 정확히 {len(recs)}행이어야 합니다.",
                 "unit_id | sent_no/n_sent | 관광지 | 플랫폼 | 문장"]
        for r in recs:
            sent = str(r["sent"]).replace("\n", " ").replace("|", "/").strip()
            lines.append(f'{r["unit_id"]} | {r["sent_no"]}/{r["n_sent"]} | '
                         f'{r["place"]} | {r["platform"]} | {sent}')
        (OUT / f"전수_{i:02d}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"텍스트 보유 리뷰 {len(t)} · 라벨된 리뷰 {len(labeled)} 제외 -> **{len(rest)}리뷰**")
    print(f"문장 {len(df)} · 묶음 {len(groups)} (목표 {TARGET}문장, seed {SEED})")
    print(f"  묶음 크기 분포: 최소 {min(len(g) for g in groups)} · 최대 {max(len(g) for g in groups)}")
    print(f"  플랫폼: {rest.platform.value_counts().to_dict()} · 관광지 {rest.place.nunique()}곳")
    print(f"\n출력: {OUT}\n대조표: {OUT_DIR / '문장목록.csv'}")


if __name__ == "__main__":
    main()
