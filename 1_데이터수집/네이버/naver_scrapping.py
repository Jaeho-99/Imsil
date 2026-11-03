"""
네이버 플레이스 방문자 리뷰 수집기 (다중 장소 / 운영용)

PHASE 2 헤더 이등분 실험 결과 반영 (2026-08 검증)
  - cookie, x-wtm-ncaptcha-token 불필요 → 로그인/토큰 갱신 없이 동작
  - sec-ch-ua*, sec-fetch-*, priority 필수 → 없으면 405 (봇 차단)
  - size 상한: 50 OK / 100 은 null 반환

2026-11 수정 (네이버 쪽 변경 대응)
  - QUERY 에서 `userIdno` 필드 삭제 → 스키마에서 빠져 400 GRAPHQL_VALIDATION_FAILED 의 원인
  - 요청 헤더에 origin·referer·x-wtm-graphql(장소 ID를 담은 base64 JSON) 추가,
    Client Hints 를 Chrome 152 / Windows 값으로 갱신
  - cidList 추출 실패 대비: CID_OVERRIDE 에 브라우저에서 확인한 값을 넣을 수 있다
  - 명령행에 장소 ID 를 주면 그 장소만 수집
  - 숙박·캠핑장처럼 /place/ 가 아닌 업종 페이지(/accommodation/ 등)로 넘어가는 곳은
    BUSINESS_TYPE 에 업종을 적는다. businessType·referer·x-wtm-graphql 에 같이 쓰인다.
  - 2026-11 부터 405 가 헤더 문제가 아니라 요청 속도 차단으로도 나온다(같은 헤더로 1페이지 성공 후
    2페이지에서 405). 요청 간격을 늘렸고, 405 를 받으면 그 자리에서 멈추고 저장한다(재시도하지 않음).
    시간을 두고 다시 실행하면 output/{ID}_raw.json 의 last_cursor 부터 이어받는다.

사용법
  PLACE_IDS 에 수집할 장소 ID를 넣고 실행.
  장소 ID는 지도 URL의 /place/{숫자} 부분.

    python naver_scrapping.py                       # PLACE_IDS 전체
    python naver_scrapping.py 13491702 2006533162   # 지정한 장소만
"""

import base64
import csv
import json
import random
import re
import sys
import time
from pathlib import Path

import requests

# ══════════════════════════════════════════════════════════
PLACE_IDS = [
    "1208503663",   # 1.도화지 도예문화원
    "1029752338",   # 2.세심자연휴양림
    "1281789019",   # 3.임실치즈마을
    "1514459962",   # 4.임실치즈테마파크
    "31679045",     # 5.전북119안전체험관
    "13338277",     # 6.전북종합사격장
    "1637440800",   # 7.청소년수련원
    "17660144",     # 8.필봉농악전수교육관
    "11526227",     # 9.국립 임실호국원
    "37766238",     # 10.섬진강댐 물문화관
    "12442513",     # 11.소충사
    "1160065525",   # 12.옥정호출렁다리
    "13374614",     # 13.전주샹그릴라CC
    "11491834",     # 14.옥정호
    "13346280",     # 15.사선대관광지
    "1962656265",   # 16.임실역
    "1671220194",   # 17.오수역
    "13519814",     # 18.임실시외버스터미널
    "13302059",     # 19.국사봉전망대
    "11636501",     # 20.관촌역
    "1486494459",   # 21.붕어섬생태공원
    "1925803749",   # 22.요산공원
    "17655687",     # 23.오수공용버스터미널
    "17413446",     # 24.관촌시외버스터미널
    "13345918",     # 25.임실전통시장
    "17658593",     # 26.사선대조각공원
    "17655364",     # 27.오수의견공원
    "1705972994",   # 28.성수산왕의숲자연휴양림
    "17410534",     # 29.상이암
    # "",           # 30.옥정호작약꽃밭 -> 네이버 플레이스에 없음.
    # "",           # 31.섬진강자전거길인증센터 -> 네이버 플레이스에 없음.
    "17658791",     # 32.관촌시장
    "17659891",     # 33.강진공용버스터미널
    "1753061067",   # 34.옥정호전망대
    "13491702",     # 35.성수산 (2026-11 추가)
    "2006533162",   # 36.오수의견국민여가캠핑장 (2026-11 추가)
]

