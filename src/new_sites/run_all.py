# -*- coding: utf-8 -*-
"""추가 관광지 분석의 수집 뒤 전 과정을 순서대로 실행한다 (수집은 collect_naver.py 로 따로 한다).

API 를 부르지 않는다. LLM 이 판정하는 단계(감성·만족·불만 요인, 외국어가 있으면 번역)는
판정 대상만 output/ 에 내보내고, Claude Code 가 input/new_sites/ 에 저장한 판정 파일이 다 갖춰진 단계만
결과까지 만든다. 판정이 덜 된 단계는 무엇이 남았는지 마지막에 알려 준다. 판정을 채운 뒤 다시 실행하면 된다.

    python src/new_sites/run_all.py
    IMSIL_DEMO=1 python src/new_sites/run_all.py --demo   # 시험 실행: 가짜 수집 원본·가짜 판정 (output/_demo/ 에만 쓴다)

순서: build_dataset → preprocess → keywords → association
      → sentiment build·check (→ 판정이 있으면 review·merge, 검증셋 validate)
      → satisfaction export (→ 판정이 다 되면 merge → combined_report) → summary
판정 방법과 순서는 docs/new_sites.md, 지시문은 input/new_sites/claude_지시문/ 에 있다.
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def step(*args):
    print(f"\n{'=' * 70}\n▶ {' '.join(args)}\n{'=' * 70}", flush=True)
    subprocess.run([sys.executable, str(HERE / args[0]), *args[1:]], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--demo", action="store_true", help="IMSIL_DEMO=1 과 함께: 가짜 수집 원본·가짜 판정 생성")
    a = ap.parse_args()

    import satisfaction
    import sentiment
    from common import config, rel
    if a.demo and not config.DEMO:
        sys.exit("--demo 는 IMSIL_DEMO=1 과 함께 써야 합니다 (실제 input/·output/ 보호).")

    left = []
    raw = [config.RAW_NAVER / f"{n}_naver_reviews.csv" for n in config.TARGET_NAMES]
    if a.demo or any(p.exists() for p in raw) or not config.DATASET.exists():
        step("build_dataset.py", *(["--demo"] if a.demo else []))
    else:
        print(f"수집 원본({rel(config.RAW_NAVER)}/)이 없어 build_dataset.py 를 건너뜁니다. "
              f"git 에 있는 {rel(config.DATASET)} 을 그대로 씁니다.")
    step("preprocess.py")
    if config.TRANSLATE_TODO.exists():
        left.append(f"번역: {rel(config.TRANSLATE_TODO)} → {rel(config.TRANSLATE_DONE)} (claude_지시문/번역.md)")
    step("keywords.py")
    step("association.py")

    step("sentiment.py", "build")
    if a.demo:
        step("demo_judgments.py")
    stale = sentiment.stale_left()
    if stale:
        left.append(f"감성 판정 파일 {len(stale)}개가 이전 문장으로 만든 것입니다 (목록 {rel(sentiment.STALE_LIST)}). "
                    "다른 곳으로 옮기고 새 묶음으로 다시 판정 (claude_지시문/감성_판정.md)")
    else:
        step("sentiment.py", "check")
    if not stale and sentiment.sentences_ready():
        if not sentiment.REVIEW_XLSX.exists():
            step("sentiment.py", "review")
        step("sentiment.py", "merge")
        if not sentiment.REVIEW_FILLED.exists():
            left.append(f"감성 사람 검토: {rel(sentiment.REVIEW_XLSX)} 를 {rel(sentiment.REVIEW_FILLED)} 로 "
                        "복사해 채운 뒤 다시 실행")
        if not sentiment.run_complete(config.SENT_RUNS, "run2",
                                      set(sentiment.read_csv(sentiment.OUT / "문장목록.csv")["unit_id"])):
            left.append(f"감성 판정 run2 (재현성): {rel(config.SENT_RUNS / 'run2')} — run1 과 다른 새 대화에서")
    elif not stale:
        left.append(f"감성 판정: {rel(config.SENT_RUNS)}/run1·run2 (claude_지시문/감성_판정.md)")
    vexp = sentiment.validation_ids()
    for run in ("run1", "run2"):
        if sentiment.run_complete(config.SENT_VAL_RUNS, run, vexp):
            step("sentiment.py", "validate", "--run", run)
        else:
            left.append(f"감성 검증셋 판정: {rel(config.SENT_VAL_RUNS / run)} (claude_지시문/감성_검증.md)")

    step("satisfaction.py", "export")
    if satisfaction.complete():
        step("satisfaction.py", "merge")
        step("combined_report.py")     # 34개소 + 추가 2개소 합산 표·그림 (보고서 리뷰 분석 절)
    else:
        left.append(f"요인 판정: {rel(config.FACTOR_ANN)} (claude_지시문/요인.md)")

    step("summary.py")
    print(f"\n{'=' * 70}")
    if left:
        print("남은 일 — 판정을 채운 뒤 다시 실행하면 이어서 만듭니다:")
        for x in left:
            print("  -", x)
    else:
        print("모든 단계가 끝났습니다.")


if __name__ == "__main__":
    main()
