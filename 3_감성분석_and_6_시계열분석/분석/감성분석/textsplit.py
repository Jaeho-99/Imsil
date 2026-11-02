# -*- coding: utf-8 -*-
"""문장 분리 — 파이프라인 전체가 이 함수 하나만 쓴다.

구분자에서 자르고 나면 뒤에 문장부호만 남은 조각이 독립 문장으로 떨어져 나온다.

    "벚꽃축제날에 방문했는데 사람이 엄청 많았어요~~~! 주차는 못 올라가게..."
      -> ["...많았어요", "!", "주차는 못 올라가게..."]

가운데 "!"는 라벨할 수 있는 단위가 아니라 앞 문장의 꼬리다. 그대로 두면
라벨링 파일에 빈 껍데기 행이 생기고(검증셋 539문장 중 6개), 예측 쪽에서도
같은 조각이 '중립'으로 세어져 분포와 macro-F1을 함께 오염시킨다.
그래서 내용이 없는 조각은 앞 문장에 도로 붙인다.

전체 5,697문장 중 15개(0.26%)가 여기 해당한다.
"""
import re

SPLIT = re.compile(r"(?:\r?\n)+|(?<=[.!?…])\s+|~{2,}\s*")

# 한글(자모 포함)·영문·숫자가 하나라도 있으면 내용이 있는 문장으로 본다.
# 'ㅋㅋㅋ' 'ㅠㅠ'는 그 자체로 감성을 담고 있으므로 독립 문장으로 남긴다.
# 반면 '!' '...' '(*ฅ́˘ฅ̀*)' 같은 조각은 앞 문장에 붙인다.
CONTENT = re.compile(r"[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ]")


def split_sentences(text: str) -> list[str]:
    out: list[str] = []
    pending = ""  # 붙일 앞 문장이 아직 없을 때 다음 문장 앞에 붙여 둔다
    for part in SPLIT.split(text or ""):
        part = part.strip()
        if not part:
            continue
        if not CONTENT.search(part):
            if out:
                out[-1] += part
            else:
                pending += part
            continue
        out.append(pending + part)
        pending = ""
    if pending:  # 전체가 문장부호뿐인 리뷰
        out.append(pending)
    return out


if __name__ == "__main__":
    CASES = [
        ("벚꽃축제날에 방문했는데 많았어요~~~! 주차는 막아놨어요.",
         ["벚꽃축제날에 방문했는데 많았어요!", "주차는 막아놨어요."]),
        ("꽃은 봐도봐도 예쁘네용.\n!!\n또 갈래요",
         ["꽃은 봐도봐도 예쁘네용.!!", "또 갈래요"]),
        ("좋아요.\n.\n.", ["좋아요..."]),          # 연쇄 조각도 하나로 붙는다
        ("재밌어요 ㅋㅋㅋ", ["재밌어요 ㅋㅋㅋ"]),
        ("좋아요\nㅠㅠ", ["좋아요", "ㅠㅠ"]),        # 자모는 독립 문장으로 남긴다
        ("!!!", ["!!!"]),                           # 전체가 문장부호뿐
        ("", []),
    ]
    bad = 0
    for text, want in CASES:
        got = split_sentences(text)
        ok = got == want
        bad += not ok
        print(f"{'OK ' if ok else 'FAIL'} {text!r}\n     -> {got!r}"
              + ("" if ok else f"\n     기대 {want!r}"))
    print("\n통과" if not bad else f"\n실패 {bad}건")
