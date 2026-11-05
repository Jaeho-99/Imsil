"""키워드 사전(config/키워드사전_v*.csv) 로더.

검색어·별칭·거를 글 조건은 코드 상수가 아니라 이 사전 한 파일에서 읽는다.
사전을 바꾸면 v2 로 새 파일을 만들고 날짜와 이유를 비고에 적는다(수집기록에 버전이 남는다).

열
  층            지역 | 전북 | 관광지 | 축제 | 특산물
  주제어        묶음 이름 (데이터랩 주제어, 결과표의 그룹명)
  넣는 검색어   ';' 로 구분. 검색 API·데이터랩·키워드도구에 넣는 검색어
  거를 글       ';' 로 구분. 게시물 제목·요약에 이 말이 있으면 해당 주제어 글에서 뺀다
  쓰는 곳       ';' 로 구분. 언급비중 | 전북게시물 | 검색추이 | 게시물 | 키워드도구 | 데이터랩기준어
  본문 인정 표현 (지역 층) 게시물 본문에서 이 시군 언급으로 인정할 표현
  본문 제외 표현 (지역 층) 본문 인정 표현이 다른 뜻으로 쓰인 경우. 매칭 전에 지운다
  상태          확정 | 후보 | 확인필요 | 참고    ('확정'·'참고' 만 수집에 쓴다. --include-candidates 로 후보 포함)
  비고
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from pathlib import Path

USE_STATES = {"확정", "참고"}


@dataclass
class Entry:
    layer: str
    topic: str
    queries: list[str]
    exclude: list[str] = field(default_factory=list)
    uses: set[str] = field(default_factory=set)
    aliases: list[str] = field(default_factory=list)
    alias_exclude: list[str] = field(default_factory=list)
    status: str = "확정"
    note: str = ""


def _split(v: str | None) -> list[str]:
    return [s.strip() for s in (v or "").split(";") if s.strip()]


def default_path() -> Path:
    from .settings import REPO_ROOT

    env = os.getenv("IMSIL_KEYWORD_DICT")
    if env:
        return Path(env)
    files = sorted((REPO_ROOT / "config").glob("키워드사전_v*.csv"), key=lambda p: int(p.stem.rsplit("_v", 1)[-1] or 0))
    if not files:
        raise FileNotFoundError("config/키워드사전_v*.csv 가 없습니다")
    return files[-1]  # 가장 높은 버전


def load(path: str | Path | None = None, include_candidates: bool = False) -> list[Entry]:
    p = Path(path) if path else default_path()
    with p.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    need = {"층", "주제어", "넣는 검색어", "쓰는 곳", "상태"}
    if rows and not need <= set(rows[0]):
        raise ValueError(f"키워드 사전에 필수 열 {sorted(need - set(rows[0]))} 이 없습니다: {p}")
    out = []
    for r in rows:
        status = (r.get("상태") or "확정").strip()
        if status not in USE_STATES and not include_candidates:
            continue
        out.append(Entry(
            layer=r["층"].strip(), topic=r["주제어"].strip(), queries=_split(r["넣는 검색어"]),
            exclude=_split(r.get("거를 글")), uses=set(_split(r["쓰는 곳"])),
            aliases=_split(r.get("본문 인정 표현")), alias_exclude=_split(r.get("본문 제외 표현")),
            status=status, note=(r.get("비고") or "").strip(),
        ))
    topics = [e.topic for e in out]
    dup = {t for t in topics if topics.count(t) > 1}
    if dup:
        raise ValueError(f"주제어가 중복됩니다: {dup}")
    return out


# --------------------------------------------------------------- 용도별 보기
def regions(entries: list[Entry]) -> dict[str, list[str]]:
    """지역 층: 시군 -> 본문 인정 표현 (없으면 시군명)."""
    return {e.topic: e.aliases or [e.topic] for e in entries if e.layer == "지역"}


def region_excludes(entries: list[Entry]) -> dict[str, list[str]]:
    return {e.topic: e.alias_exclude for e in entries if e.layer == "지역" and e.alias_exclude}


def region_queries(entries: list[Entry]) -> list[tuple[str, str]]:
    return [(e.topic, q) for e in entries if e.layer == "지역" and "언급비중" in e.uses for q in e.queries]


def jeonbuk_queries(entries: list[Entry]) -> list[str]:
    return [q for e in entries if "전북게시물" in e.uses for q in e.queries]


def trend_groups(entries: list[Entry], layers: tuple[str, ...]) -> dict[str, list[str]]:
    """데이터랩 주제어 → 검색어(최대 20개)."""
    return {e.topic: e.queries[:20] for e in entries if e.layer in layers and "검색추이" in e.uses}


def anchor(entries: list[Entry]) -> str:
    a = [e.topic for e in entries if "데이터랩기준어" in e.uses]
    return a[0] if a else "임실"


def post_queries(entries: list[Entry]) -> list[tuple[str, str]]:
    """(주제어, 검색어) — 임실 관련 게시물 수집용."""
    return [(e.topic, q) for e in entries if "게시물" in e.uses for q in e.queries]


def topic_excludes(entries: list[Entry]) -> dict[str, list[str]]:
    return {e.topic: e.exclude for e in entries if e.exclude}


def searchad_seeds(entries: list[Entry]) -> list[str]:
    return [q.replace(" ", "") for e in entries if "키워드도구" in e.uses for q in e.queries[:2]]


def imsil_terms(entries: list[Entry]) -> list[str]:
    """임실 관련 글인지 판단하는 표현: 임실 지역 별칭 + 임실 관광지·축제·특산물 검색어."""
    terms = list(regions(entries).get("임실", ["임실"]))
    for e in entries:
        if e.layer in ("관광지", "축제", "특산물"):
            terms += e.queries
    return sorted(set(terms), key=len, reverse=True)
