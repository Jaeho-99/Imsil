"""키워드 사전·시군 판정·키워드도구 로더·확인표·수집기록 테스트."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from imsil_buzz import keyword_dict as KD  # noqa: E402
from imsil_buzz import manual as MN  # noqa: E402
from imsil_buzz import settings as S  # noqa: E402
from imsil_buzz.analysis import mentions as M  # noqa: E402


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_dictionary_views():
    e = KD.load()
    assert len(KD.regions(e)) == 14
    assert ("장수", "장수군 여행") in KD.region_queries(e)
    assert all(not q.startswith("장수 ") for _, q in KD.region_queries(e))
    assert len(KD.jeonbuk_queries(e)) == 7
    assert KD.anchor(e) == "임실"
    # 확정·참고만 쓰고 후보·확인필요는 빠진다
    topics = {x.topic for x in e}
    assert "성수산" in topics and "임실전통시장" not in topics and "옥정호(참고)" in topics
    assert {x.topic for x in KD.load(include_candidates=True)} >= {"임실전통시장", "상이암"}
    # 붕어섬 단독, 오수 단독, 도화지 단독 검색어는 없다
    qs = {q for x in KD.load(include_candidates=True) for q in x.queries}
    assert not {"붕어섬", "오수", "도화지", "국사봉"} & qs
    assert S.IMSIL_TREND_GROUPS and list(S.IMSIL_TREND_GROUPS)[0] == "임실"


def test_dictionary_rejects_duplicates(tmp_path):
    p = tmp_path / "키워드사전_v9.csv"
    p.write_text("층,주제어,넣는 검색어,쓰는 곳,상태\n지역,임실,임실 여행,언급비중,확정\n지역,임실,임실 관광,언급비중,확정\n", encoding="utf-8")
    with pytest.raises(ValueError):
        KD.load(p)


@pytest.mark.parametrize("text,expected", [
    ("전주 대비 매출이 늘었다", []),                       # 지난주 뜻
    ("전주 한옥마을 갔다가 임실 들렀어요", ["전주", "임실"]),
    ("하프 마라톤 완주했습니다", []),                       # 완주 = 끝까지 달림
    ("완주군 대아수목원 산책", ["완주"]),
    ("장수 비결은 걷기", []),                               # 장수(長壽)
    ("전주샹그릴라CC 라운딩 후기", ["임실"]),               # 이름에 '전주'가 있지만 임실 소재
    ("옥정호 붕어섬 출렁다리", ["임실"]),
])
def test_region_matcher(text, expected):
    match = M.RegionMatcher(S.JEONBUK_REGIONS, S.JEONBUK_REGION_EXCLUDES)
    assert sorted(match(text)) == sorted(expected)


def test_filter_topic_posts_drops_other_bungeoseom():
    posts = pd.DataFrame({
        "topic": ["옥정호 붕어섬", "옥정호 붕어섬", "성수산"],
        "title": ["붕어섬 출렁다리", "춘천 의암호 붕어섬", "성수역 맛집"],
        "description": ["임실 옥정호", "", "성수동"], "link": ["1", "2", "3"],
    })
    out = M.filter_topic_posts(posts, S.TOPIC_EXCLUDES, S.IMSIL_TERMS)
    assert out["link"].tolist() == ["1"]


def test_searchad_export(tmp_path):
    p = tmp_path / "20261107_키워드도구__seed=임실여행+옥정호.csv"
    p.write_text(
        "연관키워드,월간검색수(PC),월간검색수(모바일),월평균클릭수(PC),월평균클릭수(모바일),경쟁정도\n"
        "임실여행,\"1,230\",8900,1.2,30,낮음\n옥정호붕어섬,< 10,450,0,2,중간\n", encoding="utf-8")
    df = MN.load_searchad_export(p)
    assert df["monthly_total"].tolist() == [10130, 455]
    assert df["censored_lt10"].tolist() == [False, True]
    assert df["seed"].iloc[0] == "임실여행,옥정호"
    x = tmp_path / "b.xlsx"
    pd.DataFrame([["키워드 도구 조회 결과"], [], ["연관키워드", "월간검색수(PC)", "월간검색수(모바일)"], ["성수산", 300, "1,200"]]) \
        .to_excel(x, header=False, index=False)
    assert MN.load_searchad_export(x)["monthly_total"].tolist() == [1500]


def test_check_sheet_summary(tmp_path):
    rows = [{"층": "관광지", "주제어": "성수산", "상태": "확정", "검색어": "성수산", "순번": i,
             "맞음": "X" if i <= 4 else "O"} for i in range(1, 21)]
    rows += [{"층": "관광지", "주제어": "사선대관광지", "상태": "확정", "검색어": "사선대", "순번": i,
              "맞음": "O" if i < 20 else ""} for i in range(1, 21)]
    p = tmp_path / "확인표_20261106_blog.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8-sig")
    res = _script("00_keyword_check_sheet").summarize(p).set_index("검색어")
    assert res.loc["성수산", "판정"] == "좁히기" and res.loc["성수산", "맞음"] == 16
    assert res.loc["사선대", "판정"] == "미완료"


def test_record_and_verify(tmp_path):
    (tmp_path / "manual" / "naver_datalab").mkdir(parents=True)
    f = tmp_path / "manual" / "naver_datalab" / "a.csv"
    f.write_text("x", encoding="utf-8")
    env = {**os.environ, "IMSIL_DATA_DIR": str(tmp_path)}
    run = lambda *a: subprocess.run([sys.executable, str(ROOT / "scripts" / "06_record_collection.py"), *a],
                                    env=env, capture_output=True, text=True)
    assert run().returncode == 0
    log = pd.read_csv(tmp_path / "수집기록.csv", encoding="utf-8-sig")
    assert log["경로"].tolist() == ["manual/naver_datalab/a.csv"] and len(log["sha256"][0]) == 64
    assert run("--verify").returncode == 0
    f.write_text("y", encoding="utf-8")
    assert run("--verify").returncode == 1
