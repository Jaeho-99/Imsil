# -*- coding: utf-8 -*-
"""[키워드] 키워드 분석 — 34개소 키워드 분석과 같은 방법을 새 2개소에 적용

34개소 노트북(docs/archive/임실_리뷰데이터분석_키워드.ipynb, 스크립트판은 src/keyword/keyword_analysis.py)과
같은 순서·같은 값으로 처리한다.
  기본 정제 → Kiwi 형태소 분석(NNG·NNP·VV·VA, 용언은 '-다' 기본형) → 공통 불용어·1글자 제거
  → 관광지별 불용어 제거 → Frequency / TF-IDF / Bigram / Trigram Top 20

TF-IDF 코퍼스
  관광지 2곳만으로 IDF 를 계산하면 '두 곳 중 한 곳에만 나온 단어'만 높게 나와 의미가 없다.
  그래서 34개소 노트북의 TF-IDF 코퍼스(A·B·C 티어 21개소, output/keyword/리뷰데이터_키워드전처리완료.csv
  의 keyword_tokens_final)에 새 2개소 문서를 더해 23개 문서로 계산한다.
  새 관광지 키워드가 '임실군의 다른 관광지와 비교해 특징적인가'를 보는 값이 된다.

입력  output/new_sites/추가관광지_리뷰데이터_1차전처리.csv (preprocess.py 결과)
출력  output/new_sites/keyword/추가관광지_리뷰데이터_키워드전처리완료.csv  (34개소 같은 이름 파일과 같은 컬럼)
      output/new_sites/keyword/관광지별_{frequency,tfidf,bigram,trigram}_top20.csv
      output/new_sites/keyword/관광지별_frequency_tfidf비교.csv
      output/new_sites/keyword/네이버_키워드리뷰_집계.csv     (네이버 '이런 점이 좋았어요' 태그 빈도)
      output/new_sites/keyword/그림_관광지별_키워드_top15.png

실행
    python src/new_sites/keywords.py
    python src/new_sites/keywords.py --check-base   # 34개소 토큰 재현 여부만 점검
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter

import pandas as pd

from common import Checks, config, read_csv, rel, setup_font, write_csv

# 34개소 노트북을 실행한 Kiwi 버전. 34개소 데이터로 버전별 재현율을 재 보았다 (--check-base):
#   0.23.2 → 99.94% (5,267행 중 3행 다름) · 0.22.2 → 94.0% · 0.24.1 → 86.7% · 0.21.0 → 83.5%
KIWI_VERSION = "0.23.2"

# 34개소 노트북 셀 13의 관광지 목록 (사용자 사전·불용어용)
BASE_PLACES = [
    "도화지 도예문화원", "세심자연휴양림", "임실치즈마을", "임실치즈테마파크", "전북119안전체험관",
    "전북종합사격장", "청소년수련원", "필봉농악전수교육관", "국립 임실호국원", "섬진강댐 물문화관",
    "소충사", "옥정호출렁다리", "전주샹그릴라CC", "옥정호", "사선대관광지", "임실역", "오수역",
    "임실시외버스터미널", "국사봉전망대", "관촌역", "붕어섬생태공원", "요산공원", "오수공용버스터미널",
    "관촌시외버스터미널", "임실전통시장", "사선대조각공원", "오수의견공원", "성수산왕의숲자연휴양림",
    "상이암", "옥정호작약꽃밭", "섬진강자전거길인증센터", "관촌시장", "강진공용버스터미널", "옥정호전망대",
]
# 노트북 셀 19 — TF-IDF 코퍼스로 쓴 A·B·C 티어 21개소
BASE_TFIDF_PLACES = [
    "붕어섬생태공원", "임실치즈테마파크", "옥정호출렁다리",
    "전주샹그릴라CC", "사선대관광지", "임실치즈마을", "전북119안전체험관", "임실전통시장",
    "섬진강댐 물문화관", "전북종합사격장", "국사봉전망대", "국립 임실호국원", "요산공원", "옥정호",
    "옥정호작약꽃밭", "상이암", "섬진강자전거길인증센터", "관촌시장", "필봉농악전수교육관",
    "오수의견공원", "성수산왕의숲자연휴양림",
]


# ─────────────────────────────────────────────────────────────
# 노트북 셀 5 — 기본 정제
# ─────────────────────────────────────────────────────────────
def clean_text(text):
    if pd.isna(text):
        return None
    text = str(text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[\n\r\t]+", " ", text)
    text = re.sub(r"([!?~.,])\1+", r"\1", text)
    text = re.sub(r"[^가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9\s!?.,]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─────────────────────────────────────────────────────────────
# 노트북 셀 9~16 — Kiwi 토큰화와 불용어
# ─────────────────────────────────────────────────────────────
def make_tokenizer():
    from kiwipiepy import Kiwi
    kiwi = Kiwi()
    for place in BASE_PLACES + config.TARGET_NAMES:
        kiwi.add_user_word(place, "NNP")
        kiwi.add_user_word(place.replace(" ", ""), "NNP")

    def tokenize(text):
        if text is None or pd.isna(text):
            return []
        out = []
        for tok in kiwi.tokenize(text):
            base = tok.tag.split("-")[0]
            if base not in config.TARGET_POS:
                continue
            out.append(tok.form + "다" if base in {"VV", "VA"} else tok.form)
        return out

    return tokenize


STOPWORDS = config.COMMON_STOPWORDS | config.ANALYSIS_STOPWORDS
PLACE_STOP = {t["name"]: set(t["place_stopwords"]) for t in config.TARGETS}


def remove_stopwords(tokens):
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def add_tokens(df: pd.DataFrame) -> pd.DataFrame:
    tokenize = make_tokenizer()
    df = df.copy()
    df["clean_body"] = df["body"].apply(clean_text)
    df["tokens"] = df["clean_body"].apply(tokenize)
    df["keyword_tokens"] = df["tokens"].apply(remove_stopwords)
    df["keyword_tokens_final"] = [
        [t for t in toks if t not in PLACE_STOP.get(pl, set())]
        for toks, pl in zip(df["keyword_tokens"], df["place"])]
    return df


# ─────────────────────────────────────────────────────────────
# 집계
# ─────────────────────────────────────────────────────────────
def top_counts(df, place, n=20, gram=1):
    c = Counter()
    for toks in df.loc[df["place"] == place, "keyword_tokens_final"]:
        if gram == 1:
            c.update(toks)
        elif len(toks) >= gram:
            c.update(" ".join(toks[i:i + gram]) for i in range(len(toks) - gram + 1))
    return c.most_common(n)


def tfidf_table(df_new: pd.DataFrame) -> pd.DataFrame:
    from sklearn.feature_extraction.text import TfidfVectorizer
    base = read_csv(config.BASE_KEYWORD_DATA, usecols=["place", "keyword_tokens_final"])
    base = base[base["place"].isin(BASE_TFIDF_PLACES)].copy()
    base["keyword_tokens_final"] = base["keyword_tokens_final"].map(ast.literal_eval)
    both = pd.concat([base, df_new[["place", "keyword_tokens_final"]]], ignore_index=True)
    docs = both.groupby("place")["keyword_tokens_final"].apply(
        lambda x: " ".join(t for toks in x for t in toks))
    vec = TfidfVectorizer()
    m = vec.fit_transform(docs)
    tf = pd.DataFrame(m.toarray(), index=docs.index, columns=vec.get_feature_names_out())
    rows = []
    for place in config.TARGET_NAMES:
        if place not in tf.index:
            continue
        for rank, (kw, sc) in enumerate(tf.loc[place].sort_values(ascending=False).head(20).items(), 1):
            if sc > 0:
                rows.append({"place": place, "rank": rank, "keyword": kw, "tfidf_score": sc})
    return pd.DataFrame(rows), len(docs)


def naver_tags(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for place, g in df[df["platform"] == "네이버"].groupby("place"):
        c = Counter(t for s in g["tags"] for t in json.loads(s or "[]"))
        n = len(g)
        for rank, (tag, cnt) in enumerate(c.most_common(), 1):
            rows.append({"place": place, "rank": rank, "tag": tag, "count": cnt,
                         "리뷰수": n, "언급비율": cnt / n})
    return pd.DataFrame(rows)


def plot_top(freq: pd.DataFrame, path):
    plt = setup_font()
    places = [p for p in config.TARGET_NAMES if p in set(freq["place"])]
    fig, axes = plt.subplots(1, len(places), figsize=(6.5 * len(places), 6), squeeze=False)
    for ax, place in zip(axes[0], places):
        d = freq[freq["place"] == place].sort_values("rank").head(15).iloc[::-1]
        ax.barh(d["keyword"], d["frequency"], color="#2a78d6")
        ax.set_title(f"{place} 주요 키워드 (빈도 상위 15)")
        ax.set_xlabel("출현 빈도")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def check_base():
    """34개소 데이터에 이 스크립트의 토큰화를 돌려 노트북 결과(keyword_tokens)와 얼마나 같은지 본다.
    Kiwi 버전이 다르면 일부 토큰이 달라질 수 있다."""
    import kiwipiepy
    base = read_csv(config.BASE_KEYWORD_DATA)
    tokenize = make_tokenizer()
    got = base["body"].apply(clean_text).apply(tokenize).apply(remove_stopwords)
    want = base["keyword_tokens"].map(ast.literal_eval)
    same = (got == want)
    print(f"Kiwi {kiwipiepy.__version__}: 34개소 {len(base)}행 중 토큰 일치 {same.mean():.2%} "
          f"({(~same).sum()}행 다름)")
    return same.mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-base", action="store_true")
    args = ap.parse_args()
    if args.check_base:
        check_base()
        return

    import kiwipiepy
    ck = Checks("키워드 분석")
    ck("Kiwi 버전 = 34개소와 같은 0.23.2", kiwipiepy.__version__ == KIWI_VERSION,
       f"설치 {kiwipiepy.__version__} — 다르면 토큰이 달라짐 (0.24.1 기준 34개소 토큰 13% 불일치)",
       fatal=False)
    ck("1차 전처리 데이터 존재", config.PREPROCESSED.exists(), rel(config.PREPROCESSED))
    ck("34개소 키워드 데이터 존재 (TF-IDF 코퍼스)", config.BASE_KEYWORD_DATA.exists())
    df = read_csv(config.PREPROCESSED, dtype={"reviewId": str})
    df = add_tokens(df)
    ck("Kiwi 형태소 분석", True, f"kiwipiepy {kiwipiepy.__version__}")
    write_csv(df, config.KEYWORD_DATA)

    out = config.OUT_KEYWORD
    out.mkdir(parents=True, exist_ok=True)
    freq = pd.DataFrame([{"place": p, "rank": r, "keyword": k, "frequency": c}
                         for p in config.TARGET_NAMES
                         for r, (k, c) in enumerate(top_counts(df, p), 1)])
    tfidf, n_docs = tfidf_table(df)
    ck("TF-IDF 코퍼스", n_docs == len(BASE_TFIDF_PLACES) + df["place"].nunique(),
       f"문서 {n_docs}개 (34개소 {len(BASE_TFIDF_PLACES)} + 신규 {df['place'].nunique()})")
    bi = pd.DataFrame([{"place": p, "rank": r, "bigram": k, "count": c}
                       for p in config.TARGET_NAMES for r, (k, c) in enumerate(top_counts(df, p, gram=2), 1)])
    tri = pd.DataFrame([{"place": p, "rank": r, "trigram": k, "count": c}
                        for p in config.TARGET_NAMES for r, (k, c) in enumerate(top_counts(df, p, gram=3), 1)])

    # 노트북 셀 31~32 — Frequency·TF-IDF 비교표
    comp = pd.merge(freq.rename(columns={"rank": "freq_rank"}),
                    tfidf.rename(columns={"rank": "tfidf_rank"}),
                    on=["place", "keyword"], how="outer")
    rc = df[df["clean_body"].notna()].groupby("place").size().rename("review_count")
    comp = comp.merge(rc, on="place", how="left")
    comp["freq_ratio"] = comp["frequency"] / comp["review_count"]
    comp = comp.sort_values(["place", "freq_rank", "tfidf_rank"], na_position="last")

    for name, d in [("frequency", freq), ("tfidf", tfidf), ("bigram", bi), ("trigram", tri)]:
        write_csv(d, out / f"관광지별_{name}_top20.csv")
    write_csv(comp, out / "관광지별_frequency_tfidf비교.csv")
    tags = naver_tags(df)
    write_csv(tags, out / "네이버_키워드리뷰_집계.csv")
    if len(freq):
        plot_top(freq, out / "그림_관광지별_키워드_top15.png")

    for p in config.TARGET_NAMES:
        n_rev = int(rc.get(p, 0))
        ck(f"{p} 텍스트 리뷰 수", n_rev >= 30, f"{n_rev}건" + ("" if n_rev >= 30 else
           " — 30건 미만이면 순위가 소수 리뷰에 좌우됨 (보고서에 명시)"), fatal=False)
        f10 = ", ".join(freq[freq.place == p].head(10)["keyword"])
        t10 = ", ".join(tfidf[tfidf.place == p].head(10)["keyword"])
        print(f"\n  [{p}] 빈도 상위: {f10}\n  [{p}] TF-IDF 상위: {t10}")
    print(f"\n저장: {rel(config.KEYWORD_DATA)}\n      {rel(out)}/")


if __name__ == "__main__":
    main()
