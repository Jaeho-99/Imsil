#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""임실군 관광지 리뷰 — 리뷰별 만족·불만 요인 분석 (전처리)

입력  : input/임실군_관광지_리뷰데이터_1차전처리.csv
설정  : .env  (레포 최상위, ANTHROPIC_API_KEY=sk-ant-...)
출력  : output/satisfaction/리뷰별_만족불만요인_분석결과.csv

리뷰 1건에서 (요인 카테고리, 원문 스팬, 평가 표현, 극성)을 추출해
리뷰 단위 1행으로 정리한다. 원본 8개 컬럼은 이름과 순서를 그대로 보존하고
분석 결과 컬럼을 뒤에 덧붙인다.

실행
    python src/satisfaction/analyze_satisfaction.py                 # 전량 (중단 시 자동 재개)
    python src/satisfaction/analyze_satisfaction.py --limit 30      # 30건만 시험 실행
    python src/satisfaction/analyze_satisfaction.py --dry-run       # API 없이 대상 집계만

보고서 5장의 결과는 API 대신 Claude Code 대화에서 판정한 input/satisfaction/annotations.jsonl 로
채웠다. --dry-run 으로 빈 결과 파일을 만든 뒤 src/satisfaction/annotation/merge.py 를 실행한다.

필요 패키지: pandas, anthropic
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import ENV_FILE, REVIEWS_PRE, SATIS_RESULT  # noqa: E402
INPUT_CSV = REVIEWS_PRE
OUTPUT_CSV = SATIS_RESULT

# 원본 컬럼 — 이름과 순서를 그대로 보존한다.
BASE_COLUMNS = ["place", "platform", "reviewId", "rating",
                "body", "date", "visitCount", "tags"]

# 분석 결과 컬럼 (원본 뒤에 덧붙임)
RESULT_COLUMNS = [
    "analyzed",                    # 분석 수행 여부 (본문 없으면 False)
    "overall_sentiment",           # 리뷰 전체 극성 POS/NEG/NEU
    "n_satisfaction",              # 만족 요인 수
    "n_dissatisfaction",           # 불만 요인 수
    "satisfaction_categories",     # 만족 요인 카테고리 (| 구분)
    "dissatisfaction_categories",  # 불만 요인 카테고리 (| 구분)
    "neutral_categories",          # 중립 언급 카테고리 (| 구분)
    "satisfaction_factors",        # 만족 요인 상세 "카테고리:원문" (| 구분)
    "dissatisfaction_factors",     # 불만 요인 상세 "카테고리:원문" (| 구분)
    "factors_json",                # 추출 원문 JSON (재분석·감사용)
    "run_status",                  # ok / skipped / 오류 사유
]

# 요인 카테고리 12종 + 대상외 1종
CATEGORIES = [
    "경관·볼거리", "체험·활동", "산책·휴식공간", "편의시설",
    "관리·청결", "접근·주차", "인적서비스", "음식·특산품",
    "요금·가성비", "안내·운영", "혼잡·대기", "자연·기상조건",
    "대상외",
]

SENTIMENTS = ["POS", "NEG", "NEU"]

