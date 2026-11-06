# -*- coding: utf-8 -*-
"""옛 폴더 구조(1_데이터수집/ … 7_추가관광지분석/)에 남은 '내 PC 에만 있는 파일'을 새 위치로 옮긴다.

git 이 관리하는 파일은 git pull 로 이미 새 위치에 있다. 여기서 옮기는 것은 .gitignore 로 빠져 있어
pull 이 건드리지 않은 파일이다.
  - 수집 원본 (작성자 정보 포함): 네이버·구글 리뷰 CSV, {ID}_raw.json, 추가 관광지 리뷰ID 대응표
  - 구글 로그인 프로필 · 진단 스냅샷
  - .env (API 키)
  - 추가 관광지 분석의 중간 산출물과 사람이 만든 파일(비식별 치환목록, 감성 검토표)

실행 (레포 최상위에서)
    python src/migrate_old_layout.py           # 무엇을 어디로 옮길지 보여 주기만 한다
    python src/migrate_old_layout.py --apply   # 실제로 옮긴다

안전 규칙
  - 새 위치에 같은 이름의 파일이 이미 있으면 옮기지 않고 알려 준다 (덮어쓰지 않는다).
  - 지우는 것은 옮기고 나서 비어 버린 옛 폴더뿐이다. 옮기지 않은 파일은 그 자리에 남는다.
"""
from __future__ import annotations

import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # src/
from paths import ROOT  # noqa: E402

OLD_ROOTS = ["1_데이터수집", "2_키워드분석", "3_감성분석_and_6_시계열분석",
             "4_연관관계분석_and_5_만족-불만요인분석", "7_추가관광지분석"]
N7 = "7_추가관광지분석"

# (옛 경로, 새 경로). 폴더면 안의 파일을 같은 구조로 옮긴다. 새 경로가 None 이면 옮기지 않는다.
# 한 파일에 여러 규칙이 맞으면 가장 긴(구체적인) 옛 경로의 규칙을 쓴다.
RULES = [
    # 34개소 수집 원본 — 옛 네이버 수집기는 CSV 를 output/naver/ 에, raw.json 을 output/ 에 썼다
    ("1_데이터수집/네이버/output/naver", "output/collect/naver"),
    ("1_데이터수집/네이버/output", "output/collect/naver"),
    ("1_데이터수집/구글/output", "output/collect/google"),
    ("1_데이터수집/구글/chrome_profile_google", ".local/chrome_profile_google"),
    ("1_데이터수집/구글/diagnostics", ".local/diagnostics"),
    # API 키
    (f"{N7}/.env", ".env"),
    ("4_연관관계분석_and_5_만족-불만요인분석/.env", ".env"),
    # 추가 관광지 — 수집 원본
    (f"{N7}/data/raw/naver", "output/collect/naver"),
    (f"{N7}/data/raw/google", "output/collect/google"),
    (f"{N7}/data/raw/리뷰ID_대응표.csv", "output/collect/naver/추가관광지_리뷰ID_대응표.csv"),
    (f"{N7}/data/raw/감성_이전실행", ".local/new_sites_감성_이전실행"),
    (f"{N7}/data/raw", "output/collect/naver"),
    # 추가 관광지 — 사람이 만든 파일
    (f"{N7}/data/비식별_치환목록.csv", "input/new_sites/비식별_치환목록.csv"),
    (f"{N7}/output/3_감성/사람검토표.xlsx", "input/new_sites/사람검토표.xlsx"),
    # 추가 관광지 — 코드 산출물
    (f"{N7}/data/추가관광지_리뷰데이터_키워드전처리완료.csv",
     "output/new_sites/keyword/추가관광지_리뷰데이터_키워드전처리완료.csv"),
    (f"{N7}/data", "output/new_sites"),
    (f"{N7}/output/1_키워드", "output/new_sites/keyword"),
    (f"{N7}/output/2_연관관계", "output/new_sites/association"),
    (f"{N7}/output/3_감성/input", "output/new_sites/sentiment/chunks"),
    (f"{N7}/output/3_감성/output", "output/new_sites/sentiment/runs"),
    (f"{N7}/output/3_감성", "output/new_sites/sentiment"),
    (f"{N7}/output/4_만족불만요인", "output/new_sites/satisfaction"),
    (f"{N7}/output/5_요약", "output/new_sites/summary"),
    (f"{N7}/output", "output/new_sites"),
    (f"{N7}/_demo", None),          # 시험 실행 산출물 — 다시 만들 수 있다 (지워도 된다)
]
SKIP_PARTS = {"__pycache__", ".ipynb_checkpoints", ".plot_deps"}


