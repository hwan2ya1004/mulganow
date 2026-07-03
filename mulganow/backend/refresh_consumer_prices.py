# -*- coding: utf-8 -*-
"""
refresh_consumer_prices.py
---------------------------
한국소비자원 생필품 가격을 미리 조회해서 data/consumer_prices_snapshot.json에 저장합니다.

Vercel 같은 서버리스 환경에서는 요청이 들어올 때마다 604개 상품의 가격을
백그라운드 스레드로 실시간 조회하는 방식이 근본적으로 불안정합니다
(응답을 보내는 순간 프로세스가 멈추거나 다음 요청이 새 컨테이너로 뜨기 때문에
스레드가 끝까지 실행될 기회를 못 얻음). 대신 이 스크립트를 GitHub Actions로
주기적으로 실행해 결과를 저장소에 커밋하고, app.py는 그 스냅샷을 즉시 읽어서
서빙합니다.

가격 조회 API(getProductPriceInfoSvc.do)는 간헐적으로 인증 오류(오류코드 90)를
반환하는 경우가 있어(공공데이터포털 게이트웨이 이슈로 추정), 한 번 실패해도
전체를 몇 차례 재시도합니다.

실행: python refresh_consumer_prices.py
필요 환경변수: CONSUMER_PRICE_SERVICE_KEY
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import consumer_price_client as cpc

SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "consumer_prices_snapshot.json")
MAX_ATTEMPTS = 3


def main():
    items = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = cpc.get_products_with_prices()
        except cpc.ConsumerPriceApiError as e:
            print(f"[attempt {attempt}/{MAX_ATTEMPTS}] 실패: {e}")
            continue

        priced = sum(1 for it in result if it.get("price") is not None)
        print(f"[attempt {attempt}/{MAX_ATTEMPTS}] 상품 {len(result)}개 중 가격 {priced}개 확보")

        if priced > 0:
            items = result
            break

    if items is None:
        print("가격을 하나도 확보하지 못했습니다. 기존 스냅샷을 유지하고 종료합니다.")
        sys.exit(1)

    os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False)

    print(f"스냅샷 저장 완료: {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
