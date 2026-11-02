"""
구글 지도 리뷰 수집기 (google_reviews.py)

임실군 관광지 리뷰 빅데이터 분석용 수집 스크립트.
기존 google_crawler_final.py 의 SERP(검색결과) 지식패널 모달 경로를 버리고,
Google Maps 장소 페이지의 리뷰 탭을 직접 여는 경로로 재작성했습니다.

■ 설계 원칙 (crawling_research_notes.md 및 crawling_issues_report.md 반영)
  1. 난독화 클래스(.jftiEf 등)는 구글이 수시로 변경하므로 1순위로 쓰지 않습니다.
     data-review-id / aria-label / role 같은 안정적 속성을 우선 사용하고,
     클래스는 폴백 체인의 뒤쪽에 둡니다.
  2. 스크롤 컨테이너는 하드코딩하지 않고, 리뷰 카드의 조상 중
     실제로 overflow 스크롤이 걸린 요소를 DOM에서 찾아냅니다.
  3. 예외를 통째로 삼키지 않습니다. 실패는 카운트하고 --debug 시 원문을 출력합니다.
  4. 셀렉터가 깨졌을 때 즉시 원인을 알 수 있도록 --dump 진단 모드를 넣었습니다.
  5. 리뷰ID는 data-review-id(없으면 내용 기반 sha1)를 씁니다.
     파이썬 내장 hash()는 프로세스마다 값이 달라져 재현이 불가능하므로 쓰지 않습니다.

■ 사전 준비
  1. Chrome 프로필: 평소 쓰는 Chrome의 User Data 폴더를 복사해
     이 스크립트와 같은 위치의 chrome_profile_google/ 로 붙여넣습니다.
     (없어도 동작하지만, 로그인 세션이 있어야 캡차 확률이 크게 낮아집니다.)
  2. 스크립트 실행 전 일반 Chrome 창을 모두 닫아주세요.
     Chrome은 프로필 폴더 하나를 한 프로세스만 점유할 수 있습니다.

■ 실행 예시
  .venv\\Scripts\\python google_reviews.py --target 임실치즈테마파크 --limit 50
  .venv\\Scripts\\python google_reviews.py --all --limit 300
  .venv\\Scripts\\python google_reviews.py --target 임실치즈테마파크 --dump   # 진단 모드
"""

import argparse
import asyncio
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.parse
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from gmaps_rpc import extract_reviews, parse_batchexecute

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE_DIR, "chrome_profile_google")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DUMP_DIR = os.path.join(BASE_DIR, "diagnostics")

# ==========================================
# [수집 대상]
# cid 는 Google Maps 장소 고유 ID(10진수)입니다.
# cid 를 모르는 장소는 query 만 채워두면 검색으로 진입합니다.
# 나머지 33곳은 google_review_counts_preliminary.md 의 Place ID 확정 후 채워 넣으면 됩니다.
# ==========================================

# feature_id 는 "0x<지역해시>:0x<CID>" 형식이며 지도 URL 에 그대로 들어 있습니다.
# 모르면 query 만 채우면 검색으로 진입합니다.
#
# ※ crawling_issues_report.md 의 CID(0x93309002f23f8902 → 10606275811776997634)는
#   두 가지가 모두 틀렸습니다.
#     · 16진수를 10진수로 바꾼 값이 어긋납니다 (실제 10606135464786102530)
#     · 애초에 임실치즈테마파크의 CID 가 아닙니다
#   2026-08-11 실측한 올바른 값은 아래와 같습니다. 4차 시도의 400 에러는
#   구글의 정책 차단이 아니라 이 잘못된 CID 때문일 가능성이 큽니다.
TARGETS = [
    {
        "name": "임실치즈테마파크",
        "feature_id": "0x356fd7ba9e08fc69:0x26115af9b51d3f84",
        "query": "임실치즈테마파크",
    },
    # {"name": "옥정호출렁다리", "feature_id": None, "query": "옥정호 출렁다리"},
    # {"name": "국사봉전망대",   "feature_id": None, "query": "임실 국사봉전망대"},
]

# ==========================================
# [셀렉터 폴백 체인]
# 앞쪽일수록 안정적(속성 기반), 뒤쪽일수록 취약(난독화 클래스).
# 구글이 DOM 을 바꾸면 --dump 로 카드 HTML 을 떠서 여기만 고치면 됩니다.
# ==========================================

SEL_REVIEW_TAB = [
    'button[role="tab"][aria-label*="리뷰"]',
    'button[role="tab"]:has-text("리뷰")',
    'button[aria-label*="리뷰"]',
    'button[role="tab"][aria-label*="Reviews"]',
]

SEL_CARD = [
    "div[data-review-id][jsaction]",
    "div[data-review-id]",
    "div.jftiEf",
]

SEL_SORT_BUTTON = [
    'button[aria-label*="정렬"]',
    'button[data-value="정렬"]',
    'button:has-text("정렬")',
    'button[aria-label*="Sort"]',
]

