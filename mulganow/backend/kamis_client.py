# -*- coding: utf-8 -*-
"""
kamis_client.py
----------------
KAMIS(농산물유통정보) Open API를 호출하는 클라이언트 모듈입니다.

공식 문서: https://www.kamis.or.kr/customer/reference/openapi_list.do
API 키 발급: https://www.kamis.or.kr/customer/reference/openapi_write.do

주의:
- KAMIS Open API는 공식 문서를 직접 확인하며 파라미터를 검증하는 것을 권장합니다.
  (운영기관 정책에 따라 파라미터명/응답 포맷이 변경될 수 있습니다.)
- 이 모듈은 가장 널리 쓰이는 2개의 액션을 사용합니다.
  1) dailySalesList        : 최근일자 전체 품목 도/소매가격 (당일/1일전/1개월전/1년전 포함)
  2) periodProductList     : 특정 품목의 기간별 가격 추이
"""

import os
import requests
from datetime import date, timedelta

BASE_URL = "http://www.kamis.or.kr/service/price/xml.do"

# .env 또는 환경변수에서 인증정보를 읽어옵니다.
CERT_KEY = os.environ.get("KAMIS_CERT_KEY", "")
CERT_ID = os.environ.get("KAMIS_CERT_ID", "")


class KamisApiError(Exception):
    """KAMIS API 호출/응답 관련 오류"""
    pass


def _check_credentials():
    if not CERT_KEY or not CERT_ID:
        raise KamisApiError(
            "KAMIS_CERT_KEY / KAMIS_CERT_ID 환경변수가 설정되지 않았습니다. "
            ".env 파일을 확인해주세요."
        )


def get_daily_sales(product_cls_code: str = "02"):
    """
    최근일자 도·소매가격정보 전체 품목 조회.

    Args:
        product_cls_code: '01'=소매, '02'=도매

    Returns:
        dict: KAMIS 원본 응답을 파싱한 딕셔너리
    """
    _check_credentials()
    params = {
        "action": "dailySalesList",
        "p_product_cls_code": product_cls_code,
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
    }
    return _request(params)


def get_period_trend(
    item_category_code: str,
    item_code: str,
    kind_code: str = "00",
    product_rank_code: str = "04",
    start_day: str = None,
    end_day: str = None,
    product_cls_code: str = "02",
    convert_kg_yn: str = "N",
):
    """
    특정 품목의 기간별(도/소매) 가격 추이 조회.

    Args:
        item_category_code: 품목 분류 코드 (예: '200'=채소류)
        item_code: 품목 코드 (예: '212'=고추 등 KAMIS 코드표 참고)
        kind_code: 품종 코드 (기본 '00' = 전체/대표)
        product_rank_code: 등급 코드 (기본 '04' = 상품 등급, 품목별로 다를 수 있음)
        start_day, end_day: 'YYYY-MM-DD' 형식. 미입력 시 최근 30일
        product_cls_code: '01'=소매, '02'=도매
        convert_kg_yn: kg 단위 환산 여부 ('Y'/'N')

    Returns:
        dict: KAMIS 원본 응답을 파싱한 딕셔너리
    """
    _check_credentials()
    if not end_day:
        end_day = date.today().isoformat()
    if not start_day:
        start_day = (date.today() - timedelta(days=30)).isoformat()

    params = {
        "action": "periodProductList",
        "p_productclscode": product_cls_code,
        "p_startday": start_day,
        "p_endday": end_day,
        "p_itemcategorycode": item_category_code,
        "p_itemcode": item_code,
        "p_kindcode": kind_code,
        "p_productrankcode": product_rank_code,
        "p_convert_kg_yn": convert_kg_yn,
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
    }
    return _request(params)


def _request(params: dict):
    try:
        resp = requests.get(BASE_URL, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise KamisApiError(f"KAMIS API 호출 실패: {e}")

    try:
        data = resp.json()
    except ValueError:
        # KAMIS가 에러 시 XML이나 평문을 줄 수 있음
        raise KamisApiError(f"응답을 JSON으로 해석할 수 없습니다. 원본: {resp.text[:300]}")

    return data
