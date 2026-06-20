# -*- coding: utf-8 -*-
"""서버 API 직접 호출 테스트 - 피망/청"""
import urllib.request, json

# 슬래시를 %2F로 인코딩하지 않고 직접 포함 (서버가 q=피망/청 형태로 받아야 함)
url = "http://localhost:5000/api/shop-prices?q=%ED%94%BC%EB%A7%9D/%EC%B2%AD&price=1567"
print(f"요청 URL: {url}\n")

try:
    resp = urllib.request.urlopen(url, timeout=15)
    data = json.loads(resp.read())
    print(f"ok={data['ok']}  count={data['count']}")
    for i, it in enumerate(data.get('items', [])):
        print(f"  [{i+1}] {it['mall']:15} {it['price']:>8,}원  {it['title'][:65]}")
except Exception as e:
    print(f"오류: {e}")