# place_id → 관광지명 (파일명/place_name 컬럼에 사용)
PLACE_NAMES = {
    "1208503663": "도화지 도예문화원",
    "1029752338": "세심자연휴양림",
    "1281789019": "임실치즈마을",
    "1514459962": "임실치즈테마파크",
    "31679045": "전북119안전체험관",
    "13338277": "전북종합사격장",
    "1637440800": "청소년수련원",
    "17660144": "필봉농악전수교육관",
    "11526227": "국립 임실호국원",
    "37766238": "섬진강댐 물문화관",
    "12442513": "소충사",
    "1160065525": "옥정호출렁다리",
    "13374614": "전주샹그릴라CC",
    "11491834": "옥정호",
    "13346280": "사선대관광지",
    "1962656265": "임실역",
    "1671220194": "오수역",
    "13519814": "임실시외버스터미널",
    "13302059": "국사봉전망대",
    "11636501": "관촌역",
    "1486494459": "붕어섬생태공원",
    "1925803749": "요산공원",
    "17655687": "오수공용버스터미널",
    "17413446": "관촌시외버스터미널",
    "13345918": "임실전통시장",
    "17658593": "사선대조각공원",
    "17655364": "오수의견공원",
    "1705972994": "성수산왕의숲자연휴양림",
    "17410534": "상이암",
    "17658791": "관촌시장",
    "17659891": "강진공용버스터미널",
    "1753061067": "옥정호전망대",
    "13491702": "성수산",
    "2006533162": "오수의견국민여가캠핑장",
}

# HTML 에서 cidList 를 못 찾을 때 쓸 값. 브라우저 개발자도구 Network 탭의
# getVisitorReviews 요청 Payload 에 있는 "cidList" 를 그대로 옮긴다.
CID_OVERRIDE = {
    "13491702": ["222117", "222118", "222132"],   # 성수산 (2026-11-03 확인)
}

# 업종이 'place' 가 아닌 장소. 브라우저에서 m.place.naver.com/place/{ID} 를 열었을 때
# 넘어가는 주소의 업종 부분(예: /accommodation/{ID}/home)을 적는다.
BUSINESS_TYPE = {
    "2006533162": "accommodation",   # 오수의견국민여가캠핑장 (캠핑장, 객실예약)
}

OUT_DIR = Path("output")
SIZE = 50                  # 검증된 최대치
SLEEP_RANGE = (4.0, 8.0)   # 페이지 간 (2026-08: 1.5~3.0 → 2026-11 차단이 잦아 늘림)
PLACE_SLEEP = (20.0, 40.0) # 장소 간
MAX_PAGES = 200
MAX_RETRY = 3
BLOCK_WAIT = 60            # 429 때 첫 대기(초). 시도마다 배로 늘린다
RESUME = True              # 이전 실행의 {ID}_raw.json 이 있으면 last_cursor 부터 이어받기
# ══════════════════════════════════════════════════════════

ENDPOINT = "https://api.place.naver.com/place/graphql"

# ★ Client Hints 계열은 제거하면 405. 임의로 지우지 말 것.
HEADERS = {
    "accept": "*/*",
    "accept-language": "ko",
    "content-type": "application/json",
    "priority": "u=1, i",
    "sec-ch-ua": '"Chromium";v="152", "Not?A_Brand";v="24", "Google Chrome";v="152"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
}

QUERY = """query getVisitorReviews($input: VisitorReviewsInput) {
  visitorReviews(input: $input) {
    items {
      id
      cursor
      reviewId
      rating
      author { id nickname objectId url
        review { totalCount imageCount avgRating __typename } __typename }
      body
      thumbnail
      media { type thumbnail videoId __typename }
      status
      visitCount
      viewCount
      visited
      created
      originType
      language
      businessName
      votedKeywords { code iconCode name __typename }
      nickname
      visitCategories { code name keywords { code name __typename } __typename }
      representativeVisitDateTime
      __typename
    }
    total
    __typename
  }
}"""


