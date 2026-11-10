# -*- coding: utf-8 -*-
"""[시험 실행] 가짜 판정 파일 — Claude Code 판정 없이도 시험 실행이 끝까지 돌아가게 한다

IMSIL_DEMO=1 에서만 돈다. output/_demo/input/ 아래에만 쓴다 (실제 input/ 은 건드리지 않는다).
시험 데이터는 34개소 인접 관광지 리뷰이므로, 34개소에서 이미 만든 판정을 그 리뷰에 옮겨 붙인다.

  감성 검증셋   input/sentiment/llm_labeling/llm_runs/run1·run2 (34개소 ChatGPT 판정)를 그대로 복사한다.
               validate 가 34개소 보고 수치(macro-F1 0.906 · 0.908)를 다시 내면 채점 코드가 맞다는 뜻이다.
  감성 판정     34개소 최종 문장 라벨을 원 리뷰 ID·문장으로 찾아 붙인다(못 찾으면 중립).
               run2 는 일부 문장 라벨을 일정한 규칙으로 바꿔 2회 불일치율 계산을 시험한다.
  요인 판정     34개소 annotations.jsonl 을 원 리뷰 ID 로 찾아 붙인다. span 이 본문에 없는 요인은 뺀다.
  사람 검토표   채우지 않는다 (merge 는 남은 혼합 수만 알려 주고 진행한다).

실행 (run_all.py --demo 가 sentiment build 뒤에 부른다)
    IMSIL_DEMO=1 python src/new_sites/demo_judgments.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil

import pandas as pd

from common import config, read_csv, rel
from satisfaction import body_hash

FLIP = {"긍정": "중립", "중립": "긍정", "부정": "중립", "혼합": "부정"}


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def note(d, text):
    d.mkdir(parents=True, exist_ok=True)
    (d / "실행기록.md").write_text(f"- 시험 실행: {text}\n", encoding="utf-8")


def orig_ids() -> dict[str, str]:
    """시험 데이터의 가명 ID(RV1xxxx) → 34개소 리뷰 ID(RV0xxxx). 가짜 수집 원본의 id 가 34개소 ID 다."""
    m = read_csv(config.ID_MAP, dtype=str)
    return {r: o.split(":", 1)[1] for o, r in zip(m["orig_id"], m["reviewId"])}


def validation_runs():
    src = config.BASE_SENT_RUNS
    for run in ("run1", "run2"):
        d = config.SENT_VAL_RUNS / run
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        for f in sorted((src / run).glob("*.txt")):
            shutil.copy(f, d / f.name)
        note(d, f"34개소 ChatGPT 웹 UI 판정({rel(src / run)})을 복사")
    print(f"  감성 검증셋: 34개소 ChatGPT 판정 복사 → {rel(config.SENT_VAL_RUNS)}/run1·run2")


def sentence_runs(rid0: dict[str, str]):
    s = read_csv(config.OUT_SENT / "문장목록.csv", dtype=str)
    base = read_csv(config.BASE_SENT_SENTENCE, dtype=str)
    lab = {(r, norm(t)): l for r, t, l in zip(base["review_id"], base["sent"], base["label"])}
    s["label"] = [lab.get((rid0.get(r), norm(t)), "중립") for r, t in zip(s["review_id"], s["sent"])]
    hit = sum((rid0.get(r), norm(t)) in lab for r, t in zip(s["review_id"], s["sent"]))
    for run in ("run1", "run2"):
        d = config.SENT_RUNS / run
        if d.exists():
            shutil.rmtree(d)
        note(d, "34개소 최종 문장 라벨을 옮겨 붙인 가짜 판정" + (" (일부 문장 라벨을 바꿈)" if run == "run2" else ""))
        lines = []
        for u, l in zip(s["unit_id"], s["label"]):
            if run == "run2" and int(hashlib.md5(u.encode()).hexdigest(), 16) % 25 == 0:
                l = FLIP[l]
            lines.append(f"{u}\t{l}")
        (d / "전체.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  감성 판정: {len(s)}문장 중 34개소 라벨을 찾은 문장 {hit} → {rel(config.SENT_RUNS)}/run1·run2")


def factor_annotations(rid0: dict[str, str]):
    pend = {}
    for line in open(config.BASE_FACTOR_IN / "pending.jsonl", encoding="utf-8"):
        r = json.loads(line)
        pend[r["i"]] = r["rid"]
    ann0 = {}
    for line in open(config.BASE_FACTOR_IN / "annotations.jsonl", encoding="utf-8"):
        if line.strip():
            a = json.loads(line)
            ann0[pend[a["i"]]] = a
    d = pd.read_csv(config.PREPROCESSED_FACTOR, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    d = d[d["body"].str.strip() != ""]
    out, kept, dropped = [], 0, 0
    for rid, body in zip(d["reviewId"], d["body"]):
        a = ann0.get(rid0.get(rid), {"o": "NEU", "f": []})
        b = norm(body)
        fs = [f for f in a["f"] if norm(f[1]) in b and norm(f[2]) in b]
        kept += len(fs)
        dropped += len(a["f"]) - len(fs)
        out.append(json.dumps({"rid": rid, "h": body_hash(body), "o": a["o"], "f": fs}, ensure_ascii=False))
    config.FACTOR_ANN.parent.mkdir(parents=True, exist_ok=True)
    config.FACTOR_ANN.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"  요인 판정: 리뷰 {len(out)}건 · 요인 {kept}개 (본문과 맞지 않아 뺀 요인 {dropped}개) → {rel(config.FACTOR_ANN)}")


def main():
    assert config.DEMO, "IMSIL_DEMO=1 에서만 실행합니다 (실제 input/ 보호)"
    rid0 = orig_ids()
    validation_runs()
    sentence_runs(rid0)
    factor_annotations(rid0)


if __name__ == "__main__":
    main()
