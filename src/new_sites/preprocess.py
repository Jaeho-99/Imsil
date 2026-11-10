# -*- coding: utf-8 -*-
"""[전처리] 1차 전처리 — 34개소 `input/임실군_관광지_리뷰데이터_1차전처리.csv` 와 같은 규칙

34개소 원본과 1차전처리본을 reviewId 로 대조해 확인한 규칙을 코드로 옮겼다.
(34개소 때는 이 단계 코드가 레포에 남아 있지 않다. 5,267건 중 본문이 바뀐 464건을 보고 역산했다.)

  1. 외국어 리뷰는 한국어로 번역한다 (34개소: 123건)
  2. 이모지, 이모티콘(^^), 자모만으로 된 웃음·울음 표현(ㅎㅎ ㅋㅋ ㅠㅠ ㅜㅜ ㅡ)을 지운다
  3. 한자·가나(번역 뒤 남은 병기)를 지운다
  4. 지운 뒤 글자(한글·영문)가 하나도 없으면 본문 없음(NaN)으로 둔다 (34개소: 63건)
  5. 날짜는 '2022.6.14' 형식으로 쓴다
  그 밖의 문장부호(~ ! ? . >< 등)와 줄바꿈은 그대로 둔다. 키워드 분석용 정제는 keywords.py 에서 따로 한다.

번역 (API 를 쓰지 않는다)
  아직 번역이 없는 외국어 리뷰를 output/new_sites/번역대상.csv 로 내보내고, 그 리뷰는 원문 그대로 둔다.
  Claude Code 가 input/new_sites/claude_지시문/번역.md 대로 번역해 input/new_sites/번역결과.csv
  (열: reviewId, 원문, 번역, 방법) 로 저장한 뒤 다시 실행하면 번역문을 쓴다.
  2026-11 수집분(성수산·오수의견국민여가캠핑장 네이버 리뷰)에는 외국어 리뷰가 없다.

입력  output/new_sites/추가관광지_리뷰데이터_요인기간.csv (build_dataset.py 결과, FACTOR_DATE_END 까지)
      input/new_sites/번역결과.csv (있을 때만)
출력  output/new_sites/추가관광지_리뷰데이터_1차전처리_요인기간.csv   요인 판정용 (FACTOR_DATE_END 까지)
      output/new_sites/추가관광지_리뷰데이터_1차전처리.csv           그 가운데 DATE_END 까지 (나머지 분석용)
      (전처리는 행마다 따로 하므로 DATE_END 까지의 행은 두 파일이 같다)
      output/new_sites/번역대상.csv (번역이 빠진 외국어 리뷰가 있을 때만)

실행
    python src/new_sites/preprocess.py
"""
from __future__ import annotations

import argparse
import re

import pandas as pd

from common import Checks, config, name_candidates, read_csv, rel, write_csv

EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002300-\U000023FF"
    "\U00002B00-\U00002BFF\U0000FE00-\U0000FE0F\U0000200D\U000020E3\U00003030\U0000303D"
    "\U00003297\U00003299\U0000203C\U00002049]+")
EMOTICON = re.compile(r"\^\^+|\^_\^|\^-\^")   # ":)" 는 34개소에서도 남겼다
JAMO = re.compile(r"[\u3131-\u318E]+")   # 호환 자모 전체 (ㅎㅎ ㅠㅠ ㅡ ㆍ 등)
CJK = re.compile(r"[\u3040-\u30FF\u3400-\u9FFF\uF900-\uFAFF\u200B]+")   # 한자·가나·폭 없는 공백
CONTENT = re.compile(r"[A-Za-z가-힣]")   # 숫자만 남은 본문("1")도 34개소에서 본문 없음으로 처리
LETTER = re.compile(r"[A-Za-zÀ-ɏЀ-ӿ฀-๿぀-ヿ一-鿿가-힣]")


def is_foreign(text) -> bool:
    """글자 가운데 한글이 30% 미만이면 외국어 리뷰로 본다."""
    if not isinstance(text, str):
        return False
    letters = LETTER.findall(text)
    if len(letters) < 3:
        return False
    return sum("가" <= c <= "힣" for c in letters) / len(letters) < 0.3


