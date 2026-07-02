"""상품 목록 API 확인 및 실제 가격 API URL 탐색"""
import requests, os
from dotenv import load_dotenv

load_dotenv()
key = os.environ.get('CONSUMER_PRICE_SERVICE_KEY', '')

base = 'http://openapi.price.go.kr/openApiImpl/ProductPriceInfoService'

# 1) 상품 목록 API (이미 작동 확인됨)
print('=== 상품 목록 API ===')
r = requests.get(f'{base}/getProductInfoSvc.do',
                 params={'serviceKey': key, 'numOfRows': '3', 'pageNo': '1'},
                 timeout=10)
print(f'STATUS: {r.status_code}')
print(r.text[:300])

# 2) 서비스 목록 확인 (WSDL)
print('\n=== WSDL 확인 ===')
r2 = requests.get(f'{base}?wsdl', timeout=10)
print(f'STATUS: {r2.status_code}')
print(r2.text[:500])

# 3) 서비스 루트 확인
print('\n=== 서비스 루트 ===')
r3 = requests.get('http://openapi.price.go.kr/openApiImpl/ProductPriceInfoService', timeout=10)
print(f'STATUS: {r3.status_code}')
print(r3.text[:500])