SEL_MORE_BUTTON = [
    'button[aria-label="더보기"]',
    'button[aria-expanded="false"]:has-text("더보기")',
    "button.w8nwRe",
    'button[aria-label="See more"]',
]

SEL_TEXT = ["span.wiI7pd", "div.MyEned span", "span[lang]"]
SEL_AUTHOR = ['div.d4r55', 'button[data-href*="/maps/contrib/"]', 'a[href*="/maps/contrib/"]']
SEL_DATE = ["span.rsqaWe", "span.xRkPPb"]
SEL_RATING = ['span[role="img"][aria-label]', "span.kvMYJc[aria-label]", "[aria-label*='별표']"]

DATE_HINTS = ("일 전", "주 전", "달 전", "개월 전", "년 전", "어제", "오늘", "ago")


# ==========================================
# [휴리스틱 - crawling_research_notes.md 3절 반영]
# ==========================================


def human_delay(mean=1.2, std_dev=0.35, floor=0.35):
    """가우시안 분포 기반 지연. 고정 간격 대기는 그 자체가 봇 시그널이 됩니다."""
    time.sleep(max(floor, random.gauss(mean, std_dev)))


def generate_bezier_points(start_x, start_y, end_x, end_y, steps=28):
    """3차 베지에 곡선 좌표열. 등속 직선 이동을 피하기 위한 궤적 생성."""
    c1x = start_x + (end_x - start_x) * random.uniform(0.1, 0.4)
    c1y = start_y + (end_y - start_y) * random.uniform(0.1, 0.9)
    c2x = start_x + (end_x - start_x) * random.uniform(0.6, 0.9)
    c2y = start_y + (end_y - start_y) * random.uniform(0.1, 0.9)

    points = []
    for t in np.linspace(0, 1, steps):
        x = (1 - t) ** 3 * start_x + 3 * (1 - t) ** 2 * t * c1x + 3 * (1 - t) * t**2 * c2x + t**3 * end_x
        y = (1 - t) ** 3 * start_y + 3 * (1 - t) ** 2 * t * c1y + 3 * (1 - t) * t**2 * c2y + t**3 * end_y
        points.append((x, y))
    return points


class Cursor:
    """마우스의 현재 위치를 기억합니다.

    기존 코드는 이동할 때마다 시작점을 random 으로 새로 뽑아, 커서가 매번
    화면을 순간이동한 뒤 곡선을 그렸습니다. 궤적을 자연스럽게 만들려던 의도와
    정반대로 동작하던 부분이라 상태를 들고 가도록 고쳤습니다.
    """

    def __init__(self, page, x=400, y=400):
        self.page = page
        self.x = x
        self.y = y

    def move_to(self, end_x, end_y):
        for x, y in generate_bezier_points(self.x, self.y, end_x, end_y):
            self.page.mouse.move(x, y)
            time.sleep(random.uniform(0.006, 0.015))
        self.x, self.y = end_x, end_y

    def click_element(self, locator):
        box = locator.bounding_box()
        if not box:
            return False
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        self.move_to(cx, cy)
        self.page.wait_for_timeout(random.randint(250, 550))
        self.page.mouse.click(cx, cy)
        return True


# ==========================================
# [공통 유틸]
# ==========================================


def first_visible(page_or_card, selectors, timeout_ms=0):
    """폴백 체인을 순서대로 시도해 처음 보이는 로케이터를 반환합니다.

    어떤 셀렉터가 먹혔는지 함께 돌려주므로, 로그만 봐도
    '구글이 DOM 을 바꿔서 n번째 폴백으로 내려갔다'는 사실이 드러납니다.
    """
    for sel in selectors:
        loc = page_or_card.locator(sel).first
        try:
            if timeout_ms:
                loc.wait_for(state="visible", timeout=timeout_ms)
                return loc, sel
            if loc.count() > 0 and loc.is_visible():
                return loc, sel
        except PWTimeout:
            continue
    return None, None


TRAILING_NOISE = re.compile(r"(?:\s*…\s*|\s*\.\.\.\s*)?(?:더보기|See more)?\s*$")


def text_of(card, selectors):
    for sel in selectors:
        loc = card.locator(sel).first
        if loc.count() > 0:
            val = (loc.inner_text() or "").strip()
            if val:
                return TRAILING_NOISE.sub("", val).strip()
    return ""


