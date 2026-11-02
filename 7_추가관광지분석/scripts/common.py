# -*- coding: utf-8 -*-
"""scripts/ 공통 도구 — 경로 설정, 자체 검사 출력, 한글 글꼴, API 키."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

ENV_FILE = ROOT / ".env"


class Checks:
    """34개소 시계열 스크립트와 같은 형식의 자체 검사. 실패하면 그 자리에서 멈춘다."""

    def __init__(self, title: str):
        self.n = 0
        print(f"\n[자체 검사] {title}")

    def __call__(self, label: str, ok: bool, detail: str = "", fatal: bool = True):
        self.n += 1
        mark = "PASS" if ok else ("FAIL" if fatal else "WARN")
        print(f" {self.n:>2}. {label}: [{mark}]" + (f"  {detail}" if detail else ""))
        if not ok and fatal:
            sys.exit(f"검사 실패로 중단: {label}")
        return ok


def setup_font():
    """설치된 한글 글꼴을 찾아 matplotlib 에 지정한다. 없으면 경고만 낸다(CSV 수치에는 영향 없음)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    names = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ("Malgun Gothic", "AppleGothic", "NanumGothic", "NanumBarunGothic",
                 "Noto Sans CJK KR", "Noto Sans KR"):
        if cand in names:
            plt.rcParams["font.family"] = cand
            break
    else:
        try:  # pip install koreanize-matplotlib 가 있으면 쓴다
            import koreanize_matplotlib  # noqa: F401
        except ImportError:
            print("  [경고] 한글 글꼴을 찾지 못했습니다. 그림의 한글이 깨질 수 있습니다.")
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def anthropic_client():
    """ANTHROPIC_API_KEY 를 환경변수 → 7_추가관광지분석/.env → 4_.../.env 순서로 찾는다."""
    try:
        import anthropic
    except ImportError:
        sys.exit("오류: anthropic 패키지가 없습니다.  pip install anthropic")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        for env in (ENV_FILE, config.FACTOR_DIR / ".env"):
            if env.exists():
                for line in env.read_text(encoding="utf-8").splitlines():
                    k, _, v = line.strip().removeprefix("export ").partition("=")
                    if k.strip() == "ANTHROPIC_API_KEY" and v.strip():
                        os.environ["ANTHROPIC_API_KEY"] = v.strip().strip("'\"")
                        break
            if os.environ.get("ANTHROPIC_API_KEY"):
                break
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        sys.exit("오류: ANTHROPIC_API_KEY 가 없습니다. 7_추가관광지분석/.env 에 넣어 주세요 (.env.example 참고).")
    return anthropic.Anthropic(max_retries=8, timeout=600.0)


def read_csv(path, **kw):
    import pandas as pd
    return pd.read_csv(path, encoding="utf-8-sig", **kw)


def write_csv(df, path, **kw):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=kw.pop("index", False), encoding="utf-8-sig", **kw)
    return path


def rel(p) -> str:
    """로그·인벤토리에 절대경로가 남지 않게 레포 기준 상대경로로 바꾼다."""
    try:
        return str(Path(p).resolve().relative_to(config.REPO))
    except ValueError:
        return str(p)


# ─────────────────────────────────────────────────────────────
# 본문 속 개인 이름 가리기 (34개소 README '데이터 비식별 처리'와 같은 방식)
# ─────────────────────────────────────────────────────────────
import re as _re

NAME_HINT = _re.compile(r"(?<![가-힣])([가-힣]{2,3})(?:\s?씨(?![가-힣])|\s?(?:선생님|팀장님|과장님|주무관님|"
                        r"주무관|대표님|매니저님|해설사님|소장님|실장님|기사님))")


def load_mask_rules():
    """data/비식별_치환목록.csv (find, replace). 사람이 문맥을 보고 실명으로 확인한 표현만 적는다."""
    import pandas as pd
    if not config.MASK_RULES.exists():
        return []
    d = pd.read_csv(config.MASK_RULES, encoding="utf-8-sig", dtype=str).fillna("")
    return [(f, r or "○○○") for f, r in zip(d["find"], d["replace"]) if f]


def apply_mask(text, rules):
    if not isinstance(text, str):
        return text
    for f, r in rules:
        text = text.replace(f, r)
    return text


def name_candidates(df):
    """실명일 수 있는 표현 후보. 자동으로 가리지 않고 사람이 확인하도록 목록만 낸다."""
    rows = []
    for rid, body in zip(df["reviewId"], df["body"]):
        for m in NAME_HINT.finditer(str(body) if isinstance(body, str) else ""):
            rows.append({"reviewId": rid, "후보": m.group(0),
                         "문맥": str(body)[max(0, m.start() - 15): m.end() + 15]})
    return rows
