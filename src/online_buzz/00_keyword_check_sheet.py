"""[수집 전] 키워드 사전 검색어별 정확도 확인표.

검색어마다 네이버 검색 API 로 최신 글 20건을 받아 사람이 '맞는 글'인지 표시하는 표를 만들고,
표시가 끝난 표를 요약해 검색어별 '20건 중 맞은 수'를 남긴다(보고서 방법 절에 씀).

레포 최상위에서 실행한다.
  python src/online_buzz/00_keyword_check_sheet.py make                 # 확정 + 후보 + 확인필요 검색어 전부
  python src/online_buzz/00_keyword_check_sheet.py make --only-confirmed
  python src/online_buzz/00_keyword_check_sheet.py summarize input/online_buzz/keyword_check/확인표_20261106_blog.csv

순서
  1. make      → output/online_buzz/keyword_check/확인표_<날짜>_<채널>.csv (빈 확인표)
  2. 사람이 이 파일을 input/online_buzz/keyword_check/ 로 복사해 '맞음' 열을 채운다
     (output/ 에서 바로 고치면 make 를 다시 돌릴 때 덮어써진다)
  3. summarize → output/online_buzz/keyword_check/확인결과_<날짜>_<채널>.csv (검색어별 맞은 수, 보고서용)
                 output/online_buzz/keyword_check/판정_<날짜>_<채널>.csv   (글마다 O/X, 제목·요약·링크 없음)
확인표에는 블로그 링크(작성자 ID 포함)와 제목·요약이 있어 git 에서 제외한다. 커밋하는 것은 3의 두 파일이다.

확인표 열: 층, 주제어, 상태, 검색어, 검색결과수, 순번, 제목, 요약, 작성일, 링크, 자동_거를글(사전의 '거를 글' 표현이 보이면 Y), 맞음
'맞음' 열에 O(임실 관광 관련 글) 또는 X(엉뚱한 글)를 적는다. 빈칸은 미확인으로 센다.
판정 기준: 20건 중 X 가 3건을 넘으면 '좁히기'(검색어를 더 구체적으로 바꾼다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/

import pandas as pd

from online_buzz import keyword_dict as KD
from online_buzz.settings import CHECK_OUT

MAX_BAD = 3
# 판정표(커밋)에 남기는 열 — 제목·요약·링크는 빼고 글 순번으로만 가리킨다
JUDGEMENT_COLUMNS = ["층", "주제어", "상태", "검색어", "검색결과수", "순번", "작성일", "자동_거를글", "맞음"]


def make(a: argparse.Namespace) -> Path:
    from online_buzz.naver import NaverClient, normalize_item

    entries = KD.load(a.dict, include_candidates=not a.only_confirmed)
    cli = NaverClient.from_env()
    rows = []
    for e in entries:
        if e.layer == "전북":
            continue
        ex = re.compile("|".join(map(re.escape, e.exclude))) if e.exclude else None
        for q in e.queries:
            page = cli.search(a.channel, q, display=a.n, start=1, sort="date")
            for i, it in enumerate(page.get("items", []), 1):
                n = normalize_item(a.channel, q, it)
                text = n["title"] + " " + n["description"]
                rows.append({"층": e.layer, "주제어": e.topic, "상태": e.status, "검색어": q, "검색결과수": page.get("total"),
                             "순번": i, "제목": n["title"], "요약": n["description"], "작성일": n["date"], "링크": n["link"],
                             "자동_거를글": "Y" if ex and ex.search(text) else "", "맞음": ""})
    CHECK_OUT.mkdir(parents=True, exist_ok=True)
    out = CHECK_OUT / f"확인표_{dt.date.today():%Y%m%d}_{a.channel}.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")  # 엑셀에서 바로 열리도록 BOM
    print(f"saved -> {out}  ({len(rows)} rows, 사전 {Path(a.dict or KD.default_path()).name})")
    return out


def read_sheet(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")


def judgements(path: Path) -> pd.DataFrame:
    """채운 확인표에서 제목·요약·링크를 뺀 글별 판정표."""
    df = read_sheet(path)
    return df[[c for c in JUDGEMENT_COLUMNS if c in df.columns]]


def summarize(path: Path) -> pd.DataFrame:
    df = read_sheet(path)
    mark = df["맞음"].str.strip().str.upper()
    df["ok"] = mark.isin(["O", "Y", "1", "맞음"])
    df["bad"] = mark.isin(["X", "N", "0", "아님"])
    g = df.groupby(["층", "주제어", "상태", "검색어"], sort=False)
    out = g.agg(확인건수=("순번", "size"), 맞음=("ok", "sum"), 엉뚱함=("bad", "sum")).reset_index()
    out["미표시"] = out["확인건수"] - out["맞음"] - out["엉뚱함"]
    out["판정"] = out.apply(lambda r: "미완료" if r["미표시"] else ("좁히기" if r["엉뚱함"] > MAX_BAD else "사용"), axis=1)
    out["확인표"] = path.name
    return out


def result_name(sheet: Path, kind: str) -> str:
    """확인표_20261106_blog.csv → 확인결과_20261106_blog.csv / 판정_20261106_blog.csv"""
    stem = sheet.stem
    return (stem.replace("확인표", kind, 1) if "확인표" in stem else f"{kind}_{stem}") + ".csv"


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--dict", help="키워드 사전 경로 (기본: input/online_buzz/ 의 최신 버전)")
    m.add_argument("--channel", default="blog", choices=["blog", "cafearticle", "news"])
    m.add_argument("--n", type=int, default=20)
    m.add_argument("--only-confirmed", action="store_true")
    s = sub.add_parser("summarize")
    s.add_argument("file", type=Path, help="'맞음' 열을 채운 확인표 (보통 input/online_buzz/keyword_check/ 에 둔다)")
    a = ap.parse_args()
    if a.cmd == "make":
        make(a)
    else:
        res = summarize(a.file)
        CHECK_OUT.mkdir(parents=True, exist_ok=True)
        out = CHECK_OUT / result_name(a.file, "확인결과")
        res.to_csv(out, index=False, encoding="utf-8-sig")
        jout = CHECK_OUT / result_name(a.file, "판정")
        judgements(a.file).to_csv(jout, index=False, encoding="utf-8-sig")
        print(res.to_string(index=False))
        print("saved ->", out)
        print("saved ->", jout)


if __name__ == "__main__":
    main()
