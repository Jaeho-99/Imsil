"""[분석] 수집 원본 → 최종 분석 데이터셋·표 (data/processed/online_buzz/<스냅샷>/).

있는 원본만 분석하고 없는 단계는 건너뛴다. 실행: python scripts/05_analyze.py [--snapshot YYYYMMDD]

산출물
  A_mention_totals.csv          시군별 누적 언급량·비중(지표 A)
  B_posting_rate.csv            시군별 최근 게시 속도(지표 B)
  C_jeonbuk_mention_share.csv   전북 관광 게시물 내 시군 언급 비중(지표 C), C_imsil_co_regions.csv
  T_regions_index.csv           14개 시군 검색지수(임실 평균=100), T_regions_yearly.csv, T_regions_seasonality.csv
  T_imsil_groups_index.csv      임실 관광지·축제 검색지수, T_imsil_peaks.csv, T_imsil_seasonality.csv
  T_imsil_segments.csv          기기·성별·연령대별 추이
  T_estimated_searches.csv      검색광고 절대량으로 환산한 추정 월간 검색수
  K_search_keywords.csv         임실 관광 연관검색어(검색광고) + 교차 관심어
  K_post_frequency.csv / K_post_docfreq.csv / K_post_tfidf_by_year.csv   게시물 키워드
  R_rules.csv / R_edges.csv / R_centrality.csv   키워드 연관규칙·네트워크
  G_*.csv                       Google Trends 정리본
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from imsil_buzz import settings as S
from imsil_buzz.analysis import association as AS
from imsil_buzz.analysis import keywords as KW
from imsil_buzz.analysis import mentions as M
from imsil_buzz.analysis import trends as T
from imsil_buzz.google_trends import load_manual_csv
from imsil_buzz.snapshot import latest_snapshot
from imsil_buzz.settings import RAW_DIR, PROCESSED_DIR, MANUAL_DIR
from imsil_buzz.utils import read_jsonl


def save(df: pd.DataFrame, out: Path, name: str, index: bool = False) -> None:
    df.to_csv(out / name, index=index, encoding="utf-8-sig")
    print(f"  {name:38s} {len(df):>6} rows")


def load_datalab(path: Path) -> pd.DataFrame:
    reqs = json.loads(path.read_text(encoding="utf-8"))
    return T.concat(T.datalab_to_long(r["response"], r["request_id"]) for r in reqs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    a = ap.parse_args()
    raw = RAW_DIR / a.snapshot if a.snapshot else latest_snapshot()
    out = PROCESSED_DIR / raw.name
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
        share = M.regional_mention_share(posts, S.JEONBUK_REGIONS)
        save(share, out, "C_jeonbuk_mention_share.csv", index=True)
        by_ch = pd.concat({ch: M.regional_mention_share(g, S.JEONBUK_REGIONS) for ch, g in posts.groupby("channel")})
        save(by_ch, out, "C_jeonbuk_mention_share_by_channel.csv", index=True)
        save(M.co_mentioned_regions(posts.drop_duplicates("link"), S.JEONBUK_REGIONS).rename("n_posts").to_frame(),
             out, "C_imsil_co_regions.csv", index=True)

    # ---------------- 검색 트렌드 (데이터랩)
    rel_regions = rel_imsil = None
    if (p := raw / "datalab_regions_raw.json").exists():
        rel_regions = T.chain_by_anchor(load_datalab(p), "임실")
        save(rel_regions, out, "T_regions_index.csv")
        save(T.yearly_summary(rel_regions), out, "T_regions_yearly.csv", index=True)
        save(T.seasonality(rel_regions), out, "T_regions_seasonality.csv", index=True)
        tot = rel_regions.groupby("group")["index"].mean()
        save((tot / tot.sum() * 100).round(2).sort_values(ascending=False).rename("검색지수_점유율(%)").to_frame(),
             out, "T_regions_search_share.csv", index=True)
    if (p := raw / "datalab_regions_long_raw.json").exists():
        save(T.chain_by_anchor(load_datalab(p), "임실"), out, "T_regions_index_long.csv")
    if (p := raw / "datalab_imsil_raw.json").exists():
        rel_imsil = T.chain_by_anchor(load_datalab(p), "임실 관광(전체)")
        save(rel_imsil, out, "T_imsil_groups_index.csv")
        save(T.peak_months(rel_imsil), out, "T_imsil_peaks.csv")
        save(T.seasonality(rel_imsil), out, "T_imsil_seasonality.csv", index=True)
    if (p := raw / "datalab_imsil_daily_raw.json").exists():
        save(T.chain_by_anchor(load_datalab(p), "임실 관광(전체)"), out, "T_imsil_groups_daily.csv")
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
        posts = pd.DataFrame(read_jsonl(p)).drop_duplicates("link")
        posts = posts[posts["title"].str.contains("임실|옥정호|붕어섬|성수산|오수|사선대", na=False)
                      | posts["description"].str.contains("임실|옥정호|붕어섬|성수산|오수|사선대", na=False)]
        tok = KW.tokenize_frame(posts, stopwords={"임실", "임실군"})
        tok.drop(columns=["text"]).to_json(out / "imsil_posts_tokens.jsonl", orient="records", lines=True, force_ascii=False)
        save(KW.frequency(tok["tokens"], 50), out, "K_post_frequency.csv")
        save(KW.doc_frequency(tok["tokens"].tolist(), 50), out, "K_post_docfreq.csv")
        save(pd.concat({ch: KW.doc_frequency(g["tokens"].tolist(), 30) for ch, g in tok.groupby("channel")}),
             out, "K_post_docfreq_by_channel.csv", index=True)
        dated = tok.dropna(subset=["date"]).assign(year=lambda x: x["date"].str[:4])
        if not dated.empty:
            save(KW.tfidf_by_group(dated, "year"), out, "K_post_tfidf_by_year.csv")
        save(AS.pair_rules(tok["tokens"].tolist()), out, "R_rules.csv")
        edges = AS.cooccurrence_edges(tok["tokens"].tolist())
        save(edges, out, "R_edges.csv")
        save(AS.centrality(edges), out, "R_centrality.csv")

    # ---------------- Google Trends
    for gp in sorted(raw.glob("google_*.csv")):
        save(pd.read_csv(gp), out, "G_" + gp.name[len("google_"):])
    manual = sorted((MANUAL_DIR / "google_trends").glob("*.csv"))
    if manual:
        save(pd.concat(load_manual_csv(m) for m in manual), out, "G_manual_interest_over_time.csv")


if __name__ == "__main__":
    main()
