# -*- coding: utf-8 -*-
"""임계값 보정셋 / 채점셋 배정 (사전 등록용).

원칙
  - 라벨을 보지 않고 unit_id만으로 배정한다. 지금 배정해야 "결과 보고 고른 것"이 아니게 된다.
  - **리뷰 단위로** 자른다. 같은 리뷰의 문장이 양쪽에 갈리면 문맥이 새어 보정셋이 오염된다.
  - 부정 보강셋 162문장은 **건드리지 않는다.** 부정 재현율 측정 도구이므로 온전히 보존한다.

재생성(결정론적): python src/sentiment/calibration/build_split.py
"""
import random
import pandas as pd
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_IN, SENT_OUT  # noqa: E402
SRC = SENT_IN / "labeling"                     # 라벨링용 검증셋 (보존본)
OUT = SENT_OUT / "calibration"
SEED = 20260821
TARGET_CAL_SENTS = 150

def main():
    main_df = pd.read_csv(SRC / "검증셋_본_라벨링용.csv", encoding="utf-8-sig", dtype=str)
    aug_df = pd.read_csv(SRC / "검증셋_부정보강_라벨링용.csv", encoding="utf-8-sig", dtype=str)

    sizes = main_df.groupby("review_id", sort=False).size()
    reviews = list(sizes.index)
    random.Random(SEED).shuffle(reviews)

    cal_reviews, n = [], 0
    for r in reviews:
        if n >= TARGET_CAL_SENTS:
            break
        cal_reviews.append(r)
        n += int(sizes[r])
    cal_set = set(cal_reviews)

    rows = []
    for _, r in main_df.iterrows():
        rows.append({"unit_id": r["unit_id"], "review_id": r["review_id"],
                     "set": "MAIN", "platform": r["platform"],
                     "split": "CAL" if r["review_id"] in cal_set else "TEST"})
    for _, r in aug_df.iterrows():
        rows.append({"unit_id": r["unit_id"], "review_id": r["review_id"],
                     "set": "AUG", "platform": r["platform"], "split": "TEST"})

    out = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "보정셋_배정.csv", index=False, encoding="utf-8-sig")

    cal = out[out.split == "CAL"]
    test_main = out[(out.split == "TEST") & (out.set == "MAIN")]
    print(f"seed={SEED} · 리뷰 단위 분할")
    print(f"  CAL  (임계값 결정용) : 리뷰 {cal.review_id.nunique():3d} · 문장 {len(cal):3d}"
          f"  [구글 {(cal.platform=='구글').sum()} · 네이버 {(cal.platform=='네이버').sum()}]")
    print(f"  TEST 본  (채점용)    : 리뷰 {test_main.review_id.nunique():3d} · 문장 {len(test_main):3d}")
    print(f"  TEST 보강(부정 재현율): 문장 {(out.set=='AUG').sum():3d}  (분할 안 함)")
    print(f"  채점 총계 {len(out[out.split=='TEST'])}문장 / 전체 {len(out)}문장")

if __name__ == "__main__":
    main()
