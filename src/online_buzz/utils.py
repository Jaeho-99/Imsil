from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean_html(text: str) -> str:
    """검색 API 응답의 <b> 강조 태그와 HTML 엔티티를 제거."""
    return _WS.sub(" ", html.unescape(_TAG.sub("", text or ""))).strip()


def load_dotenv(path: str | Path | None = None) -> None:
    """의존성 없이 .env(KEY=VALUE) 를 읽어 환경변수로 설정. 이미 설정된 값은 덮어쓰지 않는다."""
    from .settings import ENV_FILE

    p = Path(path) if path else ENV_FILE
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# 결과표·제출본에 남기지 않는 열: 블로그 link 에는 작성자 ID 가, bloggername 에는 닉네임이 있다
PRIVATE_COLUMNS = ("link", "source", "bloggername", "bloggerlink", "originallink")


def drop_private(df: "pd.DataFrame") -> "pd.DataFrame":
    """작성자를 알아볼 수 있는 열을 뺀 사본."""
    return df.drop(columns=[c for c in PRIVATE_COLUMNS if c in df.columns])


def progress(items: Iterable[Any], desc: str) -> Iterable[Any]:
    """반복하면서 '[desc] 3/28' 처럼 진행 상황을 한 줄씩 출력한다."""
    items = list(items)
    for i, x in enumerate(items, 1):
        print(f"[{desc}] {i}/{len(items)}", flush=True)
        yield x


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def to_int_count(v: Any) -> int:
    """검색광고 API 는 10 미만을 '< 10' 문자열로 준다 → 5 로 대체(구간 중앙값)."""
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).replace(",", "").strip()
    if s.startswith("<"):
        return 5
    return int(float(s)) if s else 0
