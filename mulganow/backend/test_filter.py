import os
from dotenv import load_dotenv
load_dotenv()
import adpick_client

key = os.environ.get('ADPICK_API_KEY', '')

for kw in ['포기배추', '알배추', '배추 채소', '생배추']:
    items = adpick_client.search_products(kw, limit=10, api_key=key)
    print(f"\n=== '{kw}' 검색 결과 ({len(items)}개) ===")
    for it in items:
        print(f"  mall={it['mall']!r:20} title={it['title'][:60]!r}")
