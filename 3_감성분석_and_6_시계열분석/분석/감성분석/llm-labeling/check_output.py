# -*- coding: utf-8 -*-
"""GPT 출력 검증 + 2회 실행 불일치율.

사람 라벨은 건드리지 않는다. 여기서는 GPT 출력의 형식/누락/변동성만 본다.

**2026-08-23 갱신**
  - 기대 id 를 확정 TEST 548개로 바꿨다(옛 버전은 확정 전 701개를 봤다).
  - `output/run1/` 안의 **파일 개수·이름·순서를 따지지 않는다.** unit_id 가 전역 고유하므로
    묶음별 12개 파일이든 전부 이어붙인 한 파일이든 결과가 같다.
  - 사람이 붙여넣다 섞인 대화 문구("다음 묶음 주세요" 등)는 조용히 건너뛰고 개수만 센다.
    unit_id 로 시작하는 줄만 라벨로 읽는다.

실행: ../../.venv/Scripts/python.exe check_output.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "labeling" / "확정"
VALID = {"긍정", "부정", "중립", "혼합"}
# 검증셋은 MAIN-/BOOST-0000, 전수는 FULL-00000. 접두어를 가리지 않는다.
ID = re.compile(r"^([A-Z]{1,6}-\d{4,5}(?:-b)?)\b[\s|,\t]+(.+)$")


def expected_ids():
    ids = []
    for f in ["검증셋_본_확정.csv", "검증셋_보강_확정.csv"]:
        d = pd.read_csv(SRC / f, encoding="utf-8-sig", dtype=str)
        ids += d[d["split"] == "TEST"]["unit_id"].tolist()
    return ids


def read_text(p):
    """메모장 저장본을 가리지 않고 읽는다.

    Windows 메모장은 UTF-8 이 기본이지만 'ANSI'(cp949)로도 저장된다.
    인코딩 때문에 작업이 막히는 일이 없도록 순서대로 시도한다.
    """
    for enc in ("utf-8-sig", "utf-8", "cp949", "utf-16"):
        try:
            return p.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return p.read_text(encoding="utf-8", errors="replace")


def load_run(run, base=None):
    """base 를 주면 그 폴더 밑에서 찾는다(전수 적용은 fullscale/output/)."""
    d = (base or (HERE / "output")) / run
    rows, bad, dup, noise = {}, [], [], 0
    if not d.exists():
        return rows, bad, dup, noise
    for p in sorted(d.glob("*")):
        if p.suffix.lower() not in (".tsv", ".txt", ".csv"):
            continue
        for ln, line in enumerate(read_text(p).splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = ID.match(line)
            if not m:
                noise += 1          # 대화 문구·머리말 등. 무시하지만 개수는 센다
                continue
            uid = m.group(1)
            lab = m.group(2).split("|")[0].split("\t")[0].split(",")[0].strip()
            if lab.rstrip("?") not in VALID:
                bad.append(f"{p.name}:{ln} 라벨 이상 -> {uid} / {lab[:20]}")
                continue
            if uid in rows and rows[uid] != lab:
                dup.append(f"{uid}: {rows[uid]} vs {lab} ({p.name}:{ln})")
            rows[uid] = lab
    return rows, bad, dup, noise


def main():
    # 인자로 실행 폴더명을 주면 그것만 본다. 기본은 run1·run2.
    names = sys.argv[1:] or ["run1", "run2"]
    exp = expected_ids()
    print(f"기대 문장 {len(exp)}개 (확정 TEST: 본 382 + 보강 166)\n")
    runs = {}
    for run in names:
        rows, bad, dup, noise = load_run(run)
        runs[run] = rows
        if not rows:
            print(f"[{run}] 비어 있음 — 아직 실행 안 함")
            continue
        missing = [i for i in exp if i not in rows]
        extra = [i for i in rows if i not in set(exp)]
        n_q = sum(1 for v in rows.values() if v.endswith("?"))
        n_mix = sum(1 for v in rows.values() if v.rstrip("?") == "혼합")
        ok = not missing and not extra and not bad and not dup
        print(f"[{run}] {len(rows)}/{len(exp)}행  {'✅ 완결' if ok else '⚠ 확인 필요'}")
        print(f"   누락 {len(missing)} · 목록에 없는 id {len(extra)} · 라벨 이상 {len(bad)} "
              f"· 중복 불일치 {len(dup)} · 무시한 줄 {noise}")
        print(f"   확신없음(?) {n_q} ({n_q / len(rows):.1%}) · 혼합 {n_mix}")
        for b in bad[:10]:
            print("   !", b)
        for x in dup[:10]:
            print("   ! 같은 id 두 번, 라벨이 다름 —", x)
        if missing:
            print(f"   누락 예: {', '.join(missing[:12])}")
        if extra:
            print(f"   없는 id 예: {', '.join(extra[:12])}")
        dist = pd.Series([v.rstrip("?") for v in rows.values()]).value_counts(normalize=True)
        print("   분포:", " · ".join(f"{k} {v:.1%}" for k, v in dist.items()))
        print()

    a, b = runs.get("run1", {}), runs.get("run2", {})
    both = [i for i in exp if i in a and i in b]
    if both:
        diff = [i for i in both if a[i].rstrip("?") != b[i].rstrip("?")]
        print(f"[2회 실행 불일치] {len(diff)}/{len(both)} = {len(diff) / len(both):.2%}")
        print("  -> 이 값을 보고서에 그대로 싣는다(3강 재현성 요건). "
              "웹 UI면 temperature 미고정이므로 이 수치가 변동성의 유일한 증거다.")
        for i in diff[:10]:
            print(f"   {i}: run1={a[i]} run2={b[i]}")
    else:
        print("[2회 실행 불일치] run1/run2 둘 다 있어야 계산됨")


if __name__ == "__main__":
    main()
