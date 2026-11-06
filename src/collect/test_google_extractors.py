"""
google_reviews.py 파싱 로직 자체 검증 (test_extractors.py)

구글에 접속하지 않고, 로컬 HTML 픽스처만으로 추출 로직을 검사합니다.

■ 왜 필요한가
  수집이 실패했을 때 원인은 둘 중 하나입니다.
    (가) 구글이 DOM 구조를 바꿔서 셀렉터가 안 맞음
    (나) 내 파싱 코드 자체가 틀림
  이 테스트가 통과하면 (나)가 배제되므로, 남은 건 (가)입니다.
  그때는 google_reviews.py --dump 로 실제 DOM 을 떠서 셀렉터만 고치면 됩니다.

■ 실행
  python src/collect/test_google_extractors.py
"""

import json
import sys

from playwright.sync_api import sync_playwright

from gmaps_rpc import extract_reviews, next_cursor, parse_batchexecute, to_iso
from google_reviews import (
    SEL_CARD,
    extract_cards,
    find_scroll_container,
    first_visible,
    rating_from_label,
)

# 실제 Google Maps 리뷰 패널의 구조를 재현한 픽스처.
# 스크롤 컨테이너(overflow-y:auto + 내용 넘침) 안에 리뷰 카드가 들어 있는 형태입니다.
FIXTURE = """
<!doctype html><html lang="ko"><body style="margin:0">
<div id="pane" style="height:300px;overflow-y:auto;width:500px">
  <div style="height:2000px">

    <div class="jftiEf fontBodyMedium" data-review-id="REVIEW_A" jsaction="mouseover:pane.review">
      <button class="al6Kxc" data-href="/maps/contrib/111/reviews">
        <div class="d4r55">김철수</div>
      </button>
      <span class="kvMYJc" role="img" aria-label="별표 5개"></span>
      <span class="rsqaWe">2주 전</span>
      <div class="MyEned"><span class="wiI7pd">치즈 만들기 체험이 아이들에게 정말 좋았습니다…더보기</span></div>
    </div>

    <div class="jftiEf fontBodyMedium" data-review-id="REVIEW_B" jsaction="mouseover:pane.review">
      <button class="al6Kxc" data-href="/maps/contrib/222/reviews">
        <div class="d4r55">이영희</div>
      </button>
      <span class="kvMYJc" role="img" aria-label="별표 5개 중 4개"></span>
      <span class="rsqaWe">3개월 전</span>
      <div class="MyEned"><span class="wiI7pd">주차장이 넓어서 편했어요.</span></div>
    </div>

    <!-- 별점만 있고 본문이 없는 리뷰: 유효한 데이터이므로 수집되어야 함 -->
    <div class="jftiEf fontBodyMedium" data-review-id="REVIEW_C" jsaction="mouseover:pane.review">
      <button class="al6Kxc" data-href="/maps/contrib/333/reviews">
        <div class="d4r55">박민수</div>
      </button>
      <span class="kvMYJc" role="img" aria-label="별표 3개"></span>
      <span class="rsqaWe">1년 전</span>
    </div>

    <!-- REVIEW_A 와 같은 ID: 스크롤 중복 노출을 재현. 중복 제거되어야 함 -->
    <div class="jftiEf fontBodyMedium" data-review-id="REVIEW_A" jsaction="mouseover:pane.review">
      <button class="al6Kxc" data-href="/maps/contrib/111/reviews">
        <div class="d4r55">김철수</div>
      </button>
      <span class="kvMYJc" role="img" aria-label="별표 5개"></span>
      <span class="rsqaWe">2주 전</span>
      <div class="MyEned"><span class="wiI7pd">치즈 만들기 체험이 아이들에게 정말 좋았습니다…더보기</span></div>
    </div>

    <!-- 리뷰 카드가 아닌 요소: 수집되면 안 됨 -->
    <div class="someOtherPanel"><span>영업시간 09:00 - 18:00</span></div>

  </div>
</div>
</body></html>
"""

PASSED = []
FAILED = []


def check(name, actual, expected):
    if actual == expected:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name}\n          기대: {expected!r}\n          실제: {actual!r}")


def test_rating_labels():
    """별점 aria-label 표기별 파싱. 언어에 따라 정답 숫자의 위치가 반대입니다."""
    print("\n[1] 별점 라벨 파싱")
    check("한국어 단순 표기 '별표 5개'", rating_from_label("별표 5개"), 5.0)
    check("한국어 'X개 중 Y개' 는 뒤 숫자", rating_from_label("별표 5개 중 4개"), 4.0)
    check("영어 'out of' 는 앞 숫자", rating_from_label("Rated 4.0 out of 5"), 4.0)
    check("소수점 표기", rating_from_label("별표 4.5개"), 4.5)
    check("숫자 없음", rating_from_label("사진 보기"), None)
    check("빈 라벨", rating_from_label(None), None)
    check("범위 밖 값은 버림", rating_from_label("리뷰 52개"), None)


