# -*- coding: utf-8 -*-
"""[감성] 문장 단위 감성분석 — 34개소 방법(③ LLM, 프롬프트 v1)을 API 없이 그대로 적용

34개소와 같은 것
  - 문장 분리: src/sentiment/textsplit.py 의 split_sentences() 를 그대로 import
  - 프롬프트: input/sentiment/llm_labeling/프롬프트_v1.md 의 <<<PROMPT_START>>>~<<<PROMPT_END>>> 를
    한 글자도 고치지 않고 사용
  - 입력 형식: `unit_id | sent_no/n_sent | 관광지 | 플랫폼 | 문장`, 150문장 묶음, 리뷰 경계 유지,
    리뷰 순서 섞기, 별점 미제공
  - 실행 방식: 대화형 LLM 이 묶음을 하나씩 받아 판정하고, 그 응답을 파일로 저장한다. 독립 2회(run1·run2),
    두 run 은 서로 다른 새 대화에서 한다.
  - 출력 파싱: src/sentiment/llm_labeling/check_output.py 의 load_run()
  - 리뷰 단위 감성: 문장에 긍정·부정이 함께 있거나 `혼합`이면 혼합 (fullscale/merge_fullscale.py 규칙)
  - 채점: docs/sentiment/채점_규칙.md — 본 TEST 382 macro-F1, 보강 166 부정 재현율,
    `혼합`=오답(주)/제외(민감도)

34개소와 다른 것 — 보고서에 밝힐 것
  - 판정 도구: ChatGPT 웹 UI → Claude Code. 묶음과 프롬프트는 같다. Claude Code 는 묶음을 붙여 넣어 받지 않고
    파일로 읽으며, 사람 라벨·다른 run 결과를 열지 않도록 지시문이 읽을 파일을 정한다.
  - 도구가 바뀌었으므로 `validate` 로 **34개소 사람 검증셋 548문장을 같은 도구로 다시 판정·채점**해
    macro-F1 을 34개소(0.906)와 나란히 보고한다. 이 숫자가 두 분석을 잇는 근거다.

판정 파일 (Claude Code 가 만들어 input/ 에 저장 — 지시문: input/new_sites/claude_지시문/)
  input/new_sites/sentiment/runs/run1/, run2/          추가 관광지 묶음 판정
  input/new_sites/sentiment/검증_34개소/run1/, run2/     34개소 검증셋 묶음 판정
  각 폴더의 파일 이름·개수는 따지지 않는다. unit_id 로 시작하는 줄만 읽는다.
  판정한 도구·모델·날짜는 같은 폴더의 실행기록.md 에 적는다.

하위 명령 (순서대로) — 출력은 모두 output/new_sites/sentiment/ 아래
  build      문장 분리 → 문장목록.csv, chunks/추가_NN.txt (판정할 묶음)
             리뷰가 바뀐 뒤 다시 build 하면 묶음 구성과 unit_id 가 달라진다. 이때 이전 결과·검토표 양식·
             최종 라벨은 .local/new_sites_감성_이전실행/{시각}/ 으로 옮기고(지우지 않음), input/ 의 판정
             파일은 건드리지 않되 이전 문장으로 만든 것으로 기록해 두어 check·review·merge 가 쓰지 않게 한다.
  check      판정 완결성(덜 된 묶음) · 2회 불일치율 · κ → 재현성.json
             34개소 검증셋 판정도 덜 된 묶음만 본다 (사람 라벨은 읽지 않는다 — 채점은 validate)
  validate   34개소 검증셋 판정을 사람 라벨로 채점 → 검증_34개소/채점_{run}.json
  review     사람 검토표 양식(사람검토표.xlsx) 생성: 혼합·`?` 문장 확정용 + 무작위 100문장 블라인드 검증용
  merge      최종 문장·리뷰 라벨과 관광지별 집계
             사람이 채운 검토표는 input/new_sites/사람검토표.xlsx 에서 읽는다
             (review 가 만든 양식을 그 자리로 복사해 채운다 — 코드는 input/ 을 덮어쓰지 않는다).

실행 예
    python src/new_sites/sentiment.py build
    python src/new_sites/sentiment.py check
    python src/new_sites/sentiment.py validate --run run1
    python src/new_sites/sentiment.py review
    python src/new_sites/sentiment.py merge
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from common import Checks, config, file_sha, read_csv, rel, save_inputs, setup_font, write_csv

sys.path.insert(0, str(config.SENT_SRC))
sys.path.insert(0, str(config.SENT_SRC / "llm_labeling"))
from textsplit import split_sentences  # noqa: E402
from check_output import ID, load_run  # noqa: E402

OUT = config.OUT_SENT
IN_DIR = OUT / "chunks"                 # 판정할 문장 묶음 (Claude Code 가 읽는다)
RUN_DIR = config.SENT_RUNS              # 묶음 판정 run1·run2 (Claude Code 가 쓴 input/ 파일)
VAL_IN = config.SENT_VAL_RUNS           # 34개소 검증셋 판정 run1·run2 (input/)
VAL_DIR = OUT / "검증_34개소"            # 검증셋 채점 결과
REVIEW_XLSX = OUT / "사람검토표.xlsx"    # review 가 만드는 양식
REVIEW_FILLED = config.REVIEW_FILLED    # 사람이 채운 검토표 (input/new_sites/) — merge 가 읽는다
ARCHIVE = config.SENT_ARCHIVE
STALE_LIST = OUT / "이전문장_판정파일.json"   # build 가 문장이 바뀐 것을 알았을 때 그 전의 판정 파일 목록
# 입력 문장이 바뀌면 함께 무효가 되는 결과들 (build 가 옮긴다. input/ 의 판정 파일·검토표는 건드리지 않는다)
STALE_ON_REBUILD = [OUT / "재현성.json", REVIEW_XLSX,
                    OUT / "블라인드검증_결과.json", OUT / "전수_문장라벨_최종.csv",
                    OUT / "전수_리뷰라벨_최종.csv", OUT / "관광지별_문장감성_최종.csv",
                    OUT / "관광지별_리뷰감성_최종.csv", OUT / "관광지_플랫폼별_문장감성.csv",
                    OUT / "그림_관광지별_감성구성.png"]
LABELS = ["긍정", "부정", "중립"]
CATS = ["긍정", "부정", "중립", "혼합"]


def prompt_v1() -> str:
    t = config.PROMPT_V1.read_text(encoding="utf-8")
    return t.split("<<<PROMPT_START>>>", 1)[1].split("<<<PROMPT_END>>>", 1)[0].strip()


def prompt_note() -> dict:
    """판정에 쓴 프롬프트 — 결과 JSON 에 함께 남겨, 프롬프트가 34개소 v1 그대로인지 대조할 수 있게 한다."""
    import hashlib
    return {"프롬프트": rel(config.PROMPT_V1).replace("\\", "/"),
            "프롬프트_sha256": hashlib.sha256(prompt_v1().encode("utf-8")).hexdigest()}


# ─────────────────────────────────────────────────────────────
# build — fullscale/build_fullscale.py 와 같은 방식
# ─────────────────────────────────────────────────────────────
def build(_):
    ck = Checks("감성분석 입력 생성")
    d = read_csv(config.PREPROCESSED, dtype={"reviewId": str})
    t = d[d["body"].notna() & (d["body"].astype(str).str.strip() != "")].copy()
    ck("reviewId 유일", not t["reviewId"].duplicated().any())
    t = t.sample(frac=1, random_state=config.SENT_SEED).reset_index(drop=True)
    rows = []
    for r in t.itertuples():
        sents = split_sentences(str(r.body))
        for i, s in enumerate(sents, 1):
            rows.append(dict(review_id=r.reviewId, place=r.place, platform=r.platform,
                             sent_no=i, n_sent=len(sents), sent=s))
    df = pd.DataFrame(rows)
    df.insert(0, "unit_id", [f"{config.SENT_UNIT_PREFIX}-{i:05d}" for i in range(1, len(df) + 1)])
    write_csv(df, OUT / "문장목록.csv")

    groups, cur = [], []
    for _, g in df.groupby("review_id", sort=False):
        recs = g.to_dict("records")
        if cur and len(cur) + len(recs) > config.SENT_CHUNK:
            groups.append(cur)
            cur = []
        cur.extend(recs)
    if cur:
        groups.append(cur)
    new = {}
    for i, recs in enumerate(groups, 1):
        lines = [f"# 묶음 추가_{i:02d} · {len(recs)}문장 · 출력도 정확히 {len(recs)}행이어야 합니다.",
                 "unit_id | sent_no/n_sent | 관광지 | 플랫폼 | 문장"]
        for r in recs:
            sent = str(r["sent"]).replace("\n", " ").replace("|", "/").strip()
            lines.append(f'{r["unit_id"]} | {r["sent_no"]}/{r["n_sent"]} | '
                         f'{r["place"]} | {r["platform"]} | {sent}')
        new[f"추가_{i:02d}.txt"] = "\n".join(lines) + "\n"
    IN_DIR.mkdir(parents=True, exist_ok=True)
    old = {p.name: p.read_text(encoding="utf-8") for p in IN_DIR.glob("*.txt")}
    if old and old != new:
        archive_stale()
    for p in IN_DIR.glob("*.txt"):
        p.unlink()
    for name, text in new.items():
        (IN_DIR / name).write_text(text, encoding="utf-8")
    ck("문장 분리", len(df) > 0, f"리뷰 {len(t)} → 문장 {len(df)} · 묶음 {len(groups)}")
    print(df.groupby("place").agg(리뷰=("review_id", "nunique"), 문장=("unit_id", "size")).to_string())


def run_files(base: Path, run: str = "*") -> list[Path]:
    """판정 폴더(base/run1, base/run2 …) 안에서 load_run() 이 읽는 파일."""
    if not base.exists():
        return []
    return sorted(q for q in base.glob(f"{run}/*") if q.suffix.lower() in (".tsv", ".txt", ".csv"))


def merge_inputs() -> list[Path]:
    """merge 가 읽는 입력 — 결과 폴더의 입력기록.json 에 해시를 남긴다."""
    return [OUT / "문장목록.csv", *run_files(RUN_DIR, "run1"), REVIEW_FILLED]


def archive_stale():
    """입력 문장이 바뀌었을 때, 이전 문장으로 만든 결과를 정리한다.

    판정 파일은 unit_id 와 라벨만 담고 있어서, 묶음이 바뀐 뒤 그대로 읽으면 다른 문장에 옛 라벨이 붙는다.
    output/ 의 결과는 옮겨 두고(지우지 않는다), input/ 의 판정 파일·채운 검토표는 건드리지 않는 대신
    경로와 내용 해시를 STALE_LIST 에 적어 check·review·merge 가 쓰지 않게 한다.
    """
    dst = ARCHIVE / datetime.now().strftime("%Y%m%d-%H%M%S")
    moved = []
    for p in STALE_ON_REBUILD:
        if p.exists():
            dst.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dst / p.name))
            moved.append(p.name)
    if moved:
        print(f"  [주의] 입력 문장이 바뀌어 이전 감성 결과 {len(moved)}개({', '.join(moved)})를 "
              f"{rel(dst)} 로 옮겼습니다.")
    stale = run_files(RUN_DIR) + ([REVIEW_FILLED] if REVIEW_FILLED.exists() else [])
    if stale:
        old = json.loads(STALE_LIST.read_text(encoding="utf-8")) if STALE_LIST.exists() else {}
        old.update({rel(q): file_sha(q) for q in stale})
        STALE_LIST.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [주의] input/ 의 판정 파일·검토표 {len(stale)}개는 이전 문장으로 만든 것입니다.\n"
              "         다른 곳으로 옮기고 새 묶음으로 run1·run2 를 다시 판정한 뒤 review 로 검토표를 새로 만드세요.\n"
              f"         그 전에는 check·review·merge 가 멈춥니다 (목록: {rel(STALE_LIST)}).")


def stale_left() -> list[str]:
    """build 가 문장이 바뀐 것을 기록한 뒤에도 그대로 남아 있는 이전 판정 파일·검토표."""
    if not STALE_LIST.exists():
        return []
    old = json.loads(STALE_LIST.read_text(encoding="utf-8"))
    return [r for r, h in old.items() if (config.REPO / r).exists() and file_sha(config.REPO / r) == h]


def guard_stale():
    """build 가 문장이 바뀐 것을 기록한 뒤에도 그 전의 판정 파일이 그대로 남아 있으면 멈춘다."""
    left = stale_left()
    if left:
        sys.exit("[중단] 아래 파일은 지금과 다른 문장으로 만든 판정입니다 (build 가 문장이 바뀐 것을 기록함).\n  "
                 + "\n  ".join(left[:10]) + (f"\n  … 외 {len(left) - 10}개" if len(left) > 10 else "")
                 + "\n  다른 곳으로 옮기고 새 묶음으로 다시 판정하세요. 옮기거나 새 판정으로 바꾸면 이 검사는 통과합니다.")


def run_note(d: Path) -> str:
    """판정 폴더의 실행기록.md 에서 도구·모델·날짜 줄을 읽는다."""
    f = d / "실행기록.md"
    if not f.exists():
        return "실행기록.md 없음"
    lines = [x.strip().lstrip("-*# ").strip() for x in f.read_text(encoding="utf-8-sig").splitlines()
             if not x.strip().startswith("```")]
    return " · ".join(x for x in lines if x)[:500]


def chunk_ids(folder: Path, pattern: str = "*.txt") -> dict[str, set[str]]:
    """묶음 파일별 unit_id — 어느 묶음이 아직 판정되지 않았는지 알려 줄 때 쓴다."""
    out = {}
    for f in sorted(folder.glob(pattern)):
        out[f.stem] = {m.group(1) for ln in f.read_text(encoding="utf-8").splitlines()
                       if (m := ID.match(ln.strip()))}
    return out


def run_complete(base: Path, name: str, exp: set[str]) -> bool:
    """판정 폴더 base/name 이 기대 unit_id 를 모두 담고 형식 오류가 없는가."""
    rows, bad, dup, _ = load_run(name, base=base)
    return bool(rows) and exp <= set(rows) and not bad and not dup


def sentences_ready() -> bool:
    """추가 관광지 run1 판정이 지금 문장목록과 맞게 끝났는가 (run_all.py 가 review·merge 전에 본다)."""
    f = OUT / "문장목록.csv"
    return f.exists() and not stale_left() and run_complete(RUN_DIR, "run1", set(read_csv(f)["unit_id"]))


def validation_ids() -> set[str]:
    return set().union(*chunk_ids(config.BASE_SENT_CHUNKS).values())


# ─────────────────────────────────────────────────────────────
# 채점 — evaluation/run_llm3.py 와 같은 규칙
# ─────────────────────────────────────────────────────────────
def macro(pred: pd.Series, gold: pd.Series) -> dict:
    per = {}
    for c in LABELS:
        tp = int(((pred == c) & (gold == c)).sum())
        fp = int(((pred == c) & (gold != c)).sum())
        fn = int(((pred != c) & (gold == c)).sum())
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        per[c] = {"P": p, "R": r, "F1": 2 * p * r / (p + r) if p + r else 0.0, "n": int((gold == c).sum())}
    return {"macro_f1": sum(v["F1"] for v in per.values()) / 3,
            "accuracy": float((pred == gold).mean()), "per": per, "n": len(gold)}


def kappa(a: pd.Series, b: pd.Series) -> float:
    cats = sorted(set(a) | set(b))
    po = float((a == b).mean())
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def validate(args):
    run_name = args.run
    rows, bad, dup, _ = load_run(run_name, base=VAL_IN)
    if not rows:
        sys.exit(f"{rel(VAL_IN / run_name)} 에 판정 파일이 없습니다. "
                 "input/new_sites/claude_지시문/감성_검증.md 대로 판정해 저장한 뒤 다시 실행하세요.")
    VAL_DIR.mkdir(parents=True, exist_ok=True)
    gold = pd.concat([read_csv(config.BASE_SENT_GOLD / f)
                      for f in ["검증셋_본_확정.csv", "검증셋_보강_확정.csv"]])
    gold = gold[gold["split"] == "TEST"].reset_index(drop=True)
    ck = Checks(f"34개소 검증셋 재채점 ({run_name})")
    ck("출력 형식", not bad and not dup, f"라벨 이상 {len(bad)} · 중복 불일치 {len(dup)}")
    gold["raw"] = gold["unit_id"].map(rows)
    ck("548문장 완결", gold["raw"].notna().all() and len(gold) == 548,
       f"{gold['raw'].notna().sum()}/{len(gold)}")
    gold["pred"] = gold["raw"].str.rstrip("?")
    main, aug = gold[gold["set"] == "MAIN"], gold[gold["set"] != "MAIN"]
    s_main = macro(main["pred"], main["label"])
    s_drop = macro(main.loc[main.pred != "혼합", "pred"], main.loc[main.pred != "혼합", "label"])
    neg = aug[aug["label"] == "부정"]
    neg_rec = float((neg["pred"] == "부정").mean()) if len(neg) else float("nan")
    res = {"run": run_name, "판정": run_note(VAL_IN / run_name), **prompt_note(),
           "본_TEST": {"n": s_main["n"], "macro_f1": s_main["macro_f1"], "accuracy": s_main["accuracy"],
                      "class_f1": {c: s_main["per"][c]["F1"] for c in LABELS},
                      "혼합": int((main.pred == "혼합").sum()),
                      "macro_f1_혼합제외": s_drop["macro_f1"]},
           "보강_부정재현율": {"n": len(neg), "recall": neg_rec},
           "확신없음(?)": int(gold["raw"].str.endswith("?").sum()),
           "34개소_기준": {"macro_f1": "0.906 (run1) · 0.908 (run2)", "부정재현율": "0.910 · 0.820",
                        "다수클래스_기준선": 0.579}}
    (VAL_DIR / f"채점_{run_name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    write_csv(gold[["unit_id", "set", "place", "sent", "label", "raw"]], VAL_DIR / f"예측_{run_name}.csv")
    print(f"\n  본 TEST {s_main['n']}문장: macro-F1 {s_main['macro_f1']:.3f} · 정확도 {s_main['accuracy']:.3f} "
          f"(혼합 {res['본_TEST']['혼합']}건 오답 처리 · 혼합 제외 시 {s_drop['macro_f1']:.3f})")
    print("  클래스별 F1: " + " · ".join(f"{c} {s_main['per'][c]['F1']:.3f}" for c in LABELS))
    print(f"  보강 부정 재현율: {neg_rec:.3f} ({len(neg)}문장)")
    print("  34개소(ChatGPT 웹 UI): macro-F1 0.906~0.908 · 부정 재현율 0.82~0.91 · 기준선 0.579")
    a, b = load_run("run1", base=VAL_IN)[0], load_run("run2", base=VAL_IN)[0]
    both = [k for k in a if k in b]
    if both:
        sa, sb = pd.Series([a[k].rstrip("?") for k in both]), pd.Series([b[k].rstrip("?") for k in both])
        print(f"  검증셋 2회 불일치: {(sa != sb).sum()}/{len(both)} = {(sa != sb).mean():.2%} · κ {kappa(sa, sb):.3f}")


def report_run(ck, label: str, base: Path, name: str, exp: set[str], chunks: dict, guide: str):
    """판정 폴더 하나의 완결성을 출력한다. 판정이 없으면 None."""
    rows, bad, dup, noise = load_run(name, base=base)
    if not rows:
        print(f"  [{label} {name}] 아직 없음 — {rel(base / name)}/ 에 묶음 {len(chunks)}개의 판정을 저장하세요 "
              f"(input/new_sites/claude_지시문/{guide})")
        return None
    miss = exp - set(rows)
    extra = set(rows) - exp
    left = [c for c, ids in chunks.items() if ids - set(rows)]
    ck(f"{label} {name} 완결", not miss and not extra and not bad and not dup,
       f"{len(rows)}/{len(exp)} · 누락 {len(miss)} · 없는 id {len(extra)} · 라벨이상 {len(bad)} "
       f"· 중복불일치 {len(dup)} · 무시한 줄 {noise}"
       + (f" · 덜 된 묶음 {', '.join(left)}" if left else ""), fatal=False)
    for x in (bad + dup)[:5]:
        print("     !", x)
    print(f"     판정: {run_note(base / name)}")
    lab = pd.Series([v.rstrip("?") for v in rows.values()])
    print("     분포: " + " · ".join(f"{k} {v:.1%}" for k, v in lab.value_counts(normalize=True).items())
          + f" · ? {sum(v.endswith('?') for v in rows.values())}건")
    return rows


def check(_):
    guard_stale()
    src = read_csv(OUT / "문장목록.csv")
    exp = set(src["unit_id"])
    chunks = chunk_ids(IN_DIR, "추가_*.txt")
    ck = Checks("감성분석 판정 점검")
    runs = {}
    for name in ("run1", "run2"):
        rows = report_run(ck, "추가 관광지", RUN_DIR, name, exp, chunks, "감성_판정.md")
        if rows:
            runs[name] = rows
    if len(runs) == 2:
        ids = sorted(set(runs["run1"]) & set(runs["run2"]))
        a = pd.Series([runs["run1"][i].rstrip("?") for i in ids])
        b = pd.Series([runs["run2"][i].rstrip("?") for i in ids])
        flip = int((((a == "긍정") & (b == "부정")) | ((a == "부정") & (b == "긍정"))).sum())
        res = {"불일치": int((a != b).sum()), "문장": len(ids), "불일치율": float((a != b).mean()),
               "kappa": kappa(a, b), "긍부_뒤집힘": flip,
               "run1": run_note(RUN_DIR / "run1"), "run2": run_note(RUN_DIR / "run2"), **prompt_note()}
        (OUT / "재현성.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  2회 실행 불일치 {res['불일치']}/{res['문장']} = {res['불일치율']:.2%} · κ {res['kappa']:.3f} "
              f"· 긍↔부 뒤집힘 {flip}  (34개소: 4.20% · κ 0.936)")

    # 34개소 검증셋 — 덜 된 묶음만 본다. 사람 라벨은 읽지 않는다 (채점은 validate).
    vchunks = chunk_ids(config.BASE_SENT_CHUNKS)
    vexp = set().union(*vchunks.values())
    print()
    for name in ("run1", "run2"):
        if report_run(ck, "34개소 검증셋", VAL_IN, name, vexp, vchunks, "감성_검증.md"):
            print(f"     채점: python src/new_sites/sentiment.py validate --run {name}")


# ─────────────────────────────────────────────────────────────
# review — 사람 검토표
# ─────────────────────────────────────────────────────────────
def review(args):
    guard_stale()
    src = read_csv(OUT / "문장목록.csv")
    rows = load_run("run1", base=RUN_DIR)[0]
    if not rows:
        sys.exit(f"run1 판정이 없습니다 ({rel(RUN_DIR / 'run1')}/).")
    miss = set(src["unit_id"]) - set(rows)
    if miss:
        sys.exit(f"run1 판정이 {len(miss)}문장 빠져 있습니다. check 로 덜 된 묶음을 확인하세요.")
    src["모델라벨"] = src["unit_id"].map(rows)
    ctx = src.groupby("review_id")["sent"].apply(lambda s: " / ".join(s))
    src["리뷰전문"] = src["review_id"].map(ctx)
    if REVIEW_XLSX.exists() and not args.force:
        sys.exit(f"{rel(REVIEW_XLSX)} 이 이미 있습니다. 사람 판정을 덮어쓰지 않도록 중단합니다 "
                 "(정말 새로 만들려면 --force).")
    hard = src[src["모델라벨"].str.contains(r"혼합|\?", na=False)].copy()
    hard["최종판정"] = ""
    hard["메모"] = ""
    # 블라인드 검증 표본: 관광지별로 같은 수를 뽑고 모델 라벨은 보여주지 않는다
    n_each = max(1, args.sample // src["place"].nunique())
    samp = pd.concat([g.sample(min(len(g), n_each), random_state=config.SENT_SEED)
                      for _, g in src.groupby("place")])
    samp = samp.sample(frac=1, random_state=config.SENT_SEED)
    blind = samp[["unit_id", "place", "sent", "리뷰전문"]].copy()
    blind["사람라벨"] = ""
    guide = pd.DataFrame({"안내": [
        "시트 '1_혼합확정': 모델이 혼합 또는 ?로 낸 문장. 최종판정 칸에 긍정/부정/중립 중 하나를 적는다.",
        "   34개소 267건 확정과 같은 기준: 지배적 입장이 있으면 그 하나로, 정말 반반이면 '분할'이라 적고 메모에 사유.",
        "시트 '2_블라인드검증': 모델 라벨을 가린 무작위 표본. 사람라벨 칸에 긍정/부정/중립을 적는다.",
        "   판정 기준은 docs/sentiment/0001-라벨링-지침서.html (34개소와 동일).",
        f"이 파일을 {rel(REVIEW_FILLED)} 로 복사해 채운 뒤: python src/new_sites/sentiment.py merge",
    ]})
    with pd.ExcelWriter(REVIEW_XLSX) as w:
        guide.to_excel(w, sheet_name="0_안내", index=False)
        hard[["unit_id", "place", "sent", "리뷰전문", "모델라벨", "최종판정", "메모"]].to_excel(
            w, sheet_name="1_혼합확정", index=False)
        blind.to_excel(w, sheet_name="2_블라인드검증", index=False)
    print(f"저장: {rel(REVIEW_XLSX)}  혼합·? {len(hard)}문장 · 블라인드 표본 {len(blind)}문장")
    print(f"      → {rel(REVIEW_FILLED)} 로 복사해 채운 뒤 merge 를 실행하세요.")


# ─────────────────────────────────────────────────────────────
# merge — fullscale/merge_fullscale.py 의 리뷰 집계 규칙
# ─────────────────────────────────────────────────────────────
def review_label(labels) -> str:
    s = set(labels)
    if "혼합" in s or {"긍정", "부정"} <= s:
        return "혼합"
    if "긍정" in s:
        return "긍정"
    if "부정" in s:
        return "부정"
    return "중립"


def agg(df, key, col):
    t = df.pivot_table(index=key, columns=col, aggfunc="size", fill_value=0)
    for c in CATS:
        if c not in t:
            t[c] = 0
    t = t[CATS]
    t["계"] = t.sum(axis=1)
    t["긍정비율"] = t["긍정"] / t["계"]
    t["부정비율"] = t["부정"] / t["계"]
    t["부정_상한"] = (t["부정"] + t["혼합"]) / t["계"]
    return t


def merge(_):
    guard_stale()
    ck = Checks("감성분석 최종 병합")
    src = read_csv(OUT / "문장목록.csv")
    rows, bad, dup, _ = load_run("run1", base=RUN_DIR)
    ck("run1 판정 이상 없음", bool(rows) and not bad and not dup,
       "" if rows else f"{rel(RUN_DIR / 'run1')}/ 에 판정이 없습니다")
    src["label"] = src["unit_id"].map(rows).str.rstrip("?")
    ck("판정 누락 없음", src["label"].notna().all(), f"누락 {src['label'].isna().sum()}")
    src["출처"] = "LLM 판정 (run1)"

    hard_done = 0
    if not REVIEW_FILLED.exists() and REVIEW_XLSX.exists():
        print(f"  [안내] 채운 검토표가 없습니다. {rel(REVIEW_XLSX)} 를 {rel(REVIEW_FILLED)} 로 복사해 "
              "채우면 다음 merge 에 반영됩니다.")
    if REVIEW_FILLED.exists():
        cur = dict(zip(src["unit_id"], src["sent"].astype(str).str.strip()))
        for sheet in ("1_혼합확정", "2_블라인드검증"):
            s_ = pd.read_excel(REVIEW_FILLED, sheet_name=sheet, dtype=str).fillna("")
            off = sum(cur.get(u) != t.strip() for u, t in zip(s_["unit_id"], s_["sent"]))
            ck(f"사람검토표 '{sheet}' 가 지금 문장목록과 맞음", off == 0,
               f"{len(s_)}행 확인" if off == 0 else
               f"unit_id 는 같은데 문장이 다른 행 {off}개 — 검토표를 만든 뒤 데이터가 바뀌었습니다. "
               "검토표를 다른 곳으로 옮기고 review 로 새로 만드세요.")
        h = pd.read_excel(REVIEW_FILLED, sheet_name="1_혼합확정", dtype=str).fillna("")
        h = h[h["최종판정"].str.strip().isin(["긍정", "부정", "중립"])]
        fix = dict(zip(h["unit_id"], h["최종판정"].str.strip()))
        m = src["unit_id"].isin(fix)
        src.loc[m, "label"] = src.loc[m, "unit_id"].map(fix)
        src.loc[m, "출처"] = "연구자 확정"
        hard_done = int(m.sum())
    n_mix = int((src["label"] == "혼합").sum())
    ck("혼합 문장 확정", n_mix == 0, f"연구자 확정 {hard_done}건 · 남은 혼합 {n_mix}건"
       + (" — 부정 비율을 하한~상한 범위로 보고" if n_mix else ""), fatal=False)

    write_csv(src, OUT / "전수_문장라벨_최종.csv")
    rev = (src.groupby(["review_id", "place", "platform"])["label"].apply(review_label)
           .reset_index(name="리뷰감성"))
    write_csv(rev, OUT / "전수_리뷰라벨_최종.csv")
    by_sent = agg(src, "place", "label")
    by_rev = agg(rev, "place", "리뷰감성")
    by_plat = agg(src, ["place", "platform"], "label")
    write_csv(by_sent, OUT / "관광지별_문장감성_최종.csv", index=True)
    write_csv(by_rev, OUT / "관광지별_리뷰감성_최종.csv", index=True)
    write_csv(by_plat, OUT / "관광지_플랫폼별_문장감성.csv", index=True)

    # 블라인드 검증 표본 채점
    if REVIEW_FILLED.exists():
        b = pd.read_excel(REVIEW_FILLED, sheet_name="2_블라인드검증", dtype=str).fillna("")
        b = b[b["사람라벨"].str.strip().isin(LABELS)]
        if len(b):
            b["pred"] = b["unit_id"].map(dict(zip(src["unit_id"], src["label"])))
            s = macro(b["pred"], b["사람라벨"].str.strip())
            res = {"n": s["n"], "macro_f1": s["macro_f1"], "accuracy": s["accuracy"],
                   "class_f1": {c: s["per"][c]["F1"] for c in LABELS}}
            (OUT / "블라인드검증_결과.json").write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                                     encoding="utf-8")
            ck("블라인드 검증 표본 채점", True,
               f"{s['n']}문장 · 정확도 {s['accuracy']:.3f} · macro-F1 {s['macro_f1']:.3f}")

    plot(by_sent)
    save_inputs(OUT, merge_inputs())
    print("\n  관광지별 문장 감성")
    print(by_sent.to_string(float_format=lambda x: f"{x:.1%}"))
    print("\n  관광지별 리뷰 감성")
    print(by_rev.to_string(float_format=lambda x: f"{x:.1%}"))
    print(f"\n저장: {rel(OUT)}/")


def plot(by_sent: pd.DataFrame):
    """관광지별 문장 감성 구성 — 34개소 평균과 인접 관광지를 함께 놓는다."""
    plt = setup_font()
    base = read_csv(config.BASE_SENT_SENTENCE)
    rows = []
    for p in by_sent.index:
        n = int(by_sent.loc[p, LABELS].sum())
        rows.append((f"{p} (n={n})", by_sent.loc[p, LABELS] / n))
        cmp_ = config.COMPARE_PLACES.get(p)
        if cmp_ is not None and (base["place"] == cmp_).any():
            v = base.loc[base.place == cmp_, "label"].value_counts()
            v = v.reindex(LABELS, fill_value=0)
            rows.append((f"(비교) {cmp_} (n={int(v.sum())})", v / v.sum()))
    v = base["label"].value_counts().reindex(LABELS, fill_value=0)
    rows.append((f"(비교) 34개소 전체 (n={int(v.sum()):,})", v / v.sum()))
    fig, ax = plt.subplots(figsize=(10, 0.7 * len(rows) + 1.5))
    colors = {"긍정": "#2a78d6", "중립": "#c9ced6", "부정": "#d6452a"}
    names = [r[0] for r in rows][::-1]
    left = [0.0] * len(rows)
    for c in ["긍정", "중립", "부정"]:
        vals = [float(r[1][c]) for r in rows][::-1]
        ax.barh(names, vals, left=left, color=colors[c], label=c)
        for i, (l, v_) in enumerate(zip(left, vals)):
            if v_ >= 0.06:
                ax.text(l + v_ / 2, i, f"{v_:.0%}", ha="center", va="center", fontsize=9,
                        color="white" if c != "중립" else "#333333")
        left = [l + v_ for l, v_ in zip(left, vals)]
    ax.set_xlim(0, 1)
    ax.set_xlabel("문장 비율")
    ax.legend(ncol=3, loc="lower right", bbox_to_anchor=(1.0, 1.0), frameon=False)
    ax.set_title("관광지별 리뷰 문장 감성 구성", loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "그림_관광지별_감성구성.png", dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    v = sub.add_parser("validate")
    v.add_argument("--run", default="run1")
    sub.add_parser("check")
    rv = sub.add_parser("review")
    rv.add_argument("--sample", type=int, default=100)
    rv.add_argument("--force", action="store_true")
    sub.add_parser("merge")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    {"build": build, "validate": validate, "check": check,
     "review": review, "merge": merge}[args.cmd](args)


if __name__ == "__main__":
    main()
