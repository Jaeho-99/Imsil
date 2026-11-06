# -*- coding: utf-8 -*-
"""[수집] 네이버 플레이스 리뷰 수집 — 34개소 수집기를 그대로 호출한다.

src/collect/naver_reviews.py 의 crawl_place()·save() 를 고치지 않고 불러 쓰고,
대상 장소만 config.py 값으로 바꾼다. 저장 위치는 34개소 수집과 같은 output/collect/naver/ 이다.

  출력  output/collect/naver/{관광지명}_naver_reviews.csv   (작성자 닉네임 포함 → git 제외)
        output/collect/naver/{place_id}_raw.json             (API 응답 원본)
        output/collect/naver/{관광지명}_수집정보.json         (수집 시각 — 연도 없는 날짜 해석용)

실행 (네이버에 접속 가능한 PC에서)
    python src/new_sites/collect_naver.py                      # config.TARGETS 전체
    python src/new_sites/collect_naver.py 오수의견국민여가캠핑장   # 이름으로 골라서
중간에 막히면 받은 데까지 {place_id}_raw.json 에 남고, 다시 실행하면 이어받는다.
"""
import json
import random
import sys
import time
from datetime import datetime

import requests

from common import config

sys.path.insert(0, str(config.COLLECT_SRC))
import naver_reviews as ns  # noqa: E402


def main():
    pick = set(sys.argv[1:])
    unknown = pick - set(config.TARGET_NAMES)
    if unknown:
        sys.exit(f"config.TARGETS 에 없는 이름: {', '.join(unknown)}")
    todo = [t for t in config.TARGETS if t.get("naver_place_id") and (not pick or t["name"] in pick)]
    missing = [t["name"] for t in config.TARGETS
               if not t.get("naver_place_id") and (not pick or t["name"] in pick)]
    if missing:
        print(f"[경고] naver_place_id 가 비어 있어 건너뜁니다: {', '.join(missing)}")
        print("       config.py 의 TARGETS 에 네이버 지도 URL의 /place/{숫자} 를 넣어 주세요.")
    if not todo:
        sys.exit("수집할 장소가 없습니다.")

    ns.OUT_DIR = config.RAW_NAVER
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
