# -*- coding: utf-8 -*-
"""추가 관광지 분석의 수집 뒤 전 과정을 순서대로 실행한다 (수집은 collect_naver.py 로 따로 한다).

    python src/new_sites/run_all.py            # 전 과정 (API 단계 포함)
    python src/new_sites/run_all.py --no-api   # API 없는 단계만: 번역·LLM 정규화·감성 분류·요인 추출을 건너뜀
    IMSIL_DEMO=1 python src/new_sites/run_all.py --no-api --demo   # 시험 실행 (output/_demo/ 에만 쓴다)

순서: build_dataset → preprocess → keywords → association → sentiment → satisfaction → summary

감성분석의 사람 검토(사람검토표.xlsx)는 자동으로 할 수 없으므로, 전 과정 모드에서는
review 로 양식까지 만든 뒤 merge 를 한 번 돌리고 멈춘다. 양식을 input/new_sites/사람검토표.xlsx 로
복사해 채운 다음 `python src/new_sites/sentiment.py merge` → `python src/new_sites/summary.py` 를 다시 실행한다.
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
    step("build_dataset.py", *(["--demo"] if a.demo else []))
    step("preprocess.py", *([] if a.no_api else ["--translate"]))
    step("keywords.py")
    step("association.py", *(["--no-llm"] if a.no_api else []))
    step("sentiment.py", "build")
    if not a.no_api:
        step("sentiment.py", "validate", "--run", "run1")
        step("sentiment.py", "validate", "--run", "run2")
        step("sentiment.py", "run", "--run", "run1")
        step("sentiment.py", "run", "--run", "run2")
        from common import config  # noqa: E402
        if not (config.OUT_SENT / "사람검토표.xlsx").exists():
            step("sentiment.py", "review")
        step("sentiment.py", "merge")
    step("satisfaction.py", *(["--dry-run"] if a.no_api else []))
    step("summary.py")


if __name__ == "__main__":
    main()
