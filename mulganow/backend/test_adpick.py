# -*- coding: utf-8 -*-
"""
test_adpick.py
--------------
애드픽 API 테스트 스크립트.
각 제휴몰의 실제 상품 URL로 커미션 링크 변환을 테스트합니다.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error

# .env 파일 로드
def load_env(env_path=".env"):
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

script_dir = os.path.dirname(os.path.abspath(__file__))
load_env(os.path.join(script_dir, ".env"))

API_KEY = os.environ.get("ADPICK_API_KEY", "")
BASE_URL = "https://biz.adpick.co.kr/api"

print("=" * 70)
print("  애드픽(Adpick) API 제휴몰 테스트")
print("=" * 70)
print(f"  API KEY: {API_KEY[:6]}...{API_KEY[-4:]}")
print()

# 테스트할 제휴몰 상품 URL 목록
# 각 쇼핑몰의 실제 인기 상품 URL 사용
TEST_CASES = [
    {
        "name": "11번가",
        "commission": "~2.1%",
        "url": "https://www.11st.co.kr/products/5994749064",
    },
    {
        "name": "SSG",
        "commission": "1.6%",
        "url": "https://www.ssg.com/item/itemView.ssg?itemId=1000587806750",
    },
    {
        "name": "컬리",
        "commission": "2.1%",
        "url": "https://www.kurly.com/goods/1000374293",
    },
    {
        "name": "이마트몰",
        "commission": "1.6%",
        "url": "https://emart.ssg.com/item/itemView.ssg?itemId=1000543741752",
    },
    {
        "name": "GS SHOP",
        "commission": "1.28%",
        "url": "https://www.gsshop.com/shop/item/item.gs?itemId=1530282",
    },
    {
        "name": "Hmall",
        "commission": "1.15%",
        "url": "https://www.hmall.com/p/prdDetail.do?prdNo=1000000000",
    },
    {
        "name": "CJ THE MARKET",
        "commission": "1.6%",
        "url": "https://www.cjthemarket.com/pc/prod/detail?prdId=10000001",
    },
]

results = []

def test_adpick(name, commission, url):
    """애드픽 API로 커미션 링크 변환 테스트"""
    print(f"[{name}] 커미션율: {commission}")
    print(f"  입력 URL: {url}")

    params = {"url": url, "linkonly": "true"}
    query_string = urllib.parse.urlencode(params)
    api_url = f"{BASE_URL}/{urllib.parse.quote(API_KEY, safe='')}/link?{query_string}"

    try:
        req = urllib.request.Request(api_url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)

        if data.get("success"):
            commission_link = (
                data.get("data", {}).get("commissionlink")
                or data.get("commissionlink")
                or ""
            )
            if commission_link:
                print(f"  ✅ 성공! 커미션 링크: {commission_link}")
                results.append({"name": name, "status": "✅ 성공", "link": commission_link})
            else:
                print(f"  ⚠️  success=true 이지만 링크 없음")
                results.append({"name": name, "status": "⚠️ 링크없음", "link": ""})
        else:
            print(f"  ❌ 실패: success=false")
            results.append({"name": name, "status": "❌ 실패", "link": ""})

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            err_data = json.loads(body)
            err_msg = err_data.get("error", body[:100])
        except Exception:
            err_msg = body[:100]
        print(f"  ❌ HTTP {e.code}: {err_msg}")
        results.append({"name": name, "status": f"❌ HTTP {e.code}", "link": err_msg})

    except Exception as e:
        print(f"  ❌ 오류: {type(e).__name__}: {e}")
        results.append({"name": name, "status": f"❌ 오류", "link": str(e)})

    print()


# 테스트 실행
for case in TEST_CASES:
    test_adpick(case["name"], case["commission"], case["url"])

# 결과 요약
print("=" * 70)
print("  테스트 결과 요약")
print("=" * 70)
for r in results:
    if "성공" in r["status"]:
        print(f"  {r['status']}  {r['name']:15s}  → {r['link']}")
    else:
        print(f"  {r['status']}  {r['name']:15s}  ({r['link'][:60]})")

success_count = sum(1 for r in results if "성공" in r["status"])
print()
print(f"  총 {len(results)}개 중 {success_count}개 성공")
print("=" * 70)
