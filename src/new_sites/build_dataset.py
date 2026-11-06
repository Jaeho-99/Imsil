# -*- coding: utf-8 -*-
"""[통합] 수집 원본 → 통합 리뷰 데이터 (34개소 `input/임실군_관광지_리뷰데이터.csv` 와 같은 8개 컬럼)

입력
  output/collect/naver/{관광지명}_naver_reviews.csv     collect_naver.py · import_har.py 결과
  output/collect/google/{관광지명}_google_reviews.csv   src/collect/google_reviews.py 결과 (있을 때만 읽는다)
  input/new_sites/비식별_치환목록.csv                    사람이 실명으로 확인한 표현 (있을 때만)
출력
  output/new_sites/추가관광지_리뷰데이터.csv    place, platform, reviewId, rating, body, date, visitCount, tags
  output/collect/naver/추가관광지_리뷰ID_대응표.csv
                                   원본 리뷰ID ↔ 가명 ID (git 제외. 재실행해도 같은 가명을 유지)

34개소 데이터와 맞춘 규칙
  - 컬럼·값 형식: platform 은 '구글'/'네이버', date 는 YYYY-MM-DD, tags 는 JSON 리스트 문자열
    (네이버 키워드 리뷰 + 방문 목적·동반자 키워드), 구글 tags 는 "[]"
  - 수집 기간: config.DATE_START ~ config.DATE_END
  - 작성자 정보(닉네임·ID·프로필)는 버린다. 리뷰ID 는 가명(RV10001~)으로 바꾼다.

실행
    python src/new_sites/build_dataset.py
    IMSIL_DEMO=1 python src/new_sites/build_dataset.py --demo   # 시험 실행: 가짜 수집 원본부터 만든다
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime

import pandas as pd

from common import Checks, apply_mask, config, load_mask_rules, read_csv, rel, write_csv

COLS = ["place", "platform", "reviewId", "rating", "body", "date", "visitCount", "tags"]


# ─────────────────────────────────────────────────────────────
# 날짜 해석
# ─────────────────────────────────────────────────────────────
def parse_naver_date(s, year_hint: int) -> date | None:
    """네이버 created/visited 표기: '24.8.10.토' · '8.10.토'(올해) · '2024-08-10...'"""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    s = str(s).strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    nums = [p for p in s.split(".") if p.strip().isdigit()]
    try:
        if len(nums) >= 3:
            y = int(nums[0])
            return date(y + 2000 if y < 100 else y, int(nums[1]), int(nums[2]))
        if len(nums) == 2:
            return date(year_hint, int(nums[0]), int(nums[1]))
    except ValueError:
        return None
    return None


def parse_google_date(s) -> date | None:
    if s is None or (isinstance(s, float) and pd.isna(s)) or not str(s).strip():
        return None
    try:
        return pd.to_datetime(str(s)[:10]).date()
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────
# 플랫폼별 읽기
# ─────────────────────────────────────────────────────────────
def load_naver(name: str) -> pd.DataFrame:
    p = config.RAW_NAVER / f"{name}_naver_reviews.csv"
    if not p.exists():
        return pd.DataFrame()
    d = read_csv(p, dtype=str, keep_default_na=False)
    info = config.RAW_NAVER / f"{name}_수집정보.json"
    if info.exists():
        year = int(json.loads(info.read_text(encoding="utf-8"))["collected_at"][:4])
    else:
        year = datetime.fromtimestamp(p.stat().st_mtime).year
        print(f"  [경고] {info.name} 없음 — 연도 없는 날짜를 파일 수정연도 {year}년으로 해석")

    def tags(r):
        out = [x for x in str(r.get("keywords", "")).split("|") if x]
        out += [x for x in str(r.get("visitCategories", "")).split("|") if x]
        return json.dumps(out, ensure_ascii=False)

    return pd.DataFrame({
        "place": name,
        "platform": "네이버",
        "orig_id": "N:" + d["id"].astype(str),
        "rating": pd.to_numeric(d.get("rating"), errors="coerce"),
        "body": d["body"].replace("", pd.NA),
        "date": [parse_naver_date(x, year) for x in d[config.NAVER_DATE_FIELD]],
        "visitCount": pd.to_numeric(d.get("visitCount"), errors="coerce"),
        "tags": d.apply(tags, axis=1),
    })


def load_google(name: str) -> pd.DataFrame:
    p = config.RAW_GOOGLE / f"{name}_google_reviews.csv"
    if not p.exists():
        return pd.DataFrame()
    d = read_csv(p, dtype=str, keep_default_na=False)
    body = d["리뷰본문"] if "리뷰본문" in d else pd.Series([""] * len(d))
    return pd.DataFrame({
        "place": name,
        "platform": "구글",
        "orig_id": "G:" + d["리뷰ID"].astype(str),
        "rating": pd.to_numeric(d["평점"], errors="coerce"),
        "body": body.replace("", pd.NA),
        "date": [parse_google_date(x) for x in d.get("작성일", [None] * len(d))],
        "visitCount": float("nan"),
        "tags": "[]",
    })


# ─────────────────────────────────────────────────────────────
# 가명 ID
# ─────────────────────────────────────────────────────────────
def assign_ids(df: pd.DataFrame) -> pd.DataFrame:
    old = read_csv(config.ID_MAP, dtype=str) if config.ID_MAP.exists() else \
        pd.DataFrame(columns=["orig_id", "reviewId"])
    known = dict(zip(old["orig_id"], old["reviewId"]))
    nxt = max([int(v[2:]) for v in known.values()] + [config.REVIEW_ID_START - 1]) + 1
    new_ids = []
    # 정렬 순서를 고정해 처음 부여할 때도 실행마다 같은 번호가 나오게 한다
    for oid in df.sort_values(["place", "platform", "date", "orig_id"])["orig_id"]:
        if oid not in known:
            known[oid] = f"RV{nxt:05d}"
            nxt += 1
            new_ids.append(oid)
    write_csv(pd.DataFrame({"orig_id": list(known), "reviewId": list(known.values())}),
              config.ID_MAP)
    df = df.copy()
    df["reviewId"] = df["orig_id"].map(known)
    print(f"  가명 ID: 기존 {len(old)} · 신규 {len(new_ids)}")
    return df


# ─────────────────────────────────────────────────────────────
# 시험 실행용 가짜 수집 원본
# ─────────────────────────────────────────────────────────────
def make_demo_raw():
    """34개소 통합 데이터에서 인접 관광지 리뷰를 꺼내 수집기 출력 형식으로 되돌린다."""
    assert config.DEMO, "--demo 는 IMSIL_DEMO=1 과 함께 써야 합니다 (실제 output/ 보호)"
    base = read_csv(config.BASE_DATASET)
    config.RAW_NAVER.mkdir(parents=True, exist_ok=True)
    config.RAW_GOOGLE.mkdir(parents=True, exist_ok=True)
    for tgt, src in config.DEMO_SOURCES.items():
        d = base[base["place"] == src]
        n = d[d["platform"] == "네이버"]
        tg = n["tags"].map(json.loads)
        pd.DataFrame({
            "place_id": "0", "place_name": tgt, "id": n["reviewId"], "reviewId": n["reviewId"],
            "nickname": "demo", "rating": n["rating"],
            "body": n["body"].fillna("").str.replace("\n", " "),
            "visited": "", "created": [f"{x[2:4]}.{int(x[5:7])}.{int(x[8:10])}.월" for x in n["date"]],
            "visitCount": n["visitCount"], "originType": "",
            "keywords": tg.map(lambda t: "|".join(t)), "visitCategories": "", "mediaCount": 0,
        }).to_csv(config.RAW_NAVER / f"{tgt}_naver_reviews.csv", index=False, encoding="utf-8-sig")
        (config.RAW_NAVER / f"{tgt}_수집정보.json").write_text(json.dumps(
            {"place": tgt, "collected_at": "2026-08-11 00:00:00"}), encoding="utf-8")
        g = d[d["platform"] == "구글"]
        pd.DataFrame({
            "관광지명": tgt, "플랫폼": "구글", "리뷰ID": g["reviewId"], "작성자닉네임": "demo",
            "평점": g["rating"], "작성일": g["date"] + " 12:00:00", "리뷰본문": g["body"].fillna(""),
        }).to_csv(config.RAW_GOOGLE / f"{tgt}_google_reviews.csv", index=False, encoding="utf-8-sig")
        print(f"  [demo] {src} → {tgt}: 네이버 {len(n)} · 구글 {len(g)}")


# ─────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="시험용 가짜 수집 원본부터 만든다")
    args = ap.parse_args()
    if args.demo:
        make_demo_raw()

    parts, counts = [], []
    for name in config.TARGET_NAMES:
        nv, gg = load_naver(name), load_google(name)
        counts.append((name, len(nv), len(gg)))
        parts += [x for x in (nv, gg) if len(x)]
    for name, a, b in counts:
        print(f"  {name}: 네이버 {a} · 구글 {b}")

    ck = Checks("통합 리뷰 데이터")
    ck("수집 원본 존재", bool(parts), f"{rel(config.RAW_NAVER)} 에 수집 결과가 없습니다" if not parts else "")
    for name, a, b in counts:
        ck(f"{name} 수집 원본", a + b > 0, f"네이버 {a} · 구글 {b}", fatal=False)
        ck(f"{name} 양 플랫폼 수집", a > 0 and b > 0,
           "" if a and b else "한쪽 플랫폼이 비어 있음", fatal=False)

    df = pd.concat(parts, ignore_index=True)
    n0 = len(df)
    df = df.drop_duplicates("orig_id")
    ck("플랫폼 리뷰ID 중복 제거", True, f"{n0} → {len(df)}")

    no_date = df["date"].isna().sum()
    ck("날짜 해석", no_date == 0, f"해석 실패 {no_date}건", fatal=False)
    start = pd.to_datetime(config.DATE_START).date()
    end = pd.to_datetime(config.DATE_END).date() if config.DATE_END else None
    keep = df["date"].notna() & (df["date"] >= start)
    if end:
        keep &= df["date"] <= end
    ck("DATE_END 고정", end is not None,
       "config.DATE_END 가 None — 수집일 전날로 고정해 주세요", fatal=False)
    print(f"  기간 필터 {config.DATE_START} ~ {config.DATE_END or '(상한 없음)'}: "
          f"{len(df)} → {int(keep.sum())}")
    df = df[keep].copy()

    df = assign_ids(df)
    df["date"] = df["date"].map(lambda d: d.isoformat())
    rules = load_mask_rules()
    df["body"] = df["body"].map(lambda t: apply_mask(t, rules))
    print(f"  비식별 치환 규칙 {len(rules)}개 적용 ({rel(config.MASK_RULES)})")
    df = df.sort_values(["place", "platform", "date", "reviewId"])[COLS]

    ck("reviewId 유일", not df["reviewId"].duplicated().any())
    ck("34개소 ID 와 겹치지 않음", df["reviewId"].str[2:].astype(int).min() >= config.REVIEW_ID_START)
    ck("컬럼 구성이 34개소 데이터와 같음",
       list(df.columns) == list(read_csv(config.BASE_DATASET, nrows=1).columns))
    ck("작성자 정보 없음", not any(c in df.columns for c in ("nickname", "작성자닉네임", "작성자ID")))

    write_csv(df, config.DATASET)
    has_body = df["body"].fillna("").str.strip().ne("")
    print(f"\n저장: {rel(config.DATASET)}  {len(df)}행 · 본문 있는 리뷰 {int(has_body.sum())}")
    print(df.groupby(["place", "platform"]).agg(리뷰=("reviewId", "size"),
                                                 본문=("body", lambda s: s.notna().sum()),
                                                 시작=("date", "min"), 끝=("date", "max")).to_string())


if __name__ == "__main__":
    main()
