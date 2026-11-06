"""[수집 후] 수집기록.csv: 원본 파일 목록과 지문(SHA-256)을 남겨 재현성을 확인한다.

레포 최상위에서 실행한다.
  python src/online_buzz/06_record_collection.py               # output/online_buzz/수집기록.csv 작성(덮어씀)
  python src/online_buzz/06_record_collection.py --processed   # 결과표(output/online_buzz/<수집일>/ 등)도 지문에 포함
  python src/online_buzz/06_record_collection.py --verify      # 지금 파일들이 기록과 같은지 확인 (다른 PC 검증용)

기록 열: 구분, 경로(레포 최상위 기준), 크기(byte), sha256, 수정시각, 기록일시, 키워드사전, 키워드사전_sha256, git_commit
  구분  웹다운로드 = input/online_buzz/{naver_datalab,naver_searchad,google_trends}/
        API원본    = output/online_buzz/raw/<수집일>/  (git 제외. 지문만 이 기록으로 커밋한다)
        결과표     = output/online_buzz/ 의 나머지 하위 폴더 (--processed 일 때)
API 원본은 블로그 링크에 작성자 ID 가 있어 git 에 올리지 않는다. 원본을 따로 전달받은 사람은 --verify 로
같은 파일인지 확인할 수 있다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/

import pandas as pd

from online_buzz import keyword_dict as KD
from online_buzz.settings import BUZZ_IN, BUZZ_OUT, COLLECTION_LOG, RAW_DIR, REPO_ROOT

LOG = COLLECTION_LOG
WEB_DIRS = ("naver_datalab", "naver_searchad", "google_trends")
# 경로 열의 앞부분 → 실제 폴더 (테스트에서 BUZZ_IN·BUZZ_OUT 을 임시 폴더로 바꿔도 같은 이름으로 기록된다)
ROOTS = {"input/online_buzz": BUZZ_IN, "output/online_buzz": BUZZ_OUT}


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


def label(p: Path) -> str:
    for name, base in ROOTS.items():
        try:
            return f"{name}/{p.relative_to(base).as_posix()}"
        except ValueError:
            continue
    return p.relative_to(REPO_ROOT).as_posix()


def resolve(lbl: str) -> Path:
    for name, base in ROOTS.items():
        if lbl.startswith(name + "/"):
            return base / lbl[len(name) + 1:]
    return REPO_ROOT / lbl


def sections(include_processed: bool):
    yield "웹다운로드", [BUZZ_IN / d for d in WEB_DIRS]
    yield "API원본", [RAW_DIR]
    if include_processed and BUZZ_OUT.exists():
        yield "결과표", [d for d in sorted(BUZZ_OUT.iterdir()) if d.is_dir() and d != RAW_DIR]


def files_in(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("*") if p.is_file()
                  and not p.name.startswith(".") and not p.name.startswith("확인표_"))  # 확인표는 작업용(링크 포함)


def scan(include_processed: bool) -> pd.DataFrame:
    kd = KD.default_path()
    kd_hash, commit = sha256(kd), git_commit()
    now = dt.datetime.now().isoformat(timespec="seconds")
    rows = []
    for sec, bases in sections(include_processed):
        for base in bases:
            for p in files_in(base):
                st = p.stat()
                rows.append({"구분": sec, "경로": label(p), "크기": st.st_size, "sha256": sha256(p),
                             "수정시각": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                             "기록일시": now, "키워드사전": kd.name, "키워드사전_sha256": kd_hash, "git_commit": commit})
    return pd.DataFrame(rows, columns=["구분", "경로", "크기", "sha256", "수정시각", "기록일시",
                                       "키워드사전", "키워드사전_sha256", "git_commit"])


def verify() -> int:
    if not LOG.exists():
        print(f"{LOG} 가 없습니다")
        return 2
    rec = pd.read_csv(LOG, encoding="utf-8-sig")
    bad = 0
    for r in rec.itertuples():
        p = resolve(r.경로)
        if not p.exists():
            print("없음  ", r.경로)
            bad += 1
        elif sha256(p) != r.sha256:
            print("다름  ", r.경로)
            bad += 1
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
