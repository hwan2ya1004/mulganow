import sys
import os

# mulganow/backend 폴더를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mulganow', 'backend'))

from app import app

# Vercel Serverless Function 진입점
# Vercel은 'app' 변수를 WSGI 앱으로 자동 인식합니다.
