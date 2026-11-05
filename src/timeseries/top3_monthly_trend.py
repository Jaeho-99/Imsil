# -*- coding: utf-8 -*-
"""
상위 3대 집중 관광지 월별 실제 시계열 및 급증 시점 분석 (2022-01 ~ 2026-08)
파일명: top3_monthly_trend.py

목적:
  1. 붕어섬생태공원, 임실치즈테마파크, 옥정호출렁다리의 56개월(2022-01 ~ 2026-08)
     월별 리뷰 수(Google, Naver, Total) 및 월간 절대 변화량(mom_change) 산출 (168행)
  2. 완전월(2022-01 ~ 2026-07) 기준 관광지별 직전 달 대비 최대 증가(mom_change) 상위 5개 월 도출
  3. T3 연도별 결과와의 동적 교차검증을 포함한 9대 항목 자동 무결성 검증
  4. 고해상도(300dpi) 시각화 그래프 4종 생성:
     - 전체 3개 관광지 월별 비교 개요 (top3_monthly_trend_overview.png)
     - 관광지별 월별 상세 그래프 3종 (monthly_trend_*.png)
"""

import os
import sys
import hashlib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==============================================================================
# 0. 경로 및 상수 정의
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE_DIR))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import ROOT, REVIEWS, TS_OUT  # noqa: E402
PROJECT_ROOT = str(ROOT)

INPUT_CSV = str(REVIEWS)
OUTPUT_DIR = str(TS_OUT)
T3_CSV = os.path.join(OUTPUT_DIR, "annual_trend_decomposition_2022_2025.csv")

# 산출물 경로
CSV_TOP3_MONTHLY = os.path.join(OUTPUT_DIR, "top3_monthly_counts_2022_2026.csv")
CSV_LARGEST_INCREASES = os.path.join(OUTPUT_DIR, "top3_largest_monthly_increases.csv")

PNG_OVERVIEW = os.path.join(OUTPUT_DIR, "top3_monthly_trend_overview.png")
PNG_BUNGEO = os.path.join(OUTPUT_DIR, "monthly_trend_붕어섬생태공원.png")
PNG_CHEESE = os.path.join(OUTPUT_DIR, "monthly_trend_임실치즈테마파크.png")
PNG_BRIDGE = os.path.join(OUTPUT_DIR, "monthly_trend_옥정호출렁다리.png")

# 고정 분석 대상 관광지
FOCAL_ATTRACTIONS = [
    "붕어섬생태공원",
    "임실치즈테마파크",
    "옥정호출렁다리"
]

# 분석 대상 기간: 2022-01 ~ 2026-08 (56개월)
START_YEAR, START_MONTH = 2022, 1
END_YEAR, END_MONTH = 2026, 8


def get_file_md5(filepath):
    """파일의 MD5 해시를 계산하여 원본 데이터 불변성을 확인합니다."""
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


