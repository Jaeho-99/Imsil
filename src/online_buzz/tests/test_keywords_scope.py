"""키워드 사전·시군 판정·키워드도구 로더·확인표·수집기록·git 제외 규칙 테스트."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

PKG = Path(__file__).resolve().parents[1]   # src/online_buzz/
REPO = PKG.parents[1]                       # 레포 최상위
sys.path.insert(0, str(PKG.parent))         # src/

from online_buzz import keyword_dict as KD  # noqa: E402
from online_buzz import manual as MN  # noqa: E402
from online_buzz import settings as S  # noqa: E402
from online_buzz.analysis import mentions as M  # noqa: E402


def _script(name):
    spec = importlib.util.spec_from_file_location(name, PKG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_dictionary_views():
    assert KD.default_path().parent == REPO / "input" / "online_buzz"
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
    rows = [{"층": "관광지", "주제어": "성수산", "상태": "확정", "검색어": "성수산", "검색결과수": "900", "순번": i,
             "제목": f"제목{i}", "요약": "요약", "작성일": "2026-11-01", "링크": f"https://blog.naver.com/someone/{i}",
             "자동_거를글": "", "맞음": "X" if i <= 4 else "O"} for i in range(1, 21)]
    rows += [{"층": "관광지", "주제어": "사선대관광지", "상태": "확정", "검색어": "사선대", "검색결과수": "50", "순번": i,
              "제목": "", "요약": "", "작성일": "", "링크": "", "자동_거를글": "", "맞음": "O" if i < 20 else ""}
             for i in range(1, 21)]
    p = tmp_path / "확인표_20261106_blog.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8-sig")
    mod = _script("00_keyword_check_sheet")
    res = mod.summarize(p).set_index("검색어")
    assert res.loc["성수산", "판정"] == "좁히기" and res.loc["성수산", "맞음"] == 16
    assert res.loc["사선대", "판정"] == "미완료"
    # 커밋하는 판정표에는 제목·요약·링크가 없다
    j = mod.judgements(p)
    assert len(j) == 40 and not {"제목", "요약", "링크"} & set(j.columns) and "맞음" in j.columns
    assert mod.result_name(p, "판정") == "판정_20261106_blog.csv"
    assert mod.result_name(tmp_path / "내표.csv", "확인결과") == "확인결과_내표.csv"


def test_record_and_verify(tmp_path):
    buzz_in, buzz_out = tmp_path / "in", tmp_path / "out"
    (buzz_in / "naver_datalab").mkdir(parents=True)
    f = buzz_in / "naver_datalab" / "a.csv"
    f.write_text("x", encoding="utf-8")
    (buzz_out / "raw" / "20261107").mkdir(parents=True)
    (buzz_out / "raw" / "20261107" / "naver_totals.csv").write_text("t", encoding="utf-8")
    (buzz_out / "keyword_check").mkdir()
    (buzz_out / "keyword_check" / "확인표_20261106_blog.csv").write_text("링크", encoding="utf-8")
    (buzz_out / "keyword_check" / "확인결과_20261106_blog.csv").write_text("r", encoding="utf-8")
    env = {**os.environ, "IMSIL_BUZZ_IN": str(buzz_in), "IMSIL_BUZZ_OUT": str(buzz_out)}
    run = lambda *a: subprocess.run([sys.executable, str(PKG / "06_record_collection.py"), *a],
                                    env=env, capture_output=True, text=True)
    assert run().returncode == 0
    log = pd.read_csv(buzz_out / "수집기록.csv", encoding="utf-8-sig")
    assert log["경로"].tolist() == ["input/online_buzz/naver_datalab/a.csv",
                                   "output/online_buzz/raw/20261107/naver_totals.csv"]
    assert log["구분"].tolist() == ["웹다운로드", "API원본"] and len(log["sha256"][0]) == 64
    assert run("--verify").returncode == 0
    f.write_text("y", encoding="utf-8")
    assert run("--verify").returncode == 1
    # 결과표를 넣어도 링크가 든 확인표는 기록하지 않는다
    assert run("--processed").returncode == 0
    log = pd.read_csv(buzz_out / "수집기록.csv", encoding="utf-8-sig")
    assert "output/online_buzz/keyword_check/확인결과_20261106_blog.csv" in log["경로"].tolist()
    assert not log["경로"].str.contains("확인표_").any()


@pytest.mark.skipif(shutil.which("git") is None or not (REPO / ".git").exists(), reason="git 저장소가 아님")
@pytest.mark.parametrize("path,ignored", [
    ("output/online_buzz/raw/20261107/naver_region_posts.jsonl", True),   # 블로그 링크(작성자 ID)
    ("output/online_buzz/raw/20261107/meta.json", True),
    ("output/online_buzz/keyword_check/확인표_20261106_blog.csv", True),  # 링크·제목
    ("input/online_buzz/keyword_check/확인표_20261106_blog.csv", True),
    ("output/online_buzz/keyword_check/확인결과_20261106_blog.csv", False),
    ("output/online_buzz/keyword_check/판정_20261106_blog.csv", False),
    ("output/online_buzz/20261107/C_jeonbuk_mention_share.csv", False),
    ("output/online_buzz/수집기록.csv", False),
    ("input/online_buzz/naver_datalab/20261107_시군비교__anchor=임실.xlsx", False),
])
def test_gitignore_keeps_author_data_out(path, ignored):
    r = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", "--no-index", path])
    assert (r.returncode == 0) == ignored, path
