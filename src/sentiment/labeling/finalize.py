# -*- coding: utf-8 -*-
"""hold 정리 -> 확정 검증셋 생성 (1단계)

입력 — 읽기만 한다. 절대 수정하지 않는다.
  input/sentiment/labeling/검증셋_본_라벨링용.xlsx        사람이 채운 라벨 539행
  input/sentiment/labeling/검증셋_부정보강_라벨링용.xlsx  162행
  output/sentiment/calibration/보정셋_배정.csv             CAL/TEST 배정 (사전등록 2026-08-21, seed 20260821)

출력 — output/sentiment/labeling/확정/
  검증셋_본_확정.csv · 검증셋_보강_확정.csv · 제외목록.csv

라벨은 전부 사용자가 매긴 값이다. 이 스크립트는 라벨을 만들지 않는다.
쪼갠 문장의 새 라벨도 사용자가 2026-08-22에 직접 지정한 값을 그대로 옮긴다.

실행:  python src/sentiment/labeling/finalize.py
"""
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ (경로는 paths.py 한 곳에서 정한다)
from paths import SENT_IN, SENT_OUT  # noqa: E402
LAB_IN = SENT_IN / "labeling"                  # 사람이 라벨을 채운 검증셋
OUT = SENT_OUT / "labeling" / "확정"

# --- 제외: 문장분리 오류로 생긴 조각. 이웃 문장이 이미 라벨돼 있어 내용 손실 없음 ---
DROP = {
    "MAIN-0013": "문장부호만", "MAIN-0040": "문장부호만", "MAIN-0228": "문장부호만",
    "MAIN-0303": "문장부호만", "MAIN-0306": "문장부호만", "MAIN-0443": "문장부호만",
    "MAIN-0187": "과분할-날짜",  "MAIN-0189": "과분할-나열", "MAIN-0190": "과분할-나열",
    "MAIN-0191": "과분할-나열",  "MAIN-0222": "과분할-절중간", "MAIN-0293": "과분할-절중간",
}

# --- 분할: 지침서 판정순서 1번(규칙 1-1). (앞부분 원문, 앞 라벨, 뒤 라벨) ---
#     라벨 출처: 사용자 확정 2026-08-22
SPLITS = {
    "MAIN-0094": ("날씨가 더워 다니기에는 지침", "부정", "긍정"),
    "MAIN-0308": ("더운거 빼고 좋음", "긍정", "부정"),
    "MAIN-0357": ("시설은 잘돼있어서 뷰 좋고 멋집니다", "긍정", "부정"),
    "MAIN-0383": ("작은섬이네요 주변이 산이라 공기좋아요~", "긍정", "부정"),
    "MAIN-0452": ("치즈를 구매하려고 잠시 들린곳인데 아이들과 같이 가면 좋아할거 같아요", "긍정", "부정"),
    "BOOST-0066": ("볼 건 없으나", "부정", "긍정"),
    "BOOST-0083": ("맛은있으나", "긍정", "부정"),
    "BOOST-0119": ("생각보다 크고 볼걸이도 많았으나", "긍정", "부정"),
    "BOOST-0120": ("사람이 많아서 사진찍고 sns올리려면 얼굴 모자이크 하다 지쳐서 포기~", "부정", "긍정"),
}
# 쪼개지 않고 그대로 두는 것 — 지침서 규칙 1-1 단서조항(한쪽이 사실 진술이면 그대로 둔다).
# 전부 사용자 확정 2026-08-22.
KEEP = {
    "MAIN-0014": "혼합이 아니라 애매한 경우. 판정순서 2번(평가어 없음) -> 중립 유지",
    "BOOST-0125": "'주변을 걸었음'은 사실 진술 -> 중립 유지",
    "BOOST-0139": "'규모는크지만'은 사실 진술 -> 부정 유지",
}

COLS = ["unit_id", "set", "review_id", "sent_no", "n_sent", "place", "platform",
        "sent", "label", "is_boilerplate", "is_split", "note", "split"]


def load(name):
    d = pd.read_excel(LAB_IN / name, sheet_name="라벨링").fillna("")
    for c in d.columns:
        d[c] = d[c].astype(str).str.strip() if d[c].dtype == object else d[c]
    return d


