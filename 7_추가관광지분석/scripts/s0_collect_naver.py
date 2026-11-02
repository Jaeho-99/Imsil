# -*- coding: utf-8 -*-
"""[0단계] 네이버 플레이스 리뷰 수집 — 34개소 수집기를 그대로 호출한다.

1_데이터수집/네이버/naver_scrapping.py 의 crawl_place()·save() 를 고치지 않고 불러 쓰고,
대상 장소와 저장 위치만 config.py 값으로 바꾼다.

  출력  data/raw/naver/{관광지명}_naver_reviews.csv   (작성자 닉네임 포함 → git 제외)
        data/raw/{place_id}_raw.json                   (API 응답 원본)
        data/raw/naver/{관광지명}_수집정보.json         (수집 시각 — 연도 없는 날짜 해석용)

실행 (네이버에 접속 가능한 PC에서)
    python scripts/s0_collect_naver.py
"""
import json
import random
import sys
import time
from datetime import datetime

import requests

from common import config

sys.path.insert(0, str(config.REPO / "1_데이터수집" / "네이버"))
import naver_scrapping as ns  # noqa: E402


def main():
    todo = [t for t in config.TARGETS if t.get("naver_place_id")]
    missing = [t["name"] for t in config.TARGETS if not t.get("naver_place_id")]
    if missing:
        print(f"[경고] naver_place_id 가 비어 있어 건너뜁니다: {', '.join(missing)}")
        print("       config.py 의 TARGETS 에 네이버 지도 URL의 /place/{숫자} 를 넣어 주세요.")
    if not todo:
        sys.exit("수집할 장소가 없습니다.")

    ns.OUT_DIR = config.RAW_DIR
    ns.PLACE_NAMES = {t["naver_place_id"]: t["name"] for t in todo}
    config.RAW_NAVER.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    for i, t in enumerate(todo, 1):
        pid = str(t["naver_place_id"])
        started = datetime.now()
        result = ns.crawl_place(session, pid)
        ns.save(result)
        meta = {"place": t["name"], "place_id": pid, "total": result["total"],
                "collected": len(result["reviews"]),
                "collected_at": started.strftime("%Y-%m-%d %H:%M:%S")}
        (config.RAW_NAVER / f"{t['name']}_수집정보.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  저장: {t['name']} {meta['collected']}/{meta['total']}건")
        if i < len(todo):
            time.sleep(random.uniform(*ns.PLACE_SLEEP))


if __name__ == "__main__":
    main()
