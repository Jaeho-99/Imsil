#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""임실군 관광지 리뷰 — 키워드 연관관계 분석 (전처리)

입력  : output/keyword/리뷰데이터_키워드전처리완료.csv  (키워드 분석 결과)
설정  : .env  (레포 최상위, ANTHROPIC_API_KEY=sk-ant-...)
출력  : output/association/연관관계_분석결과.csv

리뷰 1건을 트랜잭션 1개로 보고 키워드 간 연관규칙(A ⇒ B)을 도출한다.

  · 판단은 LLM이  — 동의어 통합(이쁘다→예쁘다, 주차장→주차)과 기능어 제거,
                    키워드의 요인 카테고리 부여
  · 계산은 코드가  — 지지도·신뢰도·향상도·레버리지·확신도 전부 pandas/파이썬 산출

실행
    python src/association/analyze_association.py                  # 기본 (LLM 정규화 + 전체 규칙)
    python src/association/analyze_association.py --no-llm         # API 없이 원본 키워드로 계산
    python src/association/analyze_association.py --by-place       # 관광지별 규칙까지 추가 산출

보고서 4장의 결과(output/association/연관관계_분석결과.csv)는 API 없이 아래 설정으로 만들었다.
    python src/association/analyze_association.py --no-llm --by-place --min-place-transactions 50

필요 패키지: pandas, anthropic (--no-llm 이면 pandas만)
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import ASSOC_OUT, ENV_FILE, KEYWORD_DATA  # noqa: E402
INPUT_CSV = KEYWORD_DATA                       # 키워드 분석 결과 (output/keyword/)
OUTPUT_CSV = ASSOC_OUT / "연관관계_분석결과.csv"

KEYWORD_COLUMN = "keyword_tokens_final"
PLACE_COLUMN = "place"

# 만족·불만 요인 분석과 동일한 카테고리 체계 — 두 결과를 연결해 해석할 수 있다.
CATEGORIES = [
    "경관·볼거리", "체험·활동", "산책·휴식공간", "편의시설",
    "관리·청결", "접근·주차", "인적서비스", "음식·특산품",
    "요금·가성비", "안내·운영", "혼잡·대기", "자연·기상조건",
    "감정표현", "기타",
]

ADAPTIVE_MODELS = ("claude-opus-5", "claude-opus-4-8", "claude-opus-4-7",
                   "claude-sonnet-5", "claude-sonnet-4-6", "claude-fable-5")

NORMALIZE_PROMPT = """당신은 한국어 관광지 리뷰에서 추출된 키워드를 정리하는 어노테이터다.
형태소 분석으로 뽑힌 키워드 목록을 받아 각 키워드마다 세 가지를 판정한다.

1. canonical (대표어)
   의미가 같은 표기·활용형을 하나로 통합한다.
   예: 이쁘다/예쁘다 → 예쁘다,  주차장/주차 → 주차,  애기/아이 → 아이
   통합할 대상이 없으면 키워드를 그대로 쓴다. 반드시 목록 안에 있는 표현 중 하나를 고른다.

2. category (요인 카테고리)
   그 키워드가 주로 어떤 요인을 가리키는지 아래 중 하나로 정한다.
   경관·볼거리 / 체험·활동 / 산책·휴식공간 / 편의시설 / 관리·청결 / 접근·주차 /
   인적서비스 / 음식·특산품 / 요금·가성비 / 안내·운영 / 혼잡·대기 / 자연·기상조건 /
   감정표현 / 기타
   - 감정표현: 좋다·예쁘다·아쉽다처럼 대상이 아니라 평가 자체를 나타내는 말
   - 기타: 특정 요인으로 묶기 어려운 일반 명사

3. is_stopword (분석 제외 여부)
   그 자체로는 의미를 거의 담지 않는 기능어면 true.
   예: 있다, 없다, 되다, 하다, 이다, 것, 수, 등, 때, 저희, 우리
   구체적 대상이나 평가를 담은 말은 false로 둔다.

목록에 있는 키워드를 하나도 빠뜨리지 말고 전부 판정해서 반환한다."""


def normalize_schema(keywords: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "enum": keywords},
                        "canonical": {"type": "string"},
                        "category": {"type": "string", "enum": CATEGORIES},
                        "is_stopword": {"type": "boolean"},
                    },
                    "required": ["keyword", "canonical", "category", "is_stopword"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }


# ─────────────────────────────────────────────────────────────────────
# .env 로딩
# ─────────────────────────────────────────────────────────────────────

def load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    if not ENV_FILE.exists():
        sys.exit(f"오류: {ENV_FILE.name} 파일이 없습니다.\n"
                 f"      {ENV_FILE} 에 ANTHROPIC_API_KEY=sk-ant-... 를 넣어주세요.\n"
                 f"      (API 없이 돌리려면 --no-llm 옵션을 쓰세요.)")
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
# 1. 키워드 정규화 (LLM 판단)
# ─────────────────────────────────────────────────────────────────────

