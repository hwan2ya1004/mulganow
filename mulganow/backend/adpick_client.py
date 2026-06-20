# -*- coding: utf-8 -*-
"""
adpick_client.py
----------------
애드픽(Adpick) API 헬퍼 모듈.

애드픽 API 가이드: https://biz.adpick.co.kr/api
Base URL: https://biz.adpick.co.kr/api/{apikey}/{function}?{params}

현재 구현:
  - get_commission_link(): 상품 URL → 커미션 추적 링크 변환 (linkonly=true)
  - search_products(): 키워드로 여러 제휴몰 상품 검색 (커미션 링크 포함)
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error

# 애드픽 API Base URL
_BASE_URL = "https://biz.adpick.co.kr/api"

# 요청 타임아웃 (초)
_TIMEOUT = 5


class AdpickApiError(Exception):
    """애드픽 API 호출 실패 시 발생하는 예외."""
    pass


def get_commission_link(url: str, api_key: str | None = None, p_data: str = "") -> str:
    """
    제휴몰 상품 URL을 애드픽 커미션 추적 링크로 변환합니다.

    Args:
        url:     변환할 상품 URL (제휴몰 상품 상세페이지)
        api_key: 애드픽 API 키. None이면 환경변수 ADPICK_API_KEY 사용.
        p_data:  자체 전환 성과 추적용 구분 코드 (선택, 최대 50자)

    Returns:
        커미션 링크 URL 문자열.
        API 호출 실패 또는 키 미설정 시 원본 url을 그대로 반환합니다.

    Raises:
        AdpickApiError: API 응답이 success=false인 경우 (단, 호출부에서 처리 권장)
    """
    key = api_key or os.environ.get("ADPICK_API_KEY", "")
    if not key:
        # API 키 미설정 → 원본 링크 반환 (graceful fallback)
        return url

    # 파라미터 구성
    params = {"url": url, "linkonly": "true"}
    if p_data:
        params["p_data"] = p_data[:50]  # 최대 50자 제한

    query_string = urllib.parse.urlencode(params)
    api_url = f"{_BASE_URL}/{urllib.parse.quote(key, safe='')}/link?{query_string}"

    try:
        req = urllib.request.Request(api_url, method="GET")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except urllib.error.HTTPError as e:
        # HTTP 오류 (401, 403, 404 등) → 원본 링크 반환
        return url
    except Exception:
        # 네트워크 오류, 타임아웃 등 → 원본 링크 반환
        return url

    # 응답 파싱
    # 성공 응답 구조: {"success": true, "data": {"status": "success", "commissionlink": "..."}}
    if not data.get("success"):
        return url

    commission_link = (
        data.get("data", {}).get("commissionlink")
        or data.get("commissionlink")  # 구버전 응답 호환
        or ""
    )

    return commission_link if commission_link else url


def search_products(keyword: str, limit: int = 10, api_key: str | None = None, p_data: str = "") -> list[dict]:
    """
    키워드로 여러 제휴몰의 상품을 검색합니다.
    검색 결과에 커미션 링크가 포함되어 있어 별도 변환이 필요 없습니다.

    Args:
        keyword: 검색 키워드 (UTF-8)
        limit:   검색 결과 개수 (1~20, 기본값 10)
        api_key: 애드픽 API 키. None이면 환경변수 ADPICK_API_KEY 사용.
        p_data:  자체 전환 성과 추적용 구분 코드 (선택, 최대 50자)

    Returns:
        상품 딕셔너리 리스트. 각 항목:
          - title (str): 상품명
          - price (int|None): 판매가 (원)
          - image (str): 상품 이미지 URL
          - mall (str): 쇼핑몰명
          - link (str): 커미션 추적 링크
        API 호출 실패 또는 키 미설정 시 빈 리스트 반환.
    """
    key = api_key or os.environ.get("ADPICK_API_KEY", "")
    if not key:
        return []

    limit = max(1, min(20, limit))  # 1~20 범위 제한

    params: dict = {"q": keyword, "limit": limit}
    if p_data:
        params["p_data"] = p_data[:50]

    query_string = urllib.parse.urlencode(params)
    api_url = f"{_BASE_URL}/{urllib.parse.quote(key, safe='')}/search?{query_string}"

    try:
        req = urllib.request.Request(api_url, method="GET")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except urllib.error.HTTPError:
        return []
    except Exception:
        return []

    if not data.get("success"):
        return []

    raw_items = data.get("data", [])
    if not isinstance(raw_items, list):
        # 단일 객체인 경우 리스트로 감싸기
        raw_items = [raw_items] if isinstance(raw_items, dict) else []

    result = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue

        # 가격 파싱 (문자열 "12,000" → 정수 12000)
        price_raw = it.get("price_sale") or it.get("price") or it.get("price_org") or ""
        try:
            price_int = int(str(price_raw).replace(",", "").strip())
        except (ValueError, TypeError):
            price_int = None

        # 1,000원 미만 비정상 가격 제외
        if price_int is not None and price_int < 1000:
            continue

        result.append({
            "title": it.get("product_name") or it.get("title") or "",
            "price": price_int,
            "image": it.get("photo") or it.get("image") or "",
            "mall":  it.get("cp_name") or it.get("mall") or "",
            "link":  it.get("commissionlink") or it.get("buyurl") or it.get("link") or "",
        })

    return result


def convert_links_bulk(urls: list[str], api_key: str | None = None, p_data: str = "") -> list[str]:
    """
    여러 상품 URL을 순차적으로 커미션 링크로 변환합니다.

    Args:
        urls:    변환할 URL 목록
        api_key: 애드픽 API 키. None이면 환경변수 ADPICK_API_KEY 사용.
        p_data:  자체 전환 성과 추적용 구분 코드 (선택)

    Returns:
        변환된 커미션 링크 목록. 변환 실패한 항목은 원본 URL 유지.
    """
    key = api_key or os.environ.get("ADPICK_API_KEY", "")
    if not key:
        return urls  # API 키 없으면 전체 원본 반환

    return [get_commission_link(url, api_key=key, p_data=p_data) for url in urls]