def rule_for(rel: str):
    best = None
    for old, new in RULES:
        if rel == old or rel.startswith(old + "/"):
            if best is None or len(old) > len(best[0]):
                best = (old, new)
    return best


def main():
    apply = "--apply" in sys.argv
    moves, conflicts, same, kept, left = defaultdict(list), [], [], defaultdict(int), []
    venvs, planned = set(), set()
    for root in OLD_ROOTS:
        base = ROOT / root
        if not base.exists():
            continue
        for f in sorted(base.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(ROOT).as_posix()
            parts = rel.split("/")
            if SKIP_PARTS & set(parts) or rel.endswith(".pyc"):
                continue
            if ".venv" in parts:
                venvs.add("/".join(parts[:parts.index(".venv") + 1]))
                continue
            rule = rule_for(rel)
            if rule is None:
                left.append(rel)
                continue
            old, new = rule
            if new is None:
                kept[old] += 1
                continue
            dst = ROOT / new / rel[len(old):].lstrip("/") if rel != old else ROOT / new
            if dst.exists() or dst in planned:
                if dst.exists() and dst.read_bytes() == f.read_bytes():
                    same.append(rel)
                else:
                    conflicts.append((rel, dst.relative_to(ROOT).as_posix()))
                continue
            planned.add(dst)
            moves[(old, new)].append((f, dst))

    print("옮길 파일" + ("" if apply else " (아직 옮기지 않았습니다. 옮기려면 --apply)"))
    if not moves:
        print("  없음")
    for (old, new), items in moves.items():
        print(f"  {old}  →  {new}   ({len(items)}개)")
        for f, dst in items[:5]:
            print(f"      {f.relative_to(ROOT).as_posix()}  →  {dst.relative_to(ROOT).as_posix()}")
        if len(items) > 5:
            print(f"      … 외 {len(items) - 5}개")
    if conflicts:
        print("\n새 위치에 다른 내용의 파일이 이미 있어 옮기지 않음 — 직접 확인하세요")
        for rel, dst in conflicts:
            print(f"  {rel}  (새 위치: {dst})")
    if same:
        print(f"\n새 위치에 같은 내용이 이미 있어 옮기지 않음: {len(same)}개 (옛 파일은 지워도 됩니다)")
    for old, n in kept.items():
        print(f"\n옮기지 않음: {old}/ ({n}개) — 다시 만들 수 있는 시험 실행 산출물입니다. 지워도 됩니다.")
    for v in sorted(venvs):
        print(f"\n가상환경 {v}/ 는 옮기지 않습니다. 레포 최상위에서 새로 만드세요 (README '준비').")
    if left:
        print("\n규칙에 없는 파일 — 그대로 둡니다")
        for rel in left[:30]:
            print(f"  {rel}")
        if len(left) > 30:
            print(f"  … 외 {len(left) - 30}개")

    if not apply:
        return
    n = 0
    for items in moves.values():
        for f, dst in items:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dst))
            n += 1
    for root in OLD_ROOTS:          # 비어 버린 옛 폴더만 지운다
        base = ROOT / root
        if not base.exists():
            continue
        for d in sorted((p for p in base.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
        if not any(base.iterdir()):
            base.rmdir()
    print(f"\n{n}개를 옮겼습니다.")


if __name__ == "__main__":
    main()