def generate_period_grid():
    """2022-01부터 2026-08까지의 56개월 리스트 생성."""
    grid = []
    for y in range(START_YEAR, END_YEAR + 1):
        max_m = END_MONTH if y == END_YEAR else 12
        for m in range(1, max_m + 1):
            ym_str = f"{y}-{m:02d}"
            status = "partial_month" if (y == 2026 and m == 8) else "full_month"
            grid.append({"year": y, "month": m, "year_month": ym_str, "coverage_status": status})
    return pd.DataFrame(grid)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 80)
    print(" [T4-1] 상위 3곳 월별 실제 시계열 및 급증 시점 확인 (2022-01 ~ 2026-08)")
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
    df_raw["year_month"] = df_raw["parsed_date"].dt.strftime("%Y-%m")
    
    # --------------------------------------------------------------------------
    # 2. [산출물 1] 상위 3곳 월별 집계 및 MoM 변화량 산출 (168행)
    # --------------------------------------------------------------------------
    period_df = generate_period_grid()
    total_months = len(period_df)
    print(f"[분석 대상 개월 수] {total_months}개월 (2022-01 ~ 2026-08 / 2026-08 부분월)")
    
    place_monthly_frames = []
    
    for place in FOCAL_ATTRACTIONS:
        df_p = df_raw[df_raw["place"] == place].copy()
        
        # 플랫폼별 및 월별 집계
        counts = (
            df_p.groupby(["year_month", "platform"])
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        if "구글" not in counts.columns:
            counts["구글"] = 0
        if "네이버" not in counts.columns:
            counts["네이버"] = 0
            
        merged = pd.merge(period_df, counts, on="year_month", how="left").fillna(0)
        merged["place"] = place
        merged["google_count"] = merged["구글"].astype(int)
        merged["naver_count"] = merged["네이버"].astype(int)
        merged["total_count"] = merged["google_count"] + merged["naver_count"]
        
        # 월간 변화량 (mom_change) = 현재 월 total_count - 직전 월 total_count
        merged["mom_change"] = merged["total_count"].diff()
        
        # 열 순서 정리
        cols = [
            "place", "year", "month", "year_month",
            "google_count", "naver_count", "total_count",
            "coverage_status", "mom_change"
        ]
        place_monthly_frames.append(merged[cols])
        
    df_top3_monthly = pd.concat(place_monthly_frames, ignore_index=True)
    df_top3_monthly.to_csv(CSV_TOP3_MONTHLY, index=False, encoding="utf-8-sig")
    print(f"\n[저장 완료] 상위 3곳 월별 집계 CSV: {CSV_TOP3_MONTHLY} ({len(df_top3_monthly)}행)")

    # --------------------------------------------------------------------------
    # 3. [산출물 2] 관광지별 직전 달 대비 최대 증가(mom_change) 상위 5개 월 (완전월 대상)
    # --------------------------------------------------------------------------
    increases_records = []
    
    for place in FOCAL_ATTRACTIONS:
        sub = df_top3_monthly[
            (df_top3_monthly["place"] == place) & 
            (df_top3_monthly["coverage_status"] == "full_month") &
            (df_top3_monthly["mom_change"].notna())
        ].copy()
        
        # mom_change 기준 내림차순 정렬 상위 5개
        sub_top5 = sub.sort_values(by="mom_change", ascending=False).head(5).reset_index(drop=True)
        
        for r_idx, row in sub_top5.iterrows():
            cur_cnt = int(row["total_count"])
            diff = int(row["mom_change"])
            prev_cnt = cur_cnt - diff
            
            increases_records.append({
                "place": place,
                "rank": r_idx + 1,
                "year_month": row["year_month"],
                "previous_month_count": prev_cnt,
                "current_month_count": cur_cnt,
                "mom_change": diff,
                "google_count": int(row["google_count"]),
                "naver_count": int(row["naver_count"])
            })
            
    df_increases = pd.DataFrame(increases_records)
    df_increases.to_csv(CSV_LARGEST_INCREASES, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] 급증 시점 상위 5개 월 CSV: {CSV_LARGEST_INCREASES} ({len(df_increases)}행)")

    # --------------------------------------------------------------------------
    # 4. 자동 검증 (9대 항목)
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [자동 검증 실행 결과]")
    print("=" * 80)
    
    # 1. FOCAL_ATTRACTIONS 3곳 데이터 내 존재 확인
    available_places = set(df_raw["place"].dropna().unique())
    v1 = all(p in available_places for p in FOCAL_ATTRACTIONS)
    print(f" 1. FOCAL_ATTRACTIONS 3곳 데이터 내 존재 확인: {'[PASS]' if v1 else '[FAIL]'}")
    
    # 2. 날짜 파싱 실패 0건
    v2 = (parse_fail_count == 0)
    print(f" 2. 날짜 파싱 실패 건수 0건 확인: {'[PASS]' if v2 else '[FAIL]'}")
    
    # 3. 각 관광지별 56개 월 존재
    months_per_place = df_top3_monthly.groupby("place")["year_month"].nunique().to_dict()
    v3 = all(cnt == 56 for cnt in months_per_place.values())
    print(f" 3. 각 관광지에 56개 월 존재: {'[PASS]' if v3 else '[FAIL]'} (각 관광지별 {set(months_per_place.values())}개월)")
    
    # 4. 전체 출력 행수 168행
    v4 = (len(df_top3_monthly) == 168)
    print(f" 4. 전체 출력 행 수 168행(3 x 56) 확인: {'[PASS]' if v4 else '[FAIL]'} (실제 {len(df_top3_monthly)}행)")
    
    # 5. 각 행에서 Google + Naver = Total 일치
    v5 = (df_top3_monthly["google_count"] + df_top3_monthly["naver_count"] == df_top3_monthly["total_count"]).all()
    print(f" 5. 각 행에서 Google + Naver = Total 일치: {'[PASS]' if v5 else '[FAIL]'}")
    
    # 6. 2026-08만 partial_month, 나머지는 full_month
    partial_rows = df_top3_monthly[df_top3_monthly["coverage_status"] == "partial_month"]
    v6 = (set(partial_rows["year_month"].unique()) == {"2026-08"}) and (len(partial_rows) == 3)
    print(f" 6. 2026-08만 partial_month(3건), 나머지 full_month(165건) 확인: {'[PASS]' if v6 else '[FAIL]'}")
    
    # 7. 2022~2025 월 집계 연도별 합이 T3 산출물과 관광지별로 일치 (동적 비교)
    v7 = True
    t3_mismatch_info = []
    if os.path.exists(T3_CSV):
        df_t3 = pd.read_csv(T3_CSV, encoding="utf-8-sig")
        df_top3_2225 = df_top3_monthly[df_top3_monthly["year"].isin([2022, 2023, 2024, 2025])]
        t3_annual_calc = df_top3_2225.groupby(["place", "year"])["total_count"].sum().unstack(fill_value=0)
        
        for p in FOCAL_ATTRACTIONS:
            for y in [2022, 2023, 2024, 2025]:
                calc_val = t3_annual_calc.loc[p, y]
                t3_row = df_t3[df_t3["year"] == y]
                t3_val = int(t3_row[p].values[0]) if len(t3_row) > 0 and p in t3_row.columns else None
                if calc_val != t3_val:
                    v7 = False
                    t3_mismatch_info.append(f"{p} {y}년: 월별합 {calc_val} != T3값 {t3_val}")
    else:
        v7 = False
        t3_mismatch_info.append("T3 산출물 파일 없음")
    print(f" 7. 2022~2025 월 집계 연도별 합과 T3 결과 동적 일치: {'[PASS]' if v7 else '[FAIL]'} {t3_mismatch_info if not v7 else ''}")
    
    # 8. 원본 데이터 MD5 불변 검증
    final_md5 = get_file_md5(INPUT_CSV)
    v8 = (initial_md5 == final_md5)
    print(f" 8. 원본 데이터 미수정 확인(MD5): {'[PASS]' if v8 else '[FAIL]'}")
    
    # 9. 각 관광지별 2022-01~2026-08 월 집계 합계 == 원자료 해당 관광지의 2022-01~2026-08 리뷰 수 일치
    v9 = True
    direct_match_info = []
    df_raw_period = df_raw[df_raw["year_month"].isin(period_df["year_month"])].copy()
    for p in FOCAL_ATTRACTIONS:
        m_sum = df_top3_monthly[df_top3_monthly["place"] == p]["total_count"].sum()
        raw_cnt = len(df_raw_period[df_raw_period["place"] == p])
        if m_sum != raw_cnt:
            v9 = False
            direct_match_info.append(f"{p}: 집계합 {m_sum} != 원자료필터 {raw_cnt}")
        else:
            direct_match_info.append(f"{p}: {m_sum:,}건")
    print(f" 9. 각 관광지별 월 집계 합계와 원자료 대상기간(2022-01~2026-08) 일치: {'[PASS]' if v9 else '[FAIL]'} ({', '.join(direct_match_info)})")
    
    all_passed = v1 and v2 and v3 and v4 and v5 and v6 and v7 and v8 and v9
    print("-" * 80)
    print(f" >> 전체 검증 결과: {'모든 검증 통과 (ALL PASSED)' if all_passed else '검증 실패 항목 존재 (FAILED)'}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 5. 그래프 생성 (300dpi PNG)
    # --------------------------------------------------------------------------
    setup_matplotlib_font()
    
    # 56개 월 x축 인덱스 및 레이블 준비
    all_yms = period_df["year_month"].tolist()
    x_indices = np.arange(len(all_yms))
    
    # x축 tick: 각 연도의 1월과 7월 표기 (2022-01, 2022-07, 2023-01, ...)
    tick_indices = [i for i, ym in enumerate(all_yms) if ym.endswith("-01") or ym.endswith("-07")]
    tick_labels = [all_yms[i] for i in tick_indices]
    
    # --------------------------------------------------------------------------
    # 그래프 A: 상위 3곳 월별 추이 비교 (Overview)
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 6.2), dpi=300)
    
    colors = {"붕어섬생태공원": "#2B6CB0", "임실치즈테마파크": "#D69E2E", "옥정호출렁다리": "#319795"}
    markers = {"붕어섬생태공원": "o", "임실치즈테마파크": "s", "옥정호출렁다리": "^"}
    
    for place in FOCAL_ATTRACTIONS:
        sub = df_top3_monthly[df_top3_monthly["place"] == place].sort_values("year_month")
        vals = sub["total_count"].values
        ax.plot(x_indices, vals, marker=markers[place], markersize=5.5, linewidth=1.9, label=place, color=colors[place])
        
    ax.set_title("상위 3대 집중 관광지 월별 리뷰 추이 비교 (2022-01 ~ 2026-08)", fontsize=14, pad=15, fontweight="bold")
    ax.set_xlabel("연월 (Year-Month)", fontsize=12, labelpad=10)
    ax.set_ylabel("월간 리뷰 수 (건)", fontsize=12, labelpad=10)
    ax.set_xticks(tick_indices)
    ax.set_xticklabels(tick_labels, fontsize=10, rotation=0)
    ax.set_xlim(-0.8, len(all_yms) - 0.2)
    ax.set_ylim(0, df_top3_monthly["total_count"].max() * 1.15)
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right", frameon=True, fontsize=11)
    
    # 2026-08 부분월 안내 주석
    ax.annotate(
        "※ 2026-08은 8월 10일까지의 부분월(Partial Month) 데이터임",
        xy=(0.01, 0.02),
        xycoords="axes fraction",
        fontsize=9.5,
        color="#718096",
        style="italic"
    )
    
    plt.tight_layout()
    plt.savefig(PNG_OVERVIEW, dpi=300)
    plt.close()
    print(f"\n[그래프 A 저장 완료] {PNG_OVERVIEW}")

    # --------------------------------------------------------------------------
    # 그래프 B~D: 관광지별 월별 상세 그래프 (3종)
    # --------------------------------------------------------------------------
    png_map = {
        "붕어섬생태공원": PNG_BUNGEO,
        "임실치즈테마파크": PNG_CHEESE,
        "옥정호출렁다리": PNG_BRIDGE
    }
    
    for place in FOCAL_ATTRACTIONS:
        fig, ax = plt.subplots(figsize=(11, 5.8), dpi=300)
        sub = df_top3_monthly[df_top3_monthly["place"] == place].sort_values("year_month").reset_index(drop=True)
        vals = sub["total_count"].values
        
        ax.plot(x_indices, vals, marker=markers[place], markersize=6, linewidth=2.0, color=colors[place], label=f"{place} 월별 리뷰 수")
        
        # 1. 전체 기간 최고 월 찾기
        max_idx = sub["total_count"].idxmax()
        max_ym = sub.loc[max_idx, "year_month"]
        max_val = sub.loc[max_idx, "total_count"]
        
        # 2. 완전월 대상 최대 증가(mom_change) 월 찾기
        sub_full = sub[sub["coverage_status"] == "full_month"].dropna(subset=["mom_change"])
        max_inc_idx = sub_full["mom_change"].idxmax()
        max_inc_ym = sub.loc[max_inc_idx, "year_month"]
        max_inc_val = sub.loc[max_inc_idx, "total_count"]
        max_inc_diff = int(sub.loc[max_inc_idx, "mom_change"])
        
        # 최고점 표기
        ax.annotate(
            f"전체 최고치: {max_val}건\n({max_ym})",
            xy=(max_idx, max_val),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center",
            fontsize=9.5,
            fontweight="bold",
            color="#b30000",
            arrowprops=dict(arrowstyle="->", color="#b30000", lw=1.2)
        )
        
        # 최대 증가점 표기 (최고점과 다른 월일 경우에만 별도 표기, 같으면 오프셋 조정)
        if max_inc_idx != max_idx:
            ax.annotate(
                f"최대 증가: +{max_inc_diff}건\n({max_inc_ym})",
                xy=(max_inc_idx, max_inc_val),
                xytext=(0, 14),
                textcoords="offset points",
                ha="center",
                fontsize=9.5,
                fontweight="bold",
                color="#1A365D",
                arrowprops=dict(arrowstyle="->", color="#1A365D", lw=1.2)
            )
        else:
            # 최고점이 곧 최대 증가점인 경우
            pass
            
        ax.set_title(f"{place} 월별 리뷰 추이 (2022-01 ~ 2026-08)", fontsize=13.5, pad=15, fontweight="bold")
        ax.set_xlabel("연월 (Year-Month)", fontsize=11.5, labelpad=10)
        ax.set_ylabel("월간 리뷰 수 (건)", fontsize=11.5, labelpad=10)
        ax.set_xticks(tick_indices)
        ax.set_xticklabels(tick_labels, fontsize=10, rotation=0)
        ax.set_xlim(-0.8, len(all_yms) - 0.2)
        ax.set_ylim(0, max(vals) * 1.25)
        ax.grid(True, linestyle="--", alpha=0.5, axis="y")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(loc="upper right", frameon=True, fontsize=10.5)
        
        # 부분월 주석
        ax.annotate(
            "※ 2026-08은 8월 10일까지의 부분월(Partial Month) 데이터임",
            xy=(0.01, 0.02),
            xycoords="axes fraction",
            fontsize=9.5,
            color="#718096",
            style="italic"
        )
        
        target_png = png_map[place]
        plt.tight_layout()
        plt.savefig(target_png, dpi=300)
        plt.close()
        print(f"[상세 그래프 저장 완료] {target_png}")

    # --------------------------------------------------------------------------
    # 6. 콘솔 요약 출력
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [각 관광지별 전체 기간 월별 최고치 요약]")
    print("=" * 80)
    for place in FOCAL_ATTRACTIONS:
        sub = df_top3_monthly[df_top3_monthly["place"] == place]
        max_r = sub.loc[sub["total_count"].idxmax()]
        print(f" - {place:<12}: 최고 월 = {max_r['year_month']}, 리뷰 수 = {int(max_r['total_count'])}건 (Google {int(max_r['google_count'])}, Naver {int(max_r['naver_count'])})")
        
    print("\n" + "=" * 80)
    print(" [각 관광지별 MoM 최대 증가(급증) 월 요약 (완전월 기준)]")
    print("=" * 80)
    for place in FOCAL_ATTRACTIONS:
        top1_r = df_increases[(df_increases["place"] == place) & (df_increases["rank"] == 1)].iloc[0]
        print(f" - {place:<12}: 최대 증가 월 = {top1_r['year_month']}, 직전월 = {int(top1_r['previous_month_count'])}건 -> 해당월 = {int(top1_r['current_month_count'])}건 (증가량 = +{int(top1_r['mom_change'])}건)")

    print("\n" + "=" * 80)
    print(" [각 관광지별 MoM 증가량 상위 5개 월 전체 표]")
    print("=" * 80)
    print(f"{'관광지명':<12}{'순위':>4}{'연월':>10}{'직전월수':>10}{'해당월수':>10}{'증가량':>10}{'Google':>9}{'Naver':>9}")
    print("-" * 76)
    for idx, row in df_increases.iterrows():
        print(f"{row['place']:<12}{int(row['rank']):>4}{row['year_month']:>10}{int(row['previous_month_count']):>10}{int(row['current_month_count']):>10}{'+' + str(int(row['mom_change'])):>10}{int(row['google_count']):>9}{int(row['naver_count']):>9}")
    print("=" * 80)


if __name__ == "__main__":
    main()