def test_dom_extraction(page):
    print("\n[2] DOM 추출")
    page.set_content(FIXTURE)

    card_loc, card_sel = first_visible(page, SEL_CARD)
    check("리뷰 카드 셀렉터 매칭", card_sel, "div[data-review-id][jsaction]")

    scroller = find_scroll_container(page, card_sel)
    check("스크롤 컨테이너 탐색", scroller is not None, True)
    if scroller is not None:
        check("찾은 컨테이너가 #pane", scroller.evaluate("el => el.id"), "pane")

    seen = set()
    rows, failures, first_error = extract_cards(
        page, seen, "테스트장소", "최신순", "http://test.local"
    )

    check("파싱 예외 0건", (failures, first_error), (0, None))
    check("중복 제외 3건 수집", len(rows), 3)
    check("리뷰가 아닌 요소는 제외", all(r["리뷰ID"].startswith("REVIEW_") for r in rows), True)

    by_id = {r["리뷰ID"]: r for r in rows}
    check("수집된 ID 집합", sorted(by_id), ["REVIEW_A", "REVIEW_B", "REVIEW_C"])

    a = by_id["REVIEW_A"]
    check("작성자 추출", a["작성자닉네임"], "김철수")
    check("평점 추출", a["평점"], 5.0)
    check("작성일 추출", a["작성일_표시"], "2주 전")
    check("본문 말줄임·더보기 제거", a["리뷰본문"], "치즈 만들기 체험이 아이들에게 정말 좋았습니다")
    check("본문길이 계산", a["본문길이"], len(a["리뷰본문"]))
    check("메타데이터 기록", (a["관광지명"], a["정렬기준"]), ("테스트장소", "최신순"))

    check("'X개 중 Y개' 카드 평점", by_id["REVIEW_B"]["평점"], 4.0)
    check("본문 없는 리뷰도 수집", (by_id["REVIEW_C"]["리뷰본문"], by_id["REVIEW_C"]["평점"]), ("", 3.0))

    # 같은 페이지를 다시 긁어도 seen 이 살아 있으면 신규분이 없어야 합니다.
    # 스크롤 정체(stall) 판정이 이 동작에 의존합니다.
    again, _, _ = extract_cards(page, seen, "테스트장소", "최신순", "http://test.local")
    check("동일 seen 재추출 시 신규 0건", len(again), 0)


def test_id_stability(page):
    """리뷰ID 재현성. 연구용 데이터셋의 키라서 실행마다 바뀌면 안 됩니다."""
    print("\n[3] 리뷰ID 재현성")
    page.set_content(FIXTURE)
    first, _, _ = extract_cards(page, set(), "테스트장소", "최신순", "http://test.local")

    page.set_content(FIXTURE)
    second, _, _ = extract_cards(page, set(), "테스트장소", "최신순", "http://test.local")

    check(
        "두 번 추출한 ID 가 동일",
        [r["리뷰ID"] for r in first],
        [r["리뷰ID"] for r in second],
    )