def normalize_keywords(vocab: list[str], model: str, effort: str,
                       batch_size: int = 120) -> dict[str, dict]:
    try:
        import anthropic
    except ImportError:
        sys.exit("오류: anthropic 패키지가 없습니다.  pip install anthropic\n"
                 "      (API 없이 돌리려면 --no-llm 옵션을 쓰세요.)")

    client = anthropic.Anthropic(api_key=load_api_key(), max_retries=8, timeout=600.0)
    mapping: dict[str, dict] = {}
    batches = [vocab[i:i + batch_size] for i in range(0, len(vocab), batch_size)]

    for bi, batch in enumerate(batches, 1):
        kwargs = dict(
            model=model,
            max_tokens=16000,
            system=[{"type": "text", "text": NORMALIZE_PROMPT,
                     "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            messages=[{"role": "user",
                       "content": "다음 키워드를 판정하라.\n" + "\n".join(batch)}],
            output_config={"format": {"type": "json_schema",
                                      "schema": normalize_schema(batch)}},
        )
        if model.startswith(ADAPTIVE_MODELS):
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"]["effort"] = effort

        try:
            resp = client.messages.create(**kwargs)
            text = next((b.text for b in resp.content if b.type == "text"), "")
            for it in json.loads(text).get("items", []):
                kw = it.get("keyword")
                if kw in mapping or kw not in batch:
                    continue
                mapping[kw] = {
                    "canonical": (it.get("canonical") or kw).strip() or kw,
                    "category": it.get("category", "기타"),
                    "is_stopword": bool(it.get("is_stopword", False)),
                }
        except Exception as exc:
            print(f"      배치 {bi} 실패({type(exc).__name__}) — 원본 키워드로 대체")

        print(f"      정규화 {bi}/{len(batches)} 배치 완료 "
              f"(누적 {len(mapping):,}/{len(vocab):,})", flush=True)

    for kw in vocab:                       # 누락분은 원본 그대로 통과시킨다
        mapping.setdefault(kw, {"canonical": kw, "category": "기타",
                                "is_stopword": False})
    return mapping


# ─────────────────────────────────────────────────────────────────────
# 2. 연관규칙 계산 (전부 코드 산출)
# ─────────────────────────────────────────────────────────────────────

def frequent_itemsets(transactions: list[frozenset], min_count: int,
                      max_len: int) -> dict[frozenset, int]:
    """Apriori — 최소 출현 건수 이상인 항목집합을 크기 1부터 max_len까지 센다."""
    counts: dict[frozenset, int] = {}

    c1 = Counter()
    for t in transactions:
        c1.update(t)
    level = {frozenset([k]) for k, v in c1.items() if v >= min_count}
    for s in level:
        counts[s] = c1[next(iter(s))]

    k = 2
    while level and k <= max_len:
        items = sorted({i for s in level for i in s})
        allowed = set(items)
        nxt = Counter()
        for t in transactions:
            cand = sorted(t & allowed)
            if len(cand) >= k:
                for combo in combinations(cand, k):
                    nxt[frozenset(combo)] += 1
        level = {s for s, v in nxt.items() if v >= min_count}
        for s in level:
            counts[s] = nxt[s]
        k += 1
    return counts


def make_rules(counts: dict[frozenset, int], n_tx: int,
               min_conf: float, min_lift: float) -> list[dict]:
    rules = []
    for itemset, both in counts.items():
        if len(itemset) < 2:
            continue
        for r in range(1, len(itemset)):
            for ante in combinations(sorted(itemset), r):
                a = frozenset(ante)
                b = itemset - a
                ca, cb = counts.get(a), counts.get(b)
                if not ca or not cb:
                    continue
                support = both / n_tx
                conf = both / ca
                sup_b = cb / n_tx
                lift = conf / sup_b if sup_b else 0.0
                if conf < min_conf or lift < min_lift:
                    continue
                rules.append({
                    "antecedent": ", ".join(sorted(a)),
                    "consequent": ", ".join(sorted(b)),
                    "antecedent_size": len(a),
                    "support": round(support, 6),
                    "confidence": round(conf, 6),
                    "lift": round(lift, 6),
                    "leverage": round(support - (ca / n_tx) * sup_b, 6),
                    "conviction": (round((1 - sup_b) / (1 - conf), 6)
                                   if conf < 1 else ""),
                    "count_both": both,
                    "count_antecedent": ca,
                    "count_consequent": cb,
                    "n_transactions": n_tx,
                })
    rules.sort(key=lambda d: (-d["lift"], -d["support"]))
    return rules


