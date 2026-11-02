# -*- coding: utf-8 -*-
"""
Tier A 3곳의 2022~2025 계절별 리뷰 수 분석 (T-2)
파일명: tierA_seasonal_review_analysis.py

목적:
  1. Tier A 3개 관광지(붕어섬생태공원, 임실치즈테마파크, 옥정호출렁다리)의
     2022~2025년 4개년 계절별(봄, 여름, 가을, 겨울) 리뷰 수(Google, Naver, Total) 집계 (48행)
  2. 관광지별 4개년 계절 요약(4개년 총합, 연평균, 계절 비중) 산출 (12행)
  3. 기존 T3 연도별 결과와의 동적 교차검증을 포함한 10대 무결성 자동 검증
  4. 300dpi 계절별 연평균 리뷰 수 비교 시각화 차트 생성 (tierA_seasonal_review_comparison.png)
"""

import os
import hashlib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==============================================================================
# 0. 경로 및 상수 정의
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

INPUT_CSV = os.path.join(PROJECT_ROOT, "data", "임실군_관광지_리뷰데이터.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
T3_CSV = os.path.join(OUTPUT_DIR, "annual_trend_decomposition_2022_2025.csv")

# 산출물 경로
CSV_SEASONAL_COUNTS = os.path.join(OUTPUT_DIR, "tierA_seasonal_review_counts_2022_2025.csv")
CSV_SEASONAL_SUMMARY = os.path.join(OUTPUT_DIR, "tierA_seasonal_review_summary_2022_2025.csv")
PNG_SEASONAL_COMPARISON = os.path.join(OUTPUT_DIR, "tierA_seasonal_review_comparison.png")

TIER_A_PLACES = ["붕어섬생태공원", "임실치즈테마파크", "옥정호출렁다리"]
TARGET_YEARS = [2022, 2023, 2024, 2025]
SEASONS = ["봄", "여름", "가을", "겨울"]

# 계절 매핑 함수 (Calendar Year 기준: 봄=3~5, 여름=6~8, 가을=9~11, 겨울=12,1,2)
def get_season(month):
    if month in [3, 4, 5]:
        return "봄"
    elif month in [6, 7, 8]:
        return "여름"
    elif month in [9, 10, 11]:
        return "가을"
    elif month in [12, 1, 2]:
        return "겨울"
    return ""


def get_file_md5(filepath):
    """파일의 MD5 해시를 계산합니다."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def setup_matplotlib_font():
    """한글 폰트(맑은 고딕) 및 서식 설정."""
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.size"] = 11


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 80)
    print(" [T-2] Tier A 3곳의 2022~2025 계절별 리뷰 수 분석")
    print("=" * 80)
    
    # --------------------------------------------------------------------------
    # 1. 데이터 로드 및 원본 무결성 기록
    # --------------------------------------------------------------------------
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"입력 데이터 파일을 찾을 수 없습니다: {INPUT_CSV}")
        
    initial_md5 = get_file_md5(INPUT_CSV)
    print(f"[입력 파일] {INPUT_CSV}")
    print(f"[파일 해시(MD5)] {initial_md5}")
    
    df_raw = pd.read_csv(INPUT_CSV, encoding="utf-8-sig", dtype=str)
    raw_total_rows = len(df_raw)
    print(f"[전체 원본 행 수] {raw_total_rows:,}건")
    
    # 날짜 파싱
    df_raw["parsed_date"] = pd.to_datetime(df_raw["date"], errors="coerce")
    parse_fail_count = int(df_raw["parsed_date"].isna().sum())
    if parse_fail_count > 0:
        raise ValueError(f"날짜 파싱 실패 {parse_fail_count}건 발생")
        
    df_raw["year"] = df_raw["parsed_date"].dt.year
    df_raw["month"] = df_raw["parsed_date"].dt.month
    df_raw["season"] = df_raw["month"].apply(get_season)
    
    # 2022~2025년 필터링 (Tier A 3곳)
    df_filtered = df_raw[
        (df_raw["year"].isin(TARGET_YEARS)) & 
        (df_raw["place"].isin(TIER_A_PLACES))
    ].copy()
    filtered_total = len(df_filtered)
    print(f"[2022~2025 Tier A 필터 행 수] {filtered_total:,}건")
    
    # --------------------------------------------------------------------------
    # 2. [산출물 1] 연도별·계절별 집계 (48행)
    # --------------------------------------------------------------------------
    # 3개 관광지 x 4개 연도 x 4개 계절 완전 그리드 생성
    grid = []
    for place in TIER_A_PLACES:
        for year in TARGET_YEARS:
            for season in SEASONS:
                grid.append({"place": place, "year": year, "season": season})
    df_grid = pd.DataFrame(grid)
    
    # 플랫폼별 집계
    counts = (
        df_filtered.groupby(["place", "year", "season", "platform"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    if "구글" not in counts.columns:
        counts["구글"] = 0
    if "네이버" not in counts.columns:
        counts["네이버"] = 0
        
    df_counts = pd.merge(df_grid, counts, on=["place", "year", "season"], how="left").fillna(0)
    df_counts["google_count"] = df_counts["구글"].astype(int)
    df_counts["naver_count"] = df_counts["네이버"].astype(int)
    df_counts["total_count"] = df_counts["google_count"] + df_counts["naver_count"]
    
    cols_counts = ["place", "year", "season", "google_count", "naver_count", "total_count"]
    df_counts = df_counts[cols_counts]
    df_counts.to_csv(CSV_SEASONAL_COUNTS, index=False, encoding="utf-8-sig")
    print(f"\n[저장 완료] 연도별·계절별 집계 CSV: {CSV_SEASONAL_COUNTS} ({len(df_counts)}행)")

    # --------------------------------------------------------------------------
    # 3. [산출물 2] 4개년 계절 요약 (12행)
    # --------------------------------------------------------------------------
    summary_rows = []
    for place in TIER_A_PLACES:
        place_df = df_counts[df_counts["place"] == place]
        place_grand_total = place_df["total_count"].sum()
        
        for season in SEASONS:
            season_df = place_df[place_df["season"] == season]
            four_yr_tot = season_df["total_count"].sum()
            ann_mean = four_yr_tot / 4.0
            share_pct = (four_yr_tot / place_grand_total * 100.0) if place_grand_total > 0 else 0.0
            
            summary_rows.append({
                "place": place,
                "season": season,
                "four_year_total": int(four_yr_tot),
                "annual_mean": round(ann_mean, 2),
                "share_pct": round(share_pct, 2)
            })
            
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(CSV_SEASONAL_SUMMARY, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] 4개년 계절 요약 CSV: {CSV_SEASONAL_SUMMARY} ({len(df_summary)}행)")

    # --------------------------------------------------------------------------
    # 4. 자동 검증 10대 항목
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [자동 검증 실행 결과]")
    print("=" * 80)
    
    # 1. Tier A 3곳 원자료 존재 확인
    available_places = set(df_raw["place"].dropna().unique())
    v1 = all(p in available_places for p in TIER_A_PLACES)
    print(f" 1. Tier A 3곳 원자료 내 존재 확인: {'[PASS]' if v1 else '[FAIL]'}")
    
    # 2. 날짜 파싱 실패 0건
    v2 = (parse_fail_count == 0)
    print(f" 2. 날짜 파싱 실패 0건 확인: {'[PASS]' if v2 else '[FAIL]'}")
    
    # 3. 분석 기간 2022~2025 제한 확인
    years_in_counts = sorted(df_counts["year"].unique().tolist())
    v3 = (years_in_counts == TARGET_YEARS)
    print(f" 3. 분석 기간 2022~2025 제한 확인: {'[PASS]' if v3 else '[FAIL]'} (연도: {years_in_counts})")
    
    # 4. 상세 CSV 행 수 48행
    v4 = (len(df_counts) == 48)
    print(f" 4. 상세 CSV 행 수 48행(3 x 4 x 4) 확인: {'[PASS]' if v4 else '[FAIL]'} (실제 {len(df_counts)}행)")
    
    # 5. 요약 CSV 행 수 12행
    v5 = (len(df_summary) == 12)
    print(f" 5. 요약 CSV 행 수 12행(3 x 4) 확인: {'[PASS]' if v5 else '[FAIL]'} (실제 {len(df_summary)}행)")
    
    # 6. Google + Naver = Total 일치
    v6 = (df_counts["google_count"] + df_counts["naver_count"] == df_counts["total_count"]).all()
    print(f" 6. 모든 행에서 Google + Naver = Total 일치: {'[PASS]' if v6 else '[FAIL]'}")
    
    # 7. 각 관광지 x 연도에서 4계절 합계 == 원자료 해당 연도 리뷰 수 일치
    v7 = True
    for p in TIER_A_PLACES:
        for y in TARGET_YEARS:
            c_sum = df_counts[(df_counts["place"] == p) & (df_counts["year"] == y)]["total_count"].sum()
            raw_cnt = len(df_filtered[(df_filtered["place"] == p) & (df_filtered["year"] == y)])
            if c_sum != raw_cnt:
                v7 = False
                print(f"   [불일치] {p} {y}년: 계절합 {c_sum} != 원자료 {raw_cnt}")
    print(f" 7. 각 관광지 x 연도 4계절 합계와 원자료 연도별 건수 일치: {'[PASS]' if v7 else '[FAIL]'}")
    
    # 8. T3 연도별 합계와 동적 교차검증
    v8 = True
    t3_info = []
    if os.path.exists(T3_CSV):
        df_t3 = pd.read_csv(T3_CSV, encoding="utf-8-sig")
        for p in TIER_A_PLACES:
            t3_place_tot = df_t3[p].sum() if p in df_t3.columns else None
            seasonal_place_tot = df_summary[df_summary["place"] == p]["four_year_total"].sum()
            if t3_place_tot != seasonal_place_tot:
                v8 = False
                t3_info.append(f"{p}: 계절합 {seasonal_place_tot} != T3합 {t3_place_tot}")
            else:
                t3_info.append(f"{p}: {seasonal_place_tot:,}건 일치")
    else:
        v8 = False
        t3_info.append("T3 산출물 파일 부재")
    print(f" 8. T3 연도별 합계와 동적 교차검증: {'[PASS]' if v8 else '[FAIL]'} ({', '.join(t3_info)})")
    
    # 9. 관광지별 4개 계절 share_pct 합계 100% 확인 (반올림 전 기준)
    v9 = True
    for p in TIER_A_PLACES:
        p_tot = df_summary[df_summary["place"] == p]["four_year_total"].sum()
        sum_pct = (df_summary[df_summary["place"] == p]["four_year_total"] / p_tot * 100.0).sum()
        if not np.isclose(sum_pct, 100.0):
            v9 = False
            print(f"   [비중 합계 오류] {p}: {sum_pct}%")
    print(f" 9. 관광지별 4개 계절 비중 합계 100.0% 확인: {'[PASS]' if v9 else '[FAIL]'}")
    
    # 10. 원본 데이터 MD5 불변 검증
    final_md5 = get_file_md5(INPUT_CSV)
    v10 = (initial_md5 == final_md5)
    print(f" 10. 원본 데이터 미수정 확인(MD5): {'[PASS]' if v10 else '[FAIL]'}")
    
    all_passed = v1 and v2 and v3 and v4 and v5 and v6 and v7 and v8 and v9 and v10
    print("-" * 80)
    print(f" >> 전체 검증 결과: {'모든 검증 통과 (ALL PASSED)' if all_passed else '검증 실패 항목 존재 (FAILED)'}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 5. 그래프 생성 (300dpi PNG)
    # --------------------------------------------------------------------------
    setup_matplotlib_font()
    
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    
    # x축 인덱스 및 막대 너비 설정 (그룹 막대 그래프)
    x = np.arange(len(SEASONS))
    width = 0.25
    
    colors = {
        "붕어섬생태공원": "#2B6CB0",
        "임실치즈테마파크": "#D69E2E",
        "옥정호출렁다리": "#319795"
    }
    
    for idx, place in enumerate(TIER_A_PLACES):
        p_data = df_summary[df_summary["place"] == place].sort_values(by="season", key=lambda s: s.map({"봄": 0, "여름": 1, "가을": 2, "겨울": 3}))
        means = p_data["annual_mean"].values
        shares = p_data["share_pct"].values
        
        pos = x + (idx - 1) * width
        rects = ax.bar(pos, means, width, label=place, color=colors[place], alpha=0.9, edgecolor="none")
        
        # 막대 상단에 연평균 건수 및 비중 표기
        for rect, m, sh in zip(rects, means, shares):
            height = rect.get_height()
            ax.annotate(
                f"{m:.1f}건\n({sh:.1f}%)",
                xy=(rect.get_x() + rect.get_width() / 2, height),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center", va="bottom",
                fontsize=9.5,
                fontweight="bold" if sh == max(shares) else "normal"
            )
            
    ax.set_title("Tier A 주요 관광지 계절별 연평균 리뷰 수 비교 (2022~2025)", fontsize=14, pad=16, fontweight="bold")
    ax.set_xlabel("계절 (Season)", fontsize=12, labelpad=10)
    ax.set_ylabel("연평균 리뷰 수 (건/년)", fontsize=12, labelpad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(["봄 (3~5월)", "여름 (6~8월)", "가을 (9~11월)", "겨울 (12,1,2월)"], fontsize=11)
    ax.set_ylim(0, df_summary["annual_mean"].max() * 1.25)
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right", frameon=True, fontsize=11)
    
    # 주석 (그래프 최하단에 작게 배치)
    fig.text(
        0.08, 0.01,
        "※ 연평균 리뷰 수 = 4개년 총 리뷰 수 / 4년 | 계절 비중(%) = 해당 관광지 4개년 총 리뷰 수 대비 비율",
        fontsize=9,
        color="#718096"
    )
    
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(PNG_SEASONAL_COMPARISON, dpi=300)
    plt.close()
    print(f"\n[그래프 저장 완료] {PNG_SEASONAL_COMPARISON}")

    # --------------------------------------------------------------------------
    # 6. 콘솔 요약표 출력
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [Tier A 계절별 4개년 집계 요약표]")
    print("=" * 80)
    print(f"{'관광지명':<12}{'계절':>6}{'4개년 총합':>12}{'연평균(건/년)':>14}{'계절 비중(%)':>14}")
    print("-" * 62)
    for idx, row in df_summary.iterrows():
        print(f"{row['place']:<12}{row['season']:>6}{int(row['four_year_total']):>12,}{row['annual_mean']:>14.2f}{str(row['share_pct']) + '%':>14}")
    print("=" * 80)


if __name__ == "__main__":
    main()
