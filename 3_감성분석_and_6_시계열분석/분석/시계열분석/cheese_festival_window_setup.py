# -*- coding: utf-8 -*-
"""
임실N치즈축제 전·중·후 분석 구간 확정 스크립트 (T-4)
파일명: cheese_festival_window_setup.py

목적:
  1. external_timeline_evidence.csv에서 2022~2025 임실N치즈축제 공식 기간 로드
  2. 축제 전(pre, 14일), 축제 기간(festival, 실제일수), 축제 후(post, 14일) 분석 윈도우 동적 계산 (12행)
  3. 원본 리뷰 데이터(data/임실군_관광지_리뷰데이터.csv)의 수집 범위 내 존재 여부 및 15대 무결성 자동 검증
  4. output/cheese_festival_analysis_windows_2022_2025.csv 산출물 생성
"""

import os
import hashlib
import pandas as pd
import numpy as np

# ==============================================================================
# 0. 경로 및 상수 정의
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

EVIDENCE_CSV = os.path.join(BASE_DIR, "output", "external_timeline_evidence.csv")
RAW_REVIEW_CSV = os.path.join(PROJECT_ROOT, "data", "임실군_관광지_리뷰데이터.csv")

OUTPUT_DIR = os.path.join(BASE_DIR, "output")
OUTPUT_WINDOWS_CSV = os.path.join(OUTPUT_DIR, "cheese_festival_analysis_windows_2022_2025.csv")