SYSTEM_PROMPT = """당신은 한국어 관광지 리뷰의 만족·불만 요인 분석 어노테이터다.
리뷰 1건에서 (요인 카테고리, 원문 스팬, 평가 표현, 극성) 튜플을 추출한다.
학술 연구용 라벨이므로 일관성과 보수성이 최우선이다.

# 코딩 원칙

1. 리뷰 1건에서 튜플을 0개 이상 추출한다. 한 리뷰에 복수 튜플을 허용한다.
2. 카테고리는 발화의 술어가 평가하는 대상을 따른다. 같은 사물이라도 술어가 다르면
   카테고리가 다르다 — "다리(경치)가 멋있다"는 경관·볼거리,
   "건너는 게 스릴 있다/무섭다/출렁인다"는 체험·활동이다.
3. 한 발화가 복수 요인을 평가하면 각각 추출한다. 인과 연쇄(혼잡 때문에 다리가 흔들림)는
   원인과 결과 요인을 모두 코딩한다.
4. 억지 추출 금지. 판정 가능한 요인이 없으면 factors를 빈 배열로 반환한다.
   감탄·총평·재방문 의사·동반 적합성만 있는 발화("굿", "또 오고 싶다", "아이랑 가기 좋아요")는
   요인이 아니다. 빈 배열은 정답이며 감점 요인이 아니다.
5. 평가 대상이 이 관광지가 아닌 발화(주변 상권·타 관광지)는 category="대상외"로 추출한다.
   위치 표지가 없는 음식점 언급은 대상외가 기본값이다. 타 관광지는 그 자체가 평가 대상일
   때만 대상외이고, 수사적 비교나 배경 서술이면 코딩하지 않는다.
6. span과 opinion은 반드시 리뷰 본문에 있는 표현을 그대로 옮긴다. 요약·변형·번역 금지.
7. 양보절은 별도 튜플로 세우지 않는다. 핵심 주장 중심으로 코딩한다.
   예: "지금은 볼만한데 꽃 지고나면 볼게 없네요" → 핵심은 시기 의존 불만 하나다.
8. 관광지 부지 안의 판매·운영 인력은 소속(직영/입점) 불문 인적서비스다.
   리뷰어의 동행자는 인력이 아니다.
9. 수사의문·반어의 극성은 후행 절의 표지로 판정한다. 표지가 없으면 보수적으로 NEU 또는 비코딩.
   예: "국립이 관리를 이렇게 잘한다? 직원들 월급 많이줘야됨" → 관리·청결 POS.
10. "무섭다"는 재미·스릴 표지(스릴, 짜릿, 재밌)가 동반될 때만 POS, 아니면 NEG.
11. 오탈자·방언·구어체가 많다. 표기가 틀려도 의미로 판단한다.
    예: "칠절한"=친절한, "추차"=주차, "입징료"=입장료.

# 극성 (3값)

- POS: 해당 요인에 대한 긍정 평가 (만족 요인)
- NEG: 해당 요인에 대한 부정 평가 (불만 요인)
- NEU: 평가어 없는 사실·정보 언급. 예: "입장료 3천원", 운영시간 안내.
  중립 언급도 관심도 신호이므로 버리지 않는다.

# 카테고리 12종

## 경관·볼거리
자연·인공 경관, 조망, 꽃, 야간 조명, 조형·테마 연출, 역사·문화 자원 등 '볼 것'의
아름다움과 매력. 볼거리의 양·규모, 사진 촬영 적합성 포함.
제외: 수위·날씨·개화 '시점' 탓은 자연·기상조건. 걷는 길의 조성은 산책·휴식공간.

## 체험·활동
그곳에서 '하는 것' — 출렁다리 건너기, 치즈·피자 만들기, 안전 체험, 축제·공연,
사격, 골프 라운드, 등산 — 의 재미·품질·운영.
제외: 체험 예약·시간 '정보'는 안내·운영. 체험비는 요금·가성비. 강사 친절은 인적서비스.

## 산책·휴식공간
산책로·데크길·둘레길·정원 동선·잔디밭·정자·쉼터 등 걷고 쉬는 공간의 조성과 적합성.
제외: 걷다가 본 풍경은 경관·볼거리. 파손·보수 상태는 관리·청결.

## 편의시설
화장실·매점·카페·편의점·놀이터·그늘막·클럽하우스 등 지원 시설의 존재·충분성·편의성.
제외: 시설의 청결·고장은 관리·청결. 매점 음식의 맛은 음식·특산품.

## 관리·청결
청결·유지보수·안전 관리 수준, 신규 조성지의 공사 미완·정비 진행 상태.
제외: 혼잡은 혼잡·대기. 가뭄·녹조 등 자연 상태는 자연·기상조건.

## 접근·주차
오는 길·진입로·주차·셔틀·대중교통 등 도착부터 입구까지의 편의.
제외: 관광지 내부 보행 동선은 산책·휴식공간. 주차비는 요금·가성비.

## 인적서비스
직원·강사·교관·캐디·상인 등 현장 인력의 친절·응대·전문성.

## 음식·특산품
관광지 안에서 파는 음식·카페 메뉴·특산품·기념품의 맛·품질·구색.
제외: 관광지 밖 주변 식당은 대상외. 음식 가격은 요금·가성비.

## 요금·가성비
입장료·체험비·주차비·음식값의 수준과 지불 대비 가치. 무료 언급 포함.

## 안내·운영
운영시간·예약·이용 조건·안내판·해설·사전 온라인 정보의 정확성과 충실성.

## 혼잡·대기
인파·대기 시간·한산함, 타 방문객 행태로 인한 경험 변화.
한산함의 극성은 화자의 정서 표지를 따른다(힐링이면 POS, 썰렁하면 NEG, 표지 없으면 NEU).

## 자연·기상조건
수위·가뭄·녹조·날씨·더위·바람·개화 시기 등 방문 시점의 자연 조건.
시설이 통제할 수 없는 요인이므로 별도로 분리한다.
제외: 그늘막·차양 같은 대응 시설의 부족은 편의시설.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "factors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": CATEGORIES},
                    "span": {"type": "string"},
                    "opinion": {"type": "string"},
                    "sentiment": {"type": "string", "enum": SENTIMENTS},
                },
                "required": ["category", "span", "opinion", "sentiment"],
                "additionalProperties": False,
            },
        },
        "overall_sentiment": {"type": "string", "enum": SENTIMENTS},
    },
    "required": ["factors", "overall_sentiment"],
    "additionalProperties": False,
}

ADAPTIVE_MODELS = ("claude-opus-5", "claude-opus-4-8", "claude-opus-4-7",
                   "claude-sonnet-5", "claude-sonnet-4-6", "claude-fable-5")


# ─────────────────────────────────────────────────────────────────────
# .env 로딩
# ─────────────────────────────────────────────────────────────────────

def load_api_key() -> str:
    """`.env`에서 ANTHROPIC_API_KEY를 읽는다. 환경변수가 이미 있으면 그것을 쓴다."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    if not ENV_FILE.exists():
        sys.exit(f"오류: {ENV_FILE.name} 파일이 없습니다.\n"
                 f"      {ENV_FILE} 에 ANTHROPIC_API_KEY=sk-ant-... 를 넣어주세요.")
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == "ANTHROPIC_API_KEY":
            return value.strip().strip('"').strip("'")
    sys.exit(f"오류: {ENV_FILE.name} 안에 ANTHROPIC_API_KEY 항목이 없습니다.")


