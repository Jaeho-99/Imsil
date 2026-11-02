"""네이버 Open API 클라이언트 (검색 API + 데이터랩 검색어트렌드).

두 가지 백엔드를 지원한다.
- "developers": 네이버 개발자센터(openapi.naver.com). 헤더 X-Naver-Client-Id/Secret.
- "apihub":     NAVER Cloud API HUB(naverapihub.apigw.ntruss.com). 헤더 X-NCP-APIGW-API-KEY-ID/KEY.
  개발자센터 키는 API HUB에서 쓸 수 없으므로 키를 발급받은 쪽 백엔드를 고른다.

환경변수(.env)
    NAVER_BACKEND=developers|apihub   (기본 developers)
    NAVER_CLIENT_ID=...
    NAVER_CLIENT_SECRET=...
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

import requests

from .utils import clean_html, load_dotenv

BACKENDS = {
    "developers": {
        "base": "https://openapi.naver.com",
        "search": "/v1/search/{channel}.json",
        "datalab": "/v1/datalab/search",
        "id_header": "X-Naver-Client-Id",
        "secret_header": "X-Naver-Client-Secret",
    },
    # API HUB 경로는 2026-09 공식 가이드 기준. 검색 채널 경로는 뉴스(/search/v1/news) 예시를
    # 따른 것으로, 첫 실행 시 404가 나면 콘솔의 API 가이드에서 경로를 확인해 수정할 것.
    "apihub": {
        "base": "https://naverapihub.apigw.ntruss.com",
        "search": "/search/v1/{channel}",
        "datalab": "/search-trend/v1/search",
        "id_header": "X-NCP-APIGW-API-KEY-ID",
        "secret_header": "X-NCP-APIGW-API-KEY",
    },
}


class NaverAPIError(RuntimeError):
    pass


@dataclass
class NaverClient:
    client_id: str
    client_secret: str
    backend: str = "developers"
    sleep: float = 0.12  # 초당 10회 이하로 호출 (개발자센터 권장 수준)
    max_retries: int = 5
    session: requests.Session = field(default_factory=requests.Session)

    @classmethod
    def from_env(cls, **kw: Any) -> "NaverClient":
        load_dotenv()
        cid = os.getenv("NAVER_CLIENT_ID")
        secret = os.getenv("NAVER_CLIENT_SECRET")
        if not cid or not secret:
            raise NaverAPIError(
                "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 없습니다. .env.example 을 참고해 .env 를 만드세요."
            )
        return cls(cid, secret, backend=os.getenv("NAVER_BACKEND", "developers"), **kw)

    # ------------------------------------------------------------------ 공통
    @property
    def _cfg(self) -> dict[str, str]:
        return BACKENDS[self.backend]

    def _headers(self) -> dict[str, str]:
        return {
            self._cfg["id_header"]: self.client_id,
            self._cfg["secret_header"]: self.client_secret,
        }

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None,
                 body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self._cfg["base"] + path
        headers = self._headers()
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        for attempt in range(self.max_retries):
            resp = self.session.request(method, url, headers=headers, params=params, data=data, timeout=30)
            time.sleep(self.sleep)
            if resp.status_code == 200:
                return resp.json()
            # 429(속도 제한)·5xx 는 지수 백오프 후 재시도
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2**attempt)
                continue
            raise NaverAPIError(f"{resp.status_code} {url}: {resp.text[:300]}")
        raise NaverAPIError(f"재시도 {self.max_retries}회 실패: {url}")

    # ------------------------------------------------------------- 검색 API
    def search(self, channel: str, query: str, display: int = 100, start: int = 1, sort: str = "sim") -> dict[str, Any]:
        """블로그(blog)·카페(cafearticle)·뉴스(news) 검색 1회 호출. 응답의 total 이 '검색 결과 문서 수'."""
        path = self._cfg["search"].format(channel=channel)
        return self._request("GET", path, params={"query": query, "display": display, "start": start, "sort": sort})

    def search_total(self, channel: str, query: str) -> int:
        """검색 결과 총 문서 수(total)만 조회. display=1 로 호출 비용을 최소화."""
        return int(self.search(channel, query, display=1)["total"])

    def iter_search(self, channel: str, query: str, sort: str = "date", max_items: int = 1100) -> Iterator[dict[str, Any]]:
        """검색 결과 문서를 순회. API 제한(start<=1000, display<=100) 때문에 질의당 최대 1,099건이다.

        start 1,101,...,901 로 1~1000번째를 받고, 마지막에 start=1000 으로 1000~1099번째를 받는다(1000번째 중복 제거).
        """
        seen: set[str] = set()
        for start in [*range(1, 1000, 100), 1000]:
            page = self.search(channel, query, display=100, start=start, sort=sort)
            items = page.get("items", [])
            for it in items:
                row = normalize_item(channel, query, it)
                if row["link"] in seen:
                    continue
                seen.add(row["link"])
                yield row
                if len(seen) >= max_items:
                    return
            if len(items) < 100 or start + 100 > int(page.get("total", 0)):
                return

    # --------------------------------------------------------- 데이터랩 API
    def datalab_search(
        self,
        groups: dict[str, list[str]],
        start_date: str,
        end_date: str,
        time_unit: str = "month",
        device: str | None = None,
        gender: str | None = None,
        ages: list[str] | None = None,
    ) -> dict[str, Any]:
        """검색어트렌드. groups 는 최대 5개, 반환 ratio 는 요청 내 최대값=100 인 상대값."""
        if len(groups) > 5:
            raise ValueError("데이터랩은 요청당 키워드 그룹 5개까지 가능합니다.")
        body: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": [{"groupName": g, "keywords": kws[:20]} for g, kws in groups.items()],
        }
        if device:
            body["device"] = device
        if gender:
            body["gender"] = gender
        if ages:
            body["ages"] = ages
        return self._request("POST", self._cfg["datalab"], body=body)


def normalize_item(channel: str, query: str, it: dict[str, Any]) -> dict[str, Any]:
    """채널별로 다른 응답 필드를 공통 스키마로 맞춘다."""
    date = None
    if channel == "blog" and it.get("postdate"):
        p = it["postdate"]
        date = f"{p[:4]}-{p[4:6]}-{p[6:8]}"
    elif channel == "news" and it.get("pubDate"):
        from email.utils import parsedate_to_datetime

        date = parsedate_to_datetime(it["pubDate"]).date().isoformat()
    return {
        "channel": channel,
        "query": query,
        "title": clean_html(it.get("title", "")),
        "description": clean_html(it.get("description", "")),
        "link": it.get("link", ""),
        "source": it.get("bloggername") or it.get("cafename") or it.get("originallink", ""),
        "date": date,  # 카페는 API가 작성일을 주지 않으므로 None
    }
