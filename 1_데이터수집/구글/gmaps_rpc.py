"""
구글 지도 리뷰 RPC 응답 파서 (gmaps_rpc.py)

네트워크를 타지 않는 순수 함수 모듈입니다. 테스트가 쉽도록 분리했습니다.

■ 대상 응답
  POST /maps/_/MapsWizUi/data/batchexecute?rpcids=qv9Egd
  → /MapsUgcPostService.ListUgcPosts

■ 응답 구조 (2026-08-11 실측)
  batchexecute 는 ")]}'" 뒤에 "길이\\nJSON" 청크가 반복되는 형식입니다.
  길이 헤더는 바이트 단위라 한글이 섞이면 문자 인덱스와 어긋납니다.
  그래서 길이를 신뢰하지 않고 raw_decode 로 JSON 을 하나씩 끊어 읽습니다.

  wrb.fr 프레임의 [2] 를 다시 JSON 파싱하면:
    inner[1]  다음 커서
    inner[2]  리뷰 목록

  review = inner[2][i][0]
    [0]           리뷰 ID          (DOM 의 data-review-id 와 동일)
    [1][2]        작성 시각        마이크로초 (절대 시각)
    [1][3]        수정 시각        마이크로초. 수정 이력이 없으면 작성 시각과 근접
    [1][6]        상대 날짜        "3년 전" / "수정일: 3년 전"
    [1][4][5][0]  작성자명
    [1][4][5][3]  작성자 ID
    [1][4][5][5]  작성자 총 리뷰수
    [2][0][0]     평점             1~5
    [2][6]        구조화 속성 목록   화면에서 '자세히 보기'로 펼쳐야 보이는 항목
                    [i][5]           라벨 ("방문일" / "대기 시간" / "예약 권장")
                    [i][2][0][0][1]  값   ("주말" / "대기 시간 없음" / "아니요")
    [2][15][0][0] 본문             전문 (잘리지 않음)

  빈 응답은 [null,null,null,null,null,true] 형태로 옵니다.
"""

import json
from datetime import datetime, timezone

RPC_NAME = "/MapsUgcPostService.ListUgcPosts"


def at(obj, path):
    """중첩 리스트 안전 접근. 경로가 끊기면 None 을 반환합니다."""
    cur = obj
    for k in path:
        if not isinstance(cur, list) or k >= len(cur):
            return None
        cur = cur[k]
    return cur


def parse_batchexecute(text, rpc_name=RPC_NAME):
    """batchexecute 응답에서 해당 RPC 의 inner 페이로드를 꺼냅니다.

    찾지 못하면 None. 빈 결과여도 리스트를 그대로 돌려주므로,
    호출부에서 review 개수로 판단하면 됩니다.
    """
    if not text:
        return None
    body = text.lstrip()
    if body.startswith(")]}'"):
        body = body[4:]

    dec = json.JSONDecoder()
    idx = 0
    while idx < len(body):
        while idx < len(body) and body[idx] not in "[{":
            idx += 1
        if idx >= len(body):
            break
        try:
            frame, end = dec.raw_decode(body, idx)
        except json.JSONDecodeError:
            break
        idx = end

        if not isinstance(frame, list):
            continue
        for g in frame:
            if (
                isinstance(g, list)
                and len(g) > 2
                and g[0] == "wrb.fr"
                and g[1] == rpc_name
                and isinstance(g[2], str)
            ):
                try:
                    return json.loads(g[2])
                except json.JSONDecodeError:
                    return None
    return None


def to_iso(micros):
    """마이크로초 타임스탬프 → 로컬 시각 문자열."""
    if not isinstance(micros, (int, float)) or micros <= 0:
        return ""
    return (
        datetime.fromtimestamp(micros / 1_000_000, tz=timezone.utc)
        .astimezone()
        .strftime("%Y-%m-%d %H:%M:%S")
    )


# 구조화 속성 중 전용 컬럼으로 뺄 라벨.
# 라벨은 장소 유형에 따라 달라집니다(음식점이면 음식·서비스·분위기 등).
# 여기 없는 라벨은 버리지 않고 '기타속성' 컬럼에 담습니다.
ATTR_COLUMNS = {
    "방문일": "방문일",       # 주말 / 평일 / 공휴일
    "대기 시간": "대기시간",
    "예약 권장": "예약권장",   # 예 / 아니요 / 모르겠음
}


def parse_attributes(rv):
    """리뷰의 구조화 속성을 {라벨: 값} 으로 만듭니다.

    화면에서는 '자세히 보기'를 눌러야 보이는 항목들인데,
    RPC 응답에는 처음부터 들어 있어 별도 클릭이 필요 없습니다.
    """
    out = {}
    for item in (at(rv, [2, 6]) or []):
        label = at(item, [5])
        value = at(item, [2, 0, 0, 1])
        if isinstance(label, str) and isinstance(value, str) and label and value:
            out[label] = value
    return out


def extract_reviews(inner, place_name="", feature_id="", sort_name=""):
    """inner 페이로드에서 리뷰 레코드 목록을 만듭니다."""
    rows = []
    for wrapper in (at(inner, [2]) or []):
        rv = at(wrapper, [0])
        if not isinstance(rv, list) or not rv or not rv[0]:
            continue
        text = at(rv, [2, 15, 0, 0]) or ""
        attrs = parse_attributes(rv)
        extra = "|".join(
            f"{k}={v}" for k, v in sorted(attrs.items()) if k not in ATTR_COLUMNS
        )
        rows.append(
            {
                "관광지명": place_name,
                "플랫폼": "구글",
                "리뷰ID": rv[0],
                "작성자닉네임": at(rv, [1, 4, 5, 0]) or "",
                "작성자ID": at(rv, [1, 4, 5, 3]) or "",
                "작성자총리뷰수": at(rv, [1, 4, 5, 5]),
                "평점": at(rv, [2, 0, 0]),
                "작성일": to_iso(at(rv, [1, 2])),
                # 구글의 '최신순'은 작성일이 아니라 수정일 기준입니다.
                # 두 값이 크게 벌어진 행은 오래전 리뷰를 최근에 고친 경우이므로,
                # 시계열 분석에서 어느 쪽을 쓸지 반드시 정해야 합니다.
                "수정일": to_iso(at(rv, [1, 3])),
                "수정여부": "수정" if "수정" in (at(rv, [1, 6]) or "") else "",
                "작성일_상대표기": at(rv, [1, 6]) or "",
                "리뷰본문": text,
                "본문길이": len(text),
                **{col: attrs.get(label, "") for label, col in ATTR_COLUMNS.items()},
                "기타속성": extra,
                "정렬기준": sort_name,
                "feature_id": feature_id,
                "수집시각": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return rows


def next_cursor(inner):
    return at(inner, [1])