def rating_from_label(label):
    """aria-label 문자열에서 별점을 뽑습니다.

    표기가 언어별로 갈리는 데다, '몇 개 중 몇 개' 형태에서 정답 위치가 서로 반대입니다.
      · 한국어 '별표 5개 중 4개'   → 뒤쪽 숫자가 실제 별점
      · 영어   'Rated 4.0 out of 5' → 앞쪽 숫자가 실제 별점
    앞에서부터 첫 숫자를 집으면 한국어에서 전부 5점으로 잘못 기록됩니다.
    """
    if not label:
        return None
    nums = re.findall(r"\d+(?:[.,]\d+)?", label)
    if not nums:
        return None

    if "중" in label and len(nums) >= 2:
        picked = nums[-1]
    elif re.search(r"out of|/", label, re.IGNORECASE) and len(nums) >= 2:
        picked = nums[0]
    else:
        picked = nums[0]

    try:
        value = float(picked.replace(",", "."))
    except ValueError:
        return None
    return value if 0 <= value <= 5 else None


def parse_rating(card):
    for sel in SEL_RATING:
        loc = card.locator(sel).first
        if loc.count() == 0:
            continue
        value = rating_from_label(loc.get_attribute("aria-label"))
        if value is not None:
            return value
    return None


def stable_review_id(card, author, date_text, text):
    """재현 가능한 리뷰 ID.

    data-review-id 가 있으면 그대로 쓰고, 없으면 내용 기반 sha1 로 대체합니다.
    파이썬 hash() 는 PYTHONHASHSEED 때문에 실행할 때마다 값이 바뀌므로
    연구용 데이터셋의 키로 쓸 수 없습니다.
    """
    rid = card.get_attribute("data-review-id")
    if rid:
        return rid
    seed = f"{author}|{date_text}|{text}".encode("utf-8")
    return "sha1:" + hashlib.sha1(seed).hexdigest()[:16]


BLOCK_PHRASES = ("비정상적인 트래픽", "로봇이 아닙니다", "unusual traffic", "systems have detected")


def check_blocked(page):
    """캡차 / 동의 화면 / 차단 페이지 감지. 감지되면 사유 문자열을 반환합니다.

    판정은 page.content() 원문이 아니라 '눈에 보이는 텍스트'로 합니다.
    HTML 원문에는 'recaptcha' 같은 단어가 정상 페이지의 스크립트에도 들어 있어,
    원문을 검사하면 매번 차단으로 오판하고 사람 개입을 요구하게 됩니다.
    """
    url = page.url.lower()
    if "consent.google" in url or "/sorry/" in url:
        return f"차단·동의 페이지로 리다이렉트됨: {page.url}"
    try:
        visible = page.inner_text("body", timeout=5000)
    except Exception:
        return None
    lowered = visible.lower()
    for phrase in BLOCK_PHRASES:
        if phrase in visible or phrase in lowered:
            return f"봇 검증 화면 감지 (문구: {phrase})"
    return None


# ==========================================
# [브라우저 기동]
# ==========================================


def ensure_event_loop():
    """Windows + Python 3.14 의 이벤트 루프 생성 실패를 우회합니다.

    Playwright 는 내부적으로 asyncio 루프를 만드는데, 이 환경에서는 기본
    ProactorEventLoop 가 socket.socketpair() 단계에서
    WinError 10014 로 죽는 경우가 있습니다(실측). 브라우저를 띄우기도 전에
    나는 오류라 원인 파악이 어려우므로, 미리 확인해 SelectorEventLoop 로 넘깁니다.

    기본 루프가 정상이면 아무것도 바꾸지 않습니다. Playwright 는 드라이버를
    자식 프로세스로 띄우는데 Windows 의 SelectorEventLoop 는 subprocess 를
    지원하지 않으므로, 굳이 필요할 때만 전환해야 합니다.
    """
    if sys.platform != "win32":
        return None
    try:
        loop = asyncio.new_event_loop()
        loop.close()
        return None
    except OSError as e:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        return f"기본 이벤트 루프 생성 실패({type(e).__name__}: {e}) → SelectorEventLoop 로 전환"


def check_profile_lock():
    """Chrome 이 프로필을 이미 점유 중인지 확인합니다.

    이 경우 launch_persistent_context 가 조용히 빈 프로필로 뜨거나 실패합니다.
    실행 전에 잡아주는 편이 원인 추적에 훨씬 낫습니다.
    """
    lockfile = os.path.join(PROFILE_DIR, "SingletonLock")
    if os.path.exists(lockfile) or os.path.islink(lockfile):
        print("[경고] 프로필 잠금 파일이 남아 있습니다:", lockfile)
        print("       실행 중인 Chrome 창을 모두 닫은 뒤 다시 시도하세요.")
        print("       (비정상 종료로 남은 파일이라면 직접 삭제해도 됩니다.)")


def launch_context(p, headless):
    if not os.path.exists(PROFILE_DIR):
        print(f"[경고] 프로필 폴더가 없습니다: {PROFILE_DIR}")
        print("       로그인 세션이 없으면 캡차 확률이 크게 올라갑니다.")
        print("       실제 Chrome 의 User Data 폴더를 복사해두는 것을 권장합니다.")
        os.makedirs(PROFILE_DIR, exist_ok=True)
    else:
        check_profile_lock()

    return p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        channel="chrome",
        headless=headless,
        viewport={"width": 1400, "height": 1000},
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        args=[
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
        ],
    )


