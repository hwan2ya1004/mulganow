"""3일마다 도는 '물가나우 마스터 세션' 정기 점검 보고를 메일로 발송합니다.

로컬 PC를 켜지 않아도 보고를 받을 수 있도록, 마스터 세션이
mulganow/backend/standup_reports/latest.md 를 커밋·푸시하면
GitHub Actions(send-standup-report.yml)가 이 스크립트를 실행해 메일을 보냅니다.
GMAIL_ADDRESS / GMAIL_APP_PASSWORD는 generate_blog_post.py와 동일한
GitHub Actions 시크릿을 재사용합니다(새 비밀번호를 따로 저장하지 않음).
"""
import os
import smtplib
import sys
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from pathlib import Path

RECIPIENT = "seohilab@naver.com"
REPORT_PATH = Path(__file__).parent / "standup_reports" / "latest.md"


def main():
    if not REPORT_PATH.exists():
        print(f"{REPORT_PATH} 가 없어 발송을 건너뜁니다.")
        return

    body = REPORT_PATH.read_text(encoding="utf-8").strip()
    if not body:
        print("보고 내용이 비어 있어 발송을 건너뜁니다.")
        return

    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime("%Y-%m-%d")
    subject = f"[물가나우 정기점검] {today} 마스터 세션 보고"

    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not gmail_app_password:
        print("GMAIL_ADDRESS/GMAIL_APP_PASSWORD가 설정되지 않아 발송을 건너뜁니다.")
        return

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = RECIPIENT

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, [RECIPIENT], msg.as_string())
    print(f"발송 완료: {RECIPIENT}")


if __name__ == "__main__":
    sys.exit(main())
