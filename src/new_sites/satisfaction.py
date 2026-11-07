# -*- coding: utf-8 -*-
"""[만족·불만] 만족·불만 요인 — 34개소 방법(Claude Code 판정)을 API 없이 그대로 적용하고 관광지별로 집계

34개소와 같은 것
  - 판정 기준: src/satisfaction/analyze_satisfaction.py 의 SYSTEM_PROMPT(코딩 원칙·12개 요인 카테고리·극성)를
    고치지 않고 쓴다. export 가 이 프롬프트를 글자 그대로 파일로 내보낸다.
  - 판정 방식: 34개소 보고서 5장과 같이 Claude Code 대화에서 리뷰를 읽고 판정해 annotations.jsonl 에 쌓는다.
  - 검증: span·opinion 이 리뷰 본문에 그대로 있는지 본다 (src/satisfaction/annotation/merge.py 와 같은 규칙).
  - 결과 파일: 리뷰별_만족불만요인_분석결과.csv 는 34개소 같은 이름 파일과 열이 같다
    (analyze_satisfaction.py 의 to_row()·blank_row() 로 만든다).

34개소와 다른 것
  - 판정 줄을 번호(i) 대신 리뷰 ID(rid)로 잇는다. 리뷰를 다시 수집해 번호가 밀려도 판정이 다른 리뷰에 붙지 않는다.
  - 판정 줄에 본문 확인값(h, 공백을 정리한 본문의 SHA-256 앞 8자리)을 함께 적는다. 수정된 리뷰를 다시 수집했거나
    실명을 가려 본문이 바뀌면 h 가 달라지므로, 옛 본문으로 한 판정이 그대로 쓰이지 않는다.

판정 파일 (Claude Code 가 만들어 input/ 에 저장 — 지시문: input/new_sites/claude_지시문/요인.md)
  input/new_sites/satisfaction/annotations.jsonl   한 줄에 리뷰 하나
    {"rid": "RV10001", "h": "1a2b3c4d", "o": "POS", "f": [["경관·볼거리", "원문 구절", "평가 표현", "POS"], ...]}
    rid·h 는 판정대상.jsonl 의 값을 그대로 옮긴다.

하위 명령 — 출력은 모두 output/new_sites/satisfaction/ 아래
  export   판정 대상(본문 있는 리뷰)과 판정 프롬프트를 내보낸다 → 판정대상.jsonl, 판정프롬프트.txt
  check    판정 파일만 검증한다 (형식·카테고리·span 이 본문에 있는지·남은 리뷰)
  merge    검증 → 리뷰별 결과 CSV → 관광지별 집계·대표 원문·그림. 모든 리뷰의 판정이 끝나야 실행된다.

집계 (이 스크립트에서 새로 계산)
  관광지 × 요인 카테고리별로 만족·불만을 언급한 리뷰 수와 비율(분모: 본문이 있는 리뷰).
  '순만족' = 만족 언급 리뷰 비율 − 불만 언급 리뷰 비율.
  같은 요인이 34개소 전체·인접 관광지에서는 어땠는지 나란히 놓는다.
  보고서 인용용으로 요인별 대표 원문(span)을 뽑는다.

입력  output/new_sites/추가관광지_리뷰데이터_1차전처리.csv (preprocess.py 결과)
      input/new_sites/satisfaction/annotations.jsonl
출력  output/new_sites/satisfaction/판정대상.jsonl · 판정프롬프트.txt      (export)
      output/new_sites/satisfaction/리뷰별_만족불만요인_분석결과.csv      (merge — 34개소 같은 이름 파일과 같은 열)
      output/new_sites/satisfaction/관광지별_요인집계.csv
      output/new_sites/satisfaction/요인별_대표원문.csv
      output/new_sites/satisfaction/그림_{관광지}_만족불만요인.png

실행
    python src/new_sites/satisfaction.py export
    python src/new_sites/satisfaction.py check
    python src/new_sites/satisfaction.py merge
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter

import pandas as pd

from common import Checks, config, read_csv, rel, save_inputs, setup_font, write_csv

sys.path.insert(0, str(config.FACTOR_SCRIPT.parent))
import analyze_satisfaction as az  # noqa: E402  34개소 코드: 프롬프트·카테고리·결과 행 변환

CATS12 = [c for c in az.CATEGORIES if c != "대상외"]
OUT = config.OUT_FACTOR
OUT_CSV = OUT / "리뷰별_만족불만요인_분석결과.csv"
TARGETS = OUT / "판정대상.jsonl"
PROMPT = OUT / "판정프롬프트.txt"
ANN = config.FACTOR_ANN
GUIDE = "input/new_sites/claude_지시문/요인.md"


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def body_hash(body) -> str:
    """본문 확인값 — 공백을 정리한 본문의 SHA-256 앞 8자리."""
    return hashlib.sha256(norm(body).encode("utf-8")).hexdigest()[:8]


def load_targets():
    """1차전처리본 전체와, 판정 대상(본문 있는 리뷰 — analyze_satisfaction.py 와 같은 기준)."""
    if not config.PREPROCESSED.exists():
        sys.exit(f"{rel(config.PREPROCESSED)} 이 없습니다. preprocess.py 를 먼저 실행하세요.")
    df = pd.read_csv(config.PREPROCESSED, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    t = df[df["body"].str.strip() != ""]
    return df, t


def read_annotations(t: pd.DataFrame):
    """input/ 의 판정 파일을 읽어 검증한다. 돌려주는 값: ({rid: 판정}, 오류 목록, 대상 밖 리뷰 목록).

    대상 밖 리뷰: 리뷰ID 형식은 맞지만 지금 판정 대상에 없는 줄. 분석 기간(config.DATE_END)을 줄이면
    기간 밖 리뷰의 판정 줄이 남는다. 리뷰ID 는 대응표로 고정되어 있어 남은 리뷰의 판정은 그대로 쓰고,
    기간 밖 줄은 지우지 않고 읽지만 않는다 (기간을 다시 넓히면 다시 쓰인다).
    """
    body = {r: norm(b) for r, b in zip(t["reviewId"], t["body"])}
    ann, errs, outside, seen = {}, [], [], Counter()
    if not ANN.exists():
        return ann, errs, outside
    for ln, line in enumerate(ANN.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            a = json.loads(line)
        except json.JSONDecodeError as e:
            errs.append(f"{ln}번째 줄: JSON 이 아님 — {e}")
            continue
        rid = a.get("rid") if isinstance(a, dict) else None
        if isinstance(rid, str) and re.fullmatch(r"RV\d{5}", rid) and rid not in body:
            outside.append(rid)
            continue
        if rid not in body:
            errs.append(f"{ln}번째 줄: 판정 대상에 없는 리뷰 '{rid}'")
            continue
        seen[rid] += 1
        if seen[rid] > 1:
            errs.append(f"{ln}번째 줄: {rid} 가 두 번 나옴 — 한 줄만 남기세요")
            continue
        if a.get("h") != body_hash(body[rid]):
            errs.append(f"{ln}번째 줄: {rid} 본문 확인값 h='{a.get('h')}' 가 지금 본문({body_hash(body[rid])})과 다름 — "
                        "판정대상.jsonl 의 h 를 옮겨 적거나, 본문이 바뀐 리뷰라면 다시 판정하세요")
            continue
        if a.get("o") not in az.SENTIMENTS:
            errs.append(f"{ln}번째 줄: {rid} 전체 극성 o='{a.get('o')}' — POS·NEG·NEU 중 하나여야 함")
            continue
        fs = a.get("f")
        if not isinstance(fs, list):
            errs.append(f"{ln}번째 줄: {rid} f 가 목록이 아님")
            continue
        bad = False
        for f in fs:
            if not (isinstance(f, list) and len(f) == 4 and all(isinstance(x, str) for x in f)):
                errs.append(f"{ln}번째 줄: {rid} 요인 형식 오류 {f} — [카테고리, span, opinion, 극성]")
                bad = True
                continue
            cat, span, op, s = f
            if cat not in az.CATEGORIES:
                errs.append(f"{ln}번째 줄: {rid} 카테고리 '{cat}' 는 13개 목록에 없음")
                bad = True
            if s not in az.SENTIMENTS:
                errs.append(f"{ln}번째 줄: {rid} 극성 '{s}' — POS·NEG·NEU 중 하나여야 함")
                bad = True
            for name, x in (("span", span), ("opinion", op)):
                if not norm(x) or norm(x) not in body[rid]:
                    errs.append(f"{ln}번째 줄: {rid} {name} 이 본문에 그대로 없음 — '{x}'")
                    bad = True
        if not bad:
            ann[rid] = a
    return ann, errs, outside


def merge_inputs():
    """merge 가 읽는 입력 — 결과 폴더의 입력기록.json 에 해시를 남긴다."""
    return [config.PREPROCESSED, ANN]


def complete() -> bool:
    """모든 판정 대상 리뷰의 판정이 오류 없이 있는가 (run_all.py 가 merge 전에 본다)."""
    if not config.PREPROCESSED.exists():
        return False
    _, t = load_targets()
    ann, errs, outside = read_annotations(t)
    return not errs and len(t) > 0 and bool(t["reviewId"].isin(ann).all())


def ranges(nums: list[int]) -> str:
    """[1,2,3,7,9,10] → '#1–3, #7, #9–10'"""
    out, start, prev = [], None, None
    for n in nums + [None]:
        if start is None:
            start = prev = n
        elif n is not None and n == prev + 1:
            prev = n
        else:
            out.append(f"#{start}" if start == prev else f"#{start}–{prev}")
            start = prev = n
    return ", ".join(out)


def status(t: pd.DataFrame, ann: dict, errs: list, outside: list = ()):
    left = [i for i, r in enumerate(t["reviewId"], 1) if r not in ann]
    print(f"\n  판정 {len(ann)}/{len(t)}건 · 남은 리뷰 {len(left)}건 · 오류 {len(errs)}건  ({rel(ANN)})")
    if outside:
        print(f"  지금 판정 대상이 아닌 리뷰의 줄 {len(outside)}개는 읽지 않습니다 "
              f"(분석 기간 {config.DATE_START} ~ {config.DATE_END} 밖이거나 본문이 빈 리뷰).")
    for e in errs[:40]:
        print("   !", e)
    if len(errs) > 40:
        print(f"   … 외 {len(errs) - 40}건")
    if left:
        print(f"  남은 리뷰 (판정대상.jsonl 의 i): {ranges(left)[:300]}")
    return left


def export(_):
    df, t = load_targets()
    OUT.mkdir(parents=True, exist_ok=True)
    with open(TARGETS, "w", encoding="utf-8") as f:
        for i, r in enumerate(t.itertuples(), 1):
            f.write(json.dumps({"i": i, "rid": r.reviewId, "h": body_hash(r.body), "place": r.place,
                                "body": r.body.strip()}, ensure_ascii=False) + "\n")
    PROMPT.write_text(az.SYSTEM_PROMPT, encoding="utf-8")
    print(f"저장: {rel(TARGETS)}  본문 있는 리뷰 {len(t)}건 (전체 {len(df)}건)")
    print(f"      {rel(PROMPT)}  34개소 SYSTEM_PROMPT 그대로")
    print(t.groupby("place").size().rename("판정 대상").to_string())
    if config.TRANSLATE_TODO.exists():
        print(f"  [주의] 번역이 남은 외국어 리뷰가 있습니다 ({rel(config.TRANSLATE_TODO)}). "
              "번역을 넣고 preprocess.py 부터 다시 실행한 뒤 판정하세요.")
    ann, errs, outside = read_annotations(t)
    status(t, ann, errs, outside)
    print(f"  판정 방법: {GUIDE}")


def check(_):
    _, t = load_targets()
    ann, errs, outside = read_annotations(t)
    left = status(t, ann, errs, outside)
    if errs:
        sys.exit(1)
    if not left:
        print("  모든 리뷰의 판정이 끝났습니다 → python src/new_sites/satisfaction.py merge")


def merge(_):
    ck = Checks("만족·불만 요인 판정 병합")
    df, t = load_targets()
    ann, errs, outside = read_annotations(t)
    ck("판정 파일 존재", ANN.exists(), rel(ANN) if ANN.exists() else f"{rel(ANN)} 없음 — {GUIDE} 대로 판정")
    ck("판정 형식·원문 대조", not errs, f"오류 {len(errs)}건 — check 로 확인" if errs else f"{len(ann)}건")
    left = int((~t["reviewId"].isin(ann)).sum())
    ck("모든 리뷰 판정", left == 0, f"{len(ann)}/{len(t)}건" + (f" · 남은 {left}건 — check 로 확인" if left else ""))

    rows = []
    for rid in df["reviewId"]:
        if rid in ann:
            a = ann[rid]
            rows.append(az.to_row({"factors": [dict(zip(("category", "span", "opinion", "sentiment"), f))
                                               for f in a["f"]],
                                   "overall_sentiment": a["o"]}))
        else:
            rows.append(az.blank_row("skipped: 본문 없음"))
    out = df[az.BASE_COLUMNS].copy()
    for c in az.RESULT_COLUMNS:
        out[c] = [r.get(c, "") for r in rows]
    write_csv(out, OUT_CSV)
    n_f = sum(len(a["f"]) for a in ann.values())
    ck("리뷰별 결과 CSV", len(out) == len(df), f"{len(out)}행 · 요인 {n_f}개 · {rel(OUT_CSV)}")
    aggregate()
    save_inputs(OUT, merge_inputs())


# ─────────────────────────────────────────────────────────────
# 집계
# ─────────────────────────────────────────────────────────────
def factor_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in df.itertuples():
        try:
            fs = json.loads(r.factors_json).get("factors", []) if isinstance(r.factors_json, str) else []
        except json.JSONDecodeError:
            fs = []
        for f in fs:
            rows.append({"place": r.place, "reviewId": r.reviewId, "category": f.get("category"),
                         "sentiment": f.get("sentiment"), "span": f.get("span"), "opinion": f.get("opinion")})
    return pd.DataFrame(rows, columns=["place", "reviewId", "category", "sentiment", "span", "opinion"])


def place_table(df: pd.DataFrame, fr: pd.DataFrame, places) -> pd.DataFrame:
    out = []
    for p in places:
        n = int(((df["place"] == p) & (df["analyzed"].astype(str) == "True")).sum())
        f = fr[fr["place"] == p]
        for c in CATS12:
            pos = f[(f.category == c) & (f.sentiment == "POS")]["reviewId"].nunique()
            neg = f[(f.category == c) & (f.sentiment == "NEG")]["reviewId"].nunique()
            out.append({"place": p, "category": c, "분석리뷰": n, "만족리뷰": pos, "불만리뷰": neg,
                        "만족비율": pos / n if n else 0, "불만비율": neg / n if n else 0,
                        "순만족": (pos - neg) / n if n else 0})
    return pd.DataFrame(out)


def examples(fr: pd.DataFrame, k=3) -> pd.DataFrame:
    rows = []
    for (p, c, s), g in fr[fr.sentiment.isin(["POS", "NEG"])].groupby(["place", "category", "sentiment"]):
        g = g.assign(L=g["span"].str.len()).sort_values(["L", "reviewId"], ascending=[False, True])
        for span in g.drop_duplicates("span")["span"].head(k):
            rows.append({"place": p, "category": c, "구분": "만족" if s == "POS" else "불만",
                         "언급리뷰": g["reviewId"].nunique(), "원문": span})
    return pd.DataFrame(rows, columns=["place", "category", "구분", "언급리뷰", "원문"])


def plot(tab: pd.DataFrame):
    plt = setup_font()
    for p in config.TARGET_NAMES:
        t = tab[tab.place == p]
        if t.empty or t["분석리뷰"].iloc[0] == 0:
            continue
        t = t.assign(tot=t["만족리뷰"] + t["불만리뷰"]).sort_values("tot")
        t = t[t.tot > 0]
        if t.empty:
            continue
        fig, ax = plt.subplots(figsize=(9, 0.45 * len(t) + 1.6))
        ax.barh(t["category"], t["만족비율"], color="#2a78d6", label="만족 언급")
        ax.barh(t["category"], -t["불만비율"], color="#d6452a", label="불만 언급")
        for i, r in enumerate(t.itertuples()):
            if r.만족리뷰:
                ax.text(r.만족비율 + 0.005, i, f"{r.만족리뷰}", va="center", fontsize=9)
            if r.불만리뷰:
                ax.text(-r.불만비율 - 0.005, i, f"{r.불만리뷰}", va="center", ha="right", fontsize=9)
        m = max(t["만족비율"].max(), t["불만비율"].max()) * 1.25
        ax.set_xlim(-m, m)
        ax.axvline(0, color="#555555", lw=0.8)
        ticks = ax.get_xticks()
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{abs(x):.0%}" for x in ticks])
        ax.set_xlabel(f"언급 리뷰 비율 (분모: 본문 있는 리뷰 {int(t['분석리뷰'].iloc[0])}건, 막대 끝 숫자 = 리뷰 수)")
        ax.set_title(f"{p} 요인별 만족·불만", loc="left")
        ax.legend(ncol=2, loc="lower right", bbox_to_anchor=(1.0, 1.0), frameon=False)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        fig.tight_layout()
        fig.savefig(OUT / f"그림_{p}_만족불만요인.png", dpi=150)
        plt.close(fig)


def aggregate():
    ck = Checks("만족·불만 요인 집계")
    df = read_csv(OUT_CSV, dtype={"reviewId": str})
    status_ = df["run_status"].value_counts().to_dict()
    bad = {k: v for k, v in status_.items() if k not in ("ok", "skipped: 본문 없음")}
    ck("판정 누락 없음", not bad, f"상태 {status_}")
    fr = factor_rows(df)

    base = read_csv(config.BASE_FACTOR, dtype={"reviewId": str})
    bfr = factor_rows(base)
    cmp_places = list(config.COMPARE_PLACES.values())
    tab = place_table(df, fr, config.TARGET_NAMES)
    tab_cmp = place_table(base, bfr, cmp_places)
    base_all = place_table(base.assign(place="34개소 전체"), bfr.assign(place="34개소 전체"), ["34개소 전체"])
    full = pd.concat([tab, tab_cmp, base_all], ignore_index=True)
    write_csv(full, OUT / "관광지별_요인집계.csv")
    write_csv(examples(fr), OUT / "요인별_대표원문.csv")
    plot(tab)
    ck("관광지별 요인 집계", len(tab) > 0, f"{len(tab)}행 (비교 {len(tab_cmp) + len(base_all)}행 별도)")

    for p in config.TARGET_NAMES:
        t = tab[tab.place == p]
        if t.empty:
            continue
        sat = t.sort_values("만족리뷰", ascending=False).head(3)
        dis = t.sort_values("불만리뷰", ascending=False).head(3)
        print(f"\n  [{p}] 분석 리뷰 {int(t['분석리뷰'].iloc[0])}건")
        print("    만족 상위: " + " · ".join(f"{r.category} {r.만족리뷰}건({r.만족비율:.0%})" for r in sat.itertuples()))
        print("    불만 상위: " + " · ".join(f"{r.category} {r.불만리뷰}건({r.불만비율:.0%})" for r in dis.itertuples()))
    print(f"\n저장: {rel(OUT)}/")


def main():
    ap = argparse.ArgumentParser(description="만족·불만 요인: 판정 대상 내보내기 → 판정 검증 → 병합·집계")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export", help="판정 대상과 프롬프트를 output/ 에 내보낸다")
    sub.add_parser("check", help="input/ 의 판정 파일을 검증한다")
    sub.add_parser("merge", help="판정을 결과 CSV 로 병합하고 관광지별로 집계한다")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    {"export": export, "check": check, "merge": merge}[args.cmd](args)


if __name__ == "__main__":
    main()
