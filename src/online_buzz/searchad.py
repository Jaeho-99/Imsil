"""네이버 검색광고 API - 키워드도구(/keywordstool).

데이터랩은 상대값(0~100)만 주지만, 검색광고 키워드도구는
'최근 30일 PC/모바일 월간 검색수(절대값)'와 '연관키워드' 목록을 준다.
→ (1) 임실 관광 주요 검색 키워드 도출, (2) 데이터랩 상대값의 절대량 환산에 사용.

광고 집행 없이 검색광고 계정만 만들면 무료로 API 키를 발급받을 수 있다
(searchad.naver.com > 도구 > API 사용 관리).

환경변수: SEARCHAD_API_KEY, SEARCHAD_SECRET_KEY, SEARCHAD_CUSTOMER_ID
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from .utils import load_dotenv, to_int_count

BASE = "https://api.searchad.naver.com"


def signature(secret: str, timestamp: str, method: str, uri: str) -> str:
    msg = f"{timestamp}.{method}.{uri}".encode("utf-8")
    return base64.b64encode(hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()).decode()


@dataclass
class SearchAdClient:
    api_key: str
    secret_key: str
    customer_id: str
    sleep: float = 0.3
    session: requests.Session = field(default_factory=requests.Session)

    @classmethod
    def from_env(cls) -> "SearchAdClient":
        load_dotenv()
        try:
            return cls(os.environ["SEARCHAD_API_KEY"], os.environ["SEARCHAD_SECRET_KEY"], os.environ["SEARCHAD_CUSTOMER_ID"])
        except KeyError as e:
            raise RuntimeError(f"환경변수 {e} 가 없습니다. .env.example 참고.") from None

    def keywordstool(self, hint_keywords: list[str]) -> list[dict[str, Any]]:
        """hint 키워드(최대 5개, 공백 불가)와 연관키워드의 월간 검색수를 반환."""
        if len(hint_keywords) > 5:
            raise ValueError("hintKeywords 는 최대 5개")
        uri = "/keywordstool"
        ts = str(int(time.time() * 1000))
        headers = {
            "X-Timestamp": ts,
            "X-API-KEY": self.api_key,
            "X-Customer": str(self.customer_id),
            "X-Signature": signature(self.secret_key, ts, "GET", uri),
        }
        params = {"hintKeywords": ",".join(k.replace(" ", "") for k in hint_keywords), "showDetail": "1"}
        for attempt in range(5):
            r = self.session.get(BASE + uri, headers=headers, params=params, timeout=30)
            time.sleep(self.sleep)
            if r.status_code == 200:
                return [parse_keyword_row(row) for row in r.json().get("keywordList", [])]
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"검색광고 API {r.status_code}: {r.text[:300]}")
        raise RuntimeError("검색광고 API 재시도 실패")


def parse_keyword_row(row: dict[str, Any]) -> dict[str, Any]:
    pc = to_int_count(row.get("monthlyPcQcCnt", 0))
    mo = to_int_count(row.get("monthlyMobileQcCnt", 0))
    return {
        "keyword": row.get("relKeyword"),
        "monthly_pc": pc,
        "monthly_mobile": mo,
        "monthly_total": pc + mo,
        "mobile_share": round(mo / (pc + mo), 4) if pc + mo else None,
        "comp_idx": row.get("compIdx"),
        "censored_lt10": str(row.get("monthlyPcQcCnt", "")).startswith("<")
        or str(row.get("monthlyMobileQcCnt", "")).startswith("<"),
    }
