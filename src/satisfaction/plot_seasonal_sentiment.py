#!/usr/bin/env python3
"""전체 관광지의 계절별 긍정·중립·부정 리뷰 비율을 그린다.

실행: python src/satisfaction/plot_seasonal_sentiment.py
입력: output/satisfaction/리뷰별_만족불만요인_분석결과.csv
출력: output/satisfaction/계절별_감정리뷰_비율.png

각 계절의 분모는 감정 분석이 완료되고 날짜가 유효한 리뷰 수다.
본문이 없어 분석되지 않은 리뷰는 분자와 분모에서 모두 제외한다.
집계 기간은 2022년 1월 1일부터 2025년 12월 31일까지다.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

LOCAL_DEPS = Path(__file__).resolve().parent / ".plot_deps"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SATIS_OUT, SATIS_RESULT  # noqa: E402
INPUT = SATIS_RESULT
OUTPUT = SATIS_OUT / "계절별_감정리뷰_비율.png"
START_YEAR = 2022
END_YEAR = 2025
SEASONS = ("봄", "여름", "가을", "겨울")
SENTIMENTS = (("POS", "긍정", "#31846B"),
              ("NEU", "중립", "#D19A3B"),
              ("NEG", "부정", "#C65E5A"))


def setup_korean_font() -> None:
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for name in ("Malgun Gothic", "NanumGothic", "AppleGothic", "Noto Sans CJK KR"):
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    else:
        raise RuntimeError("한글 글꼴이 없습니다. 맑은 고딕 또는 나눔고딕을 설치하세요.")
    plt.rcParams["axes.unicode_minus"] = False


def season_of(review_date: datetime) -> str:
    month = review_date.month
    return SEASONS[(month % 12) // 3 - 1]  # 3~5 봄, 6~8 여름, 9~11 가을, 12~2 겨울


def count_reviews() -> tuple[Counter, int, int, int]:
    counts: Counter = Counter()
    skipped = invalid_dates = out_of_period = 0
    with INPUT.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            sentiment = row["overall_sentiment"].strip().upper()
            if row["run_status"].strip() != "ok" or sentiment not in {"POS", "NEU", "NEG"}:
                skipped += 1
                continue
            try:
                review_date = datetime.strptime(row["date"].strip(), "%Y.%m.%d")
            except ValueError:
                invalid_dates += 1
                continue
            if not START_YEAR <= review_date.year <= END_YEAR:
                out_of_period += 1
                continue
            season = season_of(review_date)
            counts[season, sentiment] += 1
    return counts, skipped, invalid_dates, out_of_period


def main() -> None:
    setup_korean_font()
    counts, skipped, invalid_dates, out_of_period = count_reviews()
    totals = {season: sum(counts[season, code] for code, _, _ in SENTIMENTS)
              for season in SEASONS}
    if not sum(totals.values()):
        raise ValueError("그래프에 사용할 분석 완료 리뷰가 없습니다.")

    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    positions = range(len(SEASONS))
    width = 0.22
    for offset, (code, label, color) in zip((-1, 0, 1), SENTIMENTS):
        percentages = [100 * counts[season, code] / totals[season]
                       if totals[season] else 0 for season in SEASONS]
        bars = ax.bar([x + offset * width for x in positions], percentages,
                      width=width, color=color, label=label)
        for season, bar, percent in zip(SEASONS, bars, percentages):
            count = counts[season, code]
            if count:
                ax.annotate(f"{percent:.1f}%\n({count:,}건)",
                            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                            xytext=(0, 5), textcoords="offset points",
                            ha="center", va="bottom", fontsize=9)

    ax.set_xticks(list(positions), [f"{season}\n(n={totals[season]:,})" for season in SEASONS])
    ax.set_ylabel("리뷰 수 비율 (%)")
    # ax.set_xlabel("계절")
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 20))
    ax.grid(axis="y", color="#DDE3E4", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=3, frameon=False, loc="upper right")
    fig.suptitle("임실군 전체 관광지의 계절별 긍정·중립·부정 리뷰 비율",
                 fontsize=17, fontweight="bold", y=0.98)
    # fig.text(0.5, 0.91, "각 계절의 분석 완료 리뷰를 100%로 계산", ha="center", fontsize=10)
    # fig.text(0.08, 0.025,
    #          f"분석 완료 {sum(totals.values()):,}건  ·  분석 제외 {skipped:,}건  ·  날짜 오류 {invalid_dates:,}건",
    #          fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, 0.055, 1, 0.89))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=200, facecolor="white")
    plt.close(fig)
    print(f"저장: {OUTPUT}")
    print(f"집계 기간: {START_YEAR}~{END_YEAR}년 (기간 외 제외 {out_of_period}건)")
    for season in SEASONS:
        values = ", ".join(f"{label} {100 * counts[season, code] / totals[season]:.1f}%"
                           if totals[season] else f"{label} 자료 없음"
                           for code, label, _ in SENTIMENTS)
        print(f"{season} (n={totals[season]}): {values}")


if __name__ == "__main__":
    main()
