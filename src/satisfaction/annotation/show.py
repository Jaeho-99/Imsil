#!/usr/bin/env python3
"""배치 출력: python src/satisfaction/annotation/show.py <시작번호> <건수>

input/satisfaction/pending.jsonl 의 리뷰를 번호 순서로 보여 준다. 판정(annotations.jsonl)을 채울 때 쓴다.
"""
import json, re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SATIS_IN  # noqa: E402
start, count = int(sys.argv[1]), int(sys.argv[2])
for line in open(SATIS_IN / 'pending.jsonl', encoding='utf-8'):
    r = json.loads(line)
    if start <= r['i'] < start + count:
        body = re.sub(r'\s*\n\s*', ' ⏎ ', r['body'])
        print(f"#{r['i']} [{r['place']}] {body}")
