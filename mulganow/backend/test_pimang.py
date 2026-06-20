# -*- coding: utf-8 -*-
"""
피망 검색 필터링 결과 테스트 (가격 필터 포함)
app.py의 shop_prices 로직을 시뮬레이션합니다.
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
import adpick_client

key = os.environ.get('ADPICK_API_KEY', '')

# KAMIS 피망 오늘 가격 (소매가 기준, 100g 단위)
KAMIS_PRICE = 1567

items = adpick_client.search_products('피망', limit=20, api_key=key)

# ── 필터 정의 ─────────────────────────────────────────────
PIMANG_EXCLUDE = [
    "모형", "인조", "장식", "장난감", "피규어", "미니어처",
    "그림책", "동화책", "스티커", "색칠", "교구", "학습",
    "케이스", "커버", "파우치", "스마트폰", "휴대폰", "아이폰",
    "도어쿠션", "쿠션커버", "인테리어",
    "지지대", "지지끈", "원예", "정원", "식물지지",
    "스프레드", "잼", "소스", "드레싱",
    "시뮬레이션", "가짜", "조화",
]
OVERSEAS_TITLE_KW = ["[해외]", "해외직구", "알리익스프레스", "aliexpress", "알리"]
OVERSEAS_MALL_KW  = ["알리익스프레스", "aliexpress", "알리", "taobao", "타오바오",
                     "아마존", "amazon", "ebay", "이베이", "위시", "wish",
                     "큐텐", "qoo10", "지마켓글로벌"]
AFFILIATE_MALLS = {
    "11번가", "SSG", "컬리", "GS SHOP", "Hmall", "CJ THE MARKET", "롯데홈쇼핑",
    "SSG.COM", "마켓컬리", "GS샵", "이마트몰", "이마트",
    "H몰", "현대홈쇼핑", "CJ더마켓", "CJ온마트", "롯데ON",
}

def is_affiliate(mall):
    if not mall: return False
    for a in AFFILIATE_MALLS:
        if a.lower() in mall.lower() or mall.lower() in a.lower():
            return True
    return False

# ── 단계별 필터 적용 ──────────────────────────────────────
s1 = [it for it in items if "피망" in (it.get("title") or "")]
s2 = [it for it in s1 if not any(kw in (it.get("title") or "") for kw in PIMANG_EXCLUDE)]
s3 = [it for it in s2
      if not any(kw in (it.get("title") or "") for kw in OVERSEAS_TITLE_KW)
      and not any(kw.lower() in (it.get("mall") or "").lower() for kw in OVERSEAS_MALL_KW)]
s4 = [it for it in s3 if is_affiliate(it.get("mall", ""))]

# 가격 필터: 0.1배 ~ 30배
price_min = KAMIS_PRICE * 0.1
price_max = KAMIS_PRICE * 30.0
s5 = [it for it in s4
      if it.get("price") is None or (price_min <= it["price"] <= price_max)]
if len(s5) < 2:
    s5 = s4  # fallback

s5.sort(key=lambda x: x["price"] if x["price"] is not None else 999999999)
final = s5[:5]

print(f"KAMIS 피망 가격: {KAMIS_PRICE:,}원/100g")
print(f"가격 허용 범위: {price_min:,.0f}원 ~ {price_max:,.0f}원")
print(f"\n원본 {len(items)}개 → 피망포함 {len(s1)}개 → 제외키워드 {len(s2)}개 → 해외제외 {len(s3)}개 → 제휴몰 {len(s4)}개 → 가격필터 {len(s5)}개")
print(f"\n✅ 최종 피망 검색 결과 (상위 {len(final)}개):")
for i, it in enumerate(final):
    print(f"  [{i+1}] {it['mall']:15} {it['price']:>8,}원  {it['title'][:60]}")