# ─────────────────────────────────────────────────────────────────────
# API 호출
# ─────────────────────────────────────────────────────────────────────

def call_api(client, model: str, effort: str, place: str, body: str) -> dict:
    kwargs = dict(
        model=model,
        max_tokens=4000,
        system=[{"type": "text", "text": SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
        messages=[{"role": "user",
                   "content": f"[관광지] {place}\n[리뷰 본문]\n{body}"}],
    )
    output_config = {"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}}
    if model.startswith(ADAPTIVE_MODELS):
        kwargs["thinking"] = {"type": "adaptive"}
        output_config["effort"] = effort
    kwargs["output_config"] = output_config

    resp = client.messages.create(**kwargs)
    if resp.stop_reason == "refusal":
        raise RuntimeError("refusal")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("max_tokens")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    if not text.strip():
        raise RuntimeError("empty_response")
    return json.loads(text)


def to_row(parsed: dict) -> dict:
    """추출 결과를 리뷰 1행으로 정리한다."""
    factors = [f for f in (parsed.get("factors") or [])
               if isinstance(f, dict)
               and f.get("category") in CATEGORIES
               and f.get("sentiment") in SENTIMENTS]

    def pick(poll):
        return [f for f in factors if f["sentiment"] == poll]

    pos, neg, neu = pick("POS"), pick("NEG"), pick("NEU")

    def cats(items):
        seen = []
        for f in items:
            if f["category"] not in seen:
                seen.append(f["category"])
        return " | ".join(seen)

    def detail(items):
        return " | ".join(f"{f['category']}:{f['span']}" for f in items)

    overall = parsed.get("overall_sentiment")
    return {
        "analyzed": True,
        "overall_sentiment": overall if overall in SENTIMENTS else "NEU",
        "n_satisfaction": len(pos),
        "n_dissatisfaction": len(neg),
        "satisfaction_categories": cats(pos),
        "dissatisfaction_categories": cats(neg),
        "neutral_categories": cats(neu),
        "satisfaction_factors": detail(pos),
        "dissatisfaction_factors": detail(neg),
        "factors_json": json.dumps({"factors": factors, "overall_sentiment": overall},
                                   ensure_ascii=False),
        "run_status": "ok",
    }


def blank_row(status: str) -> dict:
    row = {c: "" for c in RESULT_COLUMNS}
    row.update({"analyzed": False, "n_satisfaction": 0,
                "n_dissatisfaction": 0, "run_status": status})
    return row


# ─────────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="리뷰별 만족·불만 요인 분석")
    ap.add_argument("--input", type=Path, default=INPUT_CSV)
    ap.add_argument("--output", type=Path, default=OUTPUT_CSV)
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default="medium",
                    choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0, help="N건만 처리 (0=전량)")
    ap.add_argument("--dry-run", action="store_true", help="API 호출 없이 대상 집계만")
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"오류: 입력 파일이 없습니다 — {args.input}")

    # 원본을 문자열 그대로 읽어 컬럼 값을 손대지 않는다.
    df = pd.read_csv(args.input, dtype=str, keep_default_na=False,
                     encoding="utf-8-sig")
    missing = [c for c in BASE_COLUMNS if c not in df.columns]
    if missing:
        sys.exit(f"오류: 입력 파일에 필요한 컬럼이 없습니다 — {missing}")

    print(f"[1/4] 입력 {len(df):,}행 — {args.input.name}")

    # 본문이 있는 리뷰만 분석 대상
    body = df["body"].fillna("").str.strip()
    target_mask = body != ""
    print(f"      본문 있음 {int(target_mask.sum()):,}건 / "
          f"본문 없음 {int((~target_mask).sum()):,}건(분석 제외)")

    # 이어하기: 기존 출력에서 완료된 reviewId를 건너뛴다.
    done: dict[str, dict] = {}
    if args.output.exists():
        prev = pd.read_csv(args.output, dtype=str, keep_default_na=False,
                           encoding="utf-8-sig")
        for _, r in prev.iterrows():
            if r.get("run_status") == "ok":
                done[r["reviewId"]] = {c: r.get(c, "") for c in RESULT_COLUMNS}
        print(f"      기존 출력에서 완료분 {len(done):,}건 재사용")

    todo = [i for i in df.index[target_mask] if df.at[i, "reviewId"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"[2/4] 호출 대상 {len(todo):,}건 (model={args.model}, effort={args.effort})")

    results: dict[str, dict] = {}
    if args.dry_run:
        print("[3/4] --dry-run: API 호출을 건너뜁니다.")
    elif todo:
        try:
            import anthropic
        except ImportError:
            sys.exit("오류: anthropic 패키지가 없습니다.  pip install anthropic")

        client = anthropic.Anthropic(api_key=load_api_key(),
                                     max_retries=8, timeout=600.0)
        lock = threading.Lock()
        state = {"n": 0, "fail": 0}
        total = len(todo)

        def work(idx):
            rid = df.at[idx, "reviewId"]
            try:
                parsed = call_api(client, args.model, args.effort,
                                  df.at[idx, "place"], df.at[idx, "body"].strip())
                row = to_row(parsed)
            except Exception as exc:  # 실패는 버리지 않고 사유를 기록한다
                row = blank_row(f"{type(exc).__name__}: {exc}"[:200])
            with lock:
                results[rid] = row
                state["n"] += 1
                if row["run_status"] != "ok":
                    state["fail"] += 1
                if state["n"] % 25 == 0 or state["n"] == total:
                    print(f"      {state['n']:,}/{total:,} "
                          f"(실패 {state['fail']:,})", flush=True)

        print("[3/4] API 호출 시작")
        t0 = time.monotonic()
        work(todo[0])                      # 첫 호출로 프롬프트 캐시를 채운다

        # 첫 호출이 실패하면 설정 문제이므로 나머지를 헛돌리지 않고 즉시 멈춘다.
        first = results[df.at[todo[0], "reviewId"]]
        if first["run_status"] != "ok":
            sys.exit(f"\n오류: 첫 호출이 실패했습니다 — {first['run_status']}\n"
                     f"      .env의 API 키, 크레딧 잔액, 모델명(--model)을 확인하세요.\n"
                     f"      나머지 {len(todo) - 1:,}건은 실행하지 않았습니다.")

        if len(todo) > 1:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                list(pool.map(work, todo[1:]))
        print(f"      소요 {time.monotonic() - t0:,.0f}초")

    # 출력 조립 — 원본 컬럼을 그대로 두고 결과 컬럼을 덧붙인다.
    print("[4/4] 출력 파일 작성")
    rows = []
    for i in df.index:
        rid = df.at[i, "reviewId"]
        if rid in results:
            res = results[rid]
        elif rid in done:
            res = done[rid]
        elif not target_mask.at[i]:
            res = blank_row("skipped: 본문 없음")
        else:
            res = blank_row("pending: 미처리")
        rows.append(res)

    out = df[BASE_COLUMNS].copy()
    for col in RESULT_COLUMNS:
        out[col] = [r.get(col, "") for r in rows]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8-sig")

    ok = int((out["run_status"] == "ok").sum())
    print(f"\n완료: {len(out):,}행 → {args.output}")
    if ok:
        analyzed = out[out["run_status"] == "ok"]
        n_pos = pd.to_numeric(analyzed["n_satisfaction"]).sum()
        n_neg = pd.to_numeric(analyzed["n_dissatisfaction"]).sum()
        empty = int(((pd.to_numeric(analyzed["n_satisfaction"]) == 0) &
                     (pd.to_numeric(analyzed["n_dissatisfaction"]) == 0)).sum())
        print(f"  분석 성공 {ok:,}건 | 만족 요인 {n_pos:,}개 · 불만 요인 {n_neg:,}개")
        print(f"  요인 없음(감탄·총평만) {empty:,}건 ({empty / ok * 100:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
