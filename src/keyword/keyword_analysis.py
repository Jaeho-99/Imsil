# -*- coding: utf-8 -*-
"""키워드 분석 (보고서 2장)

Colab 노트북(docs/archive/임실_리뷰데이터분석_키워드.ipynb)을 같은 순서·같은 값으로 옮긴 스크립트다.
  기본 정제 → Kiwi 형태소 분석(NNG·NNP·VV·VA, 용언은 '-다' 기본형, 관광지명 사용자 사전)
  → 공통·분석 불용어와 1글자 토큰 제거 → 관광지별 불용어 제거
  → Frequency / TF-IDF / Bigram / Trigram Top 20

입력  input/임실군_관광지_리뷰데이터_1차전처리.csv
출력  output/keyword/
        리뷰데이터_키워드전처리완료.csv   리뷰별 토큰 (연관관계 분석과 추가 관광지 분석이 읽는다)
        관광지별_frequency_top20.csv      A·B·C 티어 21개소
        관광지별_tfidf_top20.csv          A·B·C 티어 21개소 (21개 관광지 문서로 IDF 계산)
        관광지별_frequency_tfidf비교.csv  위 두 표의 outer join + 텍스트 리뷰 수·언급 비율
        관광지별_bigram_top20.csv         A·B 티어 8개소
        관광지별_trigram_top20.csv        A 티어 3개소

Kiwi 버전
  형태소 분석 결과는 kiwipiepy 버전에 따라 달라진다. 노트북은 Colab 에서 버전을 고정하지 않고
  실행했고, 지금 확인되는 가장 가까운 버전은 0.23.2 다 (requirements.txt 에 고정).
  다른 버전이면 경고를 내고 계속 실행한다.

실행
    python src/keyword/keyword_analysis.py
    python src/keyword/keyword_analysis.py --out-dir 다른폴더   # 기존 결과를 두고 따로 저장
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import KEYWORD_OUT, REVIEWS_PRE  # noqa: E402

KIWI_VERSION = "0.23.2"

# ─────────────────────────────────────────────────────────────
# 노트북 셀 13 — 관광지 목록 (사용자 사전·관광지명 불용어용)
# ─────────────────────────────────────────────────────────────
PLACES = [
    "도화지 도예문화원", "세심자연휴양림", "임실치즈마을", "임실치즈테마파크",
    "전북119안전체험관", "전북종합사격장", "청소년수련원", "필봉농악전수교육관",
    "국립 임실호국원", "섬진강댐 물문화관", "소충사", "옥정호출렁다리",
    "전주샹그릴라CC", "옥정호", "사선대관광지", "임실역", "오수역",
    "임실시외버스터미널", "국사봉전망대", "관촌역", "붕어섬생태공원", "요산공원",
    "오수공용버스터미널", "관촌시외버스터미널", "임실전통시장", "사선대조각공원",
    "오수의견공원", "성수산왕의숲자연휴양림", "상이암", "옥정호작약꽃밭",
    "섬진강자전거길인증센터", "관촌시장", "강진공용버스터미널", "옥정호전망대",
]

# 노트북 셀 10·15 — 품사와 불용어
TARGET_POS = {"NNG", "NNP", "VV", "VA"}
COMMON_STOPWORDS = {"곳", "장소", "여기", "하다", "되다", "있다", "가다", "오다", "보다",
                    "들다", "주다", "때", "것", "방문"}
ANALYSIS_STOPWORDS = {"좋다", "많다", "같다", "생각", "다녀오다", "나오다", "추천"}
# 노트북 셀 15의 place_stopwords — 34개소 관광지명 자체 (띄어쓰기를 뺀 형태 포함)
PLACE_NAME_STOPWORDS = set(PLACES) | {p.replace(" ", "") for p in PLACES}

# 노트북 셀 19 — 리뷰 수 기준 티어
A_PLACES = ["붕어섬생태공원", "임실치즈테마파크", "옥정호출렁다리"]
B_PLACES = ["전주샹그릴라CC", "사선대관광지", "임실치즈마을", "전북119안전체험관", "임실전통시장"]
C_PLACES = ["섬진강댐 물문화관", "전북종합사격장", "국사봉전망대", "국립 임실호국원", "요산공원",
            "옥정호", "옥정호작약꽃밭", "상이암", "섬진강자전거길인증센터", "관촌시장",
            "필봉농악전수교육관", "오수의견공원", "성수산왕의숲자연휴양림"]
ABC_PLACES = A_PLACES + B_PLACES + C_PLACES
AB_PLACES = A_PLACES + B_PLACES

# 노트북 셀 20 — 관광지별 추가 불용어 (관광지명 자체)
PLACE_SPECIFIC_STOPWORDS = {
    "붕어섬생태공원": {"붕어섬", "임실"},
    "임실치즈테마파크": {"임실", "임실치즈", "테마파크"},
    "옥정호출렁다리": {"옥정호"},
    "전주샹그릴라CC": {"샹그릴라"},
    "사선대관광지": {"사선대", "임실"},
    "임실치즈마을": {"임실", "테마파크"},
    "전북119안전체험관": set(),
    "임실전통시장": {"임실"},
    "섬진강댐 물문화관": {"물문화관", "문화관"},
    "전북종합사격장": set(),
    "국사봉전망대": {"국사봉"},
    "국립 임실호국원": {"국립", "호국"},
    "요산공원": {"임실군"},
    "옥정호": set(),
    "옥정호작약꽃밭": set(),
    "상이암": {"상이암", "임실"},
    "섬진강자전거길인증센터": {"센터"},
    "관촌시장": set(),
    "필봉농악전수교육관": set(),
    "오수의견공원": set(),
    "성수산왕의숲자연휴양림": {"성수산", "자연휴양림", "휴양림"},
}


# ─────────────────────────────────────────────────────────────
# 저장 시점별 불용어 — 노트북은 셀을 고쳐 가며 파일을 따로 저장했다.
# 커밋된 결과와 대조해 각 파일이 어떤 설정으로 저장됐는지 확인한 값이다 (README 「키워드 분석」 참고).
#   Top 20 표 4종  : 공통·분석 불용어 + 관광지명(place_stopwords)
#   리뷰별 토큰 파일: 공통·분석 불용어만 (노트북의 마지막 상태. 연관관계 분석이 이 파일을 읽는다)
#   Frequency 표   : 관광지별 불용어 중 두 곳을 지금 값으로 고치기 전에 저장됐다
# ─────────────────────────────────────────────────────────────
TABLE_STOPWORDS = COMMON_STOPWORDS | ANALYSIS_STOPWORDS | PLACE_NAME_STOPWORDS
TOKEN_FILE_STOPWORDS = COMMON_STOPWORDS | ANALYSIS_STOPWORDS
FREQUENCY_PLACE_STOPWORDS = {
    **PLACE_SPECIFIC_STOPWORDS,
    "붕어섬생태공원": {"붕어섬"},
    "성수산왕의숲자연휴양림": {"성수산", "자연휴양림"},
}


def tier_of(place: str) -> str:
    return "A" if place in A_PLACES else "B" if place in B_PLACES else "C"


# ─────────────────────────────────────────────────────────────
# 1. 기본 정제 (노트북 셀 5)
# ─────────────────────────────────────────────────────────────
def clean_text(text):
    if pd.isna(text):
        return None
    text = str(text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)          # URL
    text = re.sub(r"<[^>]+>", " ", text)                        # HTML 태그
    text = re.sub(r"[\n\r\t]+", " ", text)                      # 줄바꿈·탭
    text = re.sub(r"([!?~.,])\1+", r"\1", text)                 # 반복 문장부호: 좋아요!!!!! → 좋아요!
    text = re.sub(r"[^가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9\s!?.,]", " ", text)  # 한글·영문·숫자·기본 문장부호만
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─────────────────────────────────────────────────────────────
# 2. Kiwi 형태소 분석 (노트북 셀 9·10·14)
# ─────────────────────────────────────────────────────────────
def make_kiwi():
    import kiwipiepy
    from kiwipiepy import Kiwi

    if kiwipiepy.__version__ != KIWI_VERSION:
        print(f"[경고] kiwipiepy {kiwipiepy.__version__} — 노트북 재현 버전은 {KIWI_VERSION} 입니다. "
              f"토큰이 일부 달라질 수 있습니다.  pip install kiwipiepy=={KIWI_VERSION}")
    kiwi = Kiwi()
    for place in PLACES:                       # 관광지명 사용자 사전
        kiwi.add_user_word(place, "NNP")
        kiwi.add_user_word(place.replace(" ", ""), "NNP")
    return kiwi


def tokenize(kiwi, text):
    if pd.isna(text):
        return []
    result = []
    for token in kiwi.tokenize(text):
        base_tag = token.tag.split("-")[0]     # VA-I, VV-R 같은 변형 태그
        if base_tag not in TARGET_POS:
            continue
        result.append(token.form + "다" if base_tag in {"VV", "VA"} else token.form)
    return result


def apply_stopwords(df: pd.DataFrame, stopwords: set[str]) -> None:
    """노트북 셀 16·25 — 불용어·1글자 제거(keyword_tokens) 뒤 관광지별 불용어 제거(keyword_tokens_final)."""
    df["keyword_tokens"] = df["tokens"].apply(
        lambda ts: [t for t in ts if t not in stopwords and len(t) > 1])
    df["keyword_tokens_final"] = df.apply(
        lambda r: [t for t in r["keyword_tokens"]
                   if t not in PLACE_SPECIFIC_STOPWORDS.get(r["place"], set())], axis=1)


# ─────────────────────────────────────────────────────────────
# 3. 분석 (노트북 셀 16~47)
# ─────────────────────────────────────────────────────────────
def frequency_top20(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for place in ABC_PLACES:
        extra = FREQUENCY_PLACE_STOPWORDS.get(place, set())
        tokens = [t for tl in df.loc[df["place"] == place, "keyword_tokens"] for t in tl
                  if t not in extra]
        for rank, (kw, cnt) in enumerate(Counter(tokens).most_common(20), start=1):
            rows.append({"place": place, "tier": tier_of(place), "rank": rank,
                         "keyword": kw, "count": cnt})
    return pd.DataFrame(rows)


def tfidf_top20(df: pd.DataFrame) -> pd.DataFrame:
    from sklearn.feature_extraction.text import TfidfVectorizer

    docs = (df[df["place"].isin(ABC_PLACES)]
            .groupby("place")["keyword_tokens_final"]
            .apply(lambda x: " ".join(t for tl in x for t in tl)))
    vec = TfidfVectorizer()
    mat = vec.fit_transform(docs)
    tf = pd.DataFrame(mat.toarray(), index=docs.index, columns=vec.get_feature_names_out())

    rows = []
    for place in ABC_PLACES:
        if place not in tf.index:
            continue
        top = tf.loc[place].sort_values(ascending=False).head(20)
        for rank, (kw, score) in enumerate(top.items(), start=1):
            rows.append({"place": place, "tier": tier_of(place), "rank": rank,
                         "keyword": kw, "tfidf_score": score})
    return pd.DataFrame(rows)


def compare(df: pd.DataFrame, freq: pd.DataFrame, tfidf: pd.DataFrame) -> pd.DataFrame:
    out = pd.merge(freq.rename(columns={"count": "frequency"}), tfidf,
                   on=["place", "tier", "keyword"], how="outer", suffixes=("_freq", "_tfidf"))
    out = out.rename(columns={"rank_freq": "freq_rank", "rank_tfidf": "tfidf_rank"})
    review_counts = df[df["clean_body"].notna()].groupby("place").size().rename("review_count")
    out = out.merge(review_counts, on="place", how="left")
    out["freq_ratio"] = out["frequency"] / out["review_count"]       # 키워드 언급 비율
    return out


def ngram_top20(df: pd.DataFrame, places: list[str], n: int) -> pd.DataFrame:
    name = {2: "bigram", 3: "trigram"}[n]
    rows = []
    for place in places:
        sub = df[(df["place"] == place) & (df["keyword_tokens_final"].notna())]
        counter = Counter()
        for tokens in sub["keyword_tokens_final"]:          # 리뷰 안에서만 이어 붙인다
            if len(tokens) < n:
                continue
            counter.update(" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1))
        for rank, (gram, cnt) in enumerate(counter.most_common(20), start=1):
            rows.append({"place": place, "tier": tier_of(place), "rank": rank,
                         name: gram, "count": cnt})
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="키워드 분석 (보고서 2장)")
    ap.add_argument("--input", type=Path, default=REVIEWS_PRE)
    ap.add_argument("--out-dir", type=Path, default=KEYWORD_OUT)
    args = ap.parse_args()

    df = pd.read_csv(args.input)                          # 노트북과 같이 기본 dtype 으로 읽는다
    print(f"[1/4] 입력 {len(df):,}행 — {args.input.name}")

    df["clean_body"] = df["body"].apply(clean_text)
    print(f"      본문 있음 {df['clean_body'].notna().sum():,}건")

    print("[2/4] Kiwi 형태소 분석")
    kiwi = make_kiwi()
    df["tokens"] = df["clean_body"].apply(lambda t: tokenize(kiwi, t))
    apply_stopwords(df, TOKEN_FILE_STOPWORDS)              # 리뷰별 토큰 파일용

    print("[3/4] Frequency · TF-IDF · N-gram")
    tbl = df[["place", "clean_body", "tokens"]].copy()     # Top 20 표용 (관광지명까지 제거)
    apply_stopwords(tbl, TABLE_STOPWORDS)
    freq = frequency_top20(tbl)
    tfidf = tfidf_top20(tbl)
    comp = compare(tbl, freq, tfidf)
    bigram = ngram_top20(tbl, AB_PLACES, 2)
    trigram = ngram_top20(tbl, A_PLACES, 3)

    print("[4/4] 저장")
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "리뷰데이터_키워드전처리완료.csv": df,
        "관광지별_frequency_top20.csv": freq,
        "관광지별_tfidf_top20.csv": tfidf,
        "관광지별_frequency_tfidf비교.csv": comp,
        "관광지별_bigram_top20.csv": bigram,
        "관광지별_trigram_top20.csv": trigram,
    }
    for name, d in files.items():
        d.to_csv(out / name, index=False, encoding="utf-8-sig")
        print(f"      {name}  {len(d):,}행")
    print(f"저장 위치: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
