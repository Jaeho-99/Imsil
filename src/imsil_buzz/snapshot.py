"""수집 스냅샷 경로 관리. 수집일(YYYYMMDD)별 폴더에 원본을 저장해 재현성을 확보한다."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .settings import RAW_DIR


def new_snapshot(date: str | None = None) -> Path:
    d = RAW_DIR / (date or dt.date.today().strftime("%Y%m%d"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def latest_snapshot() -> Path:
    snaps = sorted(p for p in RAW_DIR.glob("[0-9]" * 8) if p.is_dir())
    if not snaps:
        raise FileNotFoundError(f"{RAW_DIR} 에 수집 스냅샷이 없습니다. scripts/01~04 를 먼저 실행하세요.")
    return snaps[-1]