def clean(text):
    if not isinstance(text, str):
        return pd.NA
    # 34개소 1차전처리본은 지운 자리에 공백을 남겼다 ("좋아요^^!" → "좋아요 !")
    t = EMOJI.sub(" ", text)
    t = EMOTICON.sub(" ", t)
    t = JAMO.sub(" ", t)
    t = CJK.sub("", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = "\n".join(line.strip() for line in t.split("\n")).strip()
    return t if CONTENT.search(t) else pd.NA


def main():
    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args()

    ck = Checks("1차 전처리")
    src = config.DATASET_FACTOR if config.DATASET_FACTOR.exists() else config.DATASET
    ck("통합 데이터 존재", src.exists(), rel(src))
    df = read_csv(src, dtype={"reviewId": str})
    n = len(df)

    # 1. 번역 — Claude Code 가 만든 input/new_sites/번역결과.csv 를 읽는다
    foreign = df[df["body"].map(is_foreign)][["reviewId", "body"]]
    done = read_csv(config.TRANSLATE_DONE, dtype=str).fillna("") if config.TRANSLATE_DONE.exists() else \
        pd.DataFrame(columns=["reviewId", "원문", "번역", "방법"])
    if len(done):
        ck("번역결과 열 구성", {"reviewId", "원문", "번역"} <= set(done.columns),
           f"{rel(config.TRANSLATE_DONE)} 에 reviewId·원문·번역 열이 있어야 합니다")
        done = done[done["번역"].str.strip() != ""]
        body = dict(zip(foreign["reviewId"], foreign["body"]))
        stale = [r for r, o in zip(done["reviewId"], done["원문"]) if r in body and o.strip() != str(body[r]).strip()]
        ck("번역결과의 원문이 지금 본문과 같음", not stale,
           f"원문이 바뀐 리뷰 {len(stale)}건 {stale[:5]} — 그 행을 지우고 다시 번역하세요" if stale else
           f"{len(done)}건", fatal=False)
        done = done[~done["reviewId"].isin(stale)]
    todo = foreign[~foreign["reviewId"].isin(done["reviewId"])]
    if len(todo):
        write_csv(todo.rename(columns={"body": "원문"}), config.TRANSLATE_TODO)
    elif config.TRANSLATE_TODO.exists():
        config.TRANSLATE_TODO.unlink()
    ck("외국어 리뷰 번역", len(todo) == 0,
       f"대상 {len(foreign)} · 완료 {len(foreign) - len(todo)} · 미번역 {len(todo)}"
       + (f" → {rel(config.TRANSLATE_TODO)} 를 Claude Code 로 번역해 {rel(config.TRANSLATE_DONE)} 에 "
          "저장한 뒤 다시 실행 (input/new_sites/claude_지시문/번역.md)" if len(todo) else ""),
       fatal=False)
    tr = dict(zip(done["reviewId"], done["번역"]))
    df["body"] = [tr.get(rid, b) for rid, b in zip(df["reviewId"], df["body"])]

    # 2~3. 이모지·자모 제거
    before = df["body"].notna().sum()
    changed = df["body"].fillna("") != df["body"].map(clean).fillna("")
    df["body"] = df["body"].map(clean)
    after = df["body"].notna().sum()
    ck("이모지·자모 정리", True, f"본문 변경 {int(changed.sum())}건 · 본문 없음으로 전환 {before - after}건")

    # 4. 날짜 형식
    d = pd.to_datetime(df["date"])
    df["date"] = [f"{x.year}.{x.month}.{x.day}" for x in d]

    ck("행 수 보존", len(df) == n, f"{n} → {len(df)}")
    ck("reviewId 유일", not df["reviewId"].duplicated().any())

    cand = name_candidates(df)
    ck("본문 속 실명 후보 점검", True,
       f"후보 {len(cand)}건" + (f" — 아래 목록을 보고 실명이면 {rel(config.MASK_RULES)} 에 추가 후 "
                               "build_dataset.py 부터 다시 실행" if cand else ""))
    for c in cand[:30]:
        print(f"      {c['reviewId']} '{c['후보']}' … {c['문맥']}")

    write_csv(df, config.PREPROCESSED_FACTOR)
    print(f"\n저장: {rel(config.PREPROCESSED_FACTOR)}  {len(df)}행 · 본문 있는 리뷰 {after}  (요인 판정용)")
    if config.DATE_END:
        keep = d.dt.date <= pd.to_datetime(config.DATE_END).date()
        df = df[keep.values]
    write_csv(df, config.PREPROCESSED)
    print(f"저장: {rel(config.PREPROCESSED)}  {len(df)}행 · 본문 있는 리뷰 {int(df['body'].notna().sum())}  "
          f"(분석 기간 ~ {config.DATE_END})")


if __name__ == "__main__":
    main()
