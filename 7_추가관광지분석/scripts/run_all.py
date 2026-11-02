# -*- coding: utf-8 -*-
"""1~7단계를 순서대로 실행한다 (수집 0단계 제외).

    python scripts/run_all.py            # 전 과정 (API 단계 포함)
    python scripts/run_all.py --no-api   # API 없는 단계만: 번역·LLM 정규화·감성 분류·요인 추출을 건너뜀
    IMSIL_DEMO=1 python scripts/run_all.py --no-api --demo   # 시험 실행

감성분석의 사람 검토(사람검토표.xlsx)는 자동으로 할 수 없으므로, 전 과정 모드에서는
review 까지 만든 뒤 merge 를 한 번 돌리고 멈춘다. 검토표를 채운 다음
`python scripts/s5_sentiment.py merge` → `python scripts/s7_summary.py` 를 다시 실행한다.
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def step(*args):
    print(f"\n{'=' * 70}\n▶ {' '.join(args)}\n{'=' * 70}", flush=True)
    subprocess.run([sys.executable, str(HERE / args[0]), *args[1:]], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-api", action="store_true")
    ap.add_argument("--demo", action="store_true", help="IMSIL_DEMO=1 과 함께: 가짜 수집 원본 생성")
    a = ap.parse_args()
    step("s1_build_dataset.py", *(["--demo"] if a.demo else []))
    step("s2_preprocess.py", *([] if a.no_api else ["--translate"]))
    step("s3_keywords.py")
    step("s4_association.py", *(["--no-llm"] if a.no_api else []))
    step("s5_sentiment.py", "build")
    if not a.no_api:
        step("s5_sentiment.py", "validate", "--run", "run1")
        step("s5_sentiment.py", "validate", "--run", "run2")
        step("s5_sentiment.py", "run", "--run", "run1")
        step("s5_sentiment.py", "run", "--run", "run2")
        from common import config  # noqa: E402
        if not (config.OUT_SENT / "사람검토표.xlsx").exists():
            step("s5_sentiment.py", "review")
        step("s5_sentiment.py", "merge")
    step("s6_satisfaction.py", *(["--dry-run"] if a.no_api else []))
    step("s7_summary.py")


if __name__ == "__main__":
    main()