def finalize(d, assign):
    rows, dropped = [], []
    for r in d.to_dict("records"):
        uid = r["unit_id"]
        if uid in DROP:
            dropped.append({"unit_id": uid, "sent": r["sent"], "사유": DROP[uid],
                            "원_split": assign.get(uid, ""), "원_note": r["note"]})
            continue
        if uid in SPLITS:
            head, lab_a, lab_b = SPLITS[uid]
            full = r["sent"]
            assert full.startswith(head), f"{uid}: 앞부분이 원문과 다르다\n  {full!r}"
            tail = full[len(head):].strip()
            assert tail, f"{uid}: 뒷부분이 비었다"
            for suffix, sent, lab in ((("", head, lab_a)), ("-b", tail, lab_b)):
                rows.append({**r, "unit_id": uid + suffix, "sent": sent, "label": lab,
                             "is_split": "Y", "is_boilerplate": ""})
            continue
        rows.append(dict(r))

    f = pd.DataFrame(rows)
    f["split"] = f["unit_id"].str.replace("-b$", "", regex=True).map(assign)  # -b는 원 문장의 배정을 따른다
    # sent_no / n_sent 는 파생값 -> 확정본 기준으로 다시 매긴다 (unit_id는 그대로 두어 추적 가능)
    f["sent_no"] = f.groupby("review_id").cumcount() + 1
    f["n_sent"] = f.groupby("review_id")["unit_id"].transform("size")
    return f[COLS], pd.DataFrame(dropped)


assign = dict(pd.read_csv(SENT_OUT / "calibration" / "보정셋_배정.csv",
                          encoding="utf-8-sig")[["unit_id", "split"]].values)

main, dropped = finalize(load("검증셋_본_라벨링용.xlsx"), assign)
boost, _ = finalize(load("검증셋_부정보강_라벨링용.xlsx"), assign)

assert main["label"].ne("").all(), "본: 빈 라벨이 남았다"
assert boost["label"].ne("").all(), "보강: 빈 라벨이 남았다"
assert main["split"].notna().all() and boost["split"].notna().all(), "배정 없는 unit_id가 있다"

OUT.mkdir(parents=True, exist_ok=True)
main.to_csv(OUT / "검증셋_본_확정.csv", index=False, encoding="utf-8-sig")
boost.to_csv(OUT / "검증셋_보강_확정.csv", index=False, encoding="utf-8-sig")
dropped.to_csv(OUT / "제외목록.csv", index=False, encoding="utf-8-sig")

n_split_main = sum(u.startswith("MAIN") for u in SPLITS)
n_split_boost = sum(u.startswith("BOOST") for u in SPLITS)
print(f"본   539 -> {len(main)}행   (제외 {len(dropped)}, 분할 {n_split_main}건 -> +{n_split_main})")
print(f"보강 162 -> {len(boost)}행   (제외 0, 분할 {n_split_boost}건 -> +{n_split_boost})")
print("\n== CAL / TEST ==")
cal = (main.split == "CAL").sum()
tst = (main.split == "TEST").sum()
print(f"  CAL      {cal:>4}   (등록값 152)")
print(f"  TEST 본  {tst:>4}   (등록값 387)")
print(f"  TEST 보강{len(boost):>4}   (등록값 162)")
print(f"  채점 합계 {tst + len(boost):>3}   (등록값 549)")
print("\n== 라벨 분포 ==")
for name, df in (("본 전체", main), ("  └ CAL", main[main.split == "CAL"]),
                 ("  └ TEST", main[main.split == "TEST"]), ("보강", boost)):
    v = df.label.value_counts()
    n = len(df)
    print(f"  {name:<9} n={n:>4}  " + "  ".join(
        f"{k} {v.get(k,0):>3} ({v.get(k,0)/n*100:>4.1f}%)" for k in ("긍정", "중립", "부정")))
print(f"\n  is_split=Y {int((main.is_split=='Y').sum())}행 · is_boilerplate=Y {int((main.is_boilerplate=='Y').sum())}행")
print(f"  출력: {OUT}")
