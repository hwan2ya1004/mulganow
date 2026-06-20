# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# .env 로드
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

import adpick_client

print('=== adpick_client.search_products() 테스트 ===')
items = adpick_client.search_products('쌀', limit=5)
print(f'결과 {len(items)}개:')
for i, it in enumerate(items):
    print(f'  [{i+1}] {it["title"][:40]}')
    print(f'       가격: {it["price"]}원 | 쇼핑몰: {it["mall"]} | 링크: {it["link"][:50]}')
