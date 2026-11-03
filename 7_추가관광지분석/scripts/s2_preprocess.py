# -*- coding: utf-8 -*-
"""[2단계] 1차 전처리 — 34개소 `임실군_관광지_리뷰데이터_1차전처리.csv` 와 같은 규칙

34개소 원본과 1차전처리본을 reviewId 로 대조해 확인한 규칙을 코드로 옮겼다.
(34개소 때는 이 단계 코드가 레포에 남아 있지 않다. 5,267건 중 본문이 바뀐 464건을 보고 역산했다.)

  1. 외국어 리뷰는 한국어로 번역한다 (34개소: 123건)
  2. 이모지, 이모티콘(^^), 자모만으로 된 웃음·울음 표현(ㅎㅎ ㅋㅋ ㅠㅠ ㅜㅜ ㅡ)을 지운다
  3. 한자·가나(번역 뒤 남은 병기)를 지운다
  4. 지운 뒤 글자(한글·영문)가 하나도 없으면 본문 없음(NaN)으로 둔다 (34개소: 63건)
  5. 날짜는 '2022.6.14' 형식으로 쓴다
  그 밖의 문장부호(~ ! ? . >< 등)와 줄바꿈은 그대로 둔다. 키워드 분석용 정제는 3단계에서 따로 한다.

번역
  --translate 를 주면 API 로 번역하고 data/번역결과.csv 에 원문·번역문을 남긴다.
  옵션 없이 돌리면 번역 대상만 data/번역대상.csv 로 내보내고 원문을 그대로 둔다.
  사람이 번역결과.csv 를 직접 채우거나 고쳐도 되며, 이미 있는 번역은 다시 요청하지 않는다.

실행
    python scripts/s2_preprocess.py --translate
"""
from __future__ import annotations

import argparse
import re

import pandas as pd

from common import Checks, anthropic_client, config, name_candidates, read_csv, rel, write_csv

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


TRANSLATE_PROMPT = """다음은 한국 관광지에 대한 외국어 리뷰다. 한국어로 자연스럽게 번역하라.
- 뜻을 더하거나 빼지 말고, 평가의 강도와 말투를 살린다.
- 고유명사(지명·인명)는 한국어 표기로 옮긴다.
- 줄바꿈은 원문대로 유지한다.
- 번역문만 출력한다. 설명·따옴표·머리말을 붙이지 않는다."""


def translate(todo: pd.DataFrame) -> pd.DataFrame:
    client = anthropic_client()
    out = []
    for i, r in enumerate(todo.itertuples(), 1):
        resp = client.messages.create(
            model=config.SENT_MODEL, max_tokens=4000,
            system=TRANSLATE_PROMPT,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": r.body}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        out.append({"reviewId": r.reviewId, "원문": r.body, "번역": text,
                    "방법": f"API {config.SENT_MODEL}"})
        print(f"  번역 {i}/{len(todo)} {r.reviewId}")
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--translate", action="store_true", help="외국어 리뷰를 API 로 번역")
    args = ap.parse_args()

    ck = Checks("1차 전처리")
    ck("통합 데이터 존재", config.DATASET.exists(), rel(config.DATASET))
    df = read_csv(config.DATASET, dtype={"reviewId": str})
    n = len(df)

    # 1. 번역
    foreign = df[df["body"].map(is_foreign)][["reviewId", "body"]]
    done = read_csv(config.TRANSLATE_DONE, dtype=str) if config.TRANSLATE_DONE.exists() else \
        pd.DataFrame(columns=["reviewId", "원문", "번역", "방법"])
    todo = foreign[~foreign["reviewId"].isin(done["reviewId"])]
    if len(todo) and args.translate:
        done = pd.concat([done, translate(todo)], ignore_index=True)
        write_csv(done, config.TRANSLATE_DONE)
        todo = todo.iloc[0:0]
    if len(todo):
        write_csv(todo, config.TRANSLATE_TODO)
    ck("외국어 리뷰 번역", len(todo) == 0,
       f"대상 {len(foreign)} · 완료 {len(foreign) - len(todo)} · 미번역 {len(todo)}"
       + (f" → {rel(config.TRANSLATE_TODO)} (--translate 로 번역)" if len(todo) else ""),
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
       f"후보 {len(cand)}건" + (" — 아래 목록을 보고 실명이면 data/비식별_치환목록.csv 에 추가 후 "
                               "s1부터 다시 실행" if cand else ""))
    for c in cand[:30]:
        print(f"      {c['reviewId']} '{c['후보']}' … {c['문맥']}")

    write_csv(df, config.PREPROCESSED)
    print(f"\n저장: {rel(config.PREPROCESSED)}  {len(df)}행 · 본문 있는 리뷰 {after}")


if __name__ == "__main__":
    main()