def fetch_place_meta(session: requests.Session, place_id: str) -> dict:
    """장소 HTML에서 이름과 cidList 추출. 실패해도 수집은 진행."""
    url = f"https://m.place.naver.com/{btype(place_id)}/{place_id}/review/visitor"
    meta = {"name": None, "cid_list": []}
    try:
        r = session.get(url, headers={"user-agent": HEADERS["user-agent"]},
                        timeout=15)
        if r.status_code != 200:
            return meta
        html = r.text
        for key in ("defaultCategoryCodeList", "categoryCodeList", "cidList"):
            m = re.search(r'"%s"\s*:\s*(\[[^\]]*\])' % key, html)
            if m:
                cids = [str(x) for x in json.loads(m.group(1))]
                if cids:
                    meta["cid_list"] = cids
                    break
        m = re.search(r'id="og:title"[^>]*content="([^"]+)"', html)
        if m:
            meta["name"] = m.group(1).replace(" : 네이버", "").strip()
    except Exception:
        pass
    return meta


def btype(place_id):
    return BUSINESS_TYPE.get(str(place_id), "place")


def build_payload(place_id, cid_list, size, after):
    inp = {
        "businessId": place_id,
        "businessType": btype(place_id),
        "item": "0",
        "bookingBusinessId": None,
        "size": size,
        "isPhotoUsed": False,
        "includeContent": True,
        "getUserStats": True,
        "includeReceiptPhotos": True,
        "cidList": cid_list,
        "getReactions": True,
        "getTrailer": True,
    }
    if after:
        inp["after"] = after
    return [{"operationName": "getVisitorReviews",
             "variables": {"input": inp}, "query": QUERY}]


def place_headers(place_id):
    """장소마다 달라지는 헤더. 브라우저가 보내는 값과 같은 형식."""
    h = dict(HEADERS)
    h["origin"] = "https://m.place.naver.com"
    t = btype(place_id)
    h["referer"] = f"https://m.place.naver.com/{t}/{place_id}/review/visitor"
    h["x-wtm-graphql"] = base64.urlsafe_b64encode(json.dumps(
        {"arg": str(place_id), "type": t, "source": "place"},
        separators=(",", ":")).encode()).decode().rstrip("=")
    return h


def request(session, place_id, cid_list, size, after):
    """(result_or_None, message). 429는 백오프 후 재시도."""
    msg = ""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            r = session.post(
                ENDPOINT, headers=place_headers(place_id),
                json=build_payload(place_id, cid_list, size, after),
                timeout=20, allow_redirects=False,
            )
        except Exception as e:
            msg = f"NETWORK: {type(e).__name__}"
            time.sleep(3 * attempt)
            continue

        if r.status_code == 429:
            msg = "429 — 요청 속도 제한. 시간을 두고 다시 실행하면 이어받습니다."
            if attempt < MAX_RETRY:
                wait = BLOCK_WAIT * 2 ** (attempt - 1)
                print(f"        429 rate limit — {wait}s 대기 후 재시도 "
                      f"({attempt}/{MAX_RETRY - 1})")
                time.sleep(wait)
            continue

        if r.status_code == 405:
            body = re.sub(r"\s+", " ", r.text)[:150]
            print(f"        응답 405: {body or '(본문 없음)'}")
            return None, ("405 — 차단 (헤더 부족 또는 요청 속도). "
                          "시간을 두고 다시 실행하면 이어받습니다.")

        if r.status_code != 200:
            return None, f"HTTP {r.status_code}: {r.text[:200]}"

        try:
            d = r.json()
            if isinstance(d, list):
                d = d[0]
            if "errors" in d:
                return None, "GRAPHQL: " + json.dumps(
                    d["errors"], ensure_ascii=False)[:200]
            res = d["data"]["visitorReviews"]
            if res is None:
                return None, "visitorReviews=null (size 초과 가능)"
            return res, ""
        except Exception as e:
            return None, f"PARSE: {e} / {r.text[:200]}"

    return None, msg


