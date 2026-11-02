"""
크롬 프로필에 구글 로그인 세션을 심어두는 준비 스크립트 (로그인해두기.py)

수집을 처음 돌리기 전에 딱 한 번만 실행하면 됩니다.

■ 무엇을 하는가
  google_reviews.py 가 쓰는 것과 똑같은 프로필 폴더(chrome_profile_google/)로
  크롬을 띄우고, 구글 로그인 페이지를 열어둔 채 기다립니다.
  창에서 직접 로그인한 뒤 터미널에서 Enter 를 누르면 세션이 그 폴더에 저장되고,
  이후 google_reviews.py 실행은 자동으로 로그인된 상태로 시작됩니다.

■ 왜 하는가
  로그인 세션이 없는 맨 브라우저로 구글 지도를 계속 긁으면
  "비정상적인 트래픽" 캡차가 자주 뜹니다. 뜨면 수집이 멈추고 사람이 풀어줘야 합니다.

■ 주의
  비밀번호는 본인이 크롬 창에 직접 입력하세요. 이 스크립트는 창만 띄웁니다.
  생성된 chrome_profile_google/ 폴더는 절대 남에게 공유하지 마세요.

■ 실행
  .venv\\Scripts\\python 로그인해두기.py
"""

from playwright.sync_api import sync_playwright

from google_reviews import PROFILE_DIR, ensure_event_loop, launch_context


def main():
    note = ensure_event_loop()
    if note:
        print(f"[환경] {note}")

    print(f"[설정] 프로필 폴더: {PROFILE_DIR}")
    print("[안내] 크롬 창이 뜹니다. 평소처럼 본인 구글 계정으로 로그인하세요.\n")

    with sync_playwright() as p:
        context = launch_context(p, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto("https://accounts.google.com/", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:  # 네트워크가 느려 첫 로딩이 늦는 경우
            print(f"[알림] 로그인 페이지 로딩이 지연됩니다({type(e).__name__}). 창에서 직접 이동해도 됩니다.")

        try:
            input("로그인을 마쳤으면 이 터미널에서 [Enter] ▶ ")
        finally:
            context.close()

    print("\n[완료] 로그인 세션이 저장되었습니다.")
    print("       이제 google_reviews.py 를 실행하면 이 세션으로 접속합니다.")
    print("       이 프로필 폴더는 본인 것입니다. 팀원에게 보내지 마세요.")


if __name__ == "__main__":
    main()