TARGET_YEARS = [2022, 2023, 2024, 2025]
EXPECTED_FESTIVAL_DATES = {
    2022: ("2022-10-07", "2022-10-10"),
    2023: ("2023-10-06", "2023-10-09"),
    2024: ("2024-10-03", "2024-10-06"),
    2025: ("2025-10-08", "2025-10-12")
}


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
    print(" [T-4] 임실N치즈축제 전·중·후 분석 구간 확정 (2022~2025)")
    print("=" * 80)
    
    # --------------------------------------------------------------------------
    # 1. 외부 근거 CSV 및 원본 리뷰 데이터 로드 & MD5 해시 기록
    # --------------------------------------------------------------------------
    if not os.path.exists(EVIDENCE_CSV):
        raise FileNotFoundError(f"외부 근거 파일이 없습니다: {EVIDENCE_CSV}")
    if not os.path.exists(RAW_REVIEW_CSV):
        raise FileNotFoundError(f"원본 리뷰 파일이 없습니다: {RAW_REVIEW_CSV}")
        
    evidence_initial_md5 = get_file_md5(EVIDENCE_CSV)
    raw_initial_md5 = get_file_md5(RAW_REVIEW_CSV)
    
    print(f"[입력 파일 1 - 외부근거] {EVIDENCE_CSV} (MD5: {evidence_initial_md5})")
    print(f"[입력 파일 2 - 원본리뷰] {RAW_REVIEW_CSV} (MD5: {raw_initial_md5})")
    
    df_evidence = pd.read_csv(EVIDENCE_CSV, encoding="utf-8-sig", dtype=str)
    df_raw = pd.read_csv(RAW_REVIEW_CSV, encoding="utf-8-sig", dtype=str)
    
    # 원본 리뷰 날짜 범위 확인
    df_raw["parsed_date"] = pd.to_datetime(df_raw["date"], errors="coerce")
    raw_date_min = df_raw["parsed_date"].min()
    raw_date_max = df_raw["parsed_date"].max()
    print(f"[원본 리뷰 수집 날짜 범위] {raw_date_min.strftime('%Y-%m-%d')} ~ {raw_date_max.strftime('%Y-%m-%d')} (총 {len(df_raw):,}건)")
    
    # --------------------------------------------------------------------------
    # 2. 임실치즈테마파크 festival 행 추출 및 날짜 연산
    # --------------------------------------------------------------------------
    df_fest = df_evidence[
        (df_evidence["place"] == "임실치즈테마파크") &
        (df_evidence["event_type"] == "festival")
    ].copy()
    
    df_fest["start_dt"] = pd.to_datetime(df_fest["event_start_date"])
    df_fest["end_dt"] = pd.to_datetime(df_fest["event_end_date"])
    df_fest["year"] = df_fest["start_dt"].dt.year
    df_fest = df_fest.sort_values(by="year").reset_index(drop=True)
    
    windows_rows = []
    
    for idx, row in df_fest.iterrows():
        yr = row["year"]
        f_start = row["start_dt"]
        f_end = row["end_dt"]
        f_days = (f_end - f_start).days + 1
        
        src_title = row["source_title"]
        src_url = row["source_url"]
        
        # 1. pre: 축제 시작일 직전 14일
        pre_start = f_start - pd.Timedelta(days=14)
        pre_end = f_start - pd.Timedelta(days=1)
        pre_days = (pre_end - pre_start).days + 1
        
        windows_rows.append({
            "year": yr,
            "period": "pre",
            "period_start_date": pre_start.strftime("%Y-%m-%d"),
            "period_end_date": pre_end.strftime("%Y-%m-%d"),
            "days_count": pre_days,
            "festival_start_date": f_start.strftime("%Y-%m-%d"),
            "festival_end_date": f_end.strftime("%Y-%m-%d"),
            "festival_days": f_days,
            "source_title": src_title,
            "source_url": src_url
        })
        
        # 2. festival: 공식 축제 기간
        windows_rows.append({
            "year": yr,
            "period": "festival",
            "period_start_date": f_start.strftime("%Y-%m-%d"),
            "period_end_date": f_end.strftime("%Y-%m-%d"),
            "days_count": f_days,
            "festival_start_date": f_start.strftime("%Y-%m-%d"),
            "festival_end_date": f_end.strftime("%Y-%m-%d"),
            "festival_days": f_days,
            "source_title": src_title,
            "source_url": src_url
        })
        
        # 3. post: 축제 종료일 직후 14일
        post_start = f_end + pd.Timedelta(days=1)
        post_end = f_end + pd.Timedelta(days=14)
        post_days = (post_end - post_start).days + 1
        
        windows_rows.append({
            "year": yr,
            "period": "post",
            "period_start_date": post_start.strftime("%Y-%m-%d"),
            "period_end_date": post_end.strftime("%Y-%m-%d"),
            "days_count": post_days,
            "festival_start_date": f_start.strftime("%Y-%m-%d"),
            "festival_end_date": f_end.strftime("%Y-%m-%d"),
            "festival_days": f_days,
            "source_title": src_title,
            "source_url": src_url
        })
        
    df_windows = pd.DataFrame(windows_rows)
    df_windows.to_csv(OUTPUT_WINDOWS_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[저장 완료] 축제 분석 구간 CSV: {OUTPUT_WINDOWS_CSV} ({len(df_windows)}행)")

    # --------------------------------------------------------------------------
    # 3. 15대 무결성 자동 검증
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [자동 검증 실행 결과 (15대 항목)]")
    print("=" * 80)
    
    # 1. external_timeline_evidence.csv 존재
    v1 = os.path.exists(EVIDENCE_CSV)
    print(f" 1. external_timeline_evidence.csv 파일 존재 확인: {'[PASS]' if v1 else '[FAIL]'}")
    
    # 2. 임실치즈테마파크 festival 행 정확히 4개
    v2 = (len(df_fest) == 4)
    print(f" 2. 임실치즈테마파크 festival 행 4개 확인: {'[PASS]' if v2 else '[FAIL]'} (실제 {len(df_fest)}개)")
    
    # 3. 대상 연도가 2022~2025 정확히 존재
    years_present = sorted(df_fest["year"].unique().tolist())
    v3 = (years_present == TARGET_YEARS)
    print(f" 3. 대상 연도(2022~2025) 일치 확인: {'[PASS]' if v3 else '[FAIL]'} (연도: {years_present})")
    
    # 4. 축제 시작일 <= 종료일
    v4 = (df_fest["start_dt"] <= df_fest["end_dt"]).all()
    print(f" 4. 모든 축제 시작일 <= 종료일 유효성 확인: {'[PASS]' if v4 else '[FAIL]'}")
    
    # 5. 기존 검증 축제 날짜와 실제 CSV 날짜 일치
    v5 = True
    for yr, (exp_s, exp_e) in EXPECTED_FESTIVAL_DATES.items():
        row_y = df_fest[df_fest["year"] == yr]
        if len(row_y) == 0:
            v5 = False
            break
        act_s = row_y["event_start_date"].values[0]
        act_e = row_y["event_end_date"].values[0]
        if act_s != exp_s or act_e != exp_e:
            v5 = False
            print(f"   [불일치] {yr}년: 예상 {exp_s}~{exp_e} != 실제 {act_s}~{act_e}")
    print(f" 5. 검증 축제 날짜와 CSV 날짜 100% 일치 확인: {'[PASS]' if v5 else '[FAIL]'}")
    
    # 6. 출력 행 수 = 12행
    v6 = (len(df_windows) == 12)
    print(f" 6. 출력 CSV 행 수 12행(4개년 x 3구간) 확인: {'[PASS]' if v6 else '[FAIL]'} (실제 {len(df_windows)}행)")
    
    # 7. 각 연도에 pre/festival/post 각각 1개씩 존재
    v7 = True
    for yr in TARGET_YEARS:
        p_list = df_windows[df_windows["year"] == yr]["period"].tolist()
        if p_list != ["pre", "festival", "post"]:
            v7 = False
            print(f"   [구간 오류] {yr}년: {p_list}")
    print(f" 7. 각 연도별 pre/festival/post 각 1개씩 완비 확인: {'[PASS]' if v7 else '[FAIL]'}")
    
    # 8. pre 기간 = 14일
    v8 = (df_windows[df_windows["period"] == "pre"]["days_count"] == 14).all()
    print(f" 8. pre 구간 길이 14일 확인: {'[PASS]' if v8 else '[FAIL]'}")
    
    # 9. post 기간 = 14일
    v9 = (df_windows[df_windows["period"] == "post"]["days_count"] == 14).all()
    print(f" 9. post 구간 길이 14일 확인: {'[PASS]' if v9 else '[FAIL]'}")
    
    # 10. festival 기간이 실제 개최일수와 일치
    v10 = (df_windows[df_windows["period"] == "festival"]["days_count"] == df_windows[df_windows["period"] == "festival"]["festival_days"]).all()
    print(f" 10. festival 구간 일수 == 실제 개최일수 일치 확인: {'[PASS]' if v10 else '[FAIL]'}")
    
    # 11. pre와 festival 사이 날짜 공백/중복 없음 (pre_end + 1 == fest_start)
    v11 = True
    for yr in TARGET_YEARS:
        pre_e = pd.to_datetime(df_windows[(df_windows["year"] == yr) & (df_windows["period"] == "pre")]["period_end_date"].values[0])
        fst_s = pd.to_datetime(df_windows[(df_windows["year"] == yr) & (df_windows["period"] == "festival")]["period_start_date"].values[0])
        if pre_e + pd.Timedelta(days=1) != fst_s:
            v11 = False
            print(f"   [연속성 오류] {yr}년 pre_end({pre_e}) -> festival_start({fst_s})")
    print(f" 11. pre ↔ festival 사이 날짜 공백/중복 0건 확인: {'[PASS]' if v11 else '[FAIL]'}")
    
    # 12. festival과 post 사이 날짜 공백/중복 없음 (fest_end + 1 == post_start)
    v12 = True
    for yr in TARGET_YEARS:
        fst_e = pd.to_datetime(df_windows[(df_windows["year"] == yr) & (df_windows["period"] == "festival")]["period_end_date"].values[0])
        pst_s = pd.to_datetime(df_windows[(df_windows["year"] == yr) & (df_windows["period"] == "post")]["period_start_date"].values[0])
        if fst_e + pd.Timedelta(days=1) != pst_s:
            v12 = False
            print(f"   [연속성 오류] {yr}년 festival_end({fst_e}) -> post_start({pst_s})")
    print(f" 12. festival ↔ post 사이 날짜 공백/중복 0건 확인: {'[PASS]' if v12 else '[FAIL]'}")
    
    # 13. 한 연도 내 pre/festival/post 날짜 비중복 확인
    v13 = True
    for yr in TARGET_YEARS:
        w_df = df_windows[df_windows["year"] == yr]
        date_sets = []
        for idx, r in w_df.iterrows():
            d_range = pd.date_range(r["period_start_date"], r["period_end_date"])
            date_sets.append(set(d_range))
        if len(date_sets[0].intersection(date_sets[1])) > 0 or len(date_sets[1].intersection(date_sets[2])) > 0 or len(date_sets[0].intersection(date_sets[2])) > 0:
            v13 = False
    print(f" 13. 연도 내 3개 구간 날짜 상호 배타성(중복 0건): {'[PASS]' if v13 else '[FAIL]'}")
    
    # 14. 모든 분석 구간이 원본 리뷰 데이터 날짜 범위 안에 존재
    earliest_date = pd.to_datetime(df_windows["period_start_date"]).min()
    latest_date = pd.to_datetime(df_windows["period_end_date"]).max()
    v14 = (earliest_date >= raw_date_min) and (latest_date <= raw_date_max)
    print(f" 14. 원본 리뷰 수집 기간 내 포함 확인: {'[PASS]' if v14 else '[FAIL]'} (구간범위: {earliest_date.strftime('%Y-%m-%d')} ~ {latest_date.strftime('%Y-%m-%d')})")
    
    # 15. 입력 파일 불변성 점검
    evidence_final_md5 = get_file_md5(EVIDENCE_CSV)
    raw_final_md5 = get_file_md5(RAW_REVIEW_CSV)
    v15 = (evidence_initial_md5 == evidence_final_md5) and (raw_initial_md5 == raw_final_md5)
    print(f" 15. 입력 파일 2종 실행 전후 불변 확인(MD5): {'[PASS]' if v15 else '[FAIL]'}")
    
    all_passed = v1 and v2 and v3 and v4 and v5 and v6 and v7 and v8 and v9 and v10 and v11 and v12 and v13 and v14 and v15
    print("-" * 80)
    print(f" >> 전체 검증 결과: {'모든 검증 통과 (ALL PASSED)' if all_passed else '검증 실패 (FAILED)'}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 4. 콘솔 요약표 출력
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" [임실N치즈축제 전·중·후 분석 구간 확정표 (2022~2025)]")
    print("=" * 80)
    print(f"{'연도':<6}{'구간(period)':<12}{'시작일':<14}{'종료일':<14}{'일수(days)':>10}{'공식축제기간':<26}")
    print("-" * 82)
    for idx, r in df_windows.iterrows():
        fest_str = f"{r['festival_start_date']} ~ {r['festival_end_date']} ({r['festival_days']}일간)"
        print(f"{r['year']:<6}{r['period']:<12}{r['period_start_date']:<14}{r['period_end_date']:<14}{r['days_count']:>10}일  {fest_str:<26}")
    print("=" * 80)


if __name__ == "__main__":
    main()
