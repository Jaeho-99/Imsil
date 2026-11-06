#!/usr/bin/env python3
"""주요 관광지 3곳의 계절별 대표 긍정·중립·부정 요인을 각각 그린다.

실행: python src/satisfaction/plot_seasonal_factors.py
입력: output/satisfaction/리뷰별_만족불만요인_분석결과.csv
출력: output/satisfaction/{관광지명}_계절별_대표요인.png (관광지마다 1장)

한 리뷰에서 같은 카테고리의 요인이 여러 번 추출되면 각각 1건으로 센다.
비율의 분모는 해당 관광지·계절·감정의 전체 요인 언급 건수다.
각 조합에서 언급이 가장 많은 카테고리 1개를 막대로 표시한다.
각 막대 위에 대표 카테고리 이름, 비율, 카테고리 요인 건수/전체 요인 건수를 표시한다.
집계 기간은 2022년 1월 1일부터 2025년 12월 31일까지다.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
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
OUTPUT_DIR = SATIS_OUT
START_YEAR = 2022
END_YEAR = 2025
PLACES = ("붕어섬생태공원", "임실치즈테마파크", "옥정호출렁다리")
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
    return SEASONS[(month % 12) // 3 - 1]


def count_factors() -> tuple[dict[tuple[str, str, str], Counter], int, int]:
    counts: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    invalid_dates = out_of_period = 0
    with INPUT.open("r", encoding="utf-8-sig", newline="") as file:
        for row_number, row in enumerate(csv.DictReader(file), start=2):
            place = row["place"].strip()
            if place not in PLACES or row["run_status"].strip() != "ok":
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
            try:
                factors = json.loads(row["factors_json"])["factors"]
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"{INPUT.name}의 {row_number}행 factors_json이 유효하지 않습니다.") from exc
            if not isinstance(factors, list):
                raise ValueError(f"{INPUT.name}의 {row_number}행 factors가 목록이 아닙니다.")
            for factor in factors:
                sentiment = str(factor.get("sentiment", "")).strip().upper()
                category = str(factor.get("category", "")).strip()
                if sentiment in {"POS", "NEU", "NEG"} and category:
                    counts[place, season, sentiment][category] += 1
    return counts, invalid_dates, out_of_period


def top_category(category_counts: Counter) -> tuple[str, int, int, float]:
    total = sum(category_counts.values())
    if not total:
        return "요인 없음", 0, 0, 0.0
    # 동률이면 이름순으로 골라 실행할 때마다 같은 결과를 낸다.
    category, count = sorted(category_counts.items(),
                             key=lambda item: (-item[1], item[0]))[0]
    return category, count, total, 100 * count / total


def bar_label(category: str, percent: float, count: int, total: int) -> str:
    """카테고리·비율·요인 건수를 막대 너비 안에 들어가는 줄로 나눈다."""
    if "·" in category:
        before, after = category.split("·", 1)
        category = f"{before}·\n{after}"
    return f"{category}\n({percent:.1f}%,\n{count}/{total})"


def plot_place(place: str, counts: dict[tuple[str, str, str], Counter]) -> Path:
    fig, ax = plt.subplots(figsize=(17, 8.5))
    width = 0.24
    for index, (code, label, color) in enumerate(SENTIMENTS):
        values = []
        annotations = []
        for season in SEASONS:
            key = (place, season, code)
            category, count, total, percent = top_category(counts[key])
            values.append(percent)
            annotations.append(bar_label(category, percent, count, total) if total else "요인 없음")
        positions = [x + (index - 1) * width for x in range(len(SEASONS))]
        bars = ax.bar(positions, values, width=width, color=color, label=label)
        for bar, annotation in zip(bars, annotations):
            if bar.get_height():
                ax.annotate(annotation,
                            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                            xytext=(0, 6), textcoords="offset points",
                            ha="center", va="bottom", fontsize=12,
                            linespacing=1.1)

    ax.set_xticks(range(len(SEASONS)), SEASONS, fontsize=14)
    ax.set_ylabel("대표 요인 카테고리 비율 (%)", fontsize=12)
    ax.set_yticks(range(0, 101, 20))
    ax.set_ylim(0, 118)
    ax.grid(axis="y", color="#DDE3E4", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.legend(*ax.get_legend_handles_labels(), ncol=3, frameon=False,
               loc="upper right", bbox_to_anchor=(0.97, 0.92), fontsize=13)

    fig.suptitle(f"{place}의 계절별 주요 긍정·중립·부정 리뷰 요인)",
                 fontsize=18, fontweight="bold", y=0.96)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.82, bottom=0.13)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{place}_계절별_대표요인.png"
    fig.savefig(output, dpi=200, facecolor="white")
    plt.close(fig)
    return output


def main() -> None:
    setup_korean_font()
    counts, invalid_dates, out_of_period = count_factors()
    if not sum(sum(categories.values()) for categories in counts.values()):
        raise ValueError("주요 관광지의 요인 분석 결과가 없습니다.")
    for place in PLACES:
        output = plot_place(place, counts)
        print(f"저장: {output}")
        for season in SEASONS:
            details = []
            for code, label, _ in SENTIMENTS:
                key = (place, season, code)
                category, top_count, total, percent = top_category(counts[key])
                if total:
                    details.append(f"{label} {category} {percent:.1f}% ({top_count}/{total})")
                else:
                    details.append(f"{label} 요인 없음")
            print(f"{place} / {season}: " + ", ".join(details))
    print(f"집계 기간: {START_YEAR}~{END_YEAR}년 (기간 외 제외 {out_of_period}건)")
    if invalid_dates:
        print(f"날짜 오류로 제외한 리뷰: {invalid_dates}건")


if __name__ == "__main__":
    main()
