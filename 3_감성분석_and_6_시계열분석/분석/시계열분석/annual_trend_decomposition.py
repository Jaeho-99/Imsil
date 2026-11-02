# -*- coding: utf-8 -*-
"""
임실군 주요 관광지 연도별 리뷰 추이 및 구성 분해 분석 (2022~2025)
파일명: annual_trend_decomposition.py

목적:
  1. 임실군 전체 리뷰 수의 연도별 변화(2022~2025)에서 상위 3대 집중 관광지와
     나머지 관광지의 구성 및 기여도를 분해 집계
  2. 상위 3대 집중 관광지(붕어섬생태공원, 임실치즈테마파크, 옥정호출렁다리)의 개별 추이 집계
  3. 플랫폼(Google/Naver) 구성비 보조 집계
  4. 데이터 무결성 7대 항목 자동 검증 및 교차검산
  5. 고해상도(300dpi) 시각화 그래프 2종 생성 (전체 구조 분해, 상위 3곳 개별 추이)
"""

import os
import hashlib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==============================================================================
# 0. 설정 및 경로
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

INPUT_CSV = os.path.join(PROJECT_ROOT, "data", "임실군_관광지_리뷰데이터.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# 산출물 경로
CSV_ANNUAL_DECOMP = os.path.join(OUTPUT_DIR, "annual_trend_decomposition_2022_2025.csv")
CSV_ANNUAL_PLATFORM = os.path.join(OUTPUT_DIR, "annual_platform_counts_2022_2025.csv")
PNG_STRUCTURE = os.path.join(OUTPUT_DIR, "annual_trend_structure_2022_2025.png")
PNG_TOP3 = os.path.join(OUTPUT_DIR, "annual_trend_top3_2022_2025.png")

# 분석 대상 고정 정의
TARGET_YEARS = [2022, 2023, 2024, 2025]
FOCAL_ATTRACTIONS = [
    "붕어섬생태공원",
    "임실치즈테마파크",
    "옥정호출렁다리"
]

# 기존 탐색 교차검산 기준값
BENCHMARK = {
    2022: {"붕어섬": 31, "치즈테마파크": 582, "출렁다리": 100, "상위3곳제외": 479, "total": 1192},
    2023: {"붕어섬": 633, "치즈테마파크": 324, "출렁다리": 504, "상위3곳제외": 356, "total": 1817},
    2024: {"붕어섬": 530, "치즈테마파크": 187, "출렁다리": 199, "상위3곳제외": 322, "total": 1238},
    2025: {"붕어섬": 309, "치즈테마파크": 143, "출렁다리": 119, "상위3곳제외": 159, "total": 730},
}


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


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 80)
    print(" [T3] 임실군 주요 관광지 연도별 리뷰 추이의 구성 분해 분석 (2022~2025)")
    print("=" * 80)
    
    # --------------------------------------------------------------------------
    # 1. 데이터 로드 및 무결성 기록
    # --------------------------------------------------------------------------
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"입력 데이터 파일을 찾을 수 없습니다: {INPUT_CSV}")
        
    initial_md5 = get_file_md5(INPUT_CSV)
    print(f"[입력 파일] {INPUT_CSV}")
    print(f"[파일 해시(MD5)] {initial_md5}")
    
    df_raw = pd.read_csv(INPUT_CSV, encoding="utf-8-sig", dtype=str)
    raw_total_rows = len(df_raw)
    print(f"[전체 원본 행 수] {raw_total_rows:,}건")
    
    # 날짜 파싱 및 연도 필터링
    df_raw["parsed_date"] = pd.to_datetime(df_raw["date"], errors="coerce")
    if df_raw["parsed_date"].isna().any():
        raise ValueError("날짜 파싱 실패(NaT)가 데이터에 존재합니다.")
        
    df_raw["year"] = df_raw["parsed_date"].dt.year
    df_filtered = df_raw[df_raw["year"].isin(TARGET_YEARS)].copy()
    filtered_total_rows = len(df_filtered)
    print(f"[2022~2025 대상 행 수] {filtered_total_rows:,}건 (2026년 {raw_total_rows - filtered_total_rows:,}건 제외)")
    
    # --------------------------------------------------------------------------
    # 2. [산출물 1] 연도별 관광지 구성 분해 집계
    # --------------------------------------------------------------------------
    decomp_rows = []
    
    for y in TARGET_YEARS:
        df_y = df_filtered[df_filtered["year"] == y]
        total_count = len(df_y)
        
        # 상위 3곳 각각 건수
        c_bung = len(df_y[df_y["place"] == FOCAL_ATTRACTIONS[0]])
        c_cheese = len(df_y[df_y["place"] == FOCAL_ATTRACTIONS[1]])
        c_bridge = len(df_y[df_y["place"] == FOCAL_ATTRACTIONS[2]])
        
        top3_count = c_bung + c_cheese + c_bridge
        others_count = total_count - top3_count
        top3_share = top3_count / total_count if total_count > 0 else 0.0
        
        decomp_rows.append({
            "year": y,
            "total_count": total_count,
            "붕어섬생태공원": c_bung,
            "임실치즈테마파크": c_cheese,
            "옥정호출렁다리": c_bridge,
            "top3_count": top3_count,
            "others_count": others_count,
            "top3_share": top3_share
        })
        
    df_decomp = pd.DataFrame(decomp_rows)
    df_decomp.to_csv(CSV_ANNUAL_DECOMP, index=False, encoding="utf-8-sig")
    print(f"\n[저장 완료] 연도별 구성 분해 집계: {CSV_ANNUAL_DECOMP} ({len(df_decomp)}행)")

    # --------------------------------------------------------------------------
    # 3. [산출물 2] 보조 자료 - 연도별 플랫폼 분포
    # --------------------------------------------------------------------------
    platform_rows = []
    for y in TARGET_YEARS:
        df_y = df_filtered[df_filtered["year"] == y]
        t_cnt = len(df_y)
        g_cnt = len(df_y[df_y["platform"] == "구글"])
        n_cnt = len(df_y[df_y["platform"] == "네이버"])
        
        g_share = g_cnt / t_cnt if t_cnt > 0 else 0.0
        n_share = n_cnt / t_cnt if t_cnt > 0 else 0.0
        
        platform_rows.append({
            "year": y,
            "google_count": g_cnt,
            "naver_count": n_cnt,
            "total_count": t_cnt,
            "google_share": g_share,
            "naver_share": n_share
        })
        
    df_platform = pd.DataFrame(platform_rows)
    df_platform.to_csv(CSV_ANNUAL_PLATFORM, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] 연도별 플랫폼 분포: {CSV_ANNUAL_PLATFORM} ({len(df_platform)}행)")

    # --------------------------------------------------------------------------
    # 4. 자동 검증 (7대 항목) 및 교차검산
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [자동 검증 실행 결과]")
    print("=" * 80)
    
    # 1. 분석 대상 연도 일치
    v1 = sorted(df_decomp["year"].tolist()) == TARGET_YEARS
    print(f" 1. 분석 대상 연도 [2022, 2023, 2024, 2025] 일치: {'[PASS]' if v1 else '[FAIL]'}")
    
    # 2. FOCAL_ATTRACTIONS 3곳 존재 확인
    available_places = set(df_filtered["place"].unique())
    v2 = all(p in available_places for p in FOCAL_ATTRACTIONS)
    print(f" 2. FOCAL_ATTRACTIONS 3곳 데이터 내 존재 확인: {'[PASS]' if v2 else '[FAIL]'}")
    
    # 3. 붕어섬 + 치즈테마파크 + 출렁다리 = top3_count
    v3 = (df_decomp["붕어섬생태공원"] + df_decomp["임실치즈테마파크"] + df_decomp["옥정호출렁다리"] == df_decomp["top3_count"]).all()
    print(f" 3. 붕어섬 + 치즈테마파크 + 출렁다리 = top3_count 일치: {'[PASS]' if v3 else '[FAIL]'}")
    
    # 4. top3_count + others_count = total_count
    v4 = (df_decomp["top3_count"] + df_decomp["others_count"] == df_decomp["total_count"]).all()
    print(f" 4. top3_count + others_count = total_count 일치: {'[PASS]' if v4 else '[FAIL]'}")
    
    # 5. 전체 합계와 원자료 필터 행수 일치 (주 검증) / T2 4,977건은 교차검산용으로 출력
    decomp_sum = df_decomp["total_count"].sum()
    v5 = (decomp_sum == filtered_total_rows)
    print(f" 5. 연도별 total 합계({decomp_sum:,}건)와 원자료 필터 행수({filtered_total_rows:,}건) 일치: {'[PASS]' if v5 else '[FAIL]'} (T2 교차검산: 4,977건)")
    
    # 6. top3_share 일치
    v6 = np.isclose(df_decomp["top3_share"], df_decomp["top3_count"] / df_decomp["total_count"]).all()
    print(f" 6. top3_share = top3_count / total_count 일치: {'[PASS]' if v6 else '[FAIL]'}")
    
    # 7. 플랫폼 집계 google + naver = total
    v7_plat = (df_platform["google_count"] + df_platform["naver_count"] == df_platform["total_count"]).all()
    print(f" 7-1. 플랫폼 집계 Google + Naver = Total 일치: {'[PASS]' if v7_plat else '[FAIL]'}")
    
    # 원본 파일 MD5 불변 검증
    final_md5 = get_file_md5(INPUT_CSV)
    v7_md5 = (initial_md5 == final_md5)
    print(f" 7-2. 원본 데이터 미수정 확인(MD5): {'[PASS]' if v7_md5 else '[FAIL]'}")
    
    all_passed = v1 and v2 and v3 and v4 and v5 and v6 and v7_plat and v7_md5
    print("-" * 80)
    print(f" >> 전체 검증 결과: {'모든 검증 통과 (ALL PASSED)' if all_passed else '검증 실패 항목 존재 (FAILED)'}")
    print("=" * 80)
    
    # --------------------------------------------------------------------------
    # 교차검산 (Benchmark Comparison)
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [기존 잠정 집계와의 교차검산 결과]")
    print("=" * 80)
    benchmark_match = True
    for idx, row in df_decomp.iterrows():
        y = int(row["year"])
        bm = BENCHMARK[y]
        c_b = row["붕어섬생태공원"]
        c_c = row["임실치즈테마파크"]
        c_br = row["옥정호출렁다리"]
        c_oth = row["others_count"]
        c_tot = row["total_count"]
        
        match = (c_b == bm["붕어섬"] and c_c == bm["치즈테마파크"] and 
                 c_br == bm["출렁다리"] and c_oth == bm["상위3곳제외"] and c_tot == bm["total"])
        if not match:
            benchmark_match = False
            print(f"  [불일치 발생] {y}년: 산출값({c_b}, {c_c}, {c_br}, {c_oth}, {c_tot}) != 기준값({bm})")
        else:
            print(f"  {y}년: 붕어섬 {c_b}건, 치즈테마파크 {c_c}건, 출렁다리 {c_br}건, 상위3곳제외 {c_oth}건, 전체 {c_tot}건 -> [100% 일치]")
            
    print(f" >> 교차검산 종합: {'기준값과 완벽히 일치함' if benchmark_match else '차이 발생 (확인 필요)'}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 5. 그래프 생성 (300dpi PNG)
    # --------------------------------------------------------------------------
    setup_matplotlib_font()
    
    years = df_decomp["year"].values
    t_counts = df_decomp["total_count"].values
    top3_counts = df_decomp["top3_count"].values
    others_counts = df_decomp["others_count"].values
    
    b_counts = df_decomp["붕어섬생태공원"].values
    c_counts = df_decomp["임실치즈테마파크"].values
    br_counts = df_decomp["옥정호출렁다리"].values
    
    # --------------------------------------------------------------------------
    # 그래프 A: 연도별 리뷰 추이의 구성 분해 (전체 vs 상위 3곳 합계 vs 상위 3곳 제외)
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9.5, 6), dpi=300)
    
    # 전체 관광지 (굵은 실선, 뚜렷한 색상)
    ax.plot(years, t_counts, marker="o", markersize=8, color="#1A365D", linewidth=2.8, label="전체 관광지")
    # 상위 3곳 합계 (중간 굵기 실선)
    ax.plot(years, top3_counts, marker="s", markersize=7, color="#E53E3E", linewidth=2.2, label="상위 3곳 합계")
    # 상위 3곳 제외 관광지 (파선)
    ax.plot(years, others_counts, marker="^", markersize=7, color="#718096", linewidth=2.0, linestyle="--", label="상위 3곳 제외 관광지")
    
    # 데이터 라벨 표기 (위치 오프셋 조정으로 겹침 방지)
    for y, tot, top3, oth in zip(years, t_counts, top3_counts, others_counts):
        # 전체 관광지 라벨 (상단)
        ax.annotate(f"{tot:,}건", xy=(y, tot), xytext=(0, 10), textcoords="offset points", ha="center", fontsize=10, fontweight="bold", color="#1A365D")
        # 상위 3곳 합계 라벨
        if y == 2022:
            ax.annotate(f"{top3:,}건", xy=(y, top3), xytext=(0, 10), textcoords="offset points", ha="center", fontsize=9.5, fontweight="bold", color="#E53E3E")
        else:
            ax.annotate(f"{top3:,}건", xy=(y, top3), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9.5, fontweight="bold", color="#E53E3E")
        # 상위 3곳 제외 관광지 라벨 (하단)
        ax.annotate(f"{oth:,}건", xy=(y, oth), xytext=(0, -16), textcoords="offset points", ha="center", fontsize=9.5, color="#4A5568")
        
    ax.set_title("2022~2025 연도별 리뷰 추이의 구성 분해", fontsize=14, pad=15, fontweight="bold")
    ax.set_xlabel("연도 (Year)", fontsize=12, labelpad=10)
    ax.set_ylabel("연간 리뷰 수 (건)", fontsize=12, labelpad=10)
    ax.set_xticks(years)
    ax.set_xticklabels([f"{y}년" for y in years], fontsize=11)
    ax.set_ylim(0, max(t_counts) * 1.18)
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right", frameon=True, fontsize=11)
    
    plt.tight_layout()
    plt.savefig(PNG_STRUCTURE, dpi=300)
    plt.close()
    print(f"\n[그래프 A 저장 완료] {PNG_STRUCTURE}")

    # --------------------------------------------------------------------------
    # 그래프 B: 상위 3대 집중 관광지 개별 연도별 추이
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9.5, 6), dpi=300)
    
    ax.plot(years, b_counts, marker="o", markersize=7.5, color="#2B6CB0", linewidth=2.2, label="붕어섬생태공원")
    ax.plot(years, c_counts, marker="s", markersize=7.5, color="#D69E2E", linewidth=2.2, label="임실치즈테마파크")
    ax.plot(years, br_counts, marker="^", markersize=7.5, color="#319795", linewidth=2.2, label="옥정호출렁다리")
    
    # 개별 데이터 라벨 표기
    for y, b_val, c_val, br_val in zip(years, b_counts, c_counts, br_counts):
        # 붕어섬 (2022년은 아래, 이후는 위)
        if y == 2022:
            ax.annotate(f"{b_val}건", xy=(y, b_val), xytext=(0, -16), textcoords="offset points", ha="center", fontsize=9.5, fontweight="bold", color="#2B6CB0")
        else:
            ax.annotate(f"{b_val}건", xy=(y, b_val), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9.5, fontweight="bold", color="#2B6CB0")
            
        # 임실치즈테마파크 (2022년은 위, 2024년은 출렁다리와 겹치지 않게 하단)
        if y in [2022, 2025]:
            ax.annotate(f"{c_val}건", xy=(y, c_val), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9.5, fontweight="bold", color="#B7791F")
        elif y == 2023:
            ax.annotate(f"{c_val}건", xy=(y, c_val), xytext=(0, -16), textcoords="offset points", ha="center", fontsize=9.5, fontweight="bold", color="#B7791F")
        else: # 2024
            ax.annotate(f"{c_val}건", xy=(y, c_val), xytext=(0, -16), textcoords="offset points", ha="center", fontsize=9.5, fontweight="bold", color="#B7791F")
            
        # 옥정호출렁다리
        if y == 2023:
            ax.annotate(f"{br_val}건", xy=(y, br_val), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9.5, fontweight="bold", color="#234E52")
        elif y == 2024:
            ax.annotate(f"{br_val}건", xy=(y, br_val), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9.5, fontweight="bold", color="#234E52")
        elif y == 2025:
            ax.annotate(f"{br_val}건", xy=(y, br_val), xytext=(0, -16), textcoords="offset points", ha="center", fontsize=9.5, fontweight="bold", color="#234E52")
        else: # 2022
            ax.annotate(f"{br_val}건", xy=(y, br_val), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9.5, fontweight="bold", color="#234E52")
            
    ax.set_title("상위 3대 집중 관광지 연도별 리뷰 추이", fontsize=14, pad=15, fontweight="bold")
    ax.set_xlabel("연도 (Year)", fontsize=12, labelpad=10)
    ax.set_ylabel("연간 리뷰 수 (건)", fontsize=12, labelpad=10)
    ax.set_xticks(years)
    ax.set_xticklabels([f"{y}년" for y in years], fontsize=11)
    ax.set_ylim(0, max(max(b_counts), max(c_counts), max(br_counts)) * 1.20)
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right", frameon=True, fontsize=11)
    
    plt.tight_layout()
    plt.savefig(PNG_TOP3, dpi=300)
    plt.close()
    print(f"[그래프 B 저장 완료] {PNG_TOP3}")

    # --------------------------------------------------------------------------
    # 6. 콘솔 최종 출력
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [최종 구성 분해 집계표]")
    print("=" * 80)
    print(f"{'연도':<6}{'전체':>8}{'붕어섬':>10}{'치즈테마':>10}{'출렁다리':>10}{'상위3곳합계':>12}{'상위3곳제외':>12}{'상위3곳비중':>12}")
    print("-" * 80)
    for idx, row in df_decomp.iterrows():
        y = int(row["year"])
        print(f"{y:>4}년 {int(row['total_count']):>8} {int(row['붕어섬생태공원']):>10} {int(row['임실치즈테마파크']):>10} {int(row['옥정호출렁다리']):>10} {int(row['top3_count']):>12} {int(row['others_count']):>12} {row['top3_share']*100:>11.2f}%")
    print("-" * 80)
    tot_all = df_decomp["total_count"].sum()
    tot_top3 = df_decomp["top3_count"].sum()
    tot_others = df_decomp["others_count"].sum()
    tot_b = df_decomp["붕어섬생태공원"].sum()
    tot_c = df_decomp["임실치즈테마파크"].sum()
    tot_br = df_decomp["옥정호출렁다리"].sum()
    tot_share = tot_top3 / tot_all
    print(f"{'합계':<6}{tot_all:>8} {tot_b:>10} {tot_c:>10} {tot_br:>10} {tot_top3:>12} {tot_others:>12} {tot_share*100:>11.2f}%")
    print("=" * 80)
    
    print("\n" + "=" * 80)
    print(" [연도별 플랫폼 구성비 보조표]")
    print("=" * 80)
    print(f"{'연도':<6}{'Google 수':>12}{'Naver 수':>12}{'전체 수':>12}{'Google 비중':>14}{'Naver 비중':>14}")
    print("-" * 72)
    for idx, row in df_platform.iterrows():
        y = int(row["year"])
        print(f"{y:>4}년 {int(row['google_count']):>12} {int(row['naver_count']):>12} {int(row['total_count']):>12} {row['google_share']*100:>13.2f}% {row['naver_share']*100:>13.2f}%")
    print("-" * 72)
    print("=" * 80)


if __name__ == "__main__":
    main()