# ==========================================
# [페이지 조작]
# ==========================================


def cid_from_feature_id(fid):
    """feature_id "0x<지역해시>:0x<CID>" 에서 10진수 CID 를 뽑습니다."""
    try:
        return int(fid.split(":")[1], 16)
    except (IndexError, ValueError):
        return None


def build_url(target):
    """장소 페이지 URL.

    ?cid= 형식을 씁니다. /maps/place/.../data=!4m6!3m5!... 형식도 가능하지만
    ! 블록의 원소 개수를 정확히 맞춰야 하고, 틀리면 구글이 조용히
    지도 홈으로 리다이렉트합니다(실측). cid 는 그런 함정이 없습니다.
    """
    fid = target.get("feature_id")
    if fid:
        cid = cid_from_feature_id(fid)
        if cid is not None:
            return f"https://www.google.com/maps?cid={cid}&hl=ko"
    q = urllib.parse.quote(target.get("query") or target["name"])
    return f"https://www.google.com/maps/search/{q}?hl=ko"


FEATURE_ID_RE = re.compile(r"0x[0-9a-f]{6,20}:0x[0-9a-f]{6,20}")


def resolve_feature_id(page, query):
    """장소명을 검색해 feature id 를 알아냅니다.

    브라우저를 거쳐야 합니다. urllib 로 같은 URL 을 받으면 구글이
    리뷰도 장소 ID 도 없는 껍데기 HTML 을 돌려줍니다 (실측 확인).
    """
    url = "https://www.google.com/maps/search/" + urllib.parse.quote(query) + "?hl=ko"
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    human_delay(3.5, 0.6)

    for _ in range(3):
        m = FEATURE_ID_RE.search(page.url)
        if m and not m.group(0).endswith(":0x0"):
            return m.group(0), page.title()
        # 검색 결과가 목록으로 나오면 첫 항목을 눌러 장소 페이지로 들어갑니다.
        first = page.locator('a[href*="/maps/place/"]').first
        if first.count() > 0:
            first.click()
            human_delay(3.0, 0.5)
        else:
            break
    return None, page.title()


def open_reviews_tab(page, cursor, debug=False):
    tab, sel = first_visible(page, SEL_REVIEW_TAB, timeout_ms=15000)
    if not tab:
        return False, "리뷰 탭을 찾지 못했습니다."
    if debug:
        print(f"  [debug] 리뷰 탭 셀렉터: {sel}")
    if not cursor.click_element(tab):
        tab.click()
    human_delay(2.0, 0.4)
    return True, None


def sort_by_newest(page, cursor, debug=False):
    """정렬을 '최신순'으로 바꿉니다.

    기본값(관련성순)은 구글이 고른 일부만 보여주고 스크롤이 일찍 끊깁니다.
    최신순으로 두어야 수집 구간이 '언제부터 언제까지'인지 명확해집니다.
    """
    btn, sel = first_visible(page, SEL_SORT_BUTTON, timeout_ms=8000)
    if not btn:
        print("  [알림] 정렬 버튼을 찾지 못해 기본 정렬(관련성순)로 수집합니다.")
        return "기본(관련성순)"
    if debug:
        print(f"  [debug] 정렬 버튼 셀렉터: {sel}")

    if not cursor.click_element(btn):
        btn.click()
    human_delay(1.0, 0.25)

    for label in ("최신순", "Newest"):
        item = page.locator(f'[role="menuitemradio"]:has-text("{label}"), [role="menuitem"]:has-text("{label}")').first
        if item.count() > 0 and item.is_visible():
            item.click()
            human_delay(2.0, 0.4)
            return "최신순"

    print("  [알림] 최신순 항목을 찾지 못했습니다. 메뉴를 닫고 기본 정렬로 진행합니다.")
    page.keyboard.press("Escape")
    return "기본(관련성순)"


FIND_SCROLLER_JS = """
(cardSelector) => {
  const card = document.querySelector(cardSelector);
  if (!card) return 'no-card';
  let el = card.parentElement;
  while (el && el !== document.body) {
    const s = getComputedStyle(el);
    const scrollable = (s.overflowY === 'auto' || s.overflowY === 'scroll');
    if (scrollable && el.scrollHeight > el.clientHeight + 50) {
      document.querySelectorAll('[data-crawl-scroller]')
              .forEach(n => n.removeAttribute('data-crawl-scroller'));
      el.setAttribute('data-crawl-scroller', '1');
      return 'ok';
    }
    el = el.parentElement;
  }
  return 'no-scroller';
}
"""


def find_scroll_container(page, card_selector, debug=False):
    """리뷰 카드의 조상 중 실제로 스크롤이 걸린 요소를 찾아 표시합니다.

    클래스명 하드코딩(.m6QErb 등)은 구글이 바꿀 때마다 깨지므로,
    computed style 로 판정합니다.
    """
    result = page.evaluate(FIND_SCROLLER_JS, card_selector)
    if debug:
        print(f"  [debug] 스크롤 컨테이너 탐색 결과: {result}")
    if result != "ok":
        return None
    return page.locator('[data-crawl-scroller="1"]').first


