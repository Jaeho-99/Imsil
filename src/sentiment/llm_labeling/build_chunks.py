# -*- coding: utf-8 -*-
"""확정 라벨셋 -> ChatGPT에 붙여넣을 묶음 파일 생성.

**2026-08-23 갱신.** 이전 버전은 확정 전(08-21) 라벨링용 CSV 701문장을 썼다.
그 사이 `src/sentiment/labeling/finalize.py` 로 12문장이 제외되고 9문장이 `-b` 로 쪼개졌으므로,
옛 묶음은 채점 대상과 12+9건 어긋난다. run1/run2 가 아직 비어 있어 재생성해도 잃을 것이 없다.

무엇을 담는가
  **TEST 548문장만** (본 382 + 보강 166). CAL 150은 ②번 임계값 결정 전용이라
  채점에 쓰지 않으므로 ③번에 라벨을 시킬 이유가 없다 — 사람이 붙여넣을 분량도 줄어든다.
  CAL/TEST 는 **리뷰 단위**로 갈랐으므로 TEST 만 남겨도 리뷰의 문장이 잘리지 않는다.

지키는 것
  - 같은 리뷰의 문장은 절대 다른 묶음으로 나누지 않는다(문맥 없이는 라벨할 수 없다).
  - 별점도 사람 라벨도 넣지 않는다. 사람 라벨러와 동일 조건이어야 공정한 비교다.

재생성: python src/sentiment/llm_labeling/build_chunks.py
묶음 크기 실험: python src/sentiment/llm_labeling/build_chunks.py 150 chunks_150

⚠ 묶음 크기는 **조건**이다. ③번 성능 0.906 은 묶음 50문장에서 잰 값이므로, 전수 적용에
   다른 크기를 쓰려면 그 크기에서도 성능이 유지되는지 먼저 실측해야 한다. 행 누락만 보는 것이 아니다.
"""
import sys

import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_OUT  # noqa: E402
SRC = SENT_OUT / "labeling" / "확정"

# 인자: [묶음당 문장 수] [출력 폴더명].  기본값은 성능을 실측한 조건 그대로다.
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 50
OUT = SENT_OUT / "llm_labeling" / (sys.argv[2] if len(sys.argv) > 2 else "chunks")

SETS = [("검증셋_본_확정.csv", "본"), ("검증셋_보강_확정.csv", "보강")]


def chunks_by_review(df, target):
    """리뷰 경계를 넘지 않게 target 문장 근처에서 끊는다."""
    out, cur = [], []
    for _, g in df.groupby("review_id", sort=False):
        rows = g.to_dict("records")
        if cur and len(cur) + len(rows) > target:
            out.append(cur)
            cur = []
        cur.extend(rows)
    if cur:
        out.append(cur)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.txt"):
        old.unlink()

    total = 0
    for fname, tag in SETS:
        df = pd.read_csv(SRC / fname, encoding="utf-8-sig", dtype=str).fillna("")
        df = df[df["split"] == "TEST"]
        groups = chunks_by_review(df, TARGET)
        for i, rows in enumerate(groups, 1):
            path = OUT / f"{tag}_{i:02d}.txt"
            lines = [
                f"# 묶음 {tag}_{i:02d} · {len(rows)}문장 · 출력도 정확히 {len(rows)}행이어야 합니다.",
                "unit_id | sent_no/n_sent | 관광지 | 플랫폼 | 문장",
            ]
            for r in rows:
                sent = r["sent"].replace("\n", " ").replace("|", "/").strip()
                lines.append(
                    f'{r["unit_id"]} | {r["sent_no"]}/{r["n_sent"]} | '
                    f'{r["place"]} | {r["platform"]} | {sent}'
                )
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            total += len(rows)
        print(f"[{tag}] {fname} TEST -> {len(groups)}묶음 / {sum(len(g) for g in groups)}문장")
    print(f"합계 {total}문장 (채점 대상 548와 일치해야 한다) · 묶음당 목표 {TARGET} · 출력 {OUT.name}")


if __name__ == "__main__":
    main()
