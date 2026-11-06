# -*- coding: utf-8 -*-
"""
사전 기반 베이스라인을 전체 5,697문장에 돌린다.

정답 라벨이 없어도 할 수 있는 검증이 하나 있다 — **예측 분포**를 보는 것.
파일럿에서 추정한 실제 분포(긍정 66% / 중립 21% / 부정 13%)와
사전이 내놓는 분포가 크게 다르면, 그 차이 자체가 이 방식의 편향이다.
"""
import sys
import pandas as pd
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import REVIEWS_PRE, SENT_OUT, save_console  # noqa: E402
SRC = REVIEWS_PRE
save_console(SENT_OUT / "pilot" / "dict_fullscale_result.txt")   # 화면 출력을 결과 파일로도 남긴다

sys.path.insert(0, str(HERE.parent))
from textsplit import split_sentences  # 문장 분리는 여기 한 곳에서만 정의한다

POS = ["좋", "굿", "굳", "최고", "예쁘", "예뻐", "이쁘", "이뻐", "멋지", "멋진", "만족", "맛있",
       "추천", "편하", "편함", "즐거", "즐길", "재밌", "재미", "아름답", "훌륭", "깨끗", "친절",
       "감사", "행복", "힐링", "괜찮", "시원", "가득", "잘되", "잘 되"]
NEG = ["아쉬", "불편", "비싸", "실망", "별로", "더럽", "짜증", "최악", "비추", "없음", "없다",
       "없어", "부족", "힘들", "좁", "시끄", "불친절", "지저분", "나쁘", "싫", "후회", "고장", "엉망"]


def predict(s):
    p = sum(1 for w in POS if w in s)
    n = sum(1 for w in NEG if w in s)
    if p > n:
        return "긍정", p, n
    if n > p:
        return "부정", p, n
    return "중립", p, n


df = pd.read_csv(SRC, encoding="utf-8-sig")
df["body"] = df["body"].fillna("").astype(str).str.strip()
df = df[df["body"] != ""]

rows = []
for _, r in df.iterrows():
    for s in split_sentences(r["body"]):
        lab, p, n = predict(s)
        rows.append({"place": r["place"], "platform": r["platform"],
                     "sent": s, "pred": lab, "pos_hits": p, "neg_hits": n})
s = pd.DataFrame(rows)

print(f"전체 문장: {len(s):,}")

print("\n== 사전 기반 예측 분포 vs 파일럿 실제 분포 ==")
pilot = {"긍정": 66.1, "중립": 21.0, "부정": 12.9}
vc = s["pred"].value_counts()
print(f"{'라벨':<6}{'예측 수':>9}{'예측 비율':>10}{'실제(파일럿)':>14}{'차이':>9}")
for k in ["긍정", "중립", "부정"]:
    pct = vc.get(k, 0) / len(s) * 100
    print(f"{k:<6}{vc.get(k,0):>9,}{pct:>9.1f}%{pilot[k]:>13.1f}%{pct-pilot[k]:>+8.1f}p")

zero = ((s.pos_hits == 0) & (s.neg_hits == 0)).sum()
tie = ((s.pos_hits > 0) & (s.pos_hits == s.neg_hits)).sum()
print(f"\n사전 단어가 하나도 안 걸린 문장: {zero:,} ({zero/len(s)*100:.1f}%)  <- 전부 '중립'으로 떨어짐")
print(f"긍정어·부정어 개수가 같아 무승부난 문장: {tie:,} ({tie/len(s)*100:.1f}%)")

print("\n== 플랫폼별 예측 부정 비율 ==")
for plat, g in s.groupby("platform"):
    print(f"  {plat}: {(g.pred=='부정').mean()*100:.1f}%  (문장 {len(g):,})")

print("\n== 관광지별 예측 부정 비율 (문장 100개 이상) ==")
big = s.groupby("place").filter(lambda g: len(g) >= 100)
t = big.groupby("place").agg(문장=("pred", "size"),
                             부정비율=("pred", lambda x: (x == "부정").mean() * 100))
print(t.sort_values("부정비율", ascending=False).round(1).to_string())

print("\n== '없' 계열 오탐 점검: 부정 예측인데 실제로는 긍정일 가능성이 높은 패턴 ==")
susp = s[(s.pred == "부정") & s.sent.str.contains("아깝지 않|부족함이 없|별로 없|나쁘지 않|빠지지 않")]
print(f"  후보 {len(susp)}건")
for x in susp["sent"].head(8):
    print("   -", x[:70])

print("\n== '굳/좋' 오탐 점검: 긍정 예측인데 부정 문장일 가능성 ==")
susp2 = s[(s.pred != "부정") & s.sent.str.contains("굳이|좋겠|좋을텐데|좋았을|좋아졌으면|좋겠음")]
print(f"  후보 {len(susp2)}건")
for x in susp2["sent"].head(8):
    print("   -", x[:70])
