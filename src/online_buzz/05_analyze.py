"""[분석] 원본 → 최종 분석 데이터셋·표 (output/online_buzz/<수집일 또는 manual_YYYYMMDD>/).

있는 원본만 분석하고 없는 단계는 건너뛴다.
실행(레포 최상위에서): python src/online_buzz/05_analyze.py [--snapshot YYYYMMDD]

읽는 곳
  output/online_buzz/raw/<수집일>/   검색 API 원본 (01_collect_naver_search.py, 선택 단계 02~04)
  input/online_buzz/                 웹에서 내려받은 파일 (형식은 input/online_buzz/README.md)

웹 다운로드 파일의 결과는 M_ 로 시작한다.
  M_datalab_long.csv, M_datalab_index_anchor-<그룹>.csv, M_datalab_yearly/seasonality/peaks_*.csv   데이터랩
  M_google_interest_over_time.csv, M_google_related_queries.csv                                   Google Trends
  M_searchad_keywords_long.csv, M_search_keywords_top.csv, M_search_keywords_network.csv         검색광고 키워드도구

검색 API 원본의 결과. 결과표에는 블로그 링크·작성자 정보를 남기지 않고 게시물은 가명 post_id 로만 가리킨다.
  A_mention_totals.csv          시군별 누적 언급량·비중(지표 A)
  B_posting_rate.csv            시군별 최근 게시 속도(지표 B)
  C_jeonbuk_mention_share.csv   전북 관광 게시물 내 시군 언급 비중(지표 C), C_imsil_co_regions.csv
  T_regions_index.csv           14개 시군 검색지수(임실 평균=100), T_regions_yearly.csv, T_regions_seasonality.csv
  T_imsil_groups_index.csv      임실 관광지·축제 검색지수, T_imsil_peaks.csv, T_imsil_seasonality.csv
  T_imsil_segments.csv          기기·성별·연령대별 추이
  T_estimated_searches.csv      검색광고 절대량으로 환산한 추정 월간 검색수
  K_search_keywords.csv         임실 관광 연관검색어(검색광고 API, 선택) + 교차 관심어
  imsil_posts_tokens.jsonl      임실 관련 게시물의 토큰 (post_id, topic, channel, query, date, tokens)
  K_post_frequency.csv / K_post_docfreq.csv / K_post_tfidf_by_year.csv   게시물 키워드
  R_rules.csv / R_edges.csv / R_centrality.csv   키워드 연관규칙·네트워크
  G_*.csv                       Google Trends 정리본 (pytrends, 선택)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/

import pandas as pd

from online_buzz import settings as S
from online_buzz.analysis import association as AS
from online_buzz.analysis import keywords as KW
from online_buzz.analysis import mentions as M
from online_buzz.analysis import trends as T
from online_buzz import manual as MN
from online_buzz.google_trends import load_manual_csv
from online_buzz.snapshot import latest_snapshot
from online_buzz.settings import RAW_DIR, PROCESSED_DIR, MANUAL_DIR
from online_buzz.utils import drop_private, read_jsonl


def save(df: pd.DataFrame, out: Path, name: str, index: bool = False) -> None:
    df.to_csv(out / name, index=index, encoding="utf-8-sig")
    print(f"  {name:38s} {len(df):>6} rows")


def with_post_id(posts: pd.DataFrame) -> pd.DataFrame:
    """링크 중복을 지우고 수집 순서대로 가명 ID(P000001…)를 붙인다. 같은 원본이면 늘 같은 ID 가 나온다."""
    d = posts.drop_duplicates("link").reset_index(drop=True)
    return d.assign(post_id=[f"P{i:06d}" for i in range(1, len(d) + 1)])


def analyze_posts(posts: pd.DataFrame, out: Path, prefix: str = "") -> None:
    """임실 관련 게시물 키워드 빈도·TF-IDF·연관규칙·네트워크."""
    posts = M.filter_topic_posts(with_post_id(posts), S.TOPIC_EXCLUDES, S.IMSIL_TERMS)
    if posts.empty:
        print("  (임실 관련 게시물 없음 → 키워드 분석 생략)")
        return
    tok = KW.tokenize_frame(posts, stopwords={"임실", "임실군"})
    keep = [c for c in ("post_id", "topic", "channel", "query", "date", "tokens") if c in tok.columns]
    drop_private(tok[keep]).to_json(out / f"{prefix}imsil_posts_tokens.jsonl", orient="records", lines=True,
                                    force_ascii=False)
    save(KW.frequency(tok["tokens"], 50), out, f"{prefix}K_post_frequency.csv")
    save(KW.doc_frequency(tok["tokens"].tolist(), 50), out, f"{prefix}K_post_docfreq.csv")
    save(pd.concat({ch: KW.doc_frequency(g["tokens"].tolist(), 30) for ch, g in tok.groupby("channel")}),
         out, f"{prefix}K_post_docfreq_by_channel.csv", index=True)
    dated = tok.dropna(subset=["date"]).assign(year=lambda x: x["date"].astype(str).str[:4])
    if not dated.empty:
        save(KW.tfidf_by_group(dated, "year"), out, f"{prefix}K_post_tfidf_by_year.csv")
    save(AS.pair_rules(tok["tokens"].tolist()), out, f"{prefix}R_rules.csv")
    edges = AS.cooccurrence_edges(tok["tokens"].tolist())
    save(edges, out, f"{prefix}R_edges.csv")
    save(AS.centrality(edges), out, f"{prefix}R_centrality.csv")


def analyze_manual(out: Path) -> None:
    """input/online_buzz/ 의 웹 다운로드 파일 분석. 결과 파일명은 M_ 로 시작한다."""
    # 네이버 데이터랩
    dl = [MN.load_datalab_export(f).assign(request_id=f.name) for f in MN.datalab_files(MANUAL_DIR / "naver_datalab")]
    if dl:
        long = pd.concat(dl, ignore_index=True)
        save(long, out, "M_datalab_long.csv")
        # 파일명에 anchor=그룹명 이 있는 파일끼리는 같은 척도로 맞춘다
        for anchor in sorted({MN.anchor_from_filename(f) for f in long["request_id"].unique()} - {None}):
            sub = long[long["request_id"].map(MN.anchor_from_filename) == anchor]
            rel = T.chain_by_anchor(sub, anchor)
            tag = anchor.replace(" ", "")
            save(rel, out, f"M_datalab_index_anchor-{tag}.csv")
            if rel["period"].dt.day.eq(1).all():  # 월 단위일 때만 연도·계절성
                save(T.yearly_summary(rel), out, f"M_datalab_yearly_anchor-{tag}.csv", index=True)
                save(T.seasonality(rel), out, f"M_datalab_seasonality_anchor-{tag}.csv", index=True)
            save(T.peak_months(rel), out, f"M_datalab_peaks_anchor-{tag}.csv")
    # 검색광고 키워드도구
    sa = [MN.load_searchad_export(f) for f in MN.datalab_files(MANUAL_DIR / "naver_searchad")]
    if sa:
        sa = pd.concat(sa, ignore_index=True)
        save(sa, out, "M_searchad_keywords_long.csv")
        save(sa.drop_duplicates("keyword").sort_values("monthly_total", ascending=False), out, "M_search_keywords_top.csv")
        if (sa["seed"] != "").any():
            exploded = sa.assign(seed=sa["seed"].str.split(",")).explode("seed")
            save(AS.search_keyword_network(exploded[exploded["seed"] != ""]), out, "M_search_keywords_network.csv")

    # Google Trends
    gdir = MANUAL_DIR / "google_trends"
    timeline = [f for f in sorted(gdir.glob("*.csv")) if "related" not in f.name.lower() and "관련" not in f.name]
    related = [f for f in sorted(gdir.glob("*.csv")) if f not in timeline]
    if timeline:
        save(pd.concat(load_manual_csv(m) for m in timeline), out, "M_google_interest_over_time.csv")
    if related:
        save(pd.concat(MN.load_google_related(m) for m in related), out, "M_google_related_queries.csv")


def load_datalab(path: Path) -> pd.DataFrame:
    reqs = json.loads(path.read_text(encoding="utf-8"))
    return T.concat(T.datalab_to_long(r["response"], r["request_id"]) for r in reqs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    a = ap.parse_args()
    # API 스냅샷이 없으면(웹 다운로드 파일만 있는 경우) input/online_buzz/ 만 분석한다
    if a.snapshot:
        raw = RAW_DIR / a.snapshot
    else:
        try:
            raw = latest_snapshot()
        except FileNotFoundError:
            raw = RAW_DIR / "_none"
    out = PROCESSED_DIR / (raw.name if raw.exists() else "manual_" + pd.Timestamp.today().strftime("%Y%m%d"))
    out.mkdir(parents=True, exist_ok=True)
    print("raw:", raw, "\nout:", out)

    # ---------------- 지표 A
    if (p := raw / "naver_totals.csv").exists():
        save(M.share_table(pd.read_csv(p)), out, "A_mention_totals.csv", index=True)

    # ---------------- 지표 B
    if (p := raw / "naver_region_posts.jsonl").exists():
        items = pd.DataFrame(read_jsonl(p))
        save(M.posting_rate(items, S.END_DATE), out, "B_posting_rate.csv")
        d = items.dropna(subset=["date"]).drop_duplicates(["region", "channel", "link"])
        d = d.assign(month=pd.to_datetime(d["date"]).dt.to_period("M").astype(str))
        save(d.groupby(["region", "channel", "month"]).size().rename("n_posts").reset_index(), out, "B_monthly_posts.csv")

    # ---------------- 지표 C
    if (p := raw / "naver_jeonbuk_posts.jsonl").exists():
        posts = pd.DataFrame(read_jsonl(p))
        share = M.regional_mention_share(posts, S.JEONBUK_REGIONS, S.JEONBUK_REGION_EXCLUDES)
        save(share, out, "C_jeonbuk_mention_share.csv", index=True)
        by_ch = pd.concat({ch: M.regional_mention_share(g, S.JEONBUK_REGIONS, S.JEONBUK_REGION_EXCLUDES) for ch, g in posts.groupby("channel")})
        save(by_ch, out, "C_jeonbuk_mention_share_by_channel.csv", index=True)
        save(M.co_mentioned_regions(posts.drop_duplicates("link"), S.JEONBUK_REGIONS, S.TREND_ANCHOR, S.JEONBUK_REGION_EXCLUDES).rename("n_posts").to_frame(),
             out, "C_imsil_co_regions.csv", index=True)

    # ---------------- 검색 트렌드 (데이터랩)
    rel_regions = rel_imsil = None
    if (p := raw / "datalab_regions_raw.json").exists():
        rel_regions = T.chain_by_anchor(load_datalab(p), S.TREND_ANCHOR)
        save(rel_regions, out, "T_regions_index.csv")
        save(T.yearly_summary(rel_regions), out, "T_regions_yearly.csv", index=True)
        save(T.seasonality(rel_regions), out, "T_regions_seasonality.csv", index=True)
        tot = rel_regions.groupby("group")["index"].mean()
        save((tot / tot.sum() * 100).round(2).sort_values(ascending=False).rename("검색지수_점유율(%)").to_frame(),
             out, "T_regions_search_share.csv", index=True)
    if (p := raw / "datalab_regions_long_raw.json").exists():
        save(T.chain_by_anchor(load_datalab(p), S.TREND_ANCHOR), out, "T_regions_index_long.csv")
    if (p := raw / "datalab_imsil_raw.json").exists():
        rel_imsil = T.chain_by_anchor(load_datalab(p), S.TREND_ANCHOR)
        save(rel_imsil, out, "T_imsil_groups_index.csv")
        save(T.peak_months(rel_imsil), out, "T_imsil_peaks.csv")
        save(T.seasonality(rel_imsil), out, "T_imsil_seasonality.csv", index=True)
    if (p := raw / "datalab_imsil_daily_raw.json").exists():
        save(T.chain_by_anchor(load_datalab(p), S.TREND_ANCHOR), out, "T_imsil_groups_daily.csv")
    if (p := raw / "datalab_imsil_segments.json").exists():
        seg = json.loads(p.read_text(encoding="utf-8"))
        save(T.concat(T.datalab_to_long(s["response"]).assign(segment=s["segment"]) for s in seg), out, "T_imsil_segments.csv")

    # ---------------- 검색광고: 연관검색어 + 절대량 환산
    if (p := raw / "searchad_related_keywords.csv").exists():
        rel = pd.read_csv(p)
        save(AS.search_keyword_network(rel), out, "K_search_keywords.csv")
        top = rel.drop_duplicates("keyword").sort_values("monthly_total", ascending=False)
        save(top, out, "K_search_keywords_top.csv")
    if (p := raw / "searchad_group_volumes.csv").exists():
        vol = pd.read_csv(p).set_index("group")["monthly_total"].to_dict()
        # 검색광고 '최근 30일' ≈ 수집 직전 월로 간주
        ref = (pd.Timestamp(raw.name).to_period("M") - 1).start_time.strftime("%Y-%m-%d")
        est = [T.calibrate_absolute(r, vol, ref) for r in (rel_regions, rel_imsil) if r is not None]
        est = [e for e in est if not e.empty]
        if est:
            save(pd.concat(est), out, "T_estimated_searches.csv")

    # ---------------- 게시물 키워드 · 연관관계
    if (p := raw / "naver_imsil_posts.jsonl").exists():
        analyze_posts(pd.DataFrame(read_jsonl(p)), out)

    # ---------------- 웹 다운로드 파일 (input/online_buzz/)
    analyze_manual(out)

    # ---------------- Google Trends
    for gp in sorted(raw.glob("google_*.csv")):
        save(pd.read_csv(gp), out, "G_" + gp.name[len("google_"):])


if __name__ == "__main__":
    main()
