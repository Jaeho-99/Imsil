# input/new_sites — 추가 관광지 분석에서 사람이 만든 입력

코드가 만들지 않는 파일만 둡니다. `src/new_sites/`의 코드는 이 폴더를 읽기만 합니다.

| 파일 | 만드는 법 | 읽는 곳 | git |
|---|---|---|:-:|
| `비식별_치환목록.csv` | `preprocess.py`가 출력한 실명 후보 중 사람이 문맥을 보고 실명으로 확인한 표현을 적습니다. 열은 `find,replace`이고, `replace`를 비우면 `○○○`로 바꿉니다 | `build_dataset.py` | 제외 (실명이 그대로 들어 있음) |
| `사람검토표.xlsx` | `sentiment.py review`가 만든 `output/new_sites/sentiment/사람검토표.xlsx`를 여기로 복사해 채웁니다 | `sentiment.py merge` | ○ |

실행 순서와 각 파일을 채우는 기준은 [docs/new_sites.md](../../docs/new_sites.md)에 있습니다.
