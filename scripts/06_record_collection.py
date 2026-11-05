"""[수집 후] 수집기록.csv: 원본 파일 목록과 지문(SHA-256)을 남겨 재현성을 확인한다.

  python scripts/06_record_collection.py                     # data/수집기록.csv 작성(덮어씀)
  python scripts/06_record_collection.py --processed         # 결과표(data/processed)도 지문에 포함
  python scripts/06_record_collection.py --verify            # 지금 파일들이 기록과 같은지 확인 (다른 PC 검증용)

기록 열: 구분, 경로(data/ 기준), 크기(byte), sha256, 수정시각, 기록일시, 키워드사전, 키워드사전_sha256, git_commit
제출 전에는 블로그 닉네임 등 개인 식별 정보가 원본에 남아 있는지 확인한다(제출본에서 bloggername 열 제거).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from imsil_buzz import keyword_dict as KD
from imsil_buzz.settings import DATA_DIR, REPO_ROOT

LOG = DATA_DIR / "수집기록.csv"
SECTIONS = {"웹다운로드": "manual", "API원본": "raw", "결과표": "processed"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


def scan(include_processed: bool) -> pd.DataFrame:
    kd = KD.default_path()
    now = dt.datetime.now().isoformat(timespec="seconds")
    rows = []
    for sec, sub in SECTIONS.items():
        if sec == "결과표" and not include_processed:
            continue
        base = DATA_DIR / sub
        for p in sorted(x for x in base.rglob("*") if x.is_file()):
            if p.name.startswith(".") or p.name.startswith("_template"):
                continue
            rows.append({"구분": sec, "경로": p.relative_to(DATA_DIR).as_posix(), "크기": p.stat().st_size,
                         "sha256": sha256(p),
                         "수정시각": dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                         "기록일시": now, "키워드사전": kd.name, "키워드사전_sha256": sha256(kd), "git_commit": git_commit()})
    return pd.DataFrame(rows)


def verify() -> int:
    if not LOG.exists():
        print("수집기록.csv 가 없습니다"); return 2
    rec = pd.read_csv(LOG, encoding="utf-8-sig")
    bad = 0
    for r in rec.itertuples():
        p = DATA_DIR / r.경로
        if not p.exists():
            print("없음  ", r.경로); bad += 1
        elif sha256(p) != r.sha256:
            print("다름  ", r.경로); bad += 1
    print(f"{len(rec)}개 중 {len(rec) - bad}개 일치" + ("" if bad else " — 모두 같습니다"))
    return 1 if bad else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.verify:
        sys.exit(verify())
    df = scan(a.processed)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(LOG, index=False, encoding="utf-8-sig")
    print(f"saved -> {LOG} ({len(df)} files)")


if __name__ == "__main__":
    main()
