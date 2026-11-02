# -*- coding: utf-8 -*-
"""
임실군 주요 관광지 리뷰 계절성 분석 (2022~2025)
파일명: monthly_seasonality_analysis.py

목적:
  1. 2022~2025년 4개 완전 연도의 월별 리뷰 수(Google, Naver, Total) 원자료 집계 (48행)
  2. 4개 연도 월별 계절성 평균 계산 (12행)
  3. 연도별 리뷰 규모 효과를 통제한 월별 점유율(monthly_share) 계절성 평균 계산 (보조 강건성 검증)
  4. 데이터 무결성 6대 항목 자동 검증
  5. 논문/보고서용 고해상도(300dpi) 시계열 계절성 시각화 그래프 2종 생성
"""

import os
import hashlib
import itertools
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==============================================================================
# 0. 경로 설정
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 프로젝트 루트: "임실 데이터 수집"
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

INPUT_CSV = os.path.join(PROJECT_ROOT, "data", "임실군_관광지_리뷰데이터.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# 산출물 경로
CSV_MONTHLY_COUNTS = os.path.join(OUTPUT_DIR, "monthly_counts_2022_2025.csv")
CSV_SEASONALITY = os.path.join(OUTPUT_DIR, "monthly_seasonality_2022_2025.csv")
CSV_SEASONALITY_SHARE = os.path.join(OUTPUT_DIR, "monthly_seasonality_share_2022_2025.csv")
PNG_TOTAL = os.path.join(OUTPUT_DIR, "monthly_seasonality_total.png")
PNG_PLATFORM = os.path.join(OUTPUT_DIR, "monthly_seasonality_platform.png")

# 분석 대상 연도
TARGET_YEARS = [2022, 2023, 2024, 2025]


def get_file_md5(filepath):
    """파일의 MD5 해시를 계산하여 원본 데이터 불변성을 확인합니다."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def setup_matplotlib_font():
    """Windows 환경 한글 폰트(맑은 고딕) 설정 및 마이너스 부호 깨짐 방지."""
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.size"] = 11


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 80)
    print(" [T2] 임실군 주요 관광지 리뷰 계절성 분석 (2022~2025)")
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
    print(f"[전체 원본 행 수] {raw_total_rows:,}건 (Google/Naver 통합)")
    
    # 날짜 파싱
    df_raw["parsed_date"] = pd.to_datetime(df_raw["date"], errors="coerce")
    if df_raw["parsed_date"].isna().any():
        raise ValueError("날짜 파싱 실패(NaT)가 원본 데이터에 존재합니다.")
        
    df_raw["year"] = df_raw["parsed_date"].dt.year
    df_raw["month"] = df_raw["parsed_date"].dt.month
    
    # 2022~2025 완전 연도 필터링 (2026년 부분연도 제외)
    df_filtered = df_raw[df_raw["year"].isin(TARGET_YEARS)].copy()
    filtered_total_rows = len(df_filtered)
    print(f"[2022~2025 대상 행 수] {filtered_total_rows:,}건 (2026년 {raw_total_rows - filtered_total_rows:,}건 제외)")
    
    # --------------------------------------------------------------------------
    # 2. [산출물 1] 월별 원자료 집계 (4개 연도 x 12개월 = 48행)
    # --------------------------------------------------------------------------
    # 48개 전체 (year, month) 조합 그리드 생성
    grid = list(itertools.product(TARGET_YEARS, range(1, 13)))
    df_grid = pd.DataFrame(grid, columns=["year", "month"])
    
    # 플랫폼별 및 전체 집계
    counts = (
        df_filtered.groupby(["year", "month", "platform"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    
    # 누락된 플랫폼 컬럼 방어
    if "구글" not in counts.columns:
        counts["구글"] = 0
    if "네이버" not in counts.columns:
        counts["네이버"] = 0
        
    # 그리드와 결합하여 리뷰가 0건인 월도 보존
    df_monthly = pd.merge(df_grid, counts, on=["year", "month"], how="left").fillna(0)
    
    df_monthly["google_count"] = df_monthly["구글"].astype(int)
    df_monthly["naver_count"] = df_monthly["네이버"].astype(int)
    df_monthly["total_count"] = df_monthly["google_count"] + df_monthly["naver_count"]
    
    # 결과 데이터프레임 정리 (명세 기준 컬럼)
    df_monthly_out = df_monthly[["year", "month", "google_count", "naver_count", "total_count"]].copy()
    df_monthly_out = df_monthly_out.rename(columns={
        "google_count": "Google 리뷰 수",
        "naver_count": "Naver 리뷰 수",
        "total_count": "전체 리뷰 수"
    })
    
    df_monthly_out.to_csv(CSV_MONTHLY_COUNTS, index=False, encoding="utf-8-sig")
    print(f"\n[저장 완료] 월별 원자료 집계: {CSV_MONTHLY_COUNTS} ({len(df_monthly_out)}행)")

    # --------------------------------------------------------------------------
    # 3. [산출물 2] 월별 계절성 평균 계산 (12행)
    # --------------------------------------------------------------------------
    # 계산 과정에서는 반올림하지 않고 실수값(float) 보존
    seasonality_records = []
    for m in range(1, 13):
        m_subset = df_monthly[df_monthly["month"] == m]
        g_mean = m_subset["google_count"].mean()
        n_mean = m_subset["naver_count"].mean()
        t_mean = m_subset["total_count"].mean()
        
        seasonality_records.append({
            "month": m,
            "google_mean": g_mean,
            "naver_mean": n_mean,
            "total_mean": t_mean
        })
        
    df_seasonality = pd.DataFrame(seasonality_records)
    df_seasonality.to_csv(CSV_SEASONALITY, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] 월별 계절성 평균: {CSV_SEASONALITY} ({len(df_seasonality)}행)")

    # --------------------------------------------------------------------------
    # 4. [산출물 3 (신규)] 연도별 점유율(Share) 기반 계절성 보조 검증 (12행)
    # --------------------------------------------------------------------------
    # 각 연도별로 해당 연도 전체 리뷰 수 대비 월별 점유율(monthly_share) 계산
    df_monthly["google_share"] = 0.0
    df_monthly["naver_share"] = 0.0
    df_monthly["total_share"] = 0.0
    
    for y in TARGET_YEARS:
        mask = df_monthly["year"] == y
        y_total = df_monthly.loc[mask, "total_count"].sum()
        y_google = df_monthly.loc[mask, "google_count"].sum()
        y_naver = df_monthly.loc[mask, "naver_count"].sum()
        
        df_monthly.loc[mask, "total_share"] = df_monthly.loc[mask, "total_count"] / y_total if y_total > 0 else 0.0
        df_monthly.loc[mask, "google_share"] = df_monthly.loc[mask, "google_count"] / y_google if y_google > 0 else 0.0
        df_monthly.loc[mask, "naver_share"] = df_monthly.loc[mask, "naver_count"] / y_naver if y_naver > 0 else 0.0
        
    share_records = []
    for m in range(1, 13):
        m_subset = df_monthly[df_monthly["month"] == m]
        g_share_mean = m_subset["google_share"].mean()
        n_share_mean = m_subset["naver_share"].mean()
        t_share_mean = m_subset["total_share"].mean()
        
        share_records.append({
            "month": m,
            "google_share_mean": g_share_mean,
            "naver_share_mean": n_share_mean,
            "total_share_mean": t_share_mean
        })
        
    df_share = pd.DataFrame(share_records)
    df_share.to_csv(CSV_SEASONALITY_SHARE, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] 월별 점유율 계절성 평균: {CSV_SEASONALITY_SHARE} ({len(df_share)}행)")

    # --------------------------------------------------------------------------
    # 5. 자동 검증 (6개 항목 - 하드코딩 제거 반영)
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [자동 검증 실행 결과]")
    print("=" * 80)
    
    v1 = sorted(df_monthly["year"].unique().tolist()) == TARGET_YEARS
    print(f" 1. 분석 대상 연도 [2022, 2023, 2024, 2025] 일치: {'[PASS]' if v1 else '[FAIL]'}")
    
    v2 = len(df_monthly) == 48
    print(f" 2. 48개 year-month 조합 존재: {'[PASS]' if v2 else '[FAIL]'} (실제 {len(df_monthly)}개 조합)")
    
    v3 = (df_monthly["google_count"] + df_monthly["naver_count"] == df_monthly["total_count"]).all()
    print(f" 3. 각 year-month에서 Google + Naver = Total 일치: {'[PASS]' if v3 else '[FAIL]'}")
    
    # 하드코딩 수치(4977) 조건 제거: 필터링된 원자료 총행 수와 월 집계 총합의 동등성만 자동 검증
    monthly_sum = df_monthly["total_count"].sum()
    v4 = (monthly_sum == filtered_total_rows)
    print(f" 4. 원자료 필터 행수({filtered_total_rows:,}건)와 월 집계 총합({monthly_sum:,}건) 일치: {'[PASS]' if v4 else '[FAIL]'}")
    
    # 4개 연도 total 직접 평균과 total_mean 일치 여부 (부동소수점 오차 감안)
    v5 = True
    for idx, row in df_seasonality.iterrows():
        m = int(row["month"])
        direct_avg = df_monthly[df_monthly["month"] == m]["total_count"].sum() / 4.0
        if not np.isclose(row["total_mean"], direct_avg):
            v5 = False
            break
    print(f" 5. 월별 평균 total_mean과 4개 연도 total 직접 평균 일치: {'[PASS]' if v5 else '[FAIL]'}")
    
    final_md5 = get_file_md5(INPUT_CSV)
    v6 = (initial_md5 == final_md5)
    print(f" 6. 원본 데이터 미수정 확인: {'[PASS]' if v6 else '[FAIL]'} (MD5 일치)")
    
    all_passed = v1 and v2 and v3 and v4 and v5 and v6
    print("-" * 80)
    print(f" >> 전체 검증 결과: {'모든 검증 통과 (ALL PASSED)' if all_passed else '검증 실패 항목 존재 (FAILED)'}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 6. 그래프 생성 (300dpi PNG)
    # --------------------------------------------------------------------------
    setup_matplotlib_font()
    
    months = df_seasonality["month"].values
    t_means = df_seasonality["total_mean"].values
    g_means = df_seasonality["google_mean"].values
    n_means = df_seasonality["naver_mean"].values
    
    # --------------------------------------------------------------------------
    # 그래프 A: 2022~2025 월별 평균 리뷰 수 (전체 total_mean)
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    
    ax.plot(months, t_means, marker="o", markersize=7, color="#1f77b4", linewidth=2.2, label="전체 월평균 리뷰 수")
    
    # 주요 피크 및 데이터 포인트 텍스트 표시
    for m, val in zip(months, t_means):
        if m in [5, 10]:
            ax.annotate(
                f"{val:.1f}건\n({m}월 피크)",
                xy=(m, val),
                xytext=(0, 10),
                textcoords="offset points",
                ha="center",
                fontsize=10,
                fontweight="bold",
                color="#b30000"
            )
        elif m in [1, 2]:
            ax.annotate(
                f"{val:.1f}건",
                xy=(m, val),
                xytext=(0, -16),
                textcoords="offset points",
                ha="center",
                fontsize=9,
                color="#555555"
            )
        else:
            ax.annotate(
                f"{val:.1f}건",
                xy=(m, val),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                fontsize=9,
                color="#333333"
            )
            
    ax.set_title("2022~2025 월별 평균 리뷰 수 (계절성 패턴)", fontsize=14, pad=15, fontweight="bold")
    ax.set_xlabel("월 (Month)", fontsize=12, labelpad=10)
    ax.set_ylabel("월평균 리뷰 수 (건)", fontsize=12, labelpad=10)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels([f"{m}월" for m in range(1, 13)], fontsize=11)
    ax.set_ylim(0, max(t_means) * 1.22)
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper left", frameon=True, fontsize=11)
    
    plt.tight_layout()
    plt.savefig(PNG_TOTAL, dpi=300)
    plt.close()
    print(f"[그래프 A 저장 완료] {PNG_TOTAL}")

    # --------------------------------------------------------------------------
    # 그래프 B: 2022~2025 플랫폼별 월평균 리뷰 수 비교 (Google vs Naver)
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    
    ax.plot(months, g_means, marker="s", markersize=6.5, color="#4285F4", linewidth=2.0, label="Google (구글)")
    ax.plot(months, n_means, marker="^", markersize=7.0, color="#03C75A", linewidth=2.0, label="Naver (네이버)")
    
    # 피크 포인트 강조 표기 (5월, 10월)
    for m, g_val, n_val in zip(months, g_means, n_means):
        if m in [5, 10]:
            ax.annotate(f"{g_val:.1f}", xy=(m, g_val), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9, fontweight="bold", color="#1a53b0")
            ax.annotate(f"{n_val:.1f}", xy=(m, n_val), xytext=(0, -15), textcoords="offset points", ha="center", fontsize=9, fontweight="bold", color="#02853c")
            
    ax.set_title("2022~2025 플랫폼별 월평균 리뷰 수 비교 (Google vs Naver)", fontsize=14, pad=15, fontweight="bold")
    ax.set_xlabel("월 (Month)", fontsize=12, labelpad=10)
    ax.set_ylabel("월평균 리뷰 수 (건)", fontsize=12, labelpad=10)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels([f"{m}월" for m in range(1, 13)], fontsize=11)
    ax.set_ylim(0, max(max(g_means), max(n_means)) * 1.25)
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper left", frameon=True, fontsize=11)
    
    plt.tight_layout()
    plt.savefig(PNG_PLATFORM, dpi=300)
    plt.close()
    print(f"[그래프 B 저장 완료] {PNG_PLATFORM}")

    # --------------------------------------------------------------------------
    # 7. 콘솔 요약 출력
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [월별 계절성 평균 요약표 (절대 건수)]")
    print("=" * 80)
    print(f"{'월':<6}{'Google 평균':>14}{'Naver 평균':>14}{'전체 평균':>14}")
    print("-" * 50)
    for idx, row in df_seasonality.iterrows():
        m = int(row["month"])
        print(f"{m:>2}월 {row['google_mean']:>14.2f} {row['naver_mean']:>14.2f} {row['total_mean']:>14.2f}")
    print("-" * 50)
    
    # 절대 건수 기준 최고/최저 월
    max_row = df_seasonality.loc[df_seasonality["total_mean"].idxmax()]
    min_row = df_seasonality.loc[df_seasonality["total_mean"].idxmin()]
    max_g_row = df_seasonality.loc[df_seasonality["google_mean"].idxmax()]
    max_n_row = df_seasonality.loc[df_seasonality["naver_mean"].idxmax()]
    
    print(f"[절대건수 전체 최고 월] {int(max_row['month'])}월 (월평균 {max_row['total_mean']:.2f}건)")
    print(f"[절대건수 전체 최저 월] {int(min_row['month'])}월 (월평균 {min_row['total_mean']:.2f}건)")
    print(f"[절대건수 Google 최고 월] {int(max_g_row['month'])}월 (월평균 {max_g_row['google_mean']:.2f}건)")
    print(f"[절대건수 Naver 최고 월] {int(max_n_row['month'])}월 (월평균 {max_n_row['naver_mean']:.2f}건)")

    # --------------------------------------------------------------------------
    # 8. 점유율(Share) 계절성 보조 검증 출력
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [월별 점유율(Share) 계절성 보조 검증 요약표 (비율 %)]")
    print("=" * 80)
    print(f"{'월':<6}{'Google Share Mean':>20}{'Naver Share Mean':>20}{'Total Share Mean':>20}")
    print("-" * 68)
    for idx, row in df_share.iterrows():
        m = int(row["month"])
        print(f"{m:>2}월 {row['google_share_mean']*100:>19.2f}% {row['naver_share_mean']*100:>19.2f}% {row['total_share_mean']*100:>19.2f}%")
    print("-" * 68)
    
    max_share_total = df_share.loc[df_share["total_share_mean"].idxmax()]
    max_share_g = df_share.loc[df_share["google_share_mean"].idxmax()]
    max_share_n = df_share.loc[df_share["naver_share_mean"].idxmax()]
    
    share_m5 = df_share.loc[df_share["month"] == 5, "total_share_mean"].values[0]
    share_m10 = df_share.loc[df_share["month"] == 10, "total_share_mean"].values[0]
    share_m2 = df_share.loc[df_share["month"] == 2, "total_share_mean"].values[0]
    
    print(f"total_share_mean 최고 월: {int(max_share_total['month'])}월 ({max_share_total['total_share_mean']*100:.2f}%)")
    print(f"google_share_mean 최고 월: {int(max_share_g['month'])}월 ({max_share_g['google_share_mean']*100:.2f}%)")
    print(f"naver_share_mean 최고 월: {int(max_share_n['month'])}월 ({max_share_n['naver_share_mean']*100:.2f}%)")
    print(f"5월 total_share_mean: {share_m5*100:.2f}% ({share_m5:.6f})")
    print(f"10월 total_share_mean: {share_m10*100:.2f}% ({share_m10:.6f})")
    print(f"2월 total_share_mean: {share_m2*100:.2f}% ({share_m2:.6f})")
    print("=" * 80)


if __name__ == "__main__":
    main()
