# -*- coding: utf-8 -*-
"""네이버 수집 결과(output/collect/naver/)의 리뷰 CSV를 읽어 관광지별 리뷰 수를 막대그래프로 그린다.

실행  python src/collect/naver_review_counts.py      (src/collect/naver_reviews.py 를 먼저 실행)
출력  output/collect/naver_review_counts.png
"""

import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import COLLECT_OUT, NAVER_RAW  # noqa: E402

OUTPUT_DIR = str(COLLECT_OUT)

PLACES = {
    "1208503663": "도화지 도예문화원",
    "1029752338": "세심자연휴양림",
    "1281789019": "임실치즈마을",
    "1514459962": "임실치즈테마파크",
    "31679045": "전북119안전체험관",
    "13338277": "전북종합사격장",
    "1637440800": "청소년수련원",
    "17660144": "필봉농악전수교육관",
    "11526227": "국립 임실호국원",
    "37766238": "섬진강댐 물문화관",
    "12442513": "소충사",
    "1160065525": "옥정호출렁다리",
    "13374614": "전주샹그릴라CC",
    "11491834": "옥정호",
    "13346280": "사선대관광지",
    "1962656265": "임실역",
    "1671220194": "오수역",
    "13519814": "임실시외버스터미널",
    "13302059": "국사봉전망대",
    "11636501": "관촌역",
    "1486494459": "붕어섬생태공원",
    "1925803749": "요산공원",
    "17655687": "오수공용버스터미널",
    "17413446": "관촌시외버스터미널",
    "13345918": "임실전통시장",
    "17658593": "사선대조각공원",
    "17655364": "오수의견공원",
    "1705972994": "성수산왕의숲자연휴양림",
    "17410534": "상이암",
    "17658791": "관촌시장",
    "17659891": "강진공용버스터미널",
    "1753061067": "옥정호전망대",
}

# macOS 한글 폰트 설정
plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False


def count_reviews(place_id):
    path = os.path.join(str(NAVER_RAW), f"{PLACES[place_id]}_naver_reviews.csv")
    if not os.path.exists(path):
        print(f"[경고] CSV 없음: {place_id} ({PLACES[place_id]})")
        return 0
    return len(pd.read_csv(path))


def main():
    counts = {name: count_reviews(pid) for pid, name in PLACES.items()}
    df = pd.Series(counts).sort_values(ascending=False)

    fig, ax = plt.subplots(figsize=(16, 7))
    ax.bar(df.index, df.values, color="#2a78d6", width=0.7)

    ax.set_xlabel("관광지명")
    ax.set_ylabel("리뷰 수")
    ax.set_title("임실군 관광지별 네이버 플레이스 리뷰 수")
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(df.index, rotation=60, ha="right")
    ax.yaxis.grid(True, color="#dddddd", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    save_path = os.path.join(OUTPUT_DIR, "naver_review_counts.png")
    fig.savefig(save_path, dpi=150)
    print(f"저장 완료: {save_path}")
    plt.show()


if __name__ == "__main__":
    main()
