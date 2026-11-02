# -*- coding: utf-8 -*-
"""[5단계] 문장 단위 감성분석 — 34개소 방법(③ LLM, 프롬프트 v1)을 API 로 그대로 적용

34개소와 같은 것
  - 문장 분리: 3_.../분석/감성분석/textsplit.py 의 split_sentences() 를 그대로 import
  - 프롬프트: llm-labeling/프롬프트_v1.md 의 <<<PROMPT_START>>>~<<<PROMPT_END>>> 를 한 글자도 고치지 않고 사용
  - 입력 형식: `unit_id | sent_no/n_sent | 관광지 | 플랫폼 | 문장`, 150문장 묶음, 리뷰 경계 유지,
    리뷰 순서 섞기, 별점 미제공
  - 출력 파싱: llm-labeling/check_output.py 의 load_run()
  - 리뷰 단위 감성: 문장에 긍정·부정이 함께 있거나 `혼합`이면 혼합 (merge_fullscale.py 규칙)
  - 채점: evaluation/채점_규칙.md — 본 TEST 382 macro-F1, 보강 166 부정 재현율, `혼합`=오답(주)/제외(민감도)

34개소와 다른 것 — 보고서에 밝힐 것
  - 실행 경로: ChatGPT 웹 UI → Anthropic API (config.SENT_MODEL). 묶음마다 새 요청
    [프롬프트 → "준비됨" → 묶음] 을 보내므로 앞 묶음의 답이 뒤 묶음에 새지 않는다.
  - 현재 모델은 temperature 를 받지 않는다. 34개소와 같이 독립 2회 실행 불일치율로 변동성을 보고한다.
  - 모델이 바뀌었으므로 `validate` 로 **34개소 사람 검증셋 548문장을 이 모델로 다시 채점**해
    macro-F1 을 34개소(0.906)와 나란히 보고한다. 이 숫자가 두 분석을 잇는 근거다.

하위 명령 (순서대로)
  build      문장 분리 → output/3_감성/문장목록.csv, input/추가_NN.txt
  validate   34개소 검증셋 548문장을 API 로 분류·채점 → output/3_감성/검증_34개소/  (API)
  run        묶음을 API 로 분류 → output/3_감성/output/{run1,run2}/                 (API)
  check      출력 완결성 · 2회 불일치율 · κ
  review     사람 검토표(xlsx) 생성: 혼합·`?` 문장 확정용 + 무작위 100문장 블라인드 검증용
  merge      최종 문장·리뷰 라벨과 관광지별 집계 (검토표에 판정이 있으면 반영)

실행 예
    python scripts/s5_sentiment.py build
    python scripts/s5_sentiment.py validate
    python scripts/s5_sentiment.py run --run run1
    python scripts/s5_sentiment.py run --run run2
    python scripts/s5_sentiment.py check
    python scripts/s5_sentiment.py review
    python scripts/s5_sentiment.py merge
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from common import Checks, anthropic_client, config, read_csv, rel, setup_font, write_csv

sys.path.insert(0, str(config.SENT_DIR))
sys.path.insert(0, str(config.SENT_DIR / "llm-labeling"))
from textsplit import split_sentences  # noqa: E402
from check_output import load_run  # noqa: E402

OUT = config.OUT_SENT
IN_DIR = OUT / "input"
RUN_DIR = OUT / "output"
VAL_DIR = OUT / "검증_34개소"
REVIEW_XLSX = OUT / "사람검토표.xlsx"
LABELS = ["긍정", "부정", "중립"]
CATS = ["긍정", "부정", "중립", "혼합"]


def prompt_v1() -> str:
    t = config.PROMPT_V1.read_text(encoding="utf-8")
    return t.split("<<<PROMPT_START>>>", 1)[1].split("<<<PROMPT_END>>>", 1)[0].strip()


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
    IN_DIR.mkdir(parents=True, exist_ok=True)
    for old in IN_DIR.glob("*.txt"):
        old.unlink()
    for i, recs in enumerate(groups, 1):
        lines = [f"# 묶음 추가_{i:02d} · {len(recs)}문장 · 출력도 정확히 {len(recs)}행이어야 합니다.",
                 "unit_id | sent_no/n_sent | 관광지 | 플랫폼 | 문장"]
        for r in recs:
            sent = str(r["sent"]).replace("\n", " ").replace("|", "/").strip()
            lines.append(f'{r["unit_id"]} | {r["sent_no"]}/{r["n_sent"]} | '
                         f'{r["place"]} | {r["platform"]} | {sent}')
        (IN_DIR / f"추가_{i:02d}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ck("문장 분리", len(df) > 0, f"리뷰 {len(t)} → 문장 {len(df)} · 묶음 {len(groups)}")
    print(df.groupby("place").agg(리뷰=("review_id", "nunique"), 문장=("unit_id", "size")).to_string())


# ─────────────────────────────────────────────────────────────
# API 실행 (validate · run 공용)
# ─────────────────────────────────────────────────────────────
def classify_files(files: list[Path], out_dir: Path, label: str):
    client = anthropic_client()
    sysp = prompt_v1()
    out_dir.mkdir(parents=True, exist_ok=True)
    log = {"model": config.SENT_MODEL, "effort": config.SENT_EFFORT,
           "prompt": rel(config.PROMPT_V1),
           "prompt_sha256": hashlib.sha256(sysp.encode("utf-8")).hexdigest(),
           "started": datetime.now().isoformat(timespec="seconds"), "chunks": []}
    for i, f in enumerate(files, 1):
        dst = out_dir / (f.stem + ".tsv")
        if dst.exists() and dst.stat().st_size:
            print(f"  [{label}] {f.name} 이미 있음 — 건너뜀")
            continue
        chunk = f.read_text(encoding="utf-8")
        resp = client.messages.create(
            model=config.SENT_MODEL, max_tokens=16000,
            output_config={"effort": config.SENT_EFFORT},
            messages=[{"role": "user", "content": sysp},
                      {"role": "assistant", "content": "준비됨"},
                      {"role": "user", "content": chunk}],
        )
        if resp.stop_reason not in ("end_turn", "stop_sequence"):
            sys.exit(f"{f.name}: stop_reason={resp.stop_reason} — 중단 (부분 결과는 저장하지 않음)")
        text = "".join(b.text for b in resp.content if b.type == "text")
        dst.write_text(text.strip() + "\n", encoding="utf-8")
        log["chunks"].append({"file": f.name, "response_model": resp.model, "id": resp.id,
                              "input_tokens": resp.usage.input_tokens,
                              "output_tokens": resp.usage.output_tokens})
        print(f"  [{label}] {i}/{len(files)} {f.name} → {dst.name}")
    log["finished"] = datetime.now().isoformat(timespec="seconds")
    logf = out_dir / "실행기록.json"
    old = json.loads(logf.read_text(encoding="utf-8")) if logf.exists() else []
    logf.write_text(json.dumps((old if isinstance(old, list) else [old]) + [log],
                               ensure_ascii=False, indent=2), encoding="utf-8")


def run(args):
    files = sorted(IN_DIR.glob("추가_*.txt"))
    if not files:
        sys.exit("입력 묶음이 없습니다. 먼저 build 를 실행하세요.")
    classify_files(files, RUN_DIR / args.run, args.run)
    check(args)


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
    files = sorted((config.SENT_DIR / "llm-labeling" / "input").glob("*.txt"))
    run_name = args.run
    if not args.score_only:
        classify_files(files, VAL_DIR / run_name, f"검증 {run_name}")
    rows, bad, dup, _ = load_run(run_name, base=VAL_DIR)
    gold = pd.concat([read_csv(config.SENT_DIR / "labeling" / "확정" / f)
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
    res = {"run": run_name, "model": config.SENT_MODEL, "effort": config.SENT_EFFORT,
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
    a, b = load_run("run1", base=VAL_DIR)[0], load_run("run2", base=VAL_DIR)[0]
    both = [k for k in a if k in b]
    if both:
        sa, sb = pd.Series([a[k].rstrip("?") for k in both]), pd.Series([b[k].rstrip("?") for k in both])
        print(f"  검증셋 2회 불일치: {(sa != sb).sum()}/{len(both)} = {(sa != sb).mean():.2%} · κ {kappa(sa, sb):.3f}")


def check(_):
    src = read_csv(OUT / "문장목록.csv")
    exp = set(src["unit_id"])
    runs = {}
    ck = Checks("감성분석 출력 점검")
    for name in ("run1", "run2"):
        rows, bad, dup, noise = load_run(name, base=RUN_DIR)
        if not rows:
            print(f"  [{name}] 아직 없음")
            continue
        miss = exp - set(rows)
        extra = set(rows) - exp
        ck(f"{name} 완결", not miss and not extra and not bad and not dup,
           f"{len(rows)}/{len(exp)} · 누락 {len(miss)} · 없는 id {len(extra)} · 라벨이상 {len(bad)} "
           f"· 중복불일치 {len(dup)} · 무시한 줄 {noise}", fatal=False)
        runs[name] = rows
        lab = pd.Series([v.rstrip("?") for v in rows.values()])
        print("     분포: " + " · ".join(f"{k} {v:.1%}" for k, v in lab.value_counts(normalize=True).items())
              + f" · ? {sum(v.endswith('?') for v in rows.values())}건")
    if len(runs) == 2:
        ids = sorted(set(runs["run1"]) & set(runs["run2"]))
        a = pd.Series([runs["run1"][i].rstrip("?") for i in ids])
        b = pd.Series([runs["run2"][i].rstrip("?") for i in ids])
        flip = int((((a == "긍정") & (b == "부정")) | ((a == "부정") & (b == "긍정"))).sum())
        res = {"불일치": int((a != b).sum()), "문장": len(ids), "불일치율": float((a != b).mean()),
               "kappa": kappa(a, b), "긍부_뒤집힘": flip}
        (RUN_DIR / "재현성.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  2회 실행 불일치 {res['불일치']}/{res['문장']} = {res['불일치율']:.2%} · κ {res['kappa']:.3f} "
              f"· 긍↔부 뒤집힘 {flip}  (34개소: 4.20% · κ 0.936)")


# ─────────────────────────────────────────────────────────────
# review — 사람 검토표
# ─────────────────────────────────────────────────────────────
def review(args):
    src = read_csv(OUT / "문장목록.csv")
    rows = load_run("run1", base=RUN_DIR)[0]
    if not rows:
        sys.exit("run1 결과가 없습니다.")
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
        "   판정 기준은 3_.../분석/감성분석/reference/0001-라벨링-지침서.html (34개소와 동일).",
        "다 채운 뒤: python scripts/s5_sentiment.py merge",
    ]})
    with pd.ExcelWriter(REVIEW_XLSX) as w:
        guide.to_excel(w, sheet_name="0_안내", index=False)
        hard[["unit_id", "place", "sent", "리뷰전문", "모델라벨", "최종판정", "메모"]].to_excel(
            w, sheet_name="1_혼합확정", index=False)
        blind.to_excel(w, sheet_name="2_블라인드검증", index=False)
    print(f"저장: {rel(REVIEW_XLSX)}  혼합·? {len(hard)}문장 · 블라인드 표본 {len(blind)}문장")


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
    ck = Checks("감성분석 최종 병합")
    src = read_csv(OUT / "문장목록.csv")
    rows, bad, dup, _ = load_run("run1", base=RUN_DIR)
    ck("run1 출력 이상 없음", not bad and not dup)
    src["label"] = src["unit_id"].map(rows).str.rstrip("?")
    ck("예측 누락 없음", src["label"].notna().all(), f"누락 {src['label'].isna().sum()}")
    src["출처"] = f"API 예측 ({config.SENT_MODEL})"

    hard_done = 0
    if REVIEW_XLSX.exists():
        h = pd.read_excel(REVIEW_XLSX, sheet_name="1_혼합확정", dtype=str).fillna("")
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
    if REVIEW_XLSX.exists():
        b = pd.read_excel(REVIEW_XLSX, sheet_name="2_블라인드검증", dtype=str).fillna("")
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
    v.add_argument("--score-only", action="store_true", help="API 호출 없이 저장된 출력만 채점")
    r = sub.add_parser("run")
    r.add_argument("--run", default="run1", choices=["run1", "run2"])
    sub.add_parser("check")
    rv = sub.add_parser("review")
    rv.add_argument("--sample", type=int, default=100)
    rv.add_argument("--force", action="store_true")
    sub.add_parser("merge")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    {"build": build, "validate": validate, "run": run, "check": check,
     "review": review, "merge": merge}[args.cmd](args)


if __name__ == "__main__":
    main()
