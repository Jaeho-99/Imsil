# -*- coding: utf-8 -*-
"""전수 적용 출력 검증 (10단계)

`src/sentiment/llm_labeling/check_output.py` 와 같은 파싱 규칙을 쓰되, 기대 id 를
`output/sentiment/fullscale/문장목록.csv` 4,987개로 본다.

전수는 정답이 없다. 그래서 여기서 볼 수 있는 것은 **형식과 누락뿐**이다.
품질의 근거는 검증셋 548문장에서 이미 쟀다(macro-F1 0.906~0.914).
그 성능이 여기 적용된다고 말하려면 **조건이 같아야** 한다 — 모델·설정·프롬프트·묶음 150문장.

실행:  python src/sentiment/fullscale/check_fullscale.py
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_IN, SENT_OUT  # noqa: E402
OUT_DIR = SENT_OUT / "fullscale"
RUNS = SENT_IN / "fullscale" / "llm_runs"     # LLM 판정 결과 (붙여 넣은 파일)
sys.path.insert(0, str(HERE.parent / "llm_labeling"))
from check_output import load_run

RUN = sys.argv[1] if len(sys.argv) > 1 else "run1"


def main():
    src = pd.read_csv(OUT_DIR / "문장목록.csv", encoding="utf-8-sig", dtype=str)
    exp = src["unit_id"].tolist()
    rows, bad, dup, noise = load_run(RUN, base=RUNS)

    print(f"기대 문장 {len(exp)}개 (라벨된 370리뷰 제외한 2,838리뷰)\n")
    if not rows:
        print(f"[{RUN}] 비어 있음 — `input/sentiment/fullscale/llm_runs/{RUN}/` 에 저장했는지 확인")
        return

    missing = [i for i in exp if i not in rows]
    extra = [i for i in rows if i not in set(exp)]
    n_q = sum(1 for v in rows.values() if v.endswith("?"))
    n_mix = sum(1 for v in rows.values() if v.rstrip("?") == "혼합")
    ok = not missing and not extra and not bad and not dup

    print(f"[{RUN}] {len(rows)}/{len(exp)}행  {'✅ 완결' if ok else '⚠ 확인 필요'}")
    print(f"   누락 {len(missing)} · 목록에 없는 id {len(extra)} · 라벨 이상 {len(bad)} "
          f"· 중복 불일치 {len(dup)} · 무시한 줄 {noise}")
    print(f"   확신없음(?) {n_q} ({n_q / len(rows):.1%}) · 혼합 {n_mix} ({n_mix / len(rows):.1%})")
    for b in bad[:10]:
        print("   !", b)
    for x in dup[:10]:
        print("   ! 같은 id 두 번, 라벨이 다름 —", x)

    if missing:
        # 어느 묶음이 통째로 빠졌는지 알려준다 — 그 묶음만 다시 붙여넣으면 된다
        pos = {u: i for i, u in enumerate(exp)}
        idx = sorted(pos[m] for m in missing)
        print(f"\n   누락 {len(missing)}건. 다시 붙여넣을 묶음을 찾으려면 아래 unit_id 범위를 본다:")
        start = prev = idx[0]
        for i in idx[1:] + [None]:
            if i is None or i != prev + 1:
                print(f"     {exp[start]} ~ {exp[prev]}  ({prev - start + 1}건)")
                start = i
            prev = i if i is not None else prev
    if extra:
        print(f"   없는 id 예: {', '.join(extra[:12])}")

    dist = pd.Series([v.rstrip("?") for v in rows.values()]).value_counts(normalize=True)
    print("\n   예측 분포:", " · ".join(f"{k} {v:.1%}" for k, v in dist.items()))
    print("   참고 · 검증셋(사람 라벨, 본 382) 실제 분포: 긍정 57.9% · 중립 25.1% · 부정 17.0%")
    print("   ※ 전수는 무작위 표본이 아니라 전체이므로 분포가 달라도 이상한 것이 아니다. 눈대중 점검용.")

    if ok:
        print(f"\n다음: python src/sentiment/fullscale/merge_fullscale.py {RUN}")


if __name__ == "__main__":
    main()
