import requests
import re

r = requests.get('http://openapi.price.go.kr/openApi/pubr/cmm/CMPubrHome/viewRQDevGuideList.do', timeout=10)
text = r.text

# href 링크 찾기
links = re.findall(r'href=["\']([^"\']+)["\']', text)
print('=== 링크 목록 ===')
for l in links[:40]:
    print(l)

print('\n=== Svc/Service 포함 텍스트 ===')
for line in text.split('\n'):
    if 'Svc' in line or 'Service' in line or 'openApiImpl' in line or 'openApi/' in line:
        print(line.strip()[:200])
