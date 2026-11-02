#!/usr/bin/env python3
"""work/batch.jsonl 의 신규 번호만 annotations.jsonl 에 추가 (재실행해도 안전)."""
import json
have = {json.loads(l)['i'] for l in open('work/annotations.jsonl', encoding='utf-8') if l.strip()}
new = []
for l in open('work/batch.jsonl', encoding='utf-8'):
    if not l.strip(): continue
    i = json.loads(l)['i']
    if i not in have:
        have.add(i); new.append(l.rstrip("\n"))
if new:
    with open('work/annotations.jsonl', 'a', encoding='utf-8') as f:
        f.write("\n".join(new) + "\n")
print(f"신규 {len(new)}건 추가")