def crawl_place(session, place_id):
    meta = fetch_place_meta(session, place_id)
    name = PLACE_NAMES.get(place_id) or meta["name"] or place_id
    cid_list = meta["cid_list"] or CID_OVERRIDE.get(place_id, [])
    print(f"\n▶ {name}  ({place_id})")
    src = "HTML" if meta["cid_list"] else ("CID_OVERRIDE" if cid_list else "")
    print(f"  cidList: {f'{cid_list} ({src})' if cid_list else '추출 실패 — 빈 값으로 진행'}")

    reviews, seen = [], set()
    after, total, cursor = None, None, None

    prev = OUT_DIR / f"{place_id}_raw.json"
    if RESUME and prev.exists():
        old = json.loads(prev.read_text(encoding="utf-8"))
        reviews = old.get("reviews") or []
        seen = {x["id"] for x in reviews}
        total = old.get("total")
        cursor = after = old.get("last_cursor")
        if total and len(reviews) >= total:
            print(f"  이전 수집 완료 {len(reviews)}/{total}건 — 건너뜀 "
                  f"(새로 받으려면 {prev.name} 삭제)")
            return old
        if after:
            print(f"  이전 수집 {len(reviews)}/{total}건에서 이어받기")
        else:
            reviews, seen = [], set()

    for page in range(1, MAX_PAGES + 1):
        res, msg = request(session, place_id, cid_list, SIZE, after)
        if res is None:
            print(f"  [{page:>3}] 중단: {msg}")
            break

        if total is None:
            total = res.get("total")
            print(f"  총 {total}건")

        items = res.get("items") or []
        if not items:
            break

        new = [x for x in items if x.get("id") not in seen]
        seen.update(x["id"] for x in new)
        reviews.extend(new)
        cursor = items[-1].get("cursor")

        print(f"  [{page:>3}] +{len(new):>3}  누적 {len(reviews):>4}/{total}")

        if not new or (total and len(reviews) >= total) or not cursor:
            break
        after = cursor
        time.sleep(random.uniform(*SLEEP_RANGE))

    return {"place_id": place_id, "name": name, "total": total,
            "reviews": reviews, "last_cursor": cursor}


def save(result):
    OUT_DIR.mkdir(exist_ok=True)
    pid = result["place_id"]

    with open(OUT_DIR / f"{pid}_raw.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    cols = ["place_id", "place_name", "id", "reviewId", "nickname", "rating",
            "body", "visited", "created", "visitCount", "originType",
            "keywords", "visitCategories", "mediaCount"]
    csv_dir = OUT_DIR / "naver"
    csv_dir.mkdir(exist_ok=True)
    with open(csv_dir / f"{result['name']}_naver_reviews.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in result["reviews"]:
            kws = [k.get("name") for k in (r.get("votedKeywords") or [])]
            cats = [k.get("name")
                    for c in (r.get("visitCategories") or [])
                    for k in (c.get("keywords") or [])]
            w.writerow({
                "place_id": pid,
                "place_name": result["name"],
                "id": r.get("id"),
                "reviewId": r.get("reviewId"),
                "nickname": (r.get("author") or {}).get("nickname"),
                "rating": r.get("rating"),
                "body": (r.get("body") or "").replace("\n", " ").strip(),
                "visited": r.get("visited"),
                "created": r.get("created"),
                "visitCount": r.get("visitCount"),
                "originType": r.get("originType"),
                "keywords": "|".join(x for x in kws if x),
                "visitCategories": "|".join(x for x in cats if x),
                "mediaCount": len(r.get("media") or []),
            })


def main():
    session = requests.Session()
    summary = []

    targets = sys.argv[1:] or PLACE_IDS
    for i, pid in enumerate(targets, 1):
        print(f"\n{'=' * 58}\n[{i}/{len(targets)}]")
        try:
            result = crawl_place(session, pid)
        except KeyboardInterrupt:
            print("\n중단됨")
            break
        except Exception as e:
            print(f"  실패: {type(e).__name__}: {e}")
            continue

        save(result)
        n = len(result["reviews"])
        body_n = sum(1 for r in result["reviews"] if (r.get("body") or "").strip())
        ok = "완료" if result["total"] and n >= result["total"] else "부분"
        summary.append((pid, result["name"], n, result["total"], body_n, ok))
        print(f"  저장: output/naver/{result['name']}_naver_reviews.csv  ({ok})")

        if i < len(targets):
            time.sleep(random.uniform(*PLACE_SLEEP))

    print(f"\n{'=' * 58}\n요약")
    print(f"{'placeId':<13}{'이름':<22}{'수집':>6}{'전체':>6}{'본문':>6}  상태")
    for pid, name, n, total, body_n, ok in summary:
        disp = (name[:18] + "…") if len(name) > 19 else name
        print(f"{pid:<13}{disp:<22}{n:>6}{total or 0:>6}{body_n:>6}  {ok}")


if __name__ == "__main__":
    main()