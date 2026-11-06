# -*- coding: utf-8 -*-
"""[수집 보조] 네이버 수집이 차단(캡차·405)으로 멈췄을 때, 몇 시간 간격으로 다시 시도해 이어받는다.

사람이 몇 시간 뒤 collect_naver.py 를 다시 돌리는 것과 같다. 시도 사이 간격을 길게 두고
(기본 3시간, 실패할 때마다 늘림) 시도 횟수에도 상한을 둬서, 차단 중에 요청을 반복하지 않는다.
다 받으면 바로 끝난다. 진행 기록은 output/collect/naver/재시도_기록.txt 에 남는다.

실행 (창을 열어 둔 채로 두면 된다. PC 가 절전 모드에 들어가지 않게 해 둘 것)
    python src/new_sites/retry_naver.py 오수의견국민여가캠핑장
    python src/new_sites/retry_naver.py 오수의견국민여가캠핑장 --first-wait 2 --interval 3 --max-tries 5
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from common import config

HERE = Path(__file__).resolve().parent
LOG = config.RAW_NAVER / "재시도_기록.txt"


def log(msg: str):
    line = f"[{datetime.now():%Y-%m-%d %H:%M}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def progress(pid: str):
    p = config.RAW_NAVER / f"{pid}_raw.json"
    if not p.exists():
        return 0, None
    d = json.loads(p.read_text(encoding="utf-8"))
    return len(d.get("reviews") or []), d.get("total")


def sleep_hours(h: float):
    log(f"다음 시도: {datetime.now() + timedelta(hours=h):%m-%d %H:%M} ({h:g}시간 뒤)")
    time.sleep(h * 3600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+", help="config.TARGETS 의 관광지 이름")
    ap.add_argument("--first-wait", type=float, default=3, help="첫 시도까지 기다릴 시간(시간)")
    ap.add_argument("--interval", type=float, default=3, help="실패 뒤 다음 시도까지(시간). 실패마다 1.5배")
    ap.add_argument("--max-tries", type=int, default=5)
    args = ap.parse_args()

    ids = {t["name"]: str(t["naver_place_id"]) for t in config.TARGETS if t.get("naver_place_id")}
    unknown = [n for n in args.names if n not in ids]
    if unknown:
        sys.exit(f"config.TARGETS 에 없는 이름: {', '.join(unknown)}")
    todo = list(args.names)
    for n in todo:
        got, total = progress(ids[n])
        log(f"시작 — {n}: 현재 {got}/{total}건")

    wait = args.interval
    sleep_hours(args.first_wait)
    for k in range(1, args.max_tries + 1):
        log(f"시도 {k}/{args.max_tries}: {', '.join(todo)}")
        subprocess.run([sys.executable, str(HERE / "collect_naver.py"), *todo], cwd=config.REPO)
        left = []
        for n in todo:
            got, total = progress(ids[n])
            done = bool(total) and got >= total
            log(f"  {n}: {got}/{total}건 {'완료' if done else '미완료'}")
            if not done:
                left.append(n)
        if not left:
            log("모두 완료. 다음은 python src/new_sites/build_dataset.py")
            return
        todo = left
        if k < args.max_tries:
            sleep_hours(wait)
            wait *= 1.5
    log(f"시도 {args.max_tries}회 후에도 미완료: {', '.join(todo)} — HAR 방법(src/new_sites/import_har.py)을 쓰세요.")


if __name__ == "__main__":
    main()
