#!/usr/bin/env python3
"""input/satisfaction/batch.jsonl 의 신규 번호만 annotations.jsonl 에 추가 (재실행해도 안전).

판정 입력용 도구다. 결과는 input/satisfaction/annotations.jsonl (사람·LLM 이 만든 입력) 에 쌓인다.
실행: python src/satisfaction/annotation/add.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SATIS_IN  # noqa: E402
have = {json.loads(l)['i'] for l in open(SATIS_IN / 'annotations.jsonl', encoding='utf-8') if l.strip()}
new = []
for l in open(SATIS_IN / 'batch.jsonl', encoding='utf-8'):
    if not l.strip(): continue
    i = json.loads(l)['i']
    if i not in have:
        have.add(i); new.append(l.rstrip("\n"))
if new:
    with open(SATIS_IN / 'annotations.jsonl', 'a', encoding='utf-8') as f:
        f.write("\n".join(new) + "\n")
print(f"신규 {len(new)}건 추가")
