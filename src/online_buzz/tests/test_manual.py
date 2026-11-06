"""웹 다운로드 파일(input/online_buzz/) 경로 테스트. 실행(레포 최상위): python -m pytest -q src/online_buzz/tests"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

PKG = Path(__file__).resolve().parents[1]   # src/online_buzz/
sys.path.insert(0, str(PKG.parent))         # src/

from online_buzz import manual as MN  # noqa: E402


def _datalab_pairs_xlsx(path: Path, groups: dict[str, list[float]]) -> None:
    """데이터랩 다운로드 형태: 위에 조건 줄 몇 개, 아래 (날짜, 그룹) 쌍 반복."""
    months = pd.date_range("2026-01-01", periods=len(next(iter(groups.values()))), freq="MS").strftime("%Y-%m-%d")
    rows = [["네이버 데이터랩 검색어트렌드"], ["기간: 2026-01 ~ 2026-03 (월간)"], []]
    hdr = []
    for g in groups:
        hdr += ["날짜", g]
    rows.append(hdr)
    for i, m in enumerate(months):
        r = []
        for g, v in groups.items():
            r += [m, v[i]]
        rows.append(r)
    pd.DataFrame(rows).to_excel(path, header=False, index=False)


def test_datalab_pairs_and_wide(tmp_path):
    p = tmp_path / "a.xlsx"
    _datalab_pairs_xlsx(p, {"임실": [50, 100, 25], "전주": [10, 20, 30]})
    df = MN.load_datalab_export(p)
    assert set(df.group) == {"임실", "전주"} and len(df) == 6
    assert df[df.group == "임실"].ratio.tolist() == [50, 100, 25]

    w = tmp_path / "b.csv"
    w.write_text("조회조건,월간\n\n날짜,임실,옥정호\n2026-01-01,10,\"1,5\"\n2026-02-01,20,3\n", encoding="cp949")
    df2 = MN.load_datalab_export(w)
    assert df2[df2.group == "옥정호"].ratio.tolist() == [15, 3]


def test_google_related(tmp_path):
    p = tmp_path / "x_related.csv"
    p.write_text("카테고리: 모든 카테고리\n\nTOP\n임실 치즈,100\n옥정호,40\n\nRISING\n붕어섬,+250%\n", encoding="utf-8")
    df = MN.load_google_related(p)
    assert df.kind.tolist() == ["TOP", "TOP", "RISING"] and df["query"].iloc[2] == "붕어섬"


def test_manual_end_to_end(tmp_path):
    m = tmp_path / "in"
    for d in ("naver_datalab", "naver_searchad", "google_trends"):
        (m / d).mkdir(parents=True)
    # 임실을 기준으로 두 번 조회한 시군 비교 (실제 비율 임실=10, 전주=40, 남원=20)
    _datalab_pairs_xlsx(m / "naver_datalab" / "20261109_1__anchor=임실.xlsx", {"임실": [25, 25, 25], "전주": [100, 100, 100]})
    _datalab_pairs_xlsx(m / "naver_datalab" / "20261109_2__anchor=임실.xlsx", {"임실": [50, 50, 50], "남원": [100, 100, 100]})
    (m / "google_trends" / "20261109_KR.csv").write_text("월,임실: (대한민국)\n2026-01,40\n2026-02,<1\n", encoding="utf-8")
    (m / "naver_searchad" / "20261107_키워드도구__seed=임실여행.csv").write_text(
        "연관키워드,월간검색수(PC),월간검색수(모바일),경쟁정도\n임실여행,\"1,230\",8900,낮음\n옥정호붕어섬,< 10,450,중간\n",
        encoding="utf-8")

    env = {**os.environ, "IMSIL_BUZZ_IN": str(m), "IMSIL_BUZZ_OUT": str(tmp_path / "out")}
    r = subprocess.run([sys.executable, str(PKG / "05_analyze.py")], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = next((tmp_path / "out").glob("manual_*"))
    idx = pd.read_csv(out / "M_datalab_index_anchor-임실.csv").groupby("group")["index"].mean()
    assert round(idx["전주"]) == 400 and round(idx["남원"]) == 200 and round(idx["임실"]) == 100
    top = pd.read_csv(out / "M_search_keywords_top.csv")
    assert top["keyword"].tolist() == ["임실여행", "옥정호붕어섬"]
    for f in ["M_google_interest_over_time.csv", "M_searchad_keywords_long.csv", "M_search_keywords_network.csv"]:
        assert (out / f).exists(), (f, r.stdout)