def build_rpc_response():
    """실제 batchexecute 응답 형식을 그대로 재현한 픽스처.

    2026-08-11 캡처본의 구조를 따릅니다. 한글을 일부러 넣어두었습니다 —
    청크 길이 헤더가 바이트 단위라 한글이 섞이면 문자 인덱스와 어긋나는데,
    파서가 길이를 무시하고 raw_decode 로 읽는지 검증하기 위함입니다.
    """
    def attr(label, value):
        """rv[2][6] 항목 하나. 실측 형식은 길이 16 배열입니다."""
        a = [None] * 16
        a[2] = [[[None, value]]]
        a[5] = label
        return a

    def review(rid, author, aid, nrev, rating, micros, rel, text, edited=None, attrs=None):
        rv = [None] * 6
        rv[0] = rid
        meta = [None] * 18
        meta[2] = micros
        meta[3] = edited if edited is not None else micros
        meta[6] = rel
        author_blk = [None] * 6
        inner_author = [None] * 6
        inner_author[0] = author
        inner_author[3] = aid
        inner_author[5] = nrev
        author_blk[5] = inner_author
        meta[4] = author_blk
        rv[1] = meta
        content = [None] * 16
        content[0] = [rating]
        content[6] = [attr(k, v) for k, v in (attrs or {}).items()] or None
        content[15] = [[text]]
        rv[2] = content
        return [rv]

    inner = [
        None,
        "CURSOR_NEXT:70",
        [
            review("REV_1", "김철수", "1111", 501, 5, 1666158286194691,
                   "3년 전", "치즈 체험이 좋았습니다.\n줄바꿈도 그대로 들어옵니다.",
                   attrs={"방문일": "주말", "대기 시간": "대기 시간 없음",
                          "예약 권장": "아니요",
                          # 장소 유형에 따라 나오는 미등록 라벨. 버리면 안 됩니다.
                          "음식": "5", "분위기": "4"}),
            # 오래전에 쓰고 최근에 고친 리뷰. 구글의 '최신순'은 수정일 기준이라
            # 이런 행이 작성일 기준으로는 순서를 거슬러 올라옵니다.
            review("REV_2", "Galaxy Cho", "2222", 807, 4, 1596000000000000,
                   "수정일: 1개월 전", "주차장이 넓어서 편했어요.",
                   edited=1751000000000000),
        ],
    ]
    frame = [["wrb.fr", "/MapsUgcPostService.ListUgcPosts",
              json.dumps(inner, ensure_ascii=False), None, None, None, "generic"]]
    payload = json.dumps(frame, ensure_ascii=False)
    trailer = json.dumps([["di", 84], ["af.httprm", 83, "-2377153688595092602", 39]])
    # 길이 헤더를 일부러 틀린 값으로 넣습니다. 파서가 이걸 믿으면 깨집니다.
    return f")]}}'\n\n999999\n{payload}\n25\n{trailer}\n"


def test_rpc_parser():
    print("\n[4] RPC 응답 파싱")
    raw = build_rpc_response()
    inner = parse_batchexecute(raw)

    check("wrb.fr 프레임 추출", inner is not None, True)
    check("다음 커서", next_cursor(inner), "CURSOR_NEXT:70")

    rows = extract_reviews(inner, "테스트장소", "0xA:0xB", "최신순")
    check("리뷰 2건 추출", len(rows), 2)

    r = rows[0]
    check("리뷰ID", r["리뷰ID"], "REV_1")
    check("작성자·ID·총리뷰수",
          (r["작성자닉네임"], r["작성자ID"], r["작성자총리뷰수"]), ("김철수", "1111", 501))
    check("평점", r["평점"], 5)
    check("본문 전문(줄바꿈 보존)",
          r["리뷰본문"], "치즈 체험이 좋았습니다.\n줄바꿈도 그대로 들어옵니다.")
    check("상대표기 보존", rows[1]["작성일_상대표기"], "수정일: 1개월 전")
    check("수정 없는 리뷰는 수정여부 빈값", r["수정여부"], "")
    check("수정된 리뷰 플래그", rows[1]["수정여부"], "수정")
    check("작성일과 수정일이 분리됨",
          (rows[1]["작성일"][:4], rows[1]["수정일"][:4]), ("2020", "2025"))

    # 구조화 속성 ('자세히 보기'로 펼쳐야 화면에 보이는 항목)
    check("방문일 추출", r["방문일"], "주말")
    check("대기시간 추출", r["대기시간"], "대기 시간 없음")
    check("예약권장 추출", r["예약권장"], "아니요")
    check("미등록 라벨은 기타속성으로 보존", r["기타속성"], "분위기=4|음식=5")
    check("속성 없는 리뷰는 빈 문자열",
          (rows[1]["방문일"], rows[1]["대기시간"], rows[1]["기타속성"]), ("", "", ""))
    check("메타데이터", (r["관광지명"], r["feature_id"], r["정렬기준"]),
          ("테스트장소", "0xA:0xB", "최신순"))

    # 절대 시각 변환: 1666158286194691μs → 2022-10-19 (UTC 기준)
    check("절대 시각 변환", to_iso(1666158286194691).startswith("2022-10-19"), True)
    check("시각 없음은 빈 문자열", to_iso(None), "")

    # 구글이 빈 결과를 줄 때의 형태
    empty = [None, None, None, None, None, True]
    check("빈 응답은 0건", extract_reviews(empty), [])
    check("빈 응답 커서 없음", next_cursor(empty), None)

    check("깨진 입력은 None", parse_batchexecute("not json at all"), None)
    check("빈 입력은 None", parse_batchexecute(""), None)


def main():
    test_rating_labels()
    test_rpc_parser()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page()
        try:
            test_dom_extraction(page)
            test_id_stability(page)
        finally:
            browser.close()

    total = len(PASSED) + len(FAILED)
    print(f"\n{'=' * 50}")
    print(f"통과 {len(PASSED)} / {total}")
    if FAILED:
        print(f"실패 {len(FAILED)}건: {', '.join(FAILED)}")
    print("=" * 50)
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
