# -*- coding: utf-8 -*-
"""
Tier A 계절별 감성 분석 플랫폼(Google vs Naver) 구성 점검 (T-3 보조 검증)
파일명: tierA_seasonal_sentiment_platform_check.py

목적:
  1. 2022~2025년 Tier A 3개 관광지(붕어섬생태공원, 임실치즈테마파크, 옥정호출렁다리)의
     계절별(봄, 여름, 가을, 겨울) 감성 문장 내 플랫폼(Google vs Naver) 구성 산출 (12행)
  2. 기존 T-3 감성 요약표의 sentence_count와의 100% 일치 무결성 검증
  3. 관광지별 계절 간 Google 문장 비중의 최대-최소 격차(%p) 산출
  4. output/timeseries/tierA_seasonal_sentiment_platform_check_2022_2025.csv 생성
"""

import os
import sys
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE_DIR))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import ROOT, REVIEWS, SENT_FINAL, TS_OUT  # noqa: E402
PROJECT_ROOT = str(ROOT)

RAW_REVIEW_CSV = str(REVIEWS)
SENTIMENT_FINAL_CSV = str(SENT_FINAL / "전수_문장라벨_최종.csv")
T3_SUMMARY_CSV = os.path.join(str(TS_OUT), "tierA_seasonal_sentiment_summary_2022_2025.csv")

OUTPUT_DIR = str(TS_OUT)
CSV_PLATFORM_CHECK = os.path.join(OUTPUT_DIR, "tierA_seasonal_sentiment_platform_check_2022_2025.csv")

TIER_A_PLACES = ["붕어섬생태공원", "임실치즈테마파크", "옥정호출렁다리"]
TARGET_YEARS = [2022, 2023, 2024, 2025]
SEASONS = ["봄", "여름", "가을", "겨울"]


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


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 80)
    print(" [T-3 보조 검증] 계절별 감성 문장 플랫폼 구성 점검 (2022~2025 Pooled)")
    print("=" * 80)
    
    df_raw = pd.read_csv(RAW_REVIEW_CSV, encoding="utf-8-sig", dtype=str)
    df_sent = pd.read_csv(SENTIMENT_FINAL_CSV, encoding="utf-8-sig", dtype=str)
    df_t3_summary = pd.read_csv(T3_SUMMARY_CSV, encoding="utf-8-sig")
    
    # 날짜 결합
    df_raw["parsed_date"] = pd.to_datetime(df_raw["date"], errors="coerce")
    df_raw["year"] = df_raw["parsed_date"].dt.year
    df_raw["month"] = df_raw["parsed_date"].dt.month
    df_raw["season"] = df_raw["month"].apply(get_season)
    
    df_sent_merged = pd.merge(
        df_sent,
        df_raw[["reviewId", "parsed_date", "year", "month", "season"]],
        left_on="review_id",
        right_on="reviewId",
        how="left"
    )
    
    df_filtered = df_sent_merged[
        (df_sent_merged["place"].isin(TIER_A_PLACES)) &
        (df_sent_merged["year"].isin(TARGET_YEARS))
    ].copy()
    
    rows = []
    for place in TIER_A_PLACES:
        for season in SEASONS:
            sub_df = df_filtered[
                (df_filtered["place"] == place) &
                (df_filtered["season"] == season)
            ]
            
            total_sents = len(sub_df)
            google_cnt = int((sub_df["platform"] == "구글").sum())
            naver_cnt = int((sub_df["platform"] == "네이버").sum())
            
            google_pct = round(google_cnt / total_sents * 100.0, 2) if total_sents > 0 else np.nan
            naver_pct = round(naver_cnt / total_sents * 100.0, 2) if total_sents > 0 else np.nan
            
            rows.append({
                "place": place,
                "season": season,
                "google_sentence_count": google_cnt,
                "naver_sentence_count": naver_cnt,
                "google_sentence_pct": google_pct,
                "naver_sentence_pct": naver_pct
            })
            
    df_plat = pd.DataFrame(rows)
    df_plat.to_csv(CSV_PLATFORM_CHECK, index=False, encoding="utf-8-sig")
    print(f"\n[저장 완료] 플랫폼 구성 점검 CSV: {CSV_PLATFORM_CHECK} ({len(df_plat)}행)")
    
    # --------------------------------------------------------------------------
    # 검증: 기존 T-3 summary와 일치 확인
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [무결성 자동 검증]")
    print("=" * 80)
    
    merged_check = pd.merge(df_plat, df_t3_summary, on=["place", "season"], how="inner")
    v1 = (len(merged_check) == 12)
    print(f" 1. 관광지 x 계절 12행 완벽 매칭: {'[PASS]' if v1 else '[FAIL]'}")
    
    v2 = (merged_check["google_sentence_count"] + merged_check["naver_sentence_count"] == merged_check["sentence_count"]).all()
    print(f" 2. Google + Naver 문장 수 == T-3 sentence_count 전수 일치: {'[PASS]' if v2 else '[FAIL]'}")
    
    v3 = np.isclose(merged_check["google_sentence_pct"] + merged_check["naver_sentence_pct"], 100.0).all()
    print(f" 3. Google + Naver 비중 합계 100% 일치: {'[PASS]' if v3 else '[FAIL]'}")
    
    print("-" * 80)
    print(f" >> 전체 검증 결과: {'모든 검증 통과 (ALL PASSED)' if v1 and v2 and v3 else '검증 실패 (FAILED)'}")
    print("=" * 80)
    
    # --------------------------------------------------------------------------
    # 관광지별 계절 간 Google 비중 격차 계산 및 출력
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [관광지별 계절 간 Google 문장 비중 및 최대-최소 격차]")
    print("=" * 80)
    
    gap_results = {}
    for place in TIER_A_PLACES:
        p_df = df_plat[df_plat["place"] == place]
        min_pct = p_df["google_sentence_pct"].min()
        max_pct = p_df["google_sentence_pct"].max()
        gap = round(max_pct - min_pct, 2)
        gap_results[place] = {"min": min_pct, "max": max_pct, "gap": gap}
        
        print(f"\n▶ {place} (계절별 Google 비중 범위: {min_pct:.2f}% ~ {max_pct:.2f}%, 격차: {gap:.2f}%p)")
        for idx, r in p_df.iterrows():
            print(f"   - {r['season']}: 구글 {r['google_sentence_count']:,}문장 ({r['google_sentence_pct']:.1f}%) | 네이버 {r['naver_sentence_count']:,}문장 ({r['naver_sentence_pct']:.1f}%) | 합계 {r['google_sentence_count']+r['naver_sentence_count']:,}문장")
            
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
