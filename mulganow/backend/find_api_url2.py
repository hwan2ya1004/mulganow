import requests
import re

# 개발가이드 JS 파일에서 API URL 찾기
js_url = 'http://openapi.price.go.kr/openApi/js/iros/pubr/rqs/RQDevGuideList.js'
r = requests.get(js_url, timeout=10)
print('JS STATUS:', r.status_code)
print(r.text[:3000])

print('\n\n=== 개발가이드 페이지 전체에서 API 경로 찾기 ===')
r2 = requests.get('http://openapi.price.go.kr/openApi/pubr/cmm/CMPubrHome/viewRQDevGuideList.do', timeout=10)
# 모든 .do 경로 찾기
dos = re.findall(r'["\']([^"\']*\.do[^"\']*)["\']', r2.text)
for d in set(dos):
    if 'ProductPrice' in d or 'product' in d.lower() or 'price' in d.lower() or 'Svc' in d:
        print(d)

print('\n=== 개발가이드 페이지 본문 내용 ===')
# 본문 텍스트만 추출
text = re.sub(r'<[^>]+>', '', r2.text)
lines = [l.strip() for l in text.split('\n') if l.strip()]
for line in lines[:50]:
    print(line)
