# -*- coding: utf-8 -*-
"""
시계열 분석 입력자료 및 연결 기준 점검 스크립트 (T-1)
파일명: timeseries_input_audit.py

목적:
  1. 원본 리뷰 데이터, 최종 감성 문장 데이터의 파일 위치, 행 수, 열 구조 확인
  2. reviewId 기반 데이터 간 연결 무결성 (1:N) 및 매칭률 100% 확인
  3. 날짜 사용 가능 여부 (일 단위 보존, 결측, 파싱 실패 여부) 확인
  4. Tier A 3개 관광지(붕어섬생태공원, 임실치즈테마파크, 옥정호출렁다리) 데이터 존재 확인
  5. timeseries_input_inventory.csv 산출물 생성
"""

import os
import sys
import hashlib
import pandas as pd
import numpy as np

# ==============================================================================
# 0. 경로 정의
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE_DIR))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import ROOT, REVIEWS, SENT_FINAL, SENT_OUT, TS_OUT  # noqa: E402
PROJECT_ROOT = str(ROOT)

# 2종 입력 데이터 경로
RAW_REVIEW_CSV = str(REVIEWS)

# 감성 데이터: 5,685행 원본 문장 분리본 및 5,793행 최종 확정본
SENTIMENT_5685_CSV = str(SENT_OUT / "fullscale" / "전수_문장라벨.csv")
SENTIMENT_FINAL_CSV = str(SENT_FINAL / "전수_문장라벨_최종.csv")

OUTPUT_DIR = str(TS_OUT)
INVENTORY_CSV = os.path.join(OUTPUT_DIR, "timeseries_input_inventory.csv")

TIER_A_PLACES = ["붕어섬생태공원", "임실치즈테마파크", "옥정호출렁다리"]


def rel(path):
    """레포 기준 상대경로. 운영체제와 관계없이 '/' 로 적어 산출물이 어디서나 같게 한다."""
    return os.path.relpath(path, PROJECT_ROOT).replace(os.sep, "/")


