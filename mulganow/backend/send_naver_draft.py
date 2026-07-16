"""작성팀이 (자동화 스크립트를 거치지 않고) 수동으로 발행한 블로그 글의
네이버 블로그용 원고를 메일로 발송합니다.

generate_blog_post.py는 스크립트 스스로 글을 생성할 때만 원고 메일을 보내므로,
작성팀이 직접 만든 특집 글은 그 경로를 안 거칩니다. 이 스크립트가 그 공백을
메꿉니다: mulganow/backend/naver_drafts/latest.md를 커밋·푸시하면
GitHub Actions(send-naver-draft.yml)가 이 파일을 그대로 메일로 보냅니다.
GMAIL_ADDRESS / GMAIL_APP_PASSWORD는 generate_blog_post.py와 동일한
GitHub Actions 시크릿을 재사용합니다.
"""
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

RECIPIENT = "seohilab@naver.com"
DRAFT_PATH = Path(__file__).parent / "naver_drafts" / "latest.md"


def main():
    if not DRAFT_PATH.exists():
        print(f"{DRAFT_PATH} 가 없어 발송을 건너뜁니다.")
        return

    text = DRAFT_PATH.read_text(encoding="utf-8").strip()
    if not text:
        print("원고 내용이 비어 있어 발송을 건너뜁니다.")
        return

    lines = text.split("\n")
    subject = lines[0].strip()
    body = text

    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not gmail_app_password:
        print("GMAIL_ADDRESS/GMAIL_APP_PASSWORD가 설정되지 않아 발송을 건너뜁니다.")
        return

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = f"[물가나우 네이버 원고] {subject}"
    msg["From"] = gmail_address
    msg["To"] = RECIPIENT

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, [RECIPIENT], msg.as_string())
    print(f"발송 완료: {RECIPIENT}")


if __name__ == "__main__":
    sys.exit(main())