def scroll_feed(page, cursor, scroller, max_steps=40, debug=False):
    """리뷰 패널 바닥까지 휠을 나눠 굴립니다.

    고정 픽셀만 내리면 안 됩니다. 구글은 목록 '바닥 근처'에 도달해야
    다음 묶음을 불러오는데, 리뷰 10건이면 패널 내용이 이미 6,000px 이 넘어서
    1,400px 만 내려서는 로딩이 트리거되지 않습니다(실측).

    다만 scrollTo 로 한 번에 낙하시키는 방식은 조사 문서 3절에서
    대표적 탐지 트리거로 지목되어 있으므로, 휠을 잘게 나눠 굴려 내려갑니다.
    """
    box = scroller.bounding_box()
    if not box:
        return False

    cursor.move_to(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(250)

    def where():
        return scroller.evaluate(
            "el => ({top: el.scrollTop, h: el.scrollHeight, c: el.clientHeight})"
        )

    try:
        start = where()
    except Exception as e:
        if debug:
            print(f"  [debug] 스크롤 위치 조회 실패: {type(e).__name__}")
        return False

    steps = 0
    pos = start
    use_js = False

    for _ in range(max_steps):
        if use_js:
            # 휠이 안 먹는 경우의 폴백. 한 번에 바닥으로 보내지 않고
            # 무작위 크기로 잘게 밀어, 등속·순간이동 패턴을 피합니다.
            scroller.evaluate("(el, d) => { el.scrollTop += d; }", random.randint(320, 560))
        else:
            page.mouse.wheel(0, random.randint(320, 560))
        steps += 1
        human_delay(0.28, 0.1, floor=0.12)

        try:
            pos = where()
        except Exception:
            return False

        # 휠을 몇 번 굴렸는데도 제자리면 이벤트가 이 컨테이너에 닿지 않는 것입니다.
        # (다른 패널이 위를 덮고 있거나 박스 중심이 지도 쪽인 경우)
        if not use_js and steps >= 3 and pos["top"] <= start["top"] + 1:
            use_js = True
            if debug:
                print(f"  [debug] 휠 {steps}회에도 top={pos['top']:.0f} → JS 증분 스크롤로 전환")
            continue

        if pos["top"] + pos["c"] >= pos["h"] - 80:
            break  # 바닥 도달 → 다음 묶음 로딩 대기

    if debug:
        print(
            f"  [debug] {'JS' if use_js else '휠'} {steps}회  "
            f"box=({box['x']:.0f},{box['y']:.0f},{box['width']:.0f}x{box['height']:.0f})  "
            f"top={pos['top']:.0f} client={pos['c']:.0f} scroll={pos['h']:.0f} "
            f"바닥까지={pos['h'] - pos['top'] - pos['c']:.0f}px"
        )

    human_delay(1.6, 0.4)  # 새 묶음이 붙을 시간
    return True


def expand_more_buttons(page, limit=25):
    """접힌 리뷰 본문('더보기')을 펼칩니다. 펼친 개수를 반환합니다."""
    opened = 0
    for sel in SEL_MORE_BUTTON:
        buttons = page.locator(sel).all()
        for btn in buttons[:limit]:
            try:
                if btn.is_visible():
                    btn.click(timeout=1500)
                    opened += 1
                    page.wait_for_timeout(random.randint(90, 180))
            except PWTimeout:
                continue
        if opened:
            break
    return opened


# ==========================================
# [RPC 응답 가로채기 — 주 수집 경로]
# ==========================================


class RpcCollector:
    """리뷰 목록 RPC 응답을 가로채 파싱합니다.

    ■ 왜 DOM 이 아니라 응답을 보는가
      구글 지도는 리뷰를 batchexecute RPC 로 받아 화면에 그립니다.
      그 JSON 을 직접 읽으면 DOM 스크래핑 대비 이점이 큽니다.
        · 본문이 잘리지 않음 → '더보기' 클릭 불필요
        · 작성 시각이 마이크로초 절대값 (DOM 은 '3년 전' 상대 표기뿐)
        · 작성자 ID·총 리뷰수 등 화면에 없는 필드까지 확보
        · 난독화 클래스 변경에 영향받지 않음

    ■ 왜 브라우저는 여전히 필요한가
      같은 RPC 를 requests/urllib 로 직접 부르면 구글이 200 을 주면서도
      [null,null,null,null,null,true] 라는 빈 결과만 돌려줍니다 (실측).
      TLS 핑거프린트 단계에서 비브라우저 클라이언트를 걸러내기 때문에,
      요청 자체는 진짜 크롬이 만들게 두고 응답만 읽습니다.
    """

    def __init__(self, page, place_name, sort_name, feature_id="", debug=False, save_raw=False):
        self.rows = []
        self.seen = set()
        self.responses = 0
        self.errors = 0
        self.sort_name = sort_name  # 정렬 확정 후 호출부에서 갱신합니다
        self._place = place_name
        self._fid = feature_id
        self._debug = debug
        self._save_raw = save_raw
        self._raw_saved = 0
        page.on("response", self._on_response)

    def _dump_raw(self, inner):
        """가공 전 원본 페이로드를 저장합니다.

        추출 경로(rv[2][15][0][0] 등)는 구글이 구조를 바꾸면 어긋납니다.
        그때 추측으로 고치지 않으려면 원본이 남아 있어야 합니다.
        아직 컬럼으로 안 뽑은 필드를 찾을 때도 이 파일을 뒤지면 됩니다.
        """
        os.makedirs(DUMP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(DUMP_DIR, f"{self._place}_{stamp}_rpc{self._raw_saved:02d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(inner, f, ensure_ascii=False, indent=1)
        self._raw_saved += 1

    def _on_response(self, response):
        url = response.url
        if "batchexecute" not in url or "qv9Egd" not in url:
            return
        try:
            body = response.text()
        except Exception as e:  # 응답 본문을 못 읽는 경우 (리다이렉트 등)
            self.errors += 1
            if self._debug:
                print(f"  [debug] RPC 본문 read 실패: {type(e).__name__}")
            return

        inner = parse_batchexecute(body)
        if inner is None:
            self.errors += 1
            if self._debug:
                print(f"  [debug] RPC 파싱 실패 ({len(body)}자)")
            return

        self.responses += 1
        if self._save_raw and self._raw_saved < 3:
            self._dump_raw(inner)
        for row in extract_reviews(inner, self._place, self._fid, self.sort_name):
            if row["리뷰ID"] in self.seen:
                continue
            self.seen.add(row["리뷰ID"])
            self.rows.append(row)

    def drain(self):
        """마지막 호출 이후 새로 모인 리뷰를 반환합니다."""
        out = self.rows
        self.rows = []
        return out


# ==========================================
# [진단 모드]
# ==========================================


def dump_diagnostics(page, target_name):
    """셀렉터가 깨졌을 때 원인을 즉시 찾기 위한 스냅샷을 남깁니다.

    diagnosing-bugs 스킬의 'tight feedback loop' 에 해당합니다.
    추측으로 셀렉터를 고치는 대신, 실제 DOM 을 보고 고치기 위한 자료입니다.
    """
    os.makedirs(DUMP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = os.path.join(DUMP_DIR, f"{target_name}_{stamp}")

    page.screenshot(path=f"{prefix}_screen.png", full_page=False)
    with open(f"{prefix}_page.html", "w", encoding="utf-8") as f:
        f.write(page.content())

    probe = {"url": page.url, "title": page.title()}
    for name, chain in [
        ("review_tab", SEL_REVIEW_TAB),
        ("card", SEL_CARD),
        ("sort", SEL_SORT_BUTTON),
        ("text", SEL_TEXT),
        ("author", SEL_AUTHOR),
        ("date", SEL_DATE),
        ("rating", SEL_RATING),
    ]:
        probe[name] = {sel: page.locator(sel).count() for sel in chain}

    card_loc, card_sel = first_visible(page, SEL_CARD)
    if card_loc:
        probe["matched_card_selector"] = card_sel
        with open(f"{prefix}_card.html", "w", encoding="utf-8") as f:
            f.write(card_loc.evaluate("el => el.outerHTML"))

    with open(f"{prefix}_probe.json", "w", encoding="utf-8") as f:
        json.dump(probe, f, ensure_ascii=False, indent=2)

    print(f"\n[진단] 스냅샷 저장 완료 → {prefix}_*")
    print("[진단] 셀렉터별 매칭 개수:")
    for name, counts in probe.items():
        if isinstance(counts, dict):
            print(f"  {name}: {counts}")
    return prefix


# ==========================================
# [수집 본체]
# ==========================================


def extract_cards(page, seen, target_name, sort_mode, source_url, debug=False):
    """현재 DOM 에 있는 리뷰 카드를 추출합니다. (신규분, 실패건수)를 반환합니다."""
    card_loc, card_sel = first_visible(page, SEL_CARD)
    if not card_loc:
        return [], 0, None

    cards = page.locator(card_sel).all()
    new_rows = []
    failures = 0
    first_error = None

    for card in cards:
        try:
            text = text_of(card, SEL_TEXT)
            author = text_of(card, SEL_AUTHOR)
            rating = parse_rating(card)

            date_text = text_of(card, SEL_DATE)
            if not date_text:
                for s in card.locator("span").all_inner_texts():
                    s = s.strip()
                    if s and any(h in s for h in DATE_HINTS):
                        date_text = s
                        break

            # 별점만 남기고 본문이 없는 리뷰도 유효한 데이터입니다.
            # 다만 본문·별점이 모두 비면 리뷰 카드가 아니므로 버립니다.
            if not text and rating is None:
                continue

            rid = stable_review_id(card, author, date_text, text)
            if rid in seen:
                continue
            seen.add(rid)

            new_rows.append(
                {
                    "관광지명": target_name,
                    "플랫폼": "구글",
                    "리뷰ID": rid,
                    "작성자닉네임": author or "",
                    "작성일_표시": date_text or "",
                    "평점": rating,
                    "리뷰본문": text,
                    "본문길이": len(text),
                    "정렬기준": sort_mode,
                    "출처URL": source_url,
                    "수집시각": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        except Exception as e:  # noqa: BLE001 - 삼키지 않고 세어서 보고합니다
            failures += 1
            if first_error is None:
                first_error = f"{type(e).__name__}: {e}"
            if debug:
                print(f"  [debug] 카드 파싱 실패: {type(e).__name__}: {e}")

    return new_rows, failures, first_error


def save(rows, target_name):
    if not rows:
        return None
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = pd.DataFrame(rows)
    stem = os.path.join(OUTPUT_DIR, f"{target_name}_google_reviews")
    df.to_csv(f"{stem}.csv", index=False, encoding="utf-8-sig")
    df.to_excel(f"{stem}.xlsx", index=False)
    return stem


def crawl_target(page, cursor, target, limit, args):
    name = target["name"]
    url = build_url(target)
    print(f"\n{'=' * 60}\n[{name}] 수집 시작 (목표 {limit}건)\n{'=' * 60}")
    print(f"  진입 URL: {url}")

    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    human_delay(3.0, 0.6)

    blocked = check_blocked(page)
    if blocked:
        print(f"\n  [차단] {blocked}")
        if args.no_hitl:
            print("  --no-hitl 이므로 이 장소를 건너뜁니다.")
            return [], "blocked"
        print("  띄워진 크롬 창에서 직접 검증을 통과시켜 주세요.")
        input("  통과 후 이 터미널에서 [Enter] ▶ ")
        human_delay(2.0, 0.4)

    ok, err = open_reviews_tab(page, cursor, args.debug)
    if not ok:
        print(f"  [실패] {err}")
        dump_diagnostics(page, name)
        return [], "no-review-tab"

    # 정렬을 바꾸면 목록 전체를 다시 받아오는 RPC 가 발생합니다.
    # 그 응답부터 잡으려면 수집기를 정렬 전에 붙여야 합니다.
    collector = RpcCollector(
        page, name, "", target.get("feature_id", ""), args.debug, getattr(args, "save_raw", False)
    )

    sort_mode = sort_by_newest(page, cursor, args.debug)
    collector.sort_name = sort_mode
    print(f"  정렬 기준: {sort_mode}")

    card_loc, card_sel = first_visible(page, SEL_CARD, timeout_ms=15000)
    if not card_loc:
        print("  [실패] 리뷰 카드를 찾지 못했습니다. 진단 스냅샷을 남깁니다.")
        dump_diagnostics(page, name)
        return [], "no-cards"
    print(f"  리뷰 카드 셀렉터: {card_sel}")

    scroller = find_scroll_container(page, card_sel, args.debug)
    if scroller is None:
        print("  [실패] 스크롤 컨테이너를 찾지 못했습니다. 진단 스냅샷을 남깁니다.")
        dump_diagnostics(page, name)
        return [], "no-scroller"

    rows = []
    dom_seen = set()
    dom_used = 0
    stall_rounds = 0
    round_no = 0

    # 고정 횟수 대신 '새 리뷰가 안 나오는 상태가 이어지는지'로 종료를 판단합니다.
    # 구글이 실제로 가진 리뷰가 목표치보다 적을 때 무한정 도는 것을 막습니다.
    while len(rows) < limit and stall_rounds < args.stall_limit:
        round_no += 1

        # 1순위: 가로챈 RPC 응답
        new_rows = collector.drain()

        # 2순위: RPC 가 한 건도 안 잡히면 DOM 으로 폴백합니다.
        # (구글이 RPC 형식을 바꿔도 최소한 수집은 계속되도록)
        if not new_rows and collector.responses == 0:
            expand_more_buttons(page)
            dom_rows, failures, first_error = extract_cards(
                page, dom_seen, name, sort_mode, url, args.debug
            )
            # RPC 로 이미 받은 리뷰와 겹치지 않게 걸러냅니다.
            dom_rows = [r for r in dom_rows if r["리뷰ID"] not in collector.seen]
            if dom_rows:
                dom_used += len(dom_rows)
                new_rows = dom_rows
            if failures and first_error and round_no == 1:
                print(f"       DOM 폴백 첫 실패 원인: {first_error}")

        rows.extend(new_rows)
        print(f"  [{round_no:>3}회] 누적 {len(rows):>4} / {limit}  (신규 {len(new_rows)}, RPC 응답 {collector.responses}건)")

        stall_rounds = stall_rounds + 1 if not new_rows else 0

        if len(rows) >= limit:
            break

        if not scroll_feed(page, cursor, scroller, debug=args.debug):
            print("  [알림] 스크롤 영역이 사라졌습니다. 재탐색합니다.")
            scroller = find_scroll_container(page, card_sel, args.debug)
            if scroller is None:
                break

    rows.extend(collector.drain())  # 마지막 스크롤로 들어온 응답 회수

    if collector.responses == 0:
        print("  [경고] RPC 응답을 한 건도 잡지 못했습니다. DOM 폴백으로만 수집했습니다.")
    if collector.errors:
        print(f"  [알림] RPC 파싱 실패 {collector.errors}건")
    if dom_used:
        print(f"  [알림] DOM 폴백으로 보충한 리뷰 {dom_used}건")

    reason = "목표 달성" if len(rows) >= limit else f"더 이상 새 리뷰 없음 ({args.stall_limit}회 연속)"
    print(f"  종료: {reason}")
    return rows[:limit], "ok"


def main():
    parser = argparse.ArgumentParser(description="구글 지도 리뷰 수집기")
    parser.add_argument("--target", help="TARGETS 중 수집할 관광지명 (미지정 시 첫 번째)")
    parser.add_argument("--all", action="store_true", help="TARGETS 전체 수집")
    parser.add_argument("--limit", type=int, default=50, help="장소당 목표 리뷰 수")
    parser.add_argument("--stall-limit", type=int, default=4, help="새 리뷰 없이 넘길 최대 스크롤 횟수")
    parser.add_argument("--headless", action="store_true", help="헤드리스 실행 (탐지 위험 높음, 비권장)")
    parser.add_argument("--no-hitl", action="store_true", help="캡차 시 사람 개입 없이 건너뜀")
    parser.add_argument("--debug", action="store_true", help="셀렉터·예외 상세 출력")
    parser.add_argument("--dump", action="store_true", help="진단 스냅샷만 남기고 종료")
    parser.add_argument("--save-raw", action="store_true",
                        help="RPC 원본 응답을 diagnostics/ 에 저장 (앞 3개, 필드 탐색용)")
    parser.add_argument("--resolve", nargs="+", metavar="QUERY", help="장소명으로 feature id 만 조회")
    args = parser.parse_args()

    note = ensure_event_loop()
    if note:
        print(f"[환경] {note}")

    if args.resolve:
        with sync_playwright() as p:
            context = launch_context(p, args.headless)
            page = context.pages[0] if context.pages else context.new_page()
            Stealth().apply_stealth_sync(page)
            try:
                print(f"\n{'장소명':<24}{'feature_id':<42}확인된 페이지 제목")
                for q in args.resolve:
                    fid, title = resolve_feature_id(page, q)
                    print(f"{q:<24}{fid or '실패':<42}{title}")
                    human_delay(4.0, 1.0)
            finally:
                context.close()
        sys.exit(0)

    if args.all:
        targets = TARGETS
    elif args.target:
        targets = [t for t in TARGETS if t["name"] == args.target]
        if not targets:
            print(f"[오류] TARGETS 에 '{args.target}' 가 없습니다.")
            print("       등록된 대상:", ", ".join(t["name"] for t in TARGETS))
            sys.exit(1)
    else:
        targets = TARGETS[:1]

    print(f"[설정] 프로필: {PROFILE_DIR}")
    print(f"[설정] 대상 {len(targets)}곳, 장소당 목표 {args.limit}건")

    summary = []
    with sync_playwright() as p:
        context = launch_context(p, args.headless)
        page = context.pages[0] if context.pages else context.new_page()
        Stealth().apply_stealth_sync(page)
        cursor = Cursor(page)

        try:
            for target in targets:
                if args.dump:
                    page.goto(build_url(target), wait_until="domcontentloaded", timeout=45000)
                    human_delay(4.0, 0.5)
                    open_reviews_tab(page, cursor, True)
                    human_delay(3.0, 0.5)
                    dump_diagnostics(page, target["name"])
                    continue

                rows, status = crawl_target(page, cursor, target, args.limit, args)
                stem = save(rows, target["name"])
                summary.append((target["name"], len(rows), status, stem))

                if target is not targets[-1]:
                    # 장소 간 간격. 연속 요청은 IP 신뢰 점수를 떨어뜨립니다.
                    human_delay(8.0, 2.0, floor=4.0)
        finally:
            context.close()

    if summary:
        print(f"\n{'=' * 60}\n수집 요약\n{'=' * 60}")
        for name, count, status, stem in summary:
            line = f"  {name:<20} {count:>5}건  [{status}]"
            if stem:
                line += f"  → {os.path.basename(stem)}.csv / .xlsx"
            print(line)


if __name__ == "__main__":
    main()