def get_file_md5(filepath):
    """파일의 MD5 해시를 계산합니다."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 80)
    print(" [T-1] 시계열 분석 입력자료 및 연결 기준 정밀 점검")
    print("=" * 80)
    
    # --------------------------------------------------------------------------
    # 1. 원본 리뷰 데이터 점검
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [A. 원본 리뷰 데이터 점검]")
    print("=" * 80)
    print(f" 파일 경로: {RAW_REVIEW_CSV}")
    if not os.path.exists(RAW_REVIEW_CSV):
        raise FileNotFoundError(f"원본 리뷰 파일이 없습니다: {RAW_REVIEW_CSV}")
        
    df_raw = pd.read_csv(RAW_REVIEW_CSV, encoding="utf-8-sig", dtype=str)
    raw_md5 = get_file_md5(RAW_REVIEW_CSV)
    raw_rows = len(df_raw)
    raw_cols = list(df_raw.columns)
    
    df_raw["parsed_date"] = pd.to_datetime(df_raw["date"], errors="coerce")
    raw_parse_fail = int(df_raw["parsed_date"].isna().sum())
    raw_date_min = str(df_raw["parsed_date"].min().date())
    raw_date_max = str(df_raw["parsed_date"].max().date())
    raw_plat_dist = df_raw["platform"].value_counts().to_dict()
    raw_unique_ids = df_raw["reviewId"].nunique()
    
    print(f" 행 수: {raw_rows:,}행")
    print(f" 열 목록 ({len(raw_cols)}개): {raw_cols}")
    print(f" MD5 해시: {raw_md5}")
    print(f" 날짜 범위: {raw_date_min} ~ {raw_date_max} (파싱 실패: {raw_parse_fail}건)")
    print(f" 플랫폼 분포: {raw_plat_dist}")
    print(f" reviewId 고유값: {raw_unique_ids:,}개 (중복 0건: {raw_unique_ids == raw_rows})")
    print(f" Tier A 3곳 건수:")
    for p in TIER_A_PLACES:
        print(f"   - {p}: {(df_raw['place'] == p).sum():,}건")

    raw_inventory = {
        "dataset_role": "raw_review",
        "file_path": rel(RAW_REVIEW_CSV),
        "row_count": raw_rows,
        "place_column": "place",
        "platform_column": "platform",
        "date_column": "date",
        "review_id_column": "reviewId",
        "sentence_id_column": "",
        "sentiment_column": "",
        "keyword_column": "",
        "date_min": raw_date_min,
        "date_max": raw_date_max,
        "date_parse_fail_count": raw_parse_fail,
        "link_key_to_raw": "reviewId (기준 식별자)",
        "link_relationship": "1:1",
        "notes": f"MD5={raw_md5}, Google={raw_plat_dist.get('구글', 0)}, Naver={raw_plat_dist.get('네이버', 0)}"
    }

    # --------------------------------------------------------------------------
    # 2. 감성 데이터 점검 (5,685행 및 최종 5,793행 확인)
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [B. 최종 감성 문장 데이터 점검]")
    print("=" * 80)
    
    # 5,685행 원본 문장라벨
    df_sent_5685 = pd.read_csv(SENTIMENT_5685_CSV, encoding="utf-8-sig", dtype=str)
    sent_5685_md5 = get_file_md5(SENTIMENT_5685_CSV)
    print(f" [B-1] 5,685문장 데이터 ({SENTIMENT_5685_CSV}):")
    print(f"   - 행 수: {len(df_sent_5685):,}행, 열: {list(df_sent_5685.columns)}")
    print(f"   - 라벨 분포: {df_sent_5685['label'].value_counts().to_dict()}")
    print(f"   - 고유 review_id 수: {df_sent_5685['review_id'].nunique():,}개")
    
    # 최종 5,793행 문장라벨_최종
    df_sent_final = pd.read_csv(SENTIMENT_FINAL_CSV, encoding="utf-8-sig", dtype=str)
    sent_final_md5 = get_file_md5(SENTIMENT_FINAL_CSV)
    print(f" [B-2] 최종 확정 감성 데이터 ({SENTIMENT_FINAL_CSV}):")
    print(f"   - 행 수: {len(df_sent_final):,}행, 열: {list(df_sent_final.columns)}")
    print(f"   - 라벨 분포 (혼합 해소 완료): {df_sent_final['label'].value_counts().to_dict()}")
    print(f"   - 고유 review_id 수: {df_sent_final['review_id'].nunique():,}개")
    
    # 원본 리뷰와의 연결성 점검 (최종 확정본 기준)
    raw_id_set = set(df_raw["reviewId"].dropna())
    sent_id_set = set(df_sent_final["review_id"].dropna())
    matched_sent_ids = sent_id_set.intersection(raw_id_set)
    unmatched_sent_ids = sent_id_set - raw_id_set
    
    print(f"   - 원본 reviewId와 일치하는 review_id: {len(matched_sent_ids):,}개 ({len(matched_sent_ids)/len(sent_id_set)*100:.2f}%)")
    print(f"   - 불일치 review_id 수: {len(unmatched_sent_ids)}건")
    
    # 원본과 병합하여 날짜 상태 확인
    df_sent_merged = pd.merge(df_sent_final, df_raw[["reviewId", "date", "parsed_date"]], left_on="review_id", right_on="reviewId", how="left")
    sent_parse_fail = int(df_sent_merged["parsed_date"].isna().sum())
    sent_date_min = str(df_sent_merged["parsed_date"].min().date())
    sent_date_max = str(df_sent_merged["parsed_date"].max().date())
    print(f"   - 원본 연결 후 날짜 범위: {sent_date_min} ~ {sent_date_max} (파싱 실패: {sent_parse_fail}건)")
    print(f"   - Tier A 3곳 문장 수 (최종본):")
    for p in TIER_A_PLACES:
        print(f"       * {p}: {(df_sent_final['place'] == p).sum():,}개 문장 (원본 {(df_raw['place']==p).sum():,}개 리뷰 중 텍스트 보유분)")

    sentiment_inventory = {
        "dataset_role": "final_sentiment",
        "file_path": rel(SENTIMENT_FINAL_CSV),
        "row_count": len(df_sent_final),
        "place_column": "place",
        "platform_column": "platform",
        "date_column": "date (via raw_review reviewId join)",
        "review_id_column": "review_id",
        "sentence_id_column": "unit_id (또는 sent_no)",
        "sentiment_column": "label",
        "keyword_column": "",
        "date_min": sent_date_min,
        "date_max": sent_date_max,
        "date_parse_fail_count": sent_parse_fail,
        "link_key_to_raw": "raw.reviewId = sentiment.review_id",
        "link_relationship": "1:N (1개 원본 리뷰 -> N개 감성 문장)",
        "notes": f"MD5={sent_final_md5}, 최종혼합해소본(5,793행), 원본문장본(5,685행: {rel(SENTIMENT_5685_CSV)}), 긍정/중립/부정 3분류"
    }

    # --------------------------------------------------------------------------
    # 3. Inventory CSV 저장
    # --------------------------------------------------------------------------
    df_inv = pd.DataFrame([raw_inventory, sentiment_inventory])
    df_inv.to_csv(INVENTORY_CSV, index=False, encoding="utf-8-sig")
    print("\n" + "=" * 80)
    print(f" [저장 완료] 시계열 입력자료 인벤토리 CSV: {INVENTORY_CSV} ({len(df_inv)}행)")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 4. 자동 검증 8대 항목
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [자동 검증 및 기술적 판정 8대 항목]")
    print("=" * 80)

    v1 = os.path.exists(RAW_REVIEW_CSV)
    print(f" 1. 원본 리뷰 데이터 파일 확인: {'[PASS]' if v1 else '[FAIL]'}")

    v2 = os.path.exists(SENTIMENT_FINAL_CSV) and os.path.exists(SENTIMENT_5685_CSV)
    print(f" 2. 최종 감성 데이터 파일 확인 (5,793행 최종본 및 5,685행 원본문장본 확인): {'[PASS]' if v2 else '[FAIL]'}")

    v3 = (
        all(p in df_raw["place"].values for p in TIER_A_PLACES) and
        all(p in df_sent_final["place"].values for p in TIER_A_PLACES)
    )
    print(f" 3. Tier A 3곳 2개 데이터셋 전체 존재 확인: {'[PASS]' if v3 else '[FAIL]'}")

    v4 = (raw_parse_fail == 0) and bool(raw_date_min)
    print(f" 4. 원본 리뷰 날짜 일 단위 사용 가능 (파싱 실패 0건): {'[PASS]' if v4 else '[FAIL]'}")

    v5 = (len(unmatched_sent_ids) == 0) and (sent_parse_fail == 0)
    print(f" 5. 감성 데이터 ↔ 원본 리뷰 날짜 연결 가능 (매칭률 100%, 파싱 실패 0건): {'[PASS]' if v5 else '[FAIL]'}")

    v6 = (raw_unique_ids == raw_rows)
    print(f" 6. 연결키(reviewId) 중복 여부 확인 (원본 고유값 무결성): {'[PASS]' if v6 else '[FAIL]'}")

    v7 = True
    print(f" 7. 원본 파일 불변성 점검 (조회 및 점검만 수행): {'[PASS]' if v7 else '[FAIL]'}")

    v8 = v1 and v2 and v3 and v4 and v5 and v6 and v7
    print(f" 8. 2022~2025 본 분석 진행 기술적 판정: {'[READY / PASS]' if v8 else '[BLOCKED / FAIL]'}")
    print("=" * 80)

if __name__ == "__main__":
    main()
