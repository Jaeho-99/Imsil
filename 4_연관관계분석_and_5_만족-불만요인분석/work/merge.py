#!/usr/bin/env python3
"""annotations.jsonl 검증 + CSV 병합.
   python work/merge.py --check   # 검증만
   python work/merge.py           # 검증 후 CSV 기록
"""
import json, re, sys, collections
import pandas as pd

CATEGORIES = ["경관·볼거리","체험·활동","산책·휴식공간","편의시설","관리·청결",
              "접근·주차","인적서비스","음식·특산품","요금·가성비","안내·운영",
              "혼잡·대기","자연·기상조건","대상외"]
SENTIMENTS = ["POS","NEG","NEU"]
OUT = 'output/리뷰별_만족불만요인_분석결과.csv'

pend = {r['i']: r for r in map(json.loads, open('work/pending.jsonl', encoding='utf-8'))}
norm = lambda s: re.sub(r'\s+', ' ', s).strip()

ann, errs, seen = {}, [], collections.Counter()
for ln, line in enumerate(open('work/annotations.jsonl', encoding='utf-8'), 1):
    line = line.strip()
    if not line:
        continue
    try:
        a = json.loads(line)
    except Exception as e:
        errs.append(f"L{ln}: JSON 파싱 실패 — {e}"); continue
    i = a.get('i')
    if i not in pend:
        errs.append(f"L{ln}: 존재하지 않는 번호 {i}"); continue
    seen[i] += 1
    if seen[i] > 1:
        errs.append(f"L{ln}: #{i} 중복"); continue
    if a.get('o') not in SENTIMENTS:
        errs.append(f"L{ln}: #{i} overall '{a.get('o')}' 부적합"); continue
    body = norm(pend[i]['body'])
    bad = False
    for f in a.get('f', []):
        if not (isinstance(f, list) and len(f) == 4):
            errs.append(f"L{ln}: #{i} 튜플 형식 오류 {f}"); bad = True; continue
        cat, span, op, sent = f
        if cat not in CATEGORIES:
            errs.append(f"L{ln}: #{i} 카테고리 '{cat}' 부적합"); bad = True
        if sent not in SENTIMENTS:
            errs.append(f"L{ln}: #{i} 극성 '{sent}' 부적합"); bad = True
        if norm(span) not in body:
            errs.append(f"L{ln}: #{i} span 본문에 없음 — '{span}'"); bad = True
        if norm(op) not in body:
            errs.append(f"L{ln}: #{i} opinion 본문에 없음 — '{op}'"); bad = True
    if not bad:
        ann[i] = a

missing = [i for i in pend if i not in ann]
print(f"라벨 {len(ann):,}/{len(pend):,}건  |  미처리 {len(missing):,}건  |  오류 {len(errs):,}건")
if errs:
    print("\n--- 오류 ---")
    for e in errs[:40]:
        print(" ", e)
if missing:
    print(f"  다음 미처리 시작번호: #{missing[0]}")
if errs:
    sys.exit(1)
if '--check' in sys.argv:
    sys.exit(0)

def row(a):
    fs = [{"category":c,"span":s,"opinion":o,"sentiment":p} for c,s,o,p in a['f']]
    pick = lambda p: [f for f in fs if f['sentiment'] == p]
    pos, neg, neu = pick("POS"), pick("NEG"), pick("NEU")
    cats = lambda it: " | ".join(dict.fromkeys(f['category'] for f in it))
    det  = lambda it: " | ".join(f"{f['category']}:{f['span']}" for f in it)
    return {"analyzed": True, "overall_sentiment": a['o'],
            "n_satisfaction": len(pos), "n_dissatisfaction": len(neg),
            "satisfaction_categories": cats(pos), "dissatisfaction_categories": cats(neg),
            "neutral_categories": cats(neu), "satisfaction_factors": det(pos),
            "dissatisfaction_factors": det(neg),
            "factors_json": json.dumps({"factors": fs, "overall_sentiment": a['o']},
                                       ensure_ascii=False),
            "run_status": "ok"}

df = pd.read_csv(OUT, dtype=str, keep_default_na=False, encoding='utf-8-sig')
by_rid = {pend[i]['rid']: row(a) for i, a in ann.items()}
n = 0
for idx in df.index:
    r = by_rid.get(df.at[idx, 'reviewId'])
    if r:
        for k, v in r.items():
            df.at[idx, k] = str(v)
        n += 1
df.to_csv(OUT, index=False, encoding='utf-8-sig')
print(f"CSV 반영 {n:,}행 → {OUT}")
