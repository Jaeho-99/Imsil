# -*- coding: utf-8 -*-
"""[0단계 보조] 브라우저에서 직접 본 네이버 리뷰를 HAR 파일에서 꺼내 수집 원본으로 저장한다.

s0_collect_naver.py 가 캡차·405 로 막힐 때, 사람이 브라우저에서 리뷰 탭을 열고 '더보기'를 눌러
본 내용을 개발자도구에서 HAR 로 내보내면 이 스크립트가 그 안의 getVisitorReviews 응답만 읽는다.
응답은 수집기와 같은 GraphQL 형식이므로 naver_scrapping.save() 로 같은 CSV 가 나온다.
이미 수집기로 받은 일부(data/raw/{ID}_raw.json)가 있으면 합친다(리뷰 id 기준 중복 제거).

HAR 만들기 (크롬)
  1. 개발자도구(F12) → Network 탭, 필터 칸에 graphql
  2. m.place.naver.com/{업종}/{ID}/review/visitor 에서 리뷰 맨 아래 '더보기'를 끝까지 누른다
  3. Network 목록 위 다운로드 아이콘(Export HAR (sanitized)...) → 저장
     sanitized 로 저장하면 쿠키·인증 헤더가 빠진다. 이 스크립트는 요청 Payload 와 응답 본문만 읽는다.

실행
    python scripts/s0_import_har.py 다운로드\\m.place.naver.com.har [더 있으면 계속]
"""
from __future__ import annotations

import base64
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from common import config

sys.path.insert(0, str(config.REPO / "1_데이터수집" / "네이버"))
import naver_scrapping as ns  # noqa: E402


def entry_text(content: dict) -> str:
    t = content.get("text") or ""
    if content.get("encoding") == "base64":
        t = base64.b64decode(t).decode("utf-8", "replace")
    return t


def read_har(path: Path):
    """(place_id, items, total) 를 응답마다 낸다."""
    har = json.loads(path.read_text(encoding="utf-8-sig"))
    for e in har.get("log", {}).get("entries", []):
        req = e.get("request", {})
        if "graphql" not in req.get("url", "") or req.get("method") != "POST":
            continue
        try:
            payload = json.loads((req.get("postData") or {}).get("text") or "[]")
            resp = json.loads(entry_text(e.get("response", {}).get("content", {})) or "[]")
        except json.JSONDecodeError:
            continue
        payload = payload if isinstance(payload, list) else [payload]
        resp = resp if isinstance(resp, list) else [resp]
        for q, r in zip(payload, resp):
            if (q or {}).get("operationName") != "getVisitorReviews":
                continue
            pid = str(((q.get("variables") or {}).get("input") or {}).get("businessId") or "")
            vr = ((r or {}).get("data") or {}).get("visitorReviews")
            if pid and vr:
                yield pid, vr.get("items") or [], vr.get("total")


def main():
    files = [Path(a) for a in sys.argv[1:]]
    if not files:
        sys.exit(__doc__)
    names = {str(t["naver_place_id"]): t["name"] for t in config.TARGETS if t.get("naver_place_id")}

    found = defaultdict(dict)
    totals = {}
    for f in files:
        n = 0
        for pid, items, total in read_har(f):
            n += 1
            if total is not None:
                totals[pid] = total
            for it in items:
                if it.get("id"):
                    found[pid].setdefault(it["id"], it)
        print(f"  {f.name}: getVisitorReviews 응답 {n}개")
    if not found:
        sys.exit("HAR 안에 getVisitorReviews 응답이 없습니다. 리뷰 탭에서 '더보기'를 누른 뒤 저장했는지 확인하세요.")

    ns.OUT_DIR = config.RAW_DIR
    config.RAW_NAVER.mkdir(parents=True, exist_ok=True)
    for pid, got in found.items():
        name = names.get(pid)
        if not name:
            print(f"  [건너뜀] {pid}: config.TARGETS 에 없는 장소")
            continue
        prev = config.RAW_DIR / f"{pid}_raw.json"
        old = json.loads(prev.read_text(encoding="utf-8")) if prev.exists() else {}
        merged = {x["id"]: x for x in old.get("reviews") or []}
        n_old = len(merged)
        for k, v in got.items():
            merged.setdefault(k, v)
        total = totals.get(pid) or old.get("total")
        result = {"place_id": pid, "name": name, "total": total,
                  "reviews": list(merged.values()), "last_cursor": old.get("last_cursor"),
                  "method": "har"}
        ns.save(result)
        info = config.RAW_NAVER / f"{name}_수집정보.json"
        meta = json.loads(info.read_text(encoding="utf-8")) if info.exists() else {}
        meta.update({"place": name, "place_id": pid, "total": total,
                     "collected": len(merged), "har_files": [f.name for f in files]})
        meta.setdefault("collected_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        info.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        ok = "완료" if total and len(merged) >= total else "부분"
        print(f"  {name}: 기존 {n_old} + HAR {len(got)} → {len(merged)}/{total}건 ({ok})")


if __name__ == "__main__":
    main()
