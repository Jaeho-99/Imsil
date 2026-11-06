"""게시물 텍스트 키워드 분석 (지난 34개 관광지 리뷰 분석과 같은 Kiwi 기반 절차).

정제 → Kiwi 형태소 분석(NNG, NNP, VV, VA; 동사·형용사는 기본형 '~다') → 불용어 제거
→ Frequency / 문서빈도(DF) / TF-IDF(그룹별 문서 통합)
"""
from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from typing import Iterable

import pandas as pd

KEEP_TAGS = {"NNG", "NNP", "VV", "VA", "VV-R", "VA-R", "VV-I", "VA-I", "SL"}

# 블로그·카페 게시물에서 흔하지만 관광 관심 특성을 설명하지 못하는 단어
COMMON_STOPWORDS = {
    # 일반 기능어·서술어
    "있다", "하다", "되다", "보다", "같다", "가다", "오다", "이다", "아니다", "주다", "받다", "들다", "나다",
    "알다", "싶다", "많다", "좋다", "어떻다", "그렇다", "이렇다", "수", "것", "거", "곳", "때", "등", "중", "번", "분",
    "정도", "이번", "오늘", "요즘", "진짜", "정말", "너무", "생각", "느낌", "후기", "포스팅", "블로그", "이웃",
    "사진", "글", "내용", "소개", "정보", "추천", "리뷰", "공유", "카페", "게시판", "댓글",
    # 검색어 자체(모든 문서에 등장 → 변별력 없음)
    "여행", "가볼만한곳", "관광", "국내", "국내여행", "전북", "전라북도", "전북특별자치도",
    "km", "com", "www", "http", "https", "naver",
}
# '없다', '아쉽다', '비싸다' 등 불만을 나타내는 표현은 지난 리뷰 분석과 같은 원칙으로 불용어에서 뺐다.


_URL = re.compile(r"https?://\S+|www\.\S+")
_NONTEXT = re.compile(r"[^0-9A-Za-z가-힣\s]")


def clean_text(t: str) -> str:
    t = _URL.sub(" ", t or "")
    t = _NONTEXT.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


@lru_cache(maxsize=1)
def _kiwi():
    from kiwipiepy import Kiwi

    kiwi = Kiwi()
    # 지역 관광 고유명사가 쪼개지지 않도록 사용자 사전 등록
    for w in [
        "임실치즈테마파크", "치즈테마파크", "임실N치즈축제", "붕어섬", "붕어섬생태공원", "옥정호", "출렁다리",
        "성수산", "상이암", "오수의견", "의견비", "사선대", "국민여가캠핑장", "치즈마을", "옥정호출렁다리",
    ]:
        kiwi.add_user_word(w, "NNP")
    return kiwi


def tokenize(text: str, stopwords: set[str] | None = None) -> list[str]:
    sw = COMMON_STOPWORDS | (stopwords or set())
    toks = []
    for tk in _kiwi().tokenize(clean_text(text)):
        if tk.tag not in KEEP_TAGS:
            continue
        w = tk.form + "다" if tk.tag.startswith(("VV", "VA")) else tk.form
        if tk.tag == "SL":
            w = w.lower()
        if len(w) < 2 or w in sw:
            continue
        toks.append(w)
    return toks


def tokenize_frame(df: pd.DataFrame, text_cols: Iterable[str] = ("title", "description"),
                   stopwords: set[str] | None = None) -> pd.DataFrame:
    d = df.copy()
    d["text"] = d[list(text_cols)].fillna("").agg(" ".join, axis=1)
    d["tokens"] = d["text"].map(lambda t: tokenize(t, stopwords))
    return d


def frequency(token_lists: Iterable[list[str]], top: int = 30) -> pd.DataFrame:
    tf = Counter(w for ts in token_lists for w in ts)
    return pd.DataFrame(tf.most_common(top), columns=["keyword", "freq"])


def doc_frequency(token_lists: list[list[str]], top: int = 30) -> pd.DataFrame:
    """키워드가 등장한 문서 수 / 비율 — 한 게시물의 반복 언급 영향을 줄인 지표."""
    n = len(token_lists)
    df = Counter(w for ts in token_lists for w in set(ts))
    out = pd.DataFrame(df.most_common(top), columns=["keyword", "n_docs"])
    out["doc_ratio(%)"] = (out["n_docs"] / n * 100).round(2) if n else 0
    return out


def tfidf_by_group(d: pd.DataFrame, group_col: str, top: int = 20) -> pd.DataFrame:
    """그룹(예: 시군, 관광지, 연도)별 토큰을 하나의 문서로 합쳐 TF-IDF 계산."""
    docs = d.groupby(group_col)["tokens"].sum()
    n = len(docs)
    df = Counter(w for ts in docs for w in set(ts))
    rows = []
    for g, ts in docs.items():
        tf = Counter(ts)
        total = sum(tf.values()) or 1
        for w, c in tf.items():
            idf = math.log((1 + n) / (1 + df[w])) + 1
            rows.append({group_col: g, "keyword": w, "tf": c, "tfidf": c / total * idf})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values([group_col, "tfidf"], ascending=[True, False]).groupby(group_col).head(top).reset_index(drop=True)
