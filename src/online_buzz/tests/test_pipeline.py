"""가짜 API 응답으로 수집 → 분석 전체 흐름을 검증한다. 실행(레포 최상위): python -m pytest -q src/online_buzz/tests"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

PKG = Path(__file__).resolve().parents[1]   # src/online_buzz/
sys.path.insert(0, str(PKG.parent))         # src/
sys.path.insert(0, str(PKG / "tests"))

from fake_naver import FakeSession  # noqa: E402
from online_buzz.analysis import association as AS  # noqa: E402
from online_buzz.analysis import mentions as M  # noqa: E402
from online_buzz.analysis import trends as T  # noqa: E402
from online_buzz.google_trends import load_manual_csv  # noqa: E402
from online_buzz.naver import NaverClient, normalize_item  # noqa: E402
from online_buzz.searchad import parse_keyword_row, signature  # noqa: E402
from online_buzz.utils import clean_html  # noqa: E402


def client(**kw):
    return NaverClient("id", "secret", sleep=0, session=FakeSession(**kw))


def test_iter_search_caps_at_1099():
    items = list(client(n_total=5000).iter_search("blog", "임실 여행"))
    assert len(items) == 1099 and len({i["link"] for i in items}) == 1099
    assert items[0]["date"] == "2026-10-31"


def test_iter_search_stops_at_total():
    c = client(n_total=150)
    total = c.search_total("news", "q")
    assert total < 1100
    assert len(list(c.iter_search("news", "q"))) == total


def test_normalize_item_drops_blogger_name():
    n = normalize_item("blog", "q", {"link": "https://blog.naver.com/someone/1", "bloggername": "닉네임",
                                      "bloggerlink": "blog.naver.com/someone", "postdate": "20261005"})
    assert "bloggername" not in n and "bloggerlink" not in n and n["source"] == ""
    assert normalize_item("cafearticle", "q", {"cafename": "전북여행"})["source"] == "전북여행"


def test_normalize_item_dates():
    assert normalize_item("blog", "q", {"postdate": "20261005"})["date"] == "2026-10-05"
    assert normalize_item("news", "q", {"pubDate": "Mon, 05 Oct 2026 09:00:00 +0900"})["date"] == "2026-10-05"
    assert normalize_item("cafearticle", "q", {"title": "a"})["date"] is None
    assert clean_html("<b>임실</b> &amp; 치즈") == "임실 & 치즈"


def test_backend_headers():
    c = NaverClient("i", "s", backend="apihub")
    assert c._headers() == {"X-NCP-APIGW-API-KEY-ID": "i", "X-NCP-APIGW-API-KEY": "s"}


def test_anchor_chaining_recovers_common_scale():
    # 실제 값: 임실=10, A=20, B=40, C=5 → 요청마다 최대값=100 으로 다르게 정규화돼도 비율이 복원돼야 함
    true = {"임실": 10, "A": 20, "B": 40, "C": 5}
    frames = []
    for rid, batch in enumerate(T.plan_anchor_batches(list(true), "임실", per_request=3)):
        mx = max(true[g] for g in batch)
        resp = {"results": [{"title": g, "data": [{"period": "2026-01-01", "ratio": true[g] / mx * 100}]} for g in batch]}
        frames.append(T.datalab_to_long(resp, rid))
    res = T.chain_by_anchor(pd.concat(frames), "임실").set_index("group")["index"]
    assert res["임실"] == pytest.approx(100)
    assert res["A"] == pytest.approx(200) and res["B"] == pytest.approx(400) and res["C"] == pytest.approx(50)
    assert res.index.tolist().count("임실") == 1


def test_calibrate_absolute():
    rel = pd.DataFrame({"group": ["g", "g"], "period": pd.to_datetime(["2026-09-01", "2026-10-01"]), "index": [50.0, 100.0]})
    est = T.calibrate_absolute(rel, {"g": 2000}, "2026-10-01")
    assert est["est_monthly_searches"].tolist() == [1000, 2000]


def test_regional_mention_share():
    posts = pd.DataFrame({
        "link": ["1", "2", "3", "3"],
        "title": ["임실 치즈", "전주 한옥", "장수 비결", "dup"],
        "description": ["전주 도 감", "", "건강 장수", ""],
    })
    s = M.regional_mention_share(posts, {"임실": ["임실"], "전주": ["전주"], "장수": ["장수군"]})
    assert s.loc["전주", "언급_게시물수"] == 2 and s.loc["임실", "언급_게시물수"] == 1
    assert s.loc["장수", "언급_게시물수"] == 0  # '장수(長壽)' 오탐 방지
    assert s.attrs["n_posts"] == 3


def test_pair_rules_lift():
    tx = [["주차", "대기"]] * 10 + [["치즈", "피자"]] * 10 + [["주차"]] * 5
    r = AS.pair_rules(tx, min_support=0.1)
    row = r[(r.antecedent == "대기") & (r.consequent == "주차")].iloc[0]
    assert row.confidence == 1.0 and row.lift == pytest.approx(25 / 15, rel=1e-3)


def test_searchad_parsing_and_signature():
    r = parse_keyword_row({"relKeyword": "임실여행", "monthlyPcQcCnt": "< 10", "monthlyMobileQcCnt": 1230})
    assert r["monthly_total"] == 1235 and r["censored_lt10"]
    assert signature("secret", "1", "GET", "/keywordstool") == "EqCU1jEo58yz1J7/rVM4RM88pYxGTEeTbpU40x7NhGs="


def test_manual_google_csv(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("카테고리: 모든 카테고리\n\n월,임실: (대한민국),옥정호: (대한민국)\n2026-01,40,<1\n2026-02,100,3\n", encoding="utf-8")
    df = load_manual_csv(p)
    assert set(df.term) == {"임실", "옥정호"} and df.value.tolist() == [40, 0.5, 100, 3]


@pytest.fixture
def buzz_dirs(tmp_path, monkeypatch):
    """input/online_buzz·output/online_buzz 대신 임시 폴더를 쓰도록 설정을 다시 읽는다."""
    import online_buzz.settings as S
    import online_buzz.snapshot as SN

    monkeypatch.setenv("IMSIL_BUZZ_IN", str(tmp_path / "in"))
    monkeypatch.setenv("IMSIL_BUZZ_OUT", str(tmp_path / "out"))
    importlib.reload(S)
    importlib.reload(SN)
    yield tmp_path / "in", tmp_path / "out"
    monkeypatch.undo()
    importlib.reload(S)
    importlib.reload(SN)


def test_end_to_end(buzz_dirs, monkeypatch):
    """01·02 수집 스크립트를 가짜 세션으로 돌리고 05 분석까지 실행."""
    buzz_in, buzz_out = buzz_dirs
    monkeypatch.setenv("NAVER_CLIENT_ID", "x")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "y")
    import requests
    monkeypatch.setattr(requests, "Session", lambda: FakeSession(n_total=400))
    import online_buzz.naver as N
    importlib.reload(N)
    monkeypatch.setattr(N.time, "sleep", lambda s: None)

    for script in ("01_collect_naver_search", "02_collect_naver_datalab"):
        spec = importlib.util.spec_from_file_location(script, PKG / f"{script}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        monkeypatch.setattr(sys, "argv", [script, "--snapshot", "20261109"])
        mod.main()

    # 검색광고 원본은 형식만 맞춘 가짜 파일
    raw = buzz_out / "raw" / "20261109"
    pd.DataFrame([{"seed": "임실", "keyword": "임실여행", "monthly_total": 900},
                  {"seed": "옥정호", "keyword": "임실여행", "monthly_total": 900},
                  {"seed": "임실", "keyword": "임실치즈테마파크", "monthly_total": 3000}]).to_csv(raw / "searchad_related_keywords.csv", index=False)
    pd.DataFrame([{"group": "임실", "monthly_total": 5000}, {"group": "전주", "monthly_total": 90000}]).to_csv(raw / "searchad_group_volumes.csv", index=False)

    env = {**os.environ, "IMSIL_BUZZ_IN": str(buzz_in), "IMSIL_BUZZ_OUT": str(buzz_out)}
    r = subprocess.run([sys.executable, str(PKG / "05_analyze.py"), "--snapshot", "20261109"],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = buzz_out / "20261109"
    must = ["A_mention_totals.csv", "B_posting_rate.csv", "C_jeonbuk_mention_share.csv", "T_regions_index.csv",
            "T_imsil_groups_index.csv", "T_imsil_segments.csv", "T_estimated_searches.csv", "K_search_keywords.csv",
            "K_post_frequency.csv", "R_rules.csv", "R_centrality.csv", "imsil_posts_tokens.jsonl"]
    missing = [m for m in must if not (out / m).exists()]
    assert not missing, (missing, r.stdout)
    share = pd.read_csv(out / "C_jeonbuk_mention_share.csv", index_col=0)
    assert "임실" in share.index and share["언급_게시물수"].sum() > 0
    a = pd.read_csv(out / "A_mention_totals.csv", index_col=0)
    assert len(a) == 14
    assert json.loads((raw / "meta.json").read_text(encoding="utf-8"))["naver_search"]["backend"] == "developers"

    # 작성자 정보: 수집 원본에 닉네임을 저장하지 않고, 결과표에는 링크·출처가 없다
    posts = [json.loads(line) for f in raw.glob("naver_*_posts.jsonl") for line in f.open(encoding="utf-8")]
    assert posts and not any("bloggername" in p or "bloggerlink" in p for p in posts)
    for f in out.rglob("*"):
        if f.suffix in (".csv", ".jsonl"):
            text = f.read_text(encoding="utf-8-sig")
            assert "blog.naver.com" not in text and "닉네임" not in text, f.name
    tok = pd.read_json(out / "imsil_posts_tokens.jsonl", lines=True)
    assert tok.columns.tolist()[:2] == ["post_id", "topic"] and not {"link", "source"} & set(tok.columns)
    assert tok["post_id"].is_unique