# ─────────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="키워드 연관관계 분석")
    ap.add_argument("--input", type=Path, default=INPUT_CSV)
    ap.add_argument("--output", type=Path, default=OUTPUT_CSV)
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default="low",
                    choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--no-llm", action="store_true",
                    help="LLM 정규화 없이 원본 키워드로 계산")
    ap.add_argument("--min-keyword-count", type=int, default=5,
                    help="이 횟수 미만 출현 키워드는 제외")
    ap.add_argument("--min-support", type=float, default=0.01)
    ap.add_argument("--min-confidence", type=float, default=0.2)
    ap.add_argument("--min-lift", type=float, default=1.0)
    ap.add_argument("--max-itemset", type=int, default=3)
    ap.add_argument("--by-place", action="store_true",
                    help="관광지별 규칙도 함께 산출")
    ap.add_argument("--min-place-transactions", type=int, default=100)
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"오류: 입력 파일이 없습니다 — {args.input}")

    df = pd.read_csv(args.input, dtype=str, keep_default_na=False,
                     encoding="utf-8-sig")
    if KEYWORD_COLUMN not in df.columns:
        sys.exit(f"오류: '{KEYWORD_COLUMN}' 컬럼이 없습니다. "
                 f"있는 컬럼: {list(df.columns)}")

    print(f"[1/4] 입력 {len(df):,}행 — {args.input.name}")

    # 트랜잭션 구성
    tx_raw, tx_place = [], []
    for _, r in df.iterrows():
        try:
            toks = ast.literal_eval(r[KEYWORD_COLUMN]) if r[KEYWORD_COLUMN] else []
        except (ValueError, SyntaxError):
            toks = []
        toks = [str(t).strip() for t in toks if str(t).strip()]
        if toks:
            tx_raw.append(toks)
            tx_place.append(r.get(PLACE_COLUMN, ""))

    freq = Counter(k for t in tx_raw for k in set(t))
    vocab = sorted([k for k, v in freq.items() if v >= args.min_keyword_count],
                   key=lambda k: (-freq[k], k))
    print(f"      트랜잭션 {len(tx_raw):,}건 | 고유 키워드 {len(freq):,}개 "
          f"→ {args.min_keyword_count}회 이상 {len(vocab):,}개")

    # 키워드 정규화
    if args.no_llm:
        print("[2/4] --no-llm: 원본 키워드를 그대로 사용")
        mapping = {k: {"canonical": k, "category": "기타", "is_stopword": False}
                   for k in vocab}
    else:
        print(f"[2/4] 키워드 정규화 (model={args.model}, effort={args.effort})")
        mapping = normalize_keywords(vocab, args.model, args.effort)

    dropped = {k for k, m in mapping.items() if m["is_stopword"]}
    canon = {k: m["canonical"] for k, m in mapping.items() if k not in dropped}
    cat_of: dict[str, str] = {}
    for k, m in mapping.items():
        cat_of.setdefault(m["canonical"], m["category"])
    print(f"      기능어 제외 {len(dropped):,}개 | "
          f"통합 후 항목 {len(set(canon.values())):,}개")

    transactions, places = [], []
    for toks, pl in zip(tx_raw, tx_place):
        s = frozenset(canon[t] for t in toks if t in canon)
        if len(s) >= 2:                    # 규칙은 항목 2개 이상에서만 나온다
            transactions.append(s)
            places.append(pl)

    # 연관규칙 계산
    print(f"[3/4] 연관규칙 계산 — 유효 트랜잭션 {len(transactions):,}건")
    all_rules = []

    def run_scope(scope: str, txs: list[frozenset]):
        n = len(txs)
        min_count = max(5, int(round(args.min_support * n)))
        counts = frequent_itemsets(txs, min_count, args.max_itemset)
        rules = make_rules(counts, n, args.min_confidence, args.min_lift)
        for r in rules:
            r["scope"] = scope
            r["antecedent_category"] = " | ".join(
                dict.fromkeys(cat_of.get(x, "기타") for x in r["antecedent"].split(", ")))
            r["consequent_category"] = " | ".join(
                dict.fromkeys(cat_of.get(x, "기타") for x in r["consequent"].split(", ")))
        all_rules.extend(rules)
        print(f"      [{scope}] 트랜잭션 {n:,} | 최소 출현 {min_count} | 규칙 {len(rules):,}개")

    run_scope("전체", transactions)

    if args.by_place:
        by = defaultdict(list)
        for t, pl in zip(transactions, places):
            by[pl].append(t)
        for pl, txs in sorted(by.items(), key=lambda kv: -len(kv[1])):
            if len(txs) >= args.min_place_transactions:
                run_scope(pl, txs)

    # 출력
    print("[4/4] 출력 파일 작성")
    cols = ["scope", "antecedent", "consequent", "antecedent_category",
            "consequent_category", "antecedent_size", "support", "confidence",
            "lift", "leverage", "conviction", "count_both", "count_antecedent",
            "count_consequent", "n_transactions"]
    out = pd.DataFrame(all_rules, columns=cols) if all_rules else pd.DataFrame(columns=cols)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"\n완료: 규칙 {len(out):,}개 → {args.output}")
    if len(out):
        top = out[out["scope"] == "전체"].head(10)
        print("\n상위 규칙 (향상도 순):")
        for _, r in top.iterrows():
            print(f"  {r['antecedent']} ⇒ {r['consequent']}  "
                  f"(지지도 {r['support']:.3f}, 신뢰도 {r['confidence']:.3f}, "
                  f"향상도 {r['lift']:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
