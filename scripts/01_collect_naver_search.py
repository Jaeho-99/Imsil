"""[수집 1] 네이버 검색 API: 블로그·카페·뉴스 언급량과 게시물 표본.

생성 파일 (data/raw/online_buzz/<수집일>/)
  naver_totals.csv          14개 시군 × 검색어 템플릿 × 채널의 total(누적 검색결과 수)      → 지표 A
  naver_region_posts.jsonl  시군별 최신순 게시물(블로그·뉴스, 질의당 최대 1,099건)           → 지표 B
  naver_jeonbuk_posts.jsonl '전북 여행' 류 게시물 표본(블로그·카페·뉴스, 정확도순+최신순)     → 지표 C
  naver_imsil_posts.jsonl   임실 관광 관련 게시물(키워드·연관관계 분석용)
  meta.json                 수집 시각·조건

호출 수 약 1,900회(일 25,000회 한도 이내). 실행: python scripts/01_collect_naver_search.py [--only totals,region,jeonbuk,imsil]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
from tqdm import tqdm

from imsil_buzz import settings as S
from imsil_buzz.naver import NaverClient
from imsil_buzz.snapshot import new_snapshot
from imsil_buzz.utils import write_jsonl


def region_queries():
    yield from S.REGION_QUERIES  # (시군, 검색어) — 키워드 사전 '쓰는 곳=언급비중'


def collect_totals(cli: NaverClient, out: Path) -> None:
    rows = []
    for region, q in tqdm(list(region_queries()), desc="totals"):
        for ch in S.NAVER_SEARCH_CHANNELS:
            rows.append({"region": region, "query": q, "channel": ch, "total": cli.search_total(ch, q)})
    pd.DataFrame(rows).to_csv(out / "naver_totals.csv", index=False, encoding="utf-8-sig")


def collect_region_posts(cli: NaverClient, out: Path) -> None:
    def gen():
        for region, q in tqdm(list(region_queries()), desc="region posts"):
            for ch in ("blog", "news"):  # 카페는 작성일이 없어 게시 속도 계산 불가
                for it in cli.iter_search(ch, q, sort="date"):
                    yield {**it, "region": region}
    write_jsonl(out / "naver_region_posts.jsonl", gen())


def collect_jeonbuk_posts(cli: NaverClient, out: Path) -> None:
    def gen():
        for q in tqdm(S.JEONBUK_TOURISM_QUERIES, desc="jeonbuk posts"):
            for ch in S.NAVER_SEARCH_CHANNELS:
                for sort in ("sim", "date"):
                    for it in cli.iter_search(ch, q, sort=sort):
                        yield {**it, "sort": sort}
    write_jsonl(out / "naver_jeonbuk_posts.jsonl", gen())


def collect_imsil_posts(cli: NaverClient, out: Path) -> None:
    def gen():
        for topic, q in tqdm(S.IMSIL_POST_QUERIES, desc="imsil posts"):
            for ch in S.NAVER_SEARCH_CHANNELS:
                for it in cli.iter_search(ch, q, sort="sim"):
                    yield {**it, "topic": topic}
    write_jsonl(out / "naver_imsil_posts.jsonl", gen())


STEPS = {"totals": collect_totals, "region": collect_region_posts, "jeonbuk": collect_jeonbuk_posts, "imsil": collect_imsil_posts}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=",".join(STEPS), help="쉼표로 구분: " + ",".join(STEPS))
    ap.add_argument("--snapshot", help="저장 폴더명(YYYYMMDD). 기본: 오늘")
    a = ap.parse_args()
    cli = NaverClient.from_env()
    out = new_snapshot(a.snapshot)
    for name in a.only.split(","):
        STEPS[name.strip()](cli, out)
    meta_p = out / "meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    meta["naver_search"] = {"collected_at": dt.datetime.now().isoformat(timespec="seconds"), "backend": cli.backend,
                            "steps": a.only.split(","), "channels": S.NAVER_SEARCH_CHANNELS,
                            "keyword_dict": S.KEYWORD_DICT_FILE.name}
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved ->", out)


if __name__ == "__main__":
    main()
