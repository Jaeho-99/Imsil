#!/usr/bin/env python3
"""배치 출력: python work/show.py <시작번호> <건수>"""
import json, sys, re
start, count = int(sys.argv[1]), int(sys.argv[2])
for line in open('work/pending.jsonl', encoding='utf-8'):
    r = json.loads(line)
    if start <= r['i'] < start + count:
        body = re.sub(r'\s*\n\s*', ' ⏎ ', r['body'])
        print(f"#{r['i']} [{r['place']}] {body}")
