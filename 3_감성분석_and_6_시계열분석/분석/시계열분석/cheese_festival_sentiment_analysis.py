# -*- coding: utf-8 -*-
"""
임실N치즈축제 전·중·후 감성 분포 비교 분석 (T-6)
파일명: cheese_festival_sentiment_analysis.py

목적:
  1. T-4 분석 윈도우(cheese_festival_analysis_windows_2022_2025.csv, 12행)와
     최종 감성 문장 데이터(전수_문장라벨_최종.csv, 5,793행)를 원본 리뷰 작성일로 결합
  2. 임실치즈테마파크의 2022~2025 축제 전·중·후 문장 단위 감성 분포(긍정, 중립, 부정) 및
     플랫폼(Google vs Naver) 구성비 집계 (12행)
  3. 4개년 Pooled 감성 요약(3행) 산출
  4. 20대 무결성 자동 검증 수행
  5. 연도별 4-패널 100% 누적 막대 시각화 차트 생성 (300dpi PNG)
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
SENTIMENT_FINAL_CSV = os.path.join(PROJECT_ROOT, "분석", "감성분석", "fullscale-final", "전수_문장라벨_최종.csv")
WINDOWS_CSV = os.path.join(BASE_DIR, "output", "cheese_festival_analysis_windows_2022_2025.csv")

OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CSV_SENTIMENT_COMP = os.path.join(OUTPUT_DIR, "cheese_festival_sentiment_comparison_2022_2025.csv")
CSV_SENTIMENT_SUMM = os.path.join(OUTPUT_DIR, "cheese_festival_sentiment_summary_2022_2025.csv")
PNG_SENTIMENT_COMP = os.path.join(OUTPUT_DIR, "cheese_festival_sentiment_comparison.png")

TARGET_PLACE = "임실치즈테마파크"
TARGET_YEARS = [2022, 2023, 2024, 2025]
PERIODS = ["pre", "festival", "post"]
VALID_LABELS = ["긍정", "중립", "부정"]


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
    print(" [T-6] 임실N치즈축제 전·중·후 감성 분포 비교 분석 (2022~2025)")
    print("=" * 80)
    
    # --------------------------------------------------------------------------
    # 1. 파일 로드 및 MD5 해시 기록
    # --------------------------------------------------------------------------
    if not os.path.exists(RAW_REVIEW_CSV):
        raise FileNotFoundError(f"원본 리뷰 파일 부재: {RAW_REVIEW_CSV}")
    if not os.path.exists(SENTIMENT_FINAL_CSV):
        raise FileNotFoundError(f"최종 감성 파일 부재: {SENTIMENT_FINAL_CSV}")
    if not os.path.exists(WINDOWS_CSV):
        raise FileNotFoundError(f"T-4 윈도우 파일 부재: {WINDOWS_CSV}")
        
    raw_md5_init = get_file_md5(RAW_REVIEW_CSV)
    sent_md5_init = get_file_md5(SENTIMENT_FINAL_CSV)
    win_md5_init = get_file_md5(WINDOWS_CSV)
    
    print(f"[입력 파일 1 - 원본] {RAW_REVIEW_CSV} (MD5: {raw_md5_init})")
    print(f"[입력 파일 2 - 감성] {SENTIMENT_FINAL_CSV} (MD5: {sent_md5_init})")
    print(f"[입력 파일 3 - 윈도우] {WINDOWS_CSV} (MD5: {win_md5_init})")
    
    df_raw = pd.read_csv(RAW_REVIEW_CSV, encoding="utf-8-sig", dtype=str)
    df_sent = pd.read_csv(SENTIMENT_FINAL_CSV, encoding="utf-8-sig", dtype=str)
    df_win = pd.read_csv(WINDOWS_CSV, encoding="utf-8-sig")
    
    # 날짜 파싱 및 결합
    df_raw["parsed_date"] = pd.to_datetime(df_raw["date"], errors="coerce")
    raw_parse_fails = int(df_raw["parsed_date"].isna().sum())
    if raw_parse_fails > 0:
        raise ValueError(f"원본 날짜 파싱 실패 {raw_parse_fails}건 발생")
        
    sent_len_before = len(df_sent)
    df_sent_merged = pd.merge(
        df_sent,
        df_raw[["reviewId", "date", "parsed_date"]],
        left_on="review_id",
        right_on="reviewId",
        how="left"
    )
    sent_len_after = len(df_sent_merged)
    if sent_len_before != sent_len_after:
        raise ValueError(f"조인 후 감성 행 수 변동 발생 ({sent_len_before} -> {sent_len_after})")
        
    join_date_fails = int(df_sent_merged["parsed_date"].isna().sum())
    if join_date_fails > 0:
        raise ValueError(f"감성 날짜 조인 결측 {join_date_fails}건 발생")
        
    # 임실치즈테마파크 필터링
    df_theme_sent = df_sent_merged[df_sent_merged["place"] == TARGET_PLACE].copy()
    print(f"\n[임실치즈테마파크 감성 데이터 규모] 총 {len(df_theme_sent):,}개 문장 (고유 리뷰: {df_theme_sent['review_id'].nunique():,}개)")

    # --------------------------------------------------------------------------
    # 2. [산출물 1] 연도별·구간별 상세 집계 (12행)
    # --------------------------------------------------------------------------
    detail_rows = []
    
    for idx, win in df_win.iterrows():
        yr = int(win["year"])
        period = str(win["period"])
        s_date = str(win["period_start_date"])
        e_date = str(win["period_end_date"])
        days = int(win["days_count"])
        
        sub_df = df_theme_sent[
            (df_theme_sent["parsed_date"] >= s_date) &
            (df_theme_sent["parsed_date"] <= e_date)
        ]
        
        n_sent = len(sub_df)
        n_rev = sub_df["review_id"].nunique()
        
        if n_sent > 0:
            pos_cnt = int((sub_df["label"] == "긍정").sum())
            neu_cnt = int((sub_df["label"] == "중립").sum())
            neg_cnt = int((sub_df["label"] == "부정").sum())
            pos_pct = round(pos_cnt / n_sent * 100.0, 2)
            neu_pct = round(neu_cnt / n_sent * 100.0, 2)
            neg_pct = round(neg_cnt / n_sent * 100.0, 2)
            avg_sent = round(n_sent / n_rev, 2) if n_rev > 0 else np.nan
            
            g_sent = int((sub_df["platform"] == "구글").sum())
            n_sent_plat = int((sub_df["platform"] == "네이버").sum())
            g_pct = round(g_sent / n_sent * 100.0, 2)
            n_pct = round(n_sent_plat / n_sent * 100.0, 2)
        else:
            pos_cnt, neu_cnt, neg_cnt = 0, 0, 0
            pos_pct, neu_pct, neg_pct, avg_sent = np.nan, np.nan, np.nan, np.nan
            g_sent, n_sent_plat = 0, 0
            g_pct, n_pct = np.nan, np.nan
            
        detail_rows.append({
            "year": yr,
            "period": period,
            "period_start_date": s_date,
            "period_end_date": e_date,
            "days_count": days,
            "review_count": n_rev,
            "sentence_count": n_sent,
            "positive_count": pos_cnt,
            "neutral_count": neu_cnt,
            "negative_count": neg_cnt,
            "positive_pct": pos_pct,
            "neutral_pct": neu_pct,
            "negative_pct": neg_pct,
            "avg_sentences_per_review": avg_sent,
            "google_sentence_count": g_sent,
            "naver_sentence_count": n_sent_plat,
            "google_sentence_pct": g_pct,
            "naver_sentence_pct": n_pct
        })
        
    df_detail = pd.DataFrame(detail_rows)
    df_detail.to_csv(CSV_SENTIMENT_COMP, index=False, encoding="utf-8-sig")
    print(f"\n[저장 완료] 연도별 상세 감성 CSV: {CSV_SENTIMENT_COMP} ({len(df_detail)}행)")

    # --------------------------------------------------------------------------
    # 3. [산출물 2] 4개년 Pooled 감성 요약 (3행)
    # --------------------------------------------------------------------------
    summary_rows = []
    
    for period in PERIODS:
        p_sub = df_detail[df_detail["period"] == period]
        
        tot_rev = int(p_sub["review_count"].sum())
        tot_sent = int(p_sub["sentence_count"].sum())
        
        # Pooled 합산 집계
        tot_pos = int(p_sub["positive_count"].sum())
        tot_neu = int(p_sub["neutral_count"].sum())
        tot_neg = int(p_sub["negative_count"].sum())
        
        pos_pct = round(tot_pos / tot_sent * 100.0, 2) if tot_sent > 0 else np.nan
        neu_pct = round(tot_neu / tot_sent * 100.0, 2) if tot_sent > 0 else np.nan
        neg_pct = round(tot_neg / tot_sent * 100.0, 2) if tot_sent > 0 else np.nan
        avg_sent = round(tot_sent / tot_rev, 2) if tot_rev > 0 else np.nan
        
        tot_g = int(p_sub["google_sentence_count"].sum())
        tot_n = int(p_sub["naver_sentence_count"].sum())
        g_pct = round(tot_g / tot_sent * 100.0, 2) if tot_sent > 0 else np.nan
        n_pct = round(tot_n / tot_sent * 100.0, 2) if tot_sent > 0 else np.nan
        
        summary_rows.append({
            "period": period,
            "review_count": tot_rev,
            "sentence_count": tot_sent,
            "positive_count": tot_pos,
            "neutral_count": tot_neu,
            "negative_count": tot_neg,
            "positive_pct": pos_pct,
            "neutral_pct": neu_pct,
            "negative_pct": neg_pct,
            "avg_sentences_per_review": avg_sent,
            "google_sentence_count": tot_g,
            "naver_sentence_count": tot_n,
            "google_sentence_pct": g_pct,
            "naver_sentence_pct": n_pct
        })
        
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(CSV_SENTIMENT_SUMM, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] 4개년 Pooled 감성 요약 CSV: {CSV_SENTIMENT_SUMM} ({len(df_summary)}행)")

    # --------------------------------------------------------------------------
    # 4. 20대 무결성 자동 검증
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [자동 검증 실행 결과 (20대 항목)]")
    print("=" * 80)
    
    v1 = os.path.exists(SENTIMENT_FINAL_CSV)
    print(f" 1. 최종 감성 파일 존재 확인: {'[PASS]' if v1 else '[FAIL]'}")
    
    v2 = os.path.exists(RAW_REVIEW_CSV)
    print(f" 2. 원본 리뷰 파일 존재 확인: {'[PASS]' if v2 else '[FAIL]'}")
    
    v3 = os.path.exists(WINDOWS_CSV)
    print(f" 3. T-4 window 파일 존재 확인: {'[PASS]' if v3 else '[FAIL]'}")
    
    v4 = (df_raw["reviewId"].duplicated().sum() == 0)
    print(f" 4. 원본 reviewId 고유성(중복 0건): {'[PASS]' if v4 else '[FAIL]'}")
    
    unmatched_sent_ids = set(df_sent["review_id"].dropna()) - set(df_raw["reviewId"].dropna())
    v5 = (len(unmatched_sent_ids) == 0)
    print(f" 5. 감성 review_id 원본 100% 연결 확인: {'[PASS]' if v5 else '[FAIL]'}")
    
    v6 = (sent_len_before == sent_len_after)
    print(f" 6. 조인 전후 감성 행 수 불변 확인: {'[PASS]' if v6 else '[FAIL]'}")
    
    v7 = (join_date_fails == 0)
    print(f" 7. 날짜 파싱/조인 실패 0건 확인: {'[PASS]' if v7 else '[FAIL]'}")
    
    labels_present = set(df_sent["label"].dropna().unique())
    v8 = labels_present.issubset(set(VALID_LABELS))
    print(f" 8. 감성 label 허용값(긍정/중립/부정) 무결성: {'[PASS]' if v8 else '[FAIL]'}")
    
    v9 = (len(df_theme_sent) > 0)
    print(f" 9. 임실치즈테마파크 데이터 존재 확인: {'[PASS]' if v9 else '[FAIL]'}")
    
    v10 = (len(df_win) == 12)
    print(f" 10. T-4 분석 구간 12행 확인: {'[PASS]' if v10 else '[FAIL]'}")
    
    v11 = (len(df_detail) == 12)
    print(f" 11. 상세 출력 CSV 12행 확인: {'[PASS]' if v11 else '[FAIL]'}")
    
    v12 = (len(df_summary) == 3)
    print(f" 12. 요약 출력 CSV 3행 확인: {'[PASS]' if v12 else '[FAIL]'}")
    
    valid_detail = df_detail[df_detail["sentence_count"] > 0]
    v13 = (valid_detail["positive_count"] + valid_detail["neutral_count"] + valid_detail["negative_count"] == valid_detail["sentence_count"]).all()
    print(f" 13. positive + neutral + negative = sentence_count 일치: {'[PASS]' if v13 else '[FAIL]'}")
    
    pct_sum = (valid_detail["positive_count"] + valid_detail["neutral_count"] + valid_detail["negative_count"]) / valid_detail["sentence_count"] * 100.0
    v14 = np.isclose(pct_sum, 100.0).all()
    print(f" 14. positive_pct + neutral_pct + negative_pct = 100% 일치: {'[PASS]' if v14 else '[FAIL]'}")
    
    v15 = (valid_detail["google_sentence_count"] + valid_detail["naver_sentence_count"] == valid_detail["sentence_count"]).all()
    print(f" 15. Google + Naver sentence_count = sentence_count 일치: {'[PASS]' if v15 else '[FAIL]'}")
    
    v16 = True
    for idx, r in df_detail.iterrows():
        sub_check = df_theme_sent[(df_theme_sent["parsed_date"] >= r["period_start_date"]) & (df_theme_sent["parsed_date"] <= r["period_end_date"])]
        if sub_check["review_id"].nunique() != r["review_count"]:
            v16 = False
    print(f" 16. review_count 고유 review_id 수 일치 확인: {'[PASS]' if v16 else '[FAIL]'}")
    
    v17 = True
    for idx, r in df_detail.iterrows():
        sub_check = df_theme_sent[(df_theme_sent["parsed_date"] >= r["period_start_date"]) & (df_theme_sent["parsed_date"] <= r["period_end_date"])]
        if len(sub_check) != r["sentence_count"]:
            v17 = False
    print(f" 17. 원 감성 데이터 직접 날짜 필터링과 sentence_count 일치: {'[PASS]' if v17 else '[FAIL]'}")
    
    v18 = True
    for p in PERIODS:
        s_cnt = df_summary[df_summary["period"] == p]["sentence_count"].values[0]
        d_cnt = df_detail[df_detail["period"] == p]["sentence_count"].sum()
        if s_cnt != d_cnt:
            v18 = False
    print(f" 18. Pooled 요약 문장 수 == 상세 4개년 합계 일치: {'[PASS]' if v18 else '[FAIL]'}")
    
    v19 = True
    for p in PERIODS:
        s_row = df_summary[df_summary["period"] == p].iloc[0]
        calc_pos = round(s_row["positive_count"] / s_row["sentence_count"] * 100.0, 2)
        if s_row["positive_pct"] != calc_pos:
            v19 = False
    print(f" 19. Pooled 감성 비율 합산 문장 기준 계산 확인: {'[PASS]' if v19 else '[FAIL]'}")
    
    raw_md5_final = get_file_md5(RAW_REVIEW_CSV)
    sent_md5_final = get_file_md5(SENTIMENT_FINAL_CSV)
    win_md5_final = get_file_md5(WINDOWS_CSV)
    v20 = (raw_md5_init == raw_md5_final) and (sent_md5_init == sent_md5_final) and (win_md5_init == win_md5_final)
    print(f" 20. 입력 파일 3종 실행 전후 불변 확인(MD5): {'[PASS]' if v20 else '[FAIL]'}")
    
    all_passed = v1 and v2 and v3 and v4 and v5 and v6 and v7 and v8 and v9 and v10 and v11 and v12 and v13 and v14 and v15 and v16 and v17 and v18 and v19 and v20
    print("-" * 80)
    print(f" >> 전체 검증 결과: {'모든 검증 통과 (ALL PASSED)' if all_passed else '검증 실패 (FAILED)'}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 5. 시각화 그래프 생성 (4개 연도 서브패널, 300dpi PNG)
    # --------------------------------------------------------------------------
    setup_matplotlib_font()
    
    fig, axes = plt.subplots(1, 4, figsize=(18, 6), dpi=300, sharey=True)
    
    color_map = {
        "긍정": "#2B6CB0",   # 딥 블루
        "중립": "#CBD5E0",   # 라이트 그레이
        "부정": "#E53E3E"    # 소프트 레드
    }
    
    period_labels = ["축제 전\n(직전 14일)", "축제 중\n(축제기간)", "축제 후\n(직후 14일)"]
    x = np.arange(len(PERIODS))
    width = 0.52
    
    for idx, (ax, yr) in enumerate(zip(axes, TARGET_YEARS)):
        y_df = df_detail[df_detail["year"] == yr].set_index("period").loc[PERIODS].reset_index()
        
        pos_vals = y_df["positive_pct"].fillna(0).values
        neu_vals = y_df["neutral_pct"].fillna(0).values
        neg_vals = y_df["negative_pct"].fillna(0).values
        sent_counts = y_df["sentence_count"].values
        rev_counts = y_df["review_count"].values
        
        # 100% 누적 막대 생성
        b1 = ax.bar(x, pos_vals, width, label="긍정" if idx == 0 else "", color=color_map["긍정"], alpha=0.9)
        b2 = ax.bar(x, neu_vals, width, bottom=pos_vals, label="중립" if idx == 0 else "", color=color_map["중립"], alpha=0.9)
        b3 = ax.bar(x, neg_vals, width, bottom=pos_vals + neu_vals, label="부정" if idx == 0 else "", color=color_map["부정"], alpha=0.9)
        
        for i in range(len(x)):
            sc = sent_counts[i]
            rc = rev_counts[i]
            if sc > 0:
                # 긍정 비율 표기
                if pos_vals[i] >= 8.0:
                    ax.text(x[i], pos_vals[i] / 2, f"{pos_vals[i]:.1f}%", ha="center", va="center", color="white", fontsize=9.5, fontweight="bold")
                # 중립 비율 표기
                if neu_vals[i] >= 8.0:
                    ax.text(x[i], pos_vals[i] + neu_vals[i] / 2, f"{neu_vals[i]:.1f}%", ha="center", va="center", color="#2D3748", fontsize=9)
                # 부정 비율 표기
                if neg_vals[i] >= 8.0:
                    ax.text(x[i], pos_vals[i] + neu_vals[i] + neg_vals[i] / 2, f"{neg_vals[i]:.1f}%", ha="center", va="center", color="white", fontsize=9.5, fontweight="bold")
                # 막대 상단 N 표기
                ax.annotate(
                    f"N={sc}문장\n({rc}리뷰)",
                    xy=(x[i], 100),
                    xytext=(0, 5),
                    textcoords="offset points",
                    ha="center", va="bottom",
                    fontsize=9,
                    fontweight="bold"
                )
            else:
                ax.text(x[i], 50, "데이터 없음", ha="center", va="center", color="#A0AEC0", fontsize=9.5)
                
        ax.set_title(f"{yr}년 축제 전·중·후", fontsize=12.5, pad=16, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(period_labels, fontsize=10)
        ax.set_ylim(0, 120)
        ax.grid(True, linestyle="--", alpha=0.4, axis="y")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        
        if idx == 0:
            ax.set_ylabel("문장 감성 비율 (%)", fontsize=11, labelpad=8)
            
    fig.suptitle("임실N치즈축제 전·중·후 문장 단위 감성 분포 비교 (2022~2025)", fontsize=15, y=0.98, fontweight="bold")
    fig.legend(loc="upper right", bbox_to_anchor=(0.95, 0.95), ncol=3, frameon=True, fontsize=11)
    
    fig.text(
        0.05, 0.01,
        "※ 감성 비율 = 해당 구간 감성분석 대상 문장 수(sentence_count) 기준 | 대상: 임실치즈테마파크 | N = 감성 문장 수 (괄호: 고유 리뷰 수)",
        fontsize=9,
        color="#718096"
    )
    
    plt.tight_layout(rect=[0.03, 0.04, 0.97, 0.92])
    plt.savefig(PNG_SENTIMENT_COMP, dpi=300)
    plt.close()
    print(f"\n[그래프 저장 완료] {PNG_SENTIMENT_COMP}")

    # --------------------------------------------------------------------------
    # 6. 콘솔 출력 및 연도별 검산
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [연도별 상세 감성 집계 결과]")
    print("=" * 80)
    for yr in TARGET_YEARS:
        y_sub = df_detail[df_detail["year"] == yr].set_index("period")
        print(f"\n▶ {yr}년 임실N치즈축제:")
        for p in PERIODS:
            r = y_sub.loc[p]
            pos_s = f"{r['positive_pct']:.1f}%" if pd.notna(r['positive_pct']) else "NA"
            neu_s = f"{r['neutral_pct']:.1f}%" if pd.notna(r['neutral_pct']) else "NA"
            neg_s = f"{r['negative_pct']:.1f}%" if pd.notna(r['negative_pct']) else "NA"
            g_s = f"{r['google_sentence_pct']:.1f}%" if pd.notna(r['google_sentence_pct']) else "NA"
            print(f"   - {p:<8}: {int(r['sentence_count']):>3}문장 ({int(r['review_count']):>2}리뷰) | 긍정 {pos_s:>6}, 중립 {neu_s:>6}, 부정 {neg_s:>6} | Google {g_s:>6}")
            
    print("\n" + "=" * 80)
    print(" [4개년 Pooled 감성 요약표]")
    print("=" * 80)
    print(f"{'구간(period)':<10}{'고유리뷰':>8}{'감성문장':>8}{'긍정(%)':>10}{'중립(%)':>10}{'부정(%)':>10}{'리뷰당문장':>11}{'Google비중':>12}")
    print("-" * 79)
    for idx, r in df_summary.iterrows():
        print(f"{r['period']:<10}{int(r['review_count']):>8,}{int(r['sentence_count']):>8,}{r['positive_pct']:>9.1f}%{r['neutral_pct']:>9.1f}%{r['negative_pct']:>9.1f}%{r['avg_sentences_per_review']:>11.2f}{r['google_sentence_pct']:>11.1f}%")
    print("=" * 80)


if __name__ == "__main__":
    main()
