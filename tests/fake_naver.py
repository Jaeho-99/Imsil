"""네트워크 없이 파이프라인을 검증하기 위한 가짜 네이버 API 응답."""
from __future__ import annotations

import datetime as dt
import json
import random
from email.utils import format_datetime
from urllib.parse import urlparse

SNIPPETS = [
    "임실치즈테마파크 에서 <b>치즈</b> 피자 만들기 체험 아이 와 함께 좋아요",
    "옥정호 붕어섬 출렁다리 산책 하고 전주 한옥마을 까지 당일치기",
    "전북 여행 코스 전주 군산 임실 순창 다녀왔어요 주차 불편",
    "남원 광한루 와 임실 사선대 드라이브 단풍 예쁘다",
    "임실N치즈축제 축제 사람 많다 주차 대기 길다",
    "성수산 자연휴양림 상이암 등산 조용하다",
    "오수의견 국민여가캠핑장 캠핑 반려견 시설 깨끗",
    "고창 선운사 부안 채석강 변산 바다 여행",
    "무주 덕유산 곤돌라 진안 마이산 탑사",
]


class FakeResp:
    def __init__(self, data, status=200):
        self._d, self.status_code, self.text = data, status, json.dumps(data, ensure_ascii=False)

    def json(self):
        return self._d


class FakeSession:
    def __init__(self, seed: int = 0, n_total: int = 1500):
        self.rng = random.Random(seed)
        self.n_total = n_total
        self.calls = 0

    def request(self, method, url, headers=None, params=None, data=None, timeout=None):
        self.calls += 1
        path = urlparse(url).path
        if "datalab" in path or "search-trend" in path:
            return FakeResp(self._datalab(json.loads(data)))
        channel = path.rsplit("/", 1)[-1].replace(".json", "")
        return FakeResp(self._search(channel, params))

    def _search(self, channel, params):
        q, start, display = params["query"], params["start"], params["display"]
        total = self.n_total + (abs(hash(q)) % 500)
        n = max(0, min(display, total - start + 1))
        items = []
        base = dt.date(2026, 10, 31)
        for i in range(n):
            k = start + i
            d = base - dt.timedelta(days=k // 3)
            it = {"title": f"{q} 후기 {k}", "link": f"https://x/{channel}/{q}/{k}",
                  "description": self.rng.choice(SNIPPETS)}
            if channel == "blog":
                it.update(postdate=d.strftime("%Y%m%d"), bloggername="b")
            elif channel == "news":
                it.update(pubDate=format_datetime(dt.datetime(d.year, d.month, d.day, 9, tzinfo=dt.timezone.utc)))
            else:
                it.update(cafename="c")
            items.append(it)
        return {"total": total, "start": start, "display": len(items), "items": items}

    def _datalab(self, body):
        start = dt.date.fromisoformat(body["startDate"])
        end = dt.date.fromisoformat(body["endDate"])
        months = []
        d = start.replace(day=1)
        while d <= end:
            months.append(d.isoformat())
            d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        raw = {g["groupName"]: [self.rng.uniform(5, 50) * (1 + len(g["groupName"]) % 3) for _ in months]
               for g in body["keywordGroups"]}
        mx = max(max(v) for v in raw.values())
        return {"startDate": body["startDate"], "endDate": body["endDate"], "timeUnit": body["timeUnit"],
                "results": [{"title": g, "keywords": [], "data": [{"period": p, "ratio": round(v / mx * 100, 5)}
                                                                  for p, v in zip(months, vs)]} for g, vs in raw.items()]}
