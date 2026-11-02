# -*- coding: utf-8 -*-
"""
외부 공식자료 운영·개장·행사 시점 확인 및 월별 리뷰 변화 대조 (T4-2 문구 정밀화)
파일명: t4_2_timeline_matching.py

수정 사항:
  1. 2025 임실N치즈축제 장소를 임실군 공식 페이지 표기대로 "임실치즈테마파크, 임실치즈마을, 임실읍 일원"으로 수정 (두 CSV 모두 반영)
  2. 2024년 붕어섬·옥정호출렁다리 휴장 사유를 뉴시스 출처 기준인 "2024년 1~2월 붕어섬 내부 시설보강을 위한 휴장"으로 수정
  3. 2022-12-19 ~ 2023-02-28 휴장 사유를 "출렁다리 야간경관조명 설치 및 보강공사·주변 정비를 위한 휴장"으로 수정
"""

import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

CSV_TIMELINE_EVIDENCE = os.path.join(OUTPUT_DIR, "external_timeline_evidence.csv")
CSV_TIMELINE_COMPARISON = os.path.join(OUTPUT_DIR, "timeline_review_comparison.csv")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 80)
    print(" [T4-2] 외부 공식자료 시점 확인 및 월별 리뷰 변화 대조표 생성 (문구 정밀화)")
    print("=" * 80)
    
    # --------------------------------------------------------------------------
    # 1. external_timeline_evidence.csv 데이터 정의 (14행)
    # --------------------------------------------------------------------------
    evidence_data = [
        # [붕어섬생태공원]
        {
            "place": "붕어섬생태공원",
            "event_type": "temporary_opening",
            "event_start_date": "2022-10-22",
            "event_end_date": "2022-12-18",
            "event_description": "옥정호 출렁다리 준공식과 함께 섬진강 댐 건설 후 육지 속 무인도였던 붕어섬 생태공원이 보도교를 통해 일반 관광객에게 최초 임시 개방(무료 시범운영)",
            "source_type": "news",
            "source_title": "‘붕어섬’ 열렸다...옥정호 출렁다리 개통",
            "source_url": "https://www.ytn.co.kr/_ln/0115_202210221913480392",
            "source_published_date": "2022-10-22",
            "evidence_level": "news",
            "notes": "출렁다리 연결로 도보 진입 가능해짐"
        },
        {
            "place": "붕어섬생태공원",
            "event_type": "seasonal_closure",
            "event_start_date": "2022-12-19",
            "event_end_date": "2023-02-28",
            "event_description": "출렁다리 야간경관조명 설치 및 보강공사·주변 정비를 위한 휴장",
            "source_type": "news",
            "source_title": "임실군, 옥정호 출렁다리·붕어섬 내달 1일 정식 개장",
            "source_url": "https://www.newspim.com/news/view/20230221000707",
            "source_published_date": "2023-02-21",
            "evidence_level": "news",
            "notes": "2022-12-19부터 휴장 후 시설 보강 거쳐 정식 개장 준비"
        },
        {
            "place": "붕어섬생태공원",
            "event_type": "reopening",
            "event_start_date": "2023-03-01",
            "event_end_date": "2023-03-01",
            "event_description": "동절기 정비 완료 후 유료화 전환과 함께 붕어섬 생태공원 정식 개장 및 운영 재개",
            "source_type": "public_institution",
            "source_title": "대한민국 구석구석 - 옥정호 출렁다리 건너 어슬렁 도보여행",
            "source_url": "https://korean.visitkorea.or.kr/detail/rem_detail.do?cotid=2af32513-ee9c-4b71-9e89-f7c93fee760e",
            "source_published_date": "",
            "evidence_level": "public_institution",
            "notes": "유료 입장 전환(성인 3,000원)"
        },
        {
            "place": "붕어섬생태공원",
            "event_type": "seasonal_closure",
            "event_start_date": "2024-01-01",
            "event_end_date": "2024-02-29",
            "event_description": "2024년 1~2월 붕어섬 내부 시설보강을 위한 휴장",
            "source_type": "news",
            "source_title": "임실 옥정호 출렁다리·붕어섬 생태공원 3월1일 재개장",
            "source_url": "https://www.newsis.com/view/NISX20240227_0002641061",
            "source_published_date": "2024-02-27",
            "evidence_level": "news",
            "notes": "동절기 1~2월 시설보강 후 3월 1일 재개장"
        },
        {
            "place": "붕어섬생태공원",
            "event_type": "reopening",
            "event_start_date": "2024-03-01",
            "event_end_date": "2024-03-01",
            "event_description": "시설보강 후 2024년 봄철 운영 재개",
            "source_type": "news",
            "source_title": "임실 옥정호 출렁다리·붕어섬 생태공원 3월1일 재개장",
            "source_url": "https://www.newsis.com/view/NISX20240227_0002641061",
            "source_published_date": "2024-02-27",
            "evidence_level": "news",
            "notes": "3월 한 달 무료 입장 프로모션"
        },
        # [옥정호출렁다리]
        {
            "place": "옥정호출렁다리",
            "event_type": "temporary_opening",
            "event_start_date": "2022-10-22",
            "event_end_date": "2022-12-18",
            "event_description": "요산공원과 붕어섬을 잇는 420m 현수교 준공식 개최 및 대중 무료 임시 개통(시범운영)",
            "source_type": "news",
            "source_title": "‘붕어섬’ 열렸다...옥정호 출렁다리 개통",
            "source_url": "https://www.ytn.co.kr/_ln/0115_202210221913480392",
            "source_published_date": "2022-10-22",
            "evidence_level": "news",
            "notes": "붕어 모티브 주탑(80m) 설치"
        },
        {
            "place": "옥정호출렁다리",
            "event_type": "seasonal_closure",
            "event_start_date": "2022-12-19",
            "event_end_date": "2023-02-28",
            "event_description": "출렁다리 야간경관조명 설치 및 보강공사·주변 정비를 위한 휴장",
            "source_type": "news",
            "source_title": "임실군, 옥정호 출렁다리·붕어섬 내달 1일 정식 개장",
            "source_url": "https://www.newspim.com/news/view/20230221000707",
            "source_published_date": "2023-02-21",
            "evidence_level": "news",
            "notes": "시범운영 기간 도출된 편의/안전시설 개선"
        },
        {
            "place": "옥정호출렁다리",
            "event_type": "reopening",
            "event_start_date": "2023-03-01",
            "event_end_date": "2023-03-01",
            "event_description": "시설 보강 완료 후 유료화 정식 개통 및 운영 재개",
            "source_type": "public_institution",
            "source_title": "대한민국 구석구석 - 옥정호 출렁다리 건너 어슬렁 도보여행",
            "source_url": "https://korean.visitkorea.or.kr/detail/rem_detail.do?cotid=2af32513-ee9c-4b71-9e89-f7c93fee760e",
            "source_published_date": "",
            "evidence_level": "public_institution",
            "notes": "정식 유료 개방"
        },
        {
            "place": "옥정호출렁다리",
            "event_type": "seasonal_closure",
            "event_start_date": "2024-01-01",
            "event_end_date": "2024-02-29",
            "event_description": "2024년 1~2월 붕어섬 내부 시설보강을 위한 휴장",
            "source_type": "news",
            "source_title": "임실 옥정호 출렁다리·붕어섬 생태공원 3월1일 재개장",
            "source_url": "https://www.newsis.com/view/NISX20240227_0002641061",
            "source_published_date": "2024-02-27",
            "evidence_level": "news",
            "notes": "동절기 시설보강 후 재개장"
        },
        {
            "place": "옥정호출렁다리",
            "event_type": "reopening",
            "event_start_date": "2024-03-01",
            "event_end_date": "2024-03-01",
            "event_description": "시설보강 후 2024년 3월 1일 운영 재개",
            "source_type": "news",
            "source_title": "임실 옥정호 출렁다리·붕어섬 생태공원 3월1일 재개장",
            "source_url": "https://www.newsis.com/view/NISX20240227_0002641061",
            "source_published_date": "2024-02-27",
            "evidence_level": "news",
            "notes": "봄철 정상 운영"
        },
        # [임실치즈테마파크 / 임실N치즈축제]
        {
            "place": "임실치즈테마파크",
            "event_type": "festival",
            "event_start_date": "2022-10-07",
            "event_end_date": "2022-10-10",
            "event_description": "2022 임실N치즈축제 개최 (주제: 즐겨요~ 치즈축제! 걸어요~ 국화꽃길!)",
            "source_type": "public_institution",
            "source_title": "대한민국 구석구석 축제정보 - 2022 임실N치즈축제",
            "source_url": "https://korean.visitkorea.or.kr/kfes/detail/fstvlDetail.do?fstvlCntntsId=b1897d26-7c9d-4786-9040-410e42d76a26",
            "source_published_date": "",
            "evidence_level": "public_institution",
            "notes": "장소: 임실치즈테마파크, 임실치즈마을"
        },
        {
            "place": "임실치즈테마파크",
            "event_type": "festival",
            "event_start_date": "2023-10-06",
            "event_end_date": "2023-10-09",
            "event_description": "2023 임실N치즈축제 개최 (주제: 임실N사랑Dream! 치즈N건강Dream!)",
            "source_type": "public_institution",
            "source_title": "대한민국 구석구석 축제정보 - 2023 임실N치즈축제",
            "source_url": "https://korean.visitkorea.or.kr/kfes/detail/fstvlDetail.do?fstvlCntntsId=2e635f5c-897d-419b-a36c-947cae4b6ebc",
            "source_published_date": "",
            "evidence_level": "public_institution",
            "notes": "장소: 임실치즈테마파크, 임실치즈마을"
        },
        {
            "place": "임실치즈테마파크",
            "event_type": "festival",
            "event_start_date": "2024-10-03",
            "event_end_date": "2024-10-06",
            "event_description": "2024 임실N치즈축제 개최 (10주년 기념 행사)",
            "source_type": "official",
            "source_title": "임실N치즈축제 공식 홈페이지 - 2024 축제개요",
            "source_url": "https://www.imsilfestival.com/?c=433%2F434&r=2024",
            "source_published_date": "",
            "evidence_level": "official",
            "notes": "장소: 임실치즈테마파크, 임실치즈마을"
        },
        {
            "place": "임실치즈테마파크",
            "event_type": "festival",
            "event_start_date": "2025-10-08",
            "event_end_date": "2025-10-12",
            "event_description": "2025 임실N치즈축제 개최 (5일간 확대 운영)",
            "source_type": "official",
            "source_title": "임실군 문화관광 - 임실N치즈축제 안내",
            "source_url": "https://www.imsil.go.kr/tour/index.imsil?menuCd=DOM_000000203001001000",
            "source_published_date": "",
            "evidence_level": "official",
            "notes": "장소: 임실치즈테마파크, 임실치즈마을, 임실읍 일원"
        }
    ]
    
    df_evidence = pd.DataFrame(evidence_data)
    df_evidence.to_csv(CSV_TIMELINE_EVIDENCE, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] 외부 공식 운영 이력 CSV: {CSV_TIMELINE_EVIDENCE} ({len(df_evidence)}행)")

    # --------------------------------------------------------------------------
    # 2. timeline_review_comparison.csv 시점 대조표 정의 (12행)
    # --------------------------------------------------------------------------
    comparison_data = [
        # [붕어섬생태공원]
        {
            "place": "붕어섬생태공원",
            "review_change_period": "2022-01 ~ 2022-09",
            "review_data_fact": "리뷰 0건 (데이터 상 관측 리뷰 없음)",
            "external_event_period": "2022-01 ~ 2022-10-21",
            "external_event_fact": "출렁다리 개통 전으로 일반 도보 접근 불가(보도교 미개통 상태)",
            "temporal_match": "yes",
            "interpretation_limit": "시기가 일치하나 리뷰 작성 여부와 도보 접근성의 인과관계는 단정하지 않음"
        },
        {
            "place": "붕어섬생태공원",
            "review_change_period": "2022-10 ~ 2022-11",
            "review_data_fact": "2022-10 첫 10건 발생 후 11월 19건으로 증가",
            "external_event_period": "2022-10-22 ~ 2022-12-18",
            "external_event_fact": "2022-10-22 출렁다리 개통과 함께 붕어섬 생태공원 최초 임시 개방(무료 시범운영)",
            "temporal_match": "yes",
            "interpretation_limit": "임시 개방 시점과 첫 리뷰 관측 시기가 겹치나 인과관계를 단정할 수 없음"
        },
        {
            "place": "붕어섬생태공원",
            "review_change_period": "2022-12 ~ 2023-02",
            "review_data_fact": "2022-12 2건으로 급감 후 2023-01~02 2개월 연속 0건",
            "external_event_period": "2022-12-19 ~ 2023-02-28",
            "external_event_fact": "출렁다리 야간경관조명 설치 및 보강공사·주변 정비를 위한 휴장",
            "temporal_match": "yes",
            "interpretation_limit": "동절기 시설 보강 휴장 기간과 리뷰 0건 시기가 시간적으로 일치하나 단정은 불가"
        },
        {
            "place": "붕어섬생태공원",
            "review_change_period": "2023-03 ~ 2023-05",
            "review_data_fact": "2023-03 54건으로 급증(MoM +54건) 후 4월 79건, 5월 104건 지속 상승",
            "external_event_period": "2023-03-01 ~",
            "external_event_fact": "2023-03-01 시설 보강 완료 후 유료화 정식 개장 및 봄철 운영 재개",
            "temporal_match": "yes",
            "interpretation_limit": "정식 개장/재개장 시점과 리뷰 급증 시기가 시간적으로 겹치나 인과관계 확인 불가"
        },
        # [옥정호출렁다리]
        {
            "place": "옥정호출렁다리",
            "review_change_period": "2022-01 ~ 2022-09",
            "review_data_fact": "리뷰 0건 (관측 리뷰 없음)",
            "external_event_period": "2022-01 ~ 2022-10-21",
            "external_event_fact": "공식 개통 전 공사/시공 기간",
            "temporal_match": "yes",
            "interpretation_limit": "개통 전 리뷰 부재와 시기가 일치하나 인과관계로 단정하지 않음"
        },
        {
            "place": "옥정호출렁다리",
            "review_change_period": "2022-10 ~ 2022-11",
            "review_data_fact": "2022-10 첫 6건 관측 후 11월 55건으로 급증(MoM +49건)",
            "external_event_period": "2022-10-22 ~ 2022-12-18",
            "external_event_fact": "2022-10-22 공식 준공식 및 무료 임시 개통",
            "temporal_match": "yes",
            "interpretation_limit": "임시 개통 시점과 첫 리뷰 관측/증가 시기가 겹치나 인과관계는 단정 불가"
        },
        {
            "place": "옥정호출렁다리",
            "review_change_period": "2022-12 ~ 2023-02",
            "review_data_fact": "2022-12 39건 → 2023-01 18건 → 2023-02 9건으로 지속 감소",
            "external_event_period": "2022-12-19 ~ 2023-02-28",
            "external_event_fact": "출렁다리 야간경관조명 설치 및 보강공사·주변 정비를 위한 휴장",
            "temporal_match": "partial",
            "interpretation_limit": "휴장 기간 중에도 1~2월 소수 리뷰가 존재(원격 조망/기존 방문 후기 등 가능성), 인과관계 단정 불가"
        },
        {
            "place": "옥정호출렁다리",
            "review_change_period": "2023-03 ~ 2023-05",
            "review_data_fact": "2023-03 60건으로 급증(MoM +51건) 후 4월 70건, 5월 74건 유지",
            "external_event_period": "2023-03-01 ~",
            "external_event_fact": "2023-03-01 유료화 정식 개통 및 봄철 운영 재개",
            "temporal_match": "yes",
            "interpretation_limit": "정식 개통 시점과 리뷰 급증 시기가 시간적으로 겹치나 인과관계는 단정 불가"
        },
        # [임실치즈테마파크]
        {
            "place": "임실치즈테마파크",
            "review_change_period": "2022-10",
            "review_data_fact": "180건 (단일 월 전체 기간 최고치, 9월 39건 대비 MoM +141건 급증)",
            "external_event_period": "2022-10-07 ~ 2022-10-10",
            "external_event_fact": "2022 임실N치즈축제 개최 (장소: 임실치즈테마파크, 임실치즈마을)",
            "temporal_match": "yes",
            "interpretation_limit": "축제 개최 월과 리뷰 급증 월이 시간적으로 겹치나 인과관계로 단정하지 않음"
        },
        {
            "place": "임실치즈테마파크",
            "review_change_period": "2023-10",
            "review_data_fact": "93건 (2023년 중 최고치, 9월 18건 대비 MoM +75건 급증)",
            "external_event_period": "2023-10-06 ~ 2023-10-09",
            "external_event_fact": "2023 임실N치즈축제 개최 (장소: 임실치즈테마파크, 임실치즈마을)",
            "temporal_match": "yes",
            "interpretation_limit": "축제 개최 월과 연간 피크 월이 시간적으로 겹치나 인과관계는 단정 불가"
        },
        {
            "place": "임실치즈테마파크",
            "review_change_period": "2024-10",
            "review_data_fact": "35건 (2024년 하반기 최고치, 9월 9건 대비 MoM +26건 증가)",
            "external_event_period": "2024-10-03 ~ 2024-10-06",
            "external_event_fact": "2024 임실N치즈축제 개최 (장소: 임실치즈테마파크, 임실치즈마을)",
            "temporal_match": "yes",
            "interpretation_limit": "10월 축제 시점과 가을철 리뷰 반등 시기가 겹치나 인과관계는 단정 불가"
        },
        {
            "place": "임실치즈테마파크",
            "review_change_period": "2025-10",
            "review_data_fact": "65건 (2025년 중 최고치, 9월 3건 대비 MoM +62건 급증)",
            "external_event_period": "2025-10-08 ~ 2025-10-12",
            "external_event_fact": "2025 임실N치즈축제 개최 (장소: 임실치즈테마파크, 임실치즈마을, 임실읍 일원)",
            "temporal_match": "yes",
            "interpretation_limit": "축제 개최 월과 연간 최고치 월이 시간적으로 겹치나 인과관계는 단정 불가"
        }
    ]
    
    df_comp = pd.DataFrame(comparison_data)
    df_comp.to_csv(CSV_TIMELINE_COMPARISON, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] 시점 대조표 CSV: {CSV_TIMELINE_COMPARISON} ({len(df_comp)}행)")

    print("\n" + "=" * 80)
    print(" [T4-2 문구 정밀화 완료]")
    print("=" * 80)


if __name__ == "__main__":
    main()
