# -*- coding: utf-8 -*-
"""
Tier A 3곳의 2022~2025 계절별 감성 분석 (T-3)
파일명: tierA_seasonal_sentiment_analysis.py

목적:
  1. 최종 확정 감성 문장 데이터(5,793행)와 원본 리뷰 데이터의 reviewId를 조인하여 일 단위 작성일 결합
  2. Tier A 3개 관광지(붕어섬생태공원, 임실치즈테마파크, 옥정호출렁다리)의 2022~2025년 4개년
     계절별(봄, 여름, 가을, 겨울) 감성 분포(긍정, 중립, 부정) 및 리뷰당 문장 수 집계 (48행)
  3. 관광지별 4개년 계절 요약(Pooled Sentence Distribution, 12행) 산출
  4. 14대 무결성 자동 검증 수행
  5. 300dpi 계절별 감성 분포 시각화 차트 생성 (tierA_seasonal_sentiment_comparison.png)
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
from paths import ROOT, REVIEWS, SENT_FINAL, TS_OUT  # noqa: E402
PROJECT_ROOT = str(ROOT)

RAW_REVIEW_CSV = str(REVIEWS)
SENTIMENT_FINAL_CSV = str(SENT_FINAL / "전수_문장라벨_최종.csv")

OUTPUT_DIR = str(TS_OUT)
CSV_SENTIMENT_COUNTS = os.path.join(OUTPUT_DIR, "tierA_seasonal_sentiment_counts_2022_2025.csv")
CSV_SENTIMENT_SUMMARY = os.path.join(OUTPUT_DIR, "tierA_seasonal_sentiment_summary_2022_2025.csv")
PNG_SENTIMENT_COMPARISON = os.path.join(OUTPUT_DIR, "tierA_seasonal_sentiment_comparison.png")

TIER_A_PLACES = ["붕어섬생태공원", "임실치즈테마파크", "옥정호출렁다리"]
TARGET_YEARS = [2022, 2023, 2024, 2025]
SEASONS = ["봄", "여름", "가을", "겨울"]
VALID_LABELS = ["긍정", "중립", "부정"]


def get_season(month):
    """Calendar Year 기준 계절 매핑."""
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
    print(" [T-3] Tier A 3곳의 2022~2025 계절별 감성 분석")
    print("=" * 80)
    
    # --------------------------------------------------------------------------
    # 1. 원본 및 감성 데이터 로드 & MD5 해시 기록
    # --------------------------------------------------------------------------
    if not os.path.exists(RAW_REVIEW_CSV):
        raise FileNotFoundError(f"원본 리뷰 파일이 없습니다: {RAW_REVIEW_CSV}")
    if not os.path.exists(SENTIMENT_FINAL_CSV):
        raise FileNotFoundError(f"최종 감성 파일이 없습니다: {SENTIMENT_FINAL_CSV}")
        
    raw_initial_md5 = get_file_md5(RAW_REVIEW_CSV)
    sent_initial_md5 = get_file_md5(SENTIMENT_FINAL_CSV)
    
    print(f"[입력 파일 1 - 원본] {RAW_REVIEW_CSV} (MD5: {raw_initial_md5})")
    print(f"[입력 파일 2 - 감성] {SENTIMENT_FINAL_CSV} (MD5: {sent_initial_md5})")
    
    df_raw = pd.read_csv(RAW_REVIEW_CSV, encoding="utf-8-sig", dtype=str)
    df_sent = pd.read_csv(SENTIMENT_FINAL_CSV, encoding="utf-8-sig", dtype=str)
    
    raw_total_rows = len(df_raw)
    sent_total_rows = len(df_sent)
    sent_unique_reviews = df_sent["review_id"].nunique()
    sent_label_dist = df_sent["label"].value_counts().to_dict()
    
    print(f"\n[데이터 기본 현황]")
    print(f" - 원본 리뷰 총 행 수: {raw_total_rows:,}건 (고유 reviewId: {df_raw['reviewId'].nunique():,}개)")
    print(f" - 최종 감성 총 문장 수: {sent_total_rows:,}개 (고유 review_id: {sent_unique_reviews:,}개)")
    print(f" - 전체 감성 라벨 분포: {sent_label_dist}")
    
    # --------------------------------------------------------------------------
    # 2. 날짜 조인 및 전처리
    # --------------------------------------------------------------------------
    # 원본 날짜 파싱
    df_raw["parsed_date"] = pd.to_datetime(df_raw["date"], errors="coerce")
    raw_parse_fail = int(df_raw["parsed_date"].isna().sum())
    if raw_parse_fail > 0:
        raise ValueError(f"원본 리뷰 날짜 파싱 실패 {raw_parse_fail}건 발생")
        
    df_raw["year"] = df_raw["parsed_date"].dt.year
    df_raw["month"] = df_raw["parsed_date"].dt.month
    df_raw["season"] = df_raw["month"].apply(get_season)
    
    # 감성 문장에 원본 날짜 및 연도/계절 결합 (review_id == reviewId)
    df_sent_merged = pd.merge(
        df_sent,
        df_raw[["reviewId", "date", "parsed_date", "year", "month", "season"]],
        left_on="review_id",
        right_on="reviewId",
        how="left"
    )
    
    join_date_fail = int(df_sent_merged["parsed_date"].isna().sum())
    if join_date_fail > 0:
        raise ValueError(f"감성 데이터 날짜 조인 실패 {join_date_fail}건 발생")
        
    # Tier A & 2022~2025 필터링
    df_sent_filtered = df_sent_merged[
        (df_sent_merged["place"].isin(TIER_A_PLACES)) &
        (df_sent_merged["year"].isin(TARGET_YEARS))
    ].copy()
    
    print(f"\n[2022~2025 Tier A 필터 현황]")
    print(f" - 필터된 감성 문장 수: {len(df_sent_filtered):,}개")
    print(f" - 필터된 고유 리뷰 수: {df_sent_filtered['review_id'].nunique():,}개")
    for p in TIER_A_PLACES:
        p_df = df_sent_filtered[df_sent_filtered["place"] == p]
        print(f"   * {p}: {len(p_df):,}개 문장 ({p_df['review_id'].nunique():,}개 리뷰)")

    # --------------------------------------------------------------------------
    # 3. [산출물 1] 연도별·계절별 상세 감성 집계 (48행)
    # --------------------------------------------------------------------------
    detail_rows = []
    for place in TIER_A_PLACES:
        for year in TARGET_YEARS:
            for season in SEASONS:
                sub_df = df_sent_filtered[
                    (df_sent_filtered["place"] == place) &
                    (df_sent_filtered["year"] == year) &
                    (df_sent_filtered["season"] == season)
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
                else:
                    pos_cnt = 0
                    neu_cnt = 0
                    neg_cnt = 0
                    pos_pct = np.nan
                    neu_pct = np.nan
                    neg_pct = np.nan
                    avg_sent = np.nan
                    
                detail_rows.append({
                    "place": place,
                    "year": year,
                    "season": season,
                    "review_count": n_rev,
                    "sentence_count": n_sent,
                    "positive_count": pos_cnt,
                    "neutral_count": neu_cnt,
                    "negative_count": neg_cnt,
                    "positive_pct": pos_pct,
                    "neutral_pct": neu_pct,
                    "negative_pct": neg_pct,
                    "avg_sentences_per_review": avg_sent
                })
                
    df_detail = pd.DataFrame(detail_rows)
    df_detail.to_csv(CSV_SENTIMENT_COUNTS, index=False, encoding="utf-8-sig")
    print(f"\n[저장 완료] 연도별·계절별 상세 감성 CSV: {CSV_SENTIMENT_COUNTS} ({len(df_detail)}행)")

    # --------------------------------------------------------------------------
    # 4. [산출물 2] 관광지별 4개년 계절 요약 (12행, Pooled Distribution)
    # --------------------------------------------------------------------------
    summary_rows = []
    for place in TIER_A_PLACES:
        for season in SEASONS:
            sub_df = df_sent_filtered[
                (df_sent_filtered["place"] == place) &
                (df_sent_filtered["season"] == season)
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
            else:
                pos_cnt = 0
                neu_cnt = 0
                neg_cnt = 0
                pos_pct = np.nan
                neu_pct = np.nan
                neg_pct = np.nan
                avg_sent = np.nan
                
            summary_rows.append({
                "place": place,
                "season": season,
                "review_count": n_rev,
                "sentence_count": n_sent,
                "positive_count": pos_cnt,
                "neutral_count": neu_cnt,
                "negative_count": neg_cnt,
                "positive_pct": pos_pct,
                "neutral_pct": neu_pct,
                "negative_pct": neg_pct,
                "avg_sentences_per_review": avg_sent
            })
            
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(CSV_SENTIMENT_SUMMARY, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] 4개년 계절 감성 요약 CSV: {CSV_SENTIMENT_SUMMARY} ({len(df_summary)}행)")

    # --------------------------------------------------------------------------
    # 5. 14대 무결성 자동 검증
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [자동 검증 실행 결과 (14대 항목)]")
    print("=" * 80)
    
    # 1. 최종 감성 파일 존재
    v1 = os.path.exists(SENTIMENT_FINAL_CSV)
    print(f" 1. 최종 감성 파일 존재 확인: {'[PASS]' if v1 else '[FAIL]'}")
    
    # 2. 감성 라벨 허용값 확인
    labels_in_data = set(df_sent["label"].dropna().unique())
    v2 = labels_in_data.issubset(set(VALID_LABELS))
    print(f" 2. 감성 라벨 허용값(긍정/중립/부정) 무결성: {'[PASS]' if v2 else '[FAIL]'} (라벨: {labels_in_data})")
    
    # 3. 감성 review_id가 원본 reviewId와 전부 연결됨
    unmatched_keys = set(df_sent["review_id"].dropna()) - set(df_raw["reviewId"].dropna())
    v3 = (len(unmatched_keys) == 0)
    print(f" 3. 감성 review_id 원본 100% 연결 확인: {'[PASS]' if v3 else '[FAIL]'} (미매칭: {len(unmatched_keys)}건)")
    
    # 4. 날짜 조인 후 결측/파싱 실패 0건
    v4 = (join_date_fail == 0)
    print(f" 4. 날짜 조인 후 결측/파싱 실패 0건 확인: {'[PASS]' if v4 else '[FAIL]'}")
    
    # 5. Tier A 3곳 모두 존재
    available_places = set(df_sent_filtered["place"].unique())
    v5 = all(p in available_places for p in TIER_A_PLACES)
    print(f" 5. Tier A 3곳 감성 데이터 존재 확인: {'[PASS]' if v5 else '[FAIL]'}")
    
    # 6. 분석기간 2022~2025 제한 확인
    years_in_filtered = sorted(df_sent_filtered["year"].unique().tolist())
    v6 = (years_in_filtered == TARGET_YEARS)
    print(f" 6. 분석 기간 2022~2025 제한 확인: {'[PASS]' if v6 else '[FAIL]'} (연도: {years_in_filtered})")
    
    # 7. 상세 CSV 48행 확인
    v7 = (len(df_detail) == 48)
    print(f" 7. 상세 CSV 48행(3 x 4 x 4) 확인: {'[PASS]' if v7 else '[FAIL]'} (실제 {len(df_detail)}행)")
    
    # 8. 요약 CSV 12행 확인
    v8 = (len(df_summary) == 12)
    print(f" 8. 요약 CSV 12행(3 x 4) 확인: {'[PASS]' if v8 else '[FAIL]'} (실제 {len(df_summary)}행)")
    
    # 9. 모든 유효 행에서 positive + neutral + negative == sentence_count
    valid_detail = df_detail[df_detail["sentence_count"] > 0]
    v9 = (valid_detail["positive_count"] + valid_detail["neutral_count"] + valid_detail["negative_count"] == valid_detail["sentence_count"]).all()
    print(f" 9. 긍정+중립+부정 문장 수 합계 일치: {'[PASS]' if v9 else '[FAIL]'}")
    
    # 10. 모든 유효 행에서 positive_pct + neutral_pct + negative_pct == 100% (원값 기준)
    pct_sum = (valid_detail["positive_count"] + valid_detail["neutral_count"] + valid_detail["negative_count"]) / valid_detail["sentence_count"] * 100.0
    v10 = np.isclose(pct_sum, 100.0).all()
    print(f" 10. 긍정+중립+부정 비율 합계 100% 확인: {'[PASS]' if v10 else '[FAIL]'}")
    
    # 11. 관광지별 상세 계절 문장 합계 == 원 감성 데이터 동일 기간 집계 일치
    v11 = True
    for p in TIER_A_PLACES:
        det_sum = df_detail[df_detail["place"] == p]["sentence_count"].sum()
        raw_sent_cnt = len(df_sent_filtered[df_sent_filtered["place"] == p])
        if det_sum != raw_sent_cnt:
            v11 = False
            print(f"   [불일치] {p}: 상세합 {det_sum} != 원본 {raw_sent_cnt}")
    print(f" 11. 상세 계절 문장 합계와 원본 데이터 건수 일치: {'[PASS]' if v11 else '[FAIL]'}")
    
    # 12. 요약 CSV 문장 수 == 상세 CSV 4개년 합계 일치
    v12 = True
    for p in TIER_A_PLACES:
        for s in SEASONS:
            sum_cnt = df_summary[(df_summary["place"] == p) & (df_summary["season"] == s)]["sentence_count"].values[0]
            det_cnt = df_detail[(df_detail["place"] == p) & (df_detail["season"] == s)]["sentence_count"].sum()
            if sum_cnt != det_cnt:
                v12 = False
                print(f"   [불일치] {p} {s}: 요약 {sum_cnt} != 상세합 {det_cnt}")
    print(f" 12. 요약 CSV 문장 수와 상세 CSV 합계 일치: {'[PASS]' if v12 else '[FAIL]'}")
    
    # 13. review_count 고유값 기준 계산 확인
    v13 = True
    for p in TIER_A_PLACES:
        for s in SEASONS:
            sum_rev = df_summary[(df_summary["place"] == p) & (df_summary["season"] == s)]["review_count"].values[0]
            sub_df = df_sent_filtered[(df_sent_filtered["place"] == p) & (df_sent_filtered["season"] == s)]
            true_rev = sub_df["review_id"].nunique()
            if sum_rev != true_rev:
                v13 = False
                print(f"   [불일치] {p} {s} 고유 리뷰수: {sum_rev} != {true_rev}")
    print(f" 13. review_count 고유 review_id 기준 무결성: {'[PASS]' if v13 else '[FAIL]'}")
    
    # 14. 파일 MD5 불변 검증
    raw_final_md5 = get_file_md5(RAW_REVIEW_CSV)
    sent_final_md5 = get_file_md5(SENTIMENT_FINAL_CSV)
    v14 = (raw_initial_md5 == raw_final_md5) and (sent_initial_md5 == sent_final_md5)
    print(f" 14. 입력 파일 2종 실행 전후 불변 확인(MD5): {'[PASS]' if v14 else '[FAIL]'}")
    
    all_passed = v1 and v2 and v3 and v4 and v5 and v6 and v7 and v8 and v9 and v10 and v11 and v12 and v13 and v14
    print("-" * 80)
    print(f" >> 전체 검증 결과: {'모든 검증 통과 (ALL PASSED)' if all_passed else '검증 실패 항목 존재 (FAILED)'}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 6. 시각화 그래프 생성 (300dpi PNG)
    # --------------------------------------------------------------------------
    setup_matplotlib_font()
    
    # 3개 관광지를 명확히 비교할 수 있는 1x3 패널 100% 누적 막대그래프
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), dpi=300, sharey=True)
    
    color_map = {
        "긍정": "#2B6CB0",   # 딥 블루
        "중립": "#CBD5E0",   # 라이트 그레이
        "부정": "#E53E3E"    # 소프트 레드
    }
    
    seasons_order = ["봄", "여름", "가을", "겨울"]
    season_labels = ["봄\n(3~5월)", "여름\n(6~8월)", "가을\n(9~11월)", "겨울\n(12,1,2월)"]
    
    for idx, (ax, place) in enumerate(zip(axes, TIER_A_PLACES)):
        p_df = df_summary[df_summary["place"] == place].set_index("season").loc[seasons_order].reset_index()
        
        x = np.arange(len(seasons_order))
        width = 0.55
        
        pos_vals = p_df["positive_pct"].fillna(0).values
        neu_vals = p_df["neutral_pct"].fillna(0).values
        neg_vals = p_df["negative_pct"].fillna(0).values
        sent_counts = p_df["sentence_count"].values
        rev_counts = p_df["review_count"].values
        avg_sents = p_df["avg_sentences_per_review"].values
        
        # 누적 막대 생성
        b1 = ax.bar(x, pos_vals, width, label="긍정" if idx == 0 else "", color=color_map["긍정"], alpha=0.9)
        b2 = ax.bar(x, neu_vals, width, bottom=pos_vals, label="중립" if idx == 0 else "", color=color_map["중립"], alpha=0.9)
        b3 = ax.bar(x, neg_vals, width, bottom=pos_vals + neu_vals, label="부정" if idx == 0 else "", color=color_map["부정"], alpha=0.9)
        
        # 막대 내부 텍스트 (비율 및 문장 수)
        for i in range(len(x)):
            sc = sent_counts[i]
            if sc > 0:
                # 긍정 비율 표기
                if pos_vals[i] >= 8.0:
                    ax.text(x[i], pos_vals[i] / 2, f"{pos_vals[i]:.1f}%", ha="center", va="center", color="white", fontsize=10, fontweight="bold")
                # 중립 비율 표기
                if neu_vals[i] >= 8.0:
                    ax.text(x[i], pos_vals[i] + neu_vals[i] / 2, f"{neu_vals[i]:.1f}%", ha="center", va="center", color="#2D3748", fontsize=9.5)
                # 부정 비율 표기
                if neg_vals[i] >= 8.0:
                    ax.text(x[i], pos_vals[i] + neu_vals[i] + neg_vals[i] / 2, f"{neg_vals[i]:.1f}%", ha="center", va="center", color="white", fontsize=10, fontweight="bold")
                # 막대 상단에 문장 수 & 리뷰 수 표기
                ax.annotate(
                    f"N={sc:,}문장\n({rev_counts[i]:,}리뷰)",
                    xy=(x[i], 100),
                    xytext=(0, 5),
                    textcoords="offset points",
                    ha="center", va="bottom",
                    fontsize=9.5,
                    fontweight="bold"
                )
            else:
                ax.text(x[i], 50, "데이터 없음\n(0문장)", ha="center", va="center", color="#A0AEC0", fontsize=10)
                
        ax.set_title(f"{place}", fontsize=13, pad=18, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(season_labels, fontsize=10.5)
        ax.set_ylim(0, 118)
        ax.grid(True, linestyle="--", alpha=0.4, axis="y")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        
        if idx == 0:
            ax.set_ylabel("문장 감성 비율 (%)", fontsize=11, labelpad=8)
            
    fig.suptitle("Tier A 주요 관광지 계절별 감성 분포 비교 (2022~2025)", fontsize=15, y=0.98, fontweight="bold")
    
    # 공통 범례
    fig.legend(loc="upper right", bbox_to_anchor=(0.95, 0.95), ncol=3, frameon=True, fontsize=11)
    
    # 하단 주석
    fig.text(
        0.05, 0.01,
        "※ 감성 비율 = 4개년 해당 계절 감성 문장 합산 기준(Pooled Sentence Distribution) | N = 감성분석 대상 문장 수 (괄호: 고유 리뷰 수)",
        fontsize=9,
        color="#718096"
    )
    
    plt.tight_layout(rect=[0.03, 0.04, 0.97, 0.92])
    plt.savefig(PNG_SENTIMENT_COMPARISON, dpi=300)
    plt.close()
    print(f"\n[그래프 저장 완료] {PNG_SENTIMENT_COMPARISON}")

    # --------------------------------------------------------------------------
    # 7. 콘솔 요약표 출력
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [Tier A 계절별 4개년 감성 요약표 (2022~2025)]")
    print("=" * 80)
    print(f"{'관광지명':<12}{'계절':>5}{'리뷰수':>8}{'문장수':>8}{'긍정(%)':>10}{'중립(%)':>10}{'부정(%)':>10}{'리뷰당문장':>11}")
    print("-" * 76)
    for idx, row in df_summary.iterrows():
        pos_str = f"{row['positive_pct']:.1f}%" if pd.notna(row['positive_pct']) else "NA"
        neu_str = f"{row['neutral_pct']:.1f}%" if pd.notna(row['neutral_pct']) else "NA"
        neg_str = f"{row['negative_pct']:.1f}%" if pd.notna(row['negative_pct']) else "NA"
        avg_str = f"{row['avg_sentences_per_review']:.2f}" if pd.notna(row['avg_sentences_per_review']) else "NA"
        print(f"{row['place']:<12}{row['season']:>5}{int(row['review_count']):>8,}{int(row['sentence_count']):>8,}{pos_str:>10}{neu_str:>10}{neg_str:>10}{avg_str:>11}")
    print("=" * 80)


if __name__ == "__main__":
    main()
