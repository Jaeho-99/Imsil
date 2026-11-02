# -*- coding: utf-8 -*-
"""
임실N치즈축제 전·중·후 리뷰 수 및 일평균 리뷰 수 비교 분석 (T-5)
파일명: cheese_festival_review_analysis.py

목적:
  1. T-4에서 확정한 분석 윈도우(cheese_festival_analysis_windows_2022_2025.csv, 12행)를 기반으로
     임실치즈테마파크의 2022~2025 축제 전(pre, 14일), 축제 중(festival, 4~5일), 축제 후(post, 14일)
     리뷰 수(Google, Naver, Total) 및 일평균 리뷰 수(건/일) 계산 (12행)
  2. 4개년 통합 Pooled 일평균 리뷰 수 요약(3행) 산출
  3. 16대 무결성 자동 검증 수행
  4. 연도별 pre / festival / post 일평균 리뷰 수 비교 시각화 차트 생성 (300dpi PNG)
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

RAW_REVIEW_CSV = os.path.join(PROJECT_ROOT, "data", "임실군_관광지_리뷰데이터.csv")
WINDOWS_CSV = os.path.join(BASE_DIR, "output", "cheese_festival_analysis_windows_2022_2025.csv")

OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CSV_COMPARISON = os.path.join(OUTPUT_DIR, "cheese_festival_review_comparison_2022_2025.csv")
CSV_SUMMARY = os.path.join(OUTPUT_DIR, "cheese_festival_review_summary_2022_2025.csv")
PNG_COMPARISON = os.path.join(OUTPUT_DIR, "cheese_festival_review_daily_avg_comparison.png")

TARGET_PLACE = "임실치즈테마파크"
TARGET_YEARS = [2022, 2023, 2024, 2025]
PERIODS = ["pre", "festival", "post"]


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
    print(" [T-5] 임실N치즈축제 전·중·후 리뷰 수 및 일평균 리뷰 수 비교 (2022~2025)")
    print("=" * 80)
    
    # --------------------------------------------------------------------------
    # 1. 파일 로드 및 MD5 해시 기록
    # --------------------------------------------------------------------------
    if not os.path.exists(RAW_REVIEW_CSV):
        raise FileNotFoundError(f"원본 리뷰 파일이 없습니다: {RAW_REVIEW_CSV}")
    if not os.path.exists(WINDOWS_CSV):
        raise FileNotFoundError(f"T-4 윈도우 파일이 없습니다: {WINDOWS_CSV}")
        
    raw_initial_md5 = get_file_md5(RAW_REVIEW_CSV)
    windows_initial_md5 = get_file_md5(WINDOWS_CSV)
    
    print(f"[입력 파일 1 - 원본] {RAW_REVIEW_CSV} (MD5: {raw_initial_md5})")
    print(f"[입력 파일 2 - 윈도우] {WINDOWS_CSV} (MD5: {windows_initial_md5})")
    
    df_raw = pd.read_csv(RAW_REVIEW_CSV, encoding="utf-8-sig", dtype=str)
    df_win = pd.read_csv(WINDOWS_CSV, encoding="utf-8-sig")
    
    # 원본 리뷰 날짜 파싱 및 임실치즈테마파크 필터링
    df_raw["parsed_date"] = pd.to_datetime(df_raw["date"], errors="coerce")
    raw_parse_fails = int(df_raw["parsed_date"].isna().sum())
    if raw_parse_fails > 0:
        raise ValueError(f"원본 날짜 파싱 실패 {raw_parse_fails}건 발생")
        
    df_theme = df_raw[df_raw["place"] == TARGET_PLACE].copy()
    print(f"[임실치즈테마파크 전체 원본 리뷰 수] {len(df_theme):,}건 (Google: {(df_theme['platform']=='구글').sum():,}건, Naver: {(df_theme['platform']=='네이버').sum():,}건)")
    
    # --------------------------------------------------------------------------
    # 2. [산출물 1] 연도별·구간별 상세 집계 (12행)
    # --------------------------------------------------------------------------
    comparison_rows = []
    
    for idx, win in df_win.iterrows():
        yr = int(win["year"])
        period = str(win["period"])
        s_date = str(win["period_start_date"])
        e_date = str(win["period_end_date"])
        days = int(win["days_count"])
        
        # 날짜 필터링 (inclusive)
        sub_df = df_theme[
            (df_theme["parsed_date"] >= s_date) &
            (df_theme["parsed_date"] <= e_date)
        ]
        
        g_cnt = int((sub_df["platform"] == "구글").sum())
        n_cnt = int((sub_df["platform"] == "네이버").sum())
        tot_cnt = g_cnt + n_cnt
        
        g_avg = round(g_cnt / days, 2)
        n_avg = round(n_cnt / days, 2)
        tot_avg = round(tot_cnt / days, 2)
        
        comparison_rows.append({
            "year": yr,
            "period": period,
            "period_start_date": s_date,
            "period_end_date": e_date,
            "days_count": days,
            "google_review_count": g_cnt,
            "naver_review_count": n_cnt,
            "total_review_count": tot_cnt,
            "google_daily_avg": g_avg,
            "naver_daily_avg": n_avg,
            "total_daily_avg": tot_avg
        })
        
    df_comp = pd.DataFrame(comparison_rows)
    df_comp.to_csv(CSV_COMPARISON, index=False, encoding="utf-8-sig")
    print(f"\n[저장 완료] 연도별 상세 비교 CSV: {CSV_COMPARISON} ({len(df_comp)}행)")

    # --------------------------------------------------------------------------
    # 3. [산출물 2] 4개년 통합 Pooled 요약 (3행)
    # --------------------------------------------------------------------------
    summary_rows = []
    
    for period in PERIODS:
        p_sub = df_comp[df_comp["period"] == period]
        
        tot_days = int(p_sub["days_count"].sum())
        tot_g = int(p_sub["google_review_count"].sum())
        tot_n = int(p_sub["naver_review_count"].sum())
        tot_rev = int(p_sub["total_review_count"].sum())
        
        g_daily_avg = round(tot_g / tot_days, 2)
        n_daily_avg = round(tot_n / tot_days, 2)
        tot_daily_avg = round(tot_rev / tot_days, 2)
        
        summary_rows.append({
            "period": period,
            "total_days": tot_days,
            "google_review_count": tot_g,
            "naver_review_count": tot_n,
            "total_review_count": tot_rev,
            "google_daily_avg": g_daily_avg,
            "naver_daily_avg": n_daily_avg,
            "total_daily_avg": tot_daily_avg
        })
        
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(CSV_SUMMARY, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] 4개년 통합 요약 CSV: {CSV_SUMMARY} ({len(df_summary)}행)")

    # --------------------------------------------------------------------------
    # 4. 16대 무결성 자동 검증
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [자동 검증 실행 결과 (16대 항목)]")
    print("=" * 80)
    
    # 1. 원본 리뷰 데이터 존재
    v1 = os.path.exists(RAW_REVIEW_CSV)
    print(f" 1. 원본 리뷰 파일 존재 확인: {'[PASS]' if v1 else '[FAIL]'}")
    
    # 2. T-4 분석 구간 CSV 존재
    v2 = os.path.exists(WINDOWS_CSV)
    print(f" 2. T-4 분석 구간 CSV 존재 확인: {'[PASS]' if v2 else '[FAIL]'}")
    
    # 3. T-4 구간 CSV 행 수 = 12행
    v3 = (len(df_win) == 12)
    print(f" 3. T-4 분석 구간 CSV 12행 확인: {'[PASS]' if v3 else '[FAIL]'}")
    
    # 4. 임실치즈테마파크 원자료 존재
    v4 = (len(df_theme) > 0)
    print(f" 4. 임실치즈테마파크 원자료 존재 확인: {'[PASS]' if v4 else '[FAIL]'}")
    
    # 5. 원본 날짜 파싱 실패 0건
    v5 = (raw_parse_fails == 0)
    print(f" 5. 날짜 파싱 실패 0건 확인: {'[PASS]' if v5 else '[FAIL]'}")
    
    # 6. 연도 내 구간 상호 배타성 (중복 리뷰 0건)
    v6 = True
    for yr in TARGET_YEARS:
        w_sub = df_comp[df_comp["year"] == yr]
        rev_id_sets = []
        for idx, r in w_sub.iterrows():
            m_ids = df_theme[(df_theme["parsed_date"] >= r["period_start_date"]) & (df_theme["parsed_date"] <= r["period_end_date"])]["reviewId"].tolist()
            rev_id_sets.append(set(m_ids))
        if len(rev_id_sets[0].intersection(rev_id_sets[1])) > 0 or len(rev_id_sets[1].intersection(rev_id_sets[2])) > 0 or len(rev_id_sets[0].intersection(rev_id_sets[2])) > 0:
            v6 = False
    print(f" 6. 연도 내 구간 간 중복 리뷰 0건 확인: {'[PASS]' if v6 else '[FAIL]'}")
    
    # 7. 직접 집계와 출력 수 일치
    v7 = True
    for idx, r in df_comp.iterrows():
        cnt_check = len(df_theme[(df_theme["parsed_date"] >= r["period_start_date"]) & (df_theme["parsed_date"] <= r["period_end_date"])])
        if cnt_check != r["total_review_count"]:
            v7 = False
    print(f" 7. 12개 구간 직접 필터링 집계와 출력 일치: {'[PASS]' if v7 else '[FAIL]'}")
    
    # 8. Google + Naver = Total 일치
    v8 = (df_comp["google_review_count"] + df_comp["naver_review_count"] == df_comp["total_review_count"]).all()
    print(f" 8. 모든 행에서 Google + Naver = Total 일치: {'[PASS]' if v8 else '[FAIL]'}")
    
    # 9. total_daily_avg = total_review_count / days_count 일치
    v9 = np.isclose(df_comp["total_daily_avg"], df_comp["total_review_count"] / df_comp["days_count"], atol=0.01).all()
    print(f" 9. 전체 일평균 리뷰 수(total_daily_avg) 계산 일치: {'[PASS]' if v9 else '[FAIL]'}")
    
    # 10. 플랫폼별 daily_avg 계산 일치
    v10_g = np.isclose(df_comp["google_daily_avg"], df_comp["google_review_count"] / df_comp["days_count"], atol=0.01).all()
    v10_n = np.isclose(df_comp["naver_daily_avg"], df_comp["naver_review_count"] / df_comp["days_count"], atol=0.01).all()
    v10 = v10_g and v10_n
    print(f" 10. 플랫폼별 일평균 리뷰 수 계산 일치: {'[PASS]' if v10 else '[FAIL]'}")
    
    # 11. 상세 출력 12행 확인
    v11 = (len(df_comp) == 12)
    print(f" 11. 상세 출력 CSV 12행 확인: {'[PASS]' if v11 else '[FAIL]'}")
    
    # 12. 요약 출력 3행 확인
    v12 = (len(df_summary) == 3)
    print(f" 12. 요약 출력 CSV 3행 확인: {'[PASS]' if v12 else '[FAIL]'}")
    
    # 13. 요약의 period별 리뷰 수 = 상세 4개년 합계
    v13 = True
    for p in PERIODS:
        s_tot = df_summary[df_summary["period"] == p]["total_review_count"].values[0]
        c_tot = df_comp[df_comp["period"] == p]["total_review_count"].sum()
        if s_tot != c_tot:
            v13 = False
    print(f" 13. 요약 리뷰 수 == 상세 4개년 합계 일치: {'[PASS]' if v13 else '[FAIL]'}")
    
    # 14. 요약 total_days = 상세 days_count 합계
    v14 = True
    for p in PERIODS:
        s_days = df_summary[df_summary["period"] == p]["total_days"].values[0]
        c_days = df_comp[df_comp["period"] == p]["days_count"].sum()
        if s_days != c_days:
            v14 = False
    print(f" 14. 요약 총 일수 == 상세 일수 합계 일치: {'[PASS]' if v14 else '[FAIL]'}")
    
    # 15. pooled daily average = 총 리뷰 수 / 총 일수 일치
    v15 = np.isclose(df_summary["total_daily_avg"], df_summary["total_review_count"] / df_summary["total_days"], atol=0.01).all()
    print(f" 15. 4개년 Pooled 일평균 리뷰 수 계산 일치: {'[PASS]' if v15 else '[FAIL]'}")
    
    # 16. 입력 파일 2종 MD5 불변 확인
    raw_final_md5 = get_file_md5(RAW_REVIEW_CSV)
    win_final_md5 = get_file_md5(WINDOWS_CSV)
    v16 = (raw_initial_md5 == raw_final_md5) and (windows_initial_md5 == win_final_md5)
    print(f" 16. 입력 파일 2종 실행 전후 불변 확인(MD5): {'[PASS]' if v16 else '[FAIL]'}")
    
    all_passed = v1 and v2 and v3 and v4 and v5 and v6 and v7 and v8 and v9 and v10 and v11 and v12 and v13 and v14 and v15 and v16
    print("-" * 80)
    print(f" >> 전체 검증 결과: {'모든 검증 통과 (ALL PASSED)' if all_passed else '검증 실패 (FAILED)'}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 5. 시각화 그래프 생성 (300dpi PNG)
    # --------------------------------------------------------------------------
    setup_matplotlib_font()
    
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    
    x = np.arange(len(TARGET_YEARS))
    width = 0.26
    
    period_colors = {
        "pre": "#4A5568",      # 슬레이트 그레이 (축제 전)
        "festival": "#D69E2E", # 웜 골드/옐로우 (축제 기간)
        "post": "#3182CE"      # 블루 (축제 후)
    }
    
    for idx, period in enumerate(PERIODS):
        p_data = df_comp[df_comp["period"] == period].sort_values(by="year")
        avgs = p_data["total_daily_avg"].values
        rev_cnts = p_data["total_review_count"].values
        days_cnts = p_data["days_count"].values
        
        pos = x + (idx - 1) * width
        label_name = "축제 전 (직전 14일)" if period == "pre" else ("축제 중 (공식 축제기간)" if period == "festival" else "축제 후 (직후 14일)")
        rects = ax.bar(pos, avgs, width, label=label_name, color=period_colors[period], alpha=0.9)
        
        for rect, avg_val, r_cnt, d_cnt in zip(rects, avgs, rev_cnts, days_cnts):
            height = rect.get_height()
            ax.annotate(
                f"{avg_val:.1f}건/일\n({r_cnt}건/{d_cnt}일)",
                xy=(rect.get_x() + rect.get_width() / 2, height),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center", va="bottom",
                fontsize=8.8,
                fontweight="bold" if period == "festival" else "normal"
            )
            
    ax.set_title("임실N치즈축제 전·중·후 일평균 리뷰 수 비교 (2022~2025)", fontsize=14, pad=16, fontweight="bold")
    ax.set_xlabel("개최 연도 (Year)", fontsize=12, labelpad=10)
    ax.set_ylabel("일평균 리뷰 수 (건/일)", fontsize=12, labelpad=10)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{yr}년" for yr in TARGET_YEARS], fontsize=11)
    ax.set_ylim(0, df_comp["total_daily_avg"].max() * 1.25)
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right", frameon=True, fontsize=10.5)
    
    fig.text(
        0.08, 0.01,
        "※ 일평균 리뷰 수 = 해당 구간 총 리뷰 수 / 기간 일수 (pre=14일, festival=4~5일, post=14일) | 대상: 임실치즈테마파크",
        fontsize=9,
        color="#718096"
    )
    
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(PNG_COMPARISON, dpi=300)
    plt.close()
    print(f"\n[그래프 저장 완료] {PNG_COMPARISON}")

    # --------------------------------------------------------------------------
    # 6. 콘솔 출력 및 연도별 검산
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [연도별 상세 검산 및 비교표]")
    print("=" * 80)
    for yr in TARGET_YEARS:
        y_sub = df_comp[df_comp["year"] == yr].set_index("period")
        pre_avg = y_sub.loc["pre", "total_daily_avg"]
        fest_avg = y_sub.loc["festival", "total_daily_avg"]
        post_avg = y_sub.loc["post", "total_daily_avg"]
        
        pre_cnt = y_sub.loc["pre", "total_review_count"]
        fest_cnt = y_sub.loc["festival", "total_review_count"]
        post_cnt = y_sub.loc["post", "total_review_count"]
        
        f_gt_pre = "YES" if fest_avg > pre_avg else "NO"
        f_gt_post = "YES" if fest_avg > post_avg else "NO"
        
        print(f"\n▶ {yr}년 임실N치즈축제 (festival > pre: {f_gt_pre}, festival > post: {f_gt_post})")
        print(f"   - pre      : {pre_cnt:>3}건 / {int(y_sub.loc['pre', 'days_count']):>2}일 / 일평균 {pre_avg:>5.2f}건/일 (Google {y_sub.loc['pre', 'google_review_count']}건, Naver {y_sub.loc['pre', 'naver_review_count']}건)")
        print(f"   - festival : {fest_cnt:>3}건 / {int(y_sub.loc['festival', 'days_count']):>2}일 / 일평균 {fest_avg:>5.2f}건/일 (Google {y_sub.loc['festival', 'google_review_count']}건, Naver {y_sub.loc['festival', 'naver_review_count']}건)")
        print(f"   - post     : {post_cnt:>3}건 / {int(y_sub.loc['post', 'days_count']):>2}일 / 일평균 {post_avg:>5.2f}건/일 (Google {y_sub.loc['post', 'google_review_count']}건, Naver {y_sub.loc['post', 'naver_review_count']}건)")
        
    print("\n" + "=" * 80)
    print(" [4개년 통합 Pooled 요약표]")
    print("=" * 80)
    print(f"{'구간(period)':<12}{'총 분석일수':>10}{'Google리뷰':>12}{'Naver리뷰':>12}{'총 리뷰수':>12}{'일평균(건/일)':>14}")
    print("-" * 74)
    for idx, r in df_summary.iterrows():
        print(f"{r['period']:<12}{r['total_days']:>10}일{r['google_review_count']:>12,}{r['naver_review_count']:>12,}{r['total_review_count']:>12,}{r['total_daily_avg']:>14.2f}")
    print("=" * 80)


if __name__ == "__main__":
    main()
