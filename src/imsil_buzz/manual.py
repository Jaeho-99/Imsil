"""웹 화면에서 직접 내려받은 CSV/XLSX 파일 로더 (API 를 쓰지 않는 기본 경로).

폴더 규칙 (data/manual/)
  naver_datalab/   네이버 데이터랩 '검색어트렌드' 다운로드 파일(.xlsx 또는 .csv)
  google_trends/   Google Trends '시간 흐름에 따른 관심도' CSV, '관련 검색어' CSV
  mentions/        언급 건수 표(mention_counts*.csv)와 게시물 텍스트 표(posts*.csv)

파일명에 다운로드일·조건을 남긴다. 예) 20261109_시군비교_월간_2022-2026.xlsx
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pandas as pd

from .google_trends import load_manual_csv as load_google_timeline  # noqa: F401  (재노출)

_DATE_HEADERS = {"날짜", "기간", "date", "period", "일자"}


def _read_any(path: Path) -> pd.DataFrame:
    """헤더 없이 원시 셀 그대로 읽는다."""
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, header=None, dtype=str)
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
        rows = list(csv.reader(io.StringIO(text)))  # 줄마다 열 수가 달라도(조건 줄) 그대로 읽는다
        width = max((len(r) for r in rows), default=0)
        return pd.DataFrame([r + [None] * (width - len(r)) for r in rows])
    raise ValueError(f"인코딩을 알 수 없습니다: {path}")


def load_datalab_export(path: str | Path) -> pd.DataFrame:
    """네이버 데이터랩 검색어트렌드 다운로드 파일 → long 형식 [group, period, ratio, source_file].

    다운로드 파일은 위쪽에 조회 조건 몇 줄이 있고, 그 아래 표가
    (날짜, 그룹1, 날짜, 그룹2, ...) 처럼 '날짜-값' 쌍이 반복되거나 (날짜, 그룹1, 그룹2, ...) 형태다.
    두 형태 모두 '날짜' 헤더가 있는 줄을 찾아 처리한다.
    """
    path = Path(path)
    raw = _read_any(path)
    hdr_row = None
    for i in range(min(len(raw), 40)):
        cells = [str(c).strip() for c in raw.iloc[i].tolist()]
        if any(c in _DATE_HEADERS for c in cells):
            hdr_row = i
            break
    if hdr_row is None:
        raise ValueError(f"'날짜' 헤더 줄을 찾지 못했습니다: {path}")
    header = [str(c).strip() if pd.notna(c) else "" for c in raw.iloc[hdr_row].tolist()]
    body = raw.iloc[hdr_row + 1 :]
    date_cols = [j for j, h in enumerate(header) if h in _DATE_HEADERS]
    rows = []
    for j, h in enumerate(header):
        if not h or h in _DATE_HEADERS:
            continue
        dcol = max([d for d in date_cols if d < j], default=date_cols[0])  # 왼쪽에서 가장 가까운 날짜 열
        for d, v in zip(body.iloc[:, dcol], body.iloc[:, j]):
            if pd.isna(d) or pd.isna(v) or str(d).strip() == "":
                continue
            try:
                rows.append({"group": h, "period": pd.to_datetime(str(d).strip()), "ratio": float(str(v).replace(",", ""))})
            except (ValueError, TypeError):
                continue
    df = pd.DataFrame(rows, columns=["group", "period", "ratio"])
    df["source_file"] = path.name
    return df


def load_google_related(path: str | Path) -> pd.DataFrame:
    """Google Trends '관련 검색어' CSV(TOP / RISING 두 블록) → [kind, query, value]."""
    text = Path(path).read_text(encoding="utf-8-sig")
    out, kind = [], None
    for line in text.splitlines():
        s = line.strip()
        up = s.upper()
        if up in ("TOP", "RISING", "인기", "급상승"):
            kind = {"인기": "TOP", "급상승": "RISING"}.get(s, up)
            continue
        if not s or kind is None:
            continue
        r = next(csv.reader(io.StringIO(s)))
        if len(r) >= 2:
            out.append({"kind": kind, "query": r[0], "value": r[1]})
    df = pd.DataFrame(out, columns=["kind", "query", "value"])
    df["source_file"] = Path(path).name
    return df


MENTION_COLUMNS = ["region", "channel", "count"]  # 선택: query, period, source, collected_at
POST_COLUMNS = ["channel", "title", "text"]  # 선택: date, link, region, query


def load_mention_counts(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("mention_counts*.csv"))
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_csv(f, encoding="utf-8-sig").assign(source_file=f.name) for f in files], ignore_index=True)
    miss = [c for c in MENTION_COLUMNS if c not in df.columns]
    if miss:
        raise ValueError(f"mention_counts 파일에 필수 열 {miss} 가 없습니다 (필수: {MENTION_COLUMNS})")
    df["count"] = pd.to_numeric(df["count"].astype(str).str.replace(",", ""), errors="coerce").fillna(0).astype(int)
    return df


def load_posts(folder: Path) -> pd.DataFrame:
    """게시물 텍스트 표 → 05_analyze 의 키워드 분석 입력 스키마(title, description, date, link, channel)."""
    files = sorted(folder.glob("posts*.csv"))
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_csv(f, encoding="utf-8-sig").assign(source_file=f.name) for f in files], ignore_index=True)
    miss = [c for c in POST_COLUMNS if c not in df.columns]
    if miss:
        raise ValueError(f"posts 파일에 필수 열 {miss} 가 없습니다 (필수: {POST_COLUMNS})")
    df = df.rename(columns={"text": "description"})
    for c in ("date", "link", "region", "query"):
        if c not in df.columns:
            df[c] = None
    df["link"] = df["link"].fillna(pd.Series(range(len(df))).map(lambda i: f"row:{i}"))
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["date"] = df["date"].where(df["date"].notna(), None)
    return df


def datalab_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("*") if p.suffix.lower() in (".xlsx", ".xls", ".csv"))


def anchor_from_filename(name: str) -> str | None:
    """파일명에 '__anchor=임실' 처럼 기준 그룹을 적으면 여러 파일을 한 척도로 합친다."""
    m = re.search(r"anchor=([^_.]+)", name)
    return m.group(1) if m else None
