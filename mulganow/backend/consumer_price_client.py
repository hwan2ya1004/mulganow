# -*- coding: utf-8 -*-
"""
consumer_price_client.py
-------------------------
한국소비자원 생필품 가격 정보 Open API 클라이언트 모듈.

공공데이터포털 API:
  1) getProductInfoSvc.do    : 전체 생필품 목록 조회 (상품명, 소분류, 단위 등)
  2) getProductPriceInfoSvc.do : 특정 날짜의 상품 가격 조회 (매주 금요일 기준)

API 키 발급: https://www.data.go.kr/data/3043385/openapi.do
환경변수: CONSUMER_PRICE_SERVICE_KEY
"""

import os
import requests
import xml.etree.ElementTree as ET
from datetime import date, timedelta

BASE_URL = "http://openapi.price.go.kr/openApiImpl/ProductPriceInfoService"
PRODUCT_INFO_URL  = f"{BASE_URL}/getProductInfoSvc.do"
PRODUCT_PRICE_URL = f"{BASE_URL}/getProductPriceInfoSvc.do"

# .env 또는 환경변수에서 서비스키를 읽어옵니다.
# 함수 호출 시점에 읽도록 _get_service_key()를 사용합니다.
SERVICE_KEY = os.environ.get("CONSUMER_PRICE_SERVICE_KEY", "")


def _get_service_key() -> str:
    """환경변수에서 서비스키를 읽어옵니다 (호출 시점에 반영)."""
    return os.environ.get("CONSUMER_PRICE_SERVICE_KEY", "") or SERVICE_KEY


class ConsumerPriceApiError(Exception):
    """한국소비자원 생필품 가격 API 호출/응답 관련 오류"""
    pass


def _check_credentials():
    key = _get_service_key()
    if not key:
        raise ConsumerPriceApiError(
            "CONSUMER_PRICE_SERVICE_KEY 환경변수가 설정되지 않았습니다. "
            ".env 파일을 확인해주세요."
        )


def get_latest_friday() -> str:
    """
    가장 최근 금요일 날짜를 'YYYYMMDD' 형식으로 반환합니다.
    오늘이 금요일이면 오늘 날짜를 반환합니다.
    """
    today = date.today()
    # weekday(): 월=0, 화=1, 수=2, 목=3, 금=4, 토=5, 일=6
    days_since_friday = (today.weekday() - 4) % 7
    last_friday = today - timedelta(days=days_since_friday)
    return last_friday.strftime("%Y%m%d")


def _parse_xml(text: str) -> list[dict]:
    """
    API XML 응답을 파싱하여 item 딕셔너리 리스트로 반환합니다.

    ※ 한국소비자원 가격 API는 두 가지 XML 구조를 사용합니다:
       1) 상품 목록: <result><item>...</item></result>
       2) 가격 정보: <result><iros.openapi.service.vo.goodPriceVO>...</iros...></result>
          → 태그명에 점(.)이 포함되어 있어 iter("item")으로 찾을 수 없음
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ConsumerPriceApiError(f"XML 파싱 실패: {e}\n원본: {text[:300]}")

    # resultCode 확인 (오류 응답 처리) - 태그명이 대소문자 혼용될 수 있음
    # 주의: XML Element는 자식이 없으면 bool() == False이므로 'is not None' 사용
    result_code_el = root.find(".//resultCode")
    if result_code_el is None:
        result_code_el = root.find(".//resultcode")
    result_msg_el = root.find(".//resultMsg")
    if result_msg_el is None:
        result_msg_el = root.find(".//resultmsg")
    if result_code_el is not None:
        code = (result_code_el.text or "").strip()
        msg  = (result_msg_el.text or "").strip() if result_msg_el is not None else ""
        if code not in ("00", "0", "ok", "OK"):
            # 오류코드별 한국어 메시지
            CODE_MSG = {
                "90": "API 인증키가 아직 활성화되지 않았습니다. 공공데이터포털에서 신청 직후에는 서버 동기화에 최대 1일이 소요됩니다. 잠시 후 다시 시도해주세요. (오류코드: 90)",
                "99": "API 서비스가 일시적으로 사용 불가 상태입니다.",
                "30": "등록되지 않은 서비스키입니다.",
                "31": "기간이 만료된 서비스키입니다.",
                "32": "일일 트래픽 한도를 초과했습니다.",
            }
            friendly = CODE_MSG.get(code, f"API 오류 (코드: {code}, 메시지: {msg})")
            raise ConsumerPriceApiError(friendly)

    items = []

    # <result> 요소 찾기
    result_el = root.find(".//result")
    if result_el is None:
        return items

    # result 하위의 모든 직접 자식 요소를 순회
    # - 상품 목록: <item> 태그
    # - 가격 정보: <iros.openapi.service.vo.goodPriceVO> 태그 (점 포함)
    for child_el in result_el:
        # 자식 요소가 실제 데이터 레코드인지 확인 (하위 자식이 있어야 함)
        if len(child_el) == 0:
            continue
        item = {}
        for field in child_el:
            item[field.tag] = (field.text or "").strip()
        if item:
            items.append(item)

    # fallback: result 직접 자식에서 못 찾으면 <item> 태그로 재시도
    if not items:
        for item_el in root.iter("item"):
            item = {}
            for child in item_el:
                item[child.tag] = (child.text or "").strip()
            if item:
                items.append(item)

    return items


def _request_xml(url: str, params: dict, retries: int = 2, timeout: int = 30) -> list[dict]:
    """
    GET 요청 후 XML 응답을 파싱하여 item 리스트를 반환합니다.
    타임아웃 시 최대 retries회 재시도합니다.
    """
    import logging, time as _t
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            # 응답이 비어있는 경우
            if not resp.text or not resp.text.strip():
                raise ConsumerPriceApiError("API 응답이 비어있습니다.")
            return _parse_xml(resp.text)
        except requests.exceptions.Timeout as e:
            last_err = e
            logging.warning("[consumer_price] 타임아웃 (시도 %d/%d): %s", attempt+1, retries, url)
            if attempt < retries - 1:
                _t.sleep(1)  # 1초 대기 후 재시도
            continue
        except requests.RequestException as e:
            raise ConsumerPriceApiError(f"API 호출 실패: {e}")
    raise ConsumerPriceApiError(f"API 호출 실패 ({retries}회 재시도): {last_err}")


def get_all_products(good_id: str = None) -> list[dict]:
    """
    전체 생필품 목록을 조회합니다.

    Args:
        good_id (str, optional): 특정 상품 아이디. 미입력 시 전체 조회.

    Returns:
        list[dict]: 상품 정보 딕셔너리 리스트
          - goodId          : 상품 아이디
          - goodName        : 상품명
          - goodSmlclsCode  : 소분류 코드
          - goodUnitDivCode : 단위 구분 코드 (G, ML, EA 등)
          - goodBaseCnt     : 단위 량
          - goodTotalCnt    : 용량
          - goodTotalDivCode: 용량 구분 코드
          - detailMean      : 상품 상세 설명
          - productEntpCode : 제조업체 코드
    """
    _check_credentials()

    params = {"ServiceKey": _get_service_key()}
    if good_id:
        params["goodId"] = good_id

    return _request_xml(PRODUCT_INFO_URL, params)




def get_product_prices(
    inspect_day: str = None,
    good_id: str = None,
    entp_id: str = None,
) -> list[dict]:
    """
    특정 날짜의 생필품 가격 정보를 조회합니다.

    ※ 주의: 이 API는 goodId 또는 entpId 중 하나가 반드시 필요합니다.
       전체 조회는 지원하지 않습니다.

    Args:
        inspect_day (str): 조사일 'YYYYMMDD' (매주 금요일). 미입력 시 가장 최근 금요일.
        good_id (str, optional): 특정 상품 아이디. 미입력 시 전체.
        entp_id (str, optional): 특정 업체 아이디. 미입력 시 전체.

    Returns:
        list[dict]: 가격 정보 딕셔너리 리스트
          - goodId         : 상품 아이디
          - entpId         : 업체 아이디
          - goodInspectDay : 조사일
          - goodPrice      : 상품 가격
          - plusoneYn      : 1+1 여부
          - goodDcYn       : 할인 여부
          - inputDttm      : 입력 일시
    """
    _check_credentials()

    if not inspect_day:
        inspect_day = get_latest_friday()

    if not good_id and not entp_id:
        raise ConsumerPriceApiError(
            "가격 조회 API는 goodId 또는 entpId 중 하나가 반드시 필요합니다."
        )

    params = {
        "ServiceKey": _get_service_key(),
        "goodInspectDay": inspect_day,
    }
    if good_id:
        params["goodId"] = good_id
    if entp_id:
        params["entpId"] = entp_id

    # 가격 API는 타임아웃을 짧게 설정 (인증 오류 시 빠른 실패)
    return _request_xml(PRODUCT_PRICE_URL, params, retries=1, timeout=8)


def get_products_with_prices(inspect_day: str = None) -> list[dict]:
    """
    전체 생필품 목록과 최근 가격 정보를 합산하여 반환합니다.

    ※ 가격 API는 goodId 또는 entpId가 필수이므로, 상품별로 개별 조회합니다.
       API 호출 횟수를 줄이기 위해 goodId 목록을 배치로 처리합니다.

    Args:
        inspect_day (str, optional): 조사일 'YYYYMMDD'. 미입력 시 가장 최근 금요일.
                                     데이터가 없으면 최대 4주 전까지 소급합니다.

    Returns:
        list[dict]: 상품 + 가격 합산 딕셔너리 리스트
    """
    import logging
    import time

    if not inspect_day:
        inspect_day = get_latest_friday()

    # 1) 전체 상품 목록 조회
    products = get_all_products()

    # ── 대소문자 무관 딕셔너리 접근 헬퍼 ──────────────────────────────────
    def _get(d: dict, *keys: str, default="") -> str:
        for k in keys:
            v = d.get(k) or d.get(k.lower()) or d.get(k.upper())
            if v is not None:
                return v
        return default

    # 2) goodId 목록 추출
    good_ids = [_get(p, "goodId", "goodid") for p in products]
    good_ids = [gid for gid in good_ids if gid]

    # 3) goodId별 가격 조회 (배치 처리, 최대 4주 소급)
    #    API 제한을 고려해 일부 상품만 샘플링하여 데이터 존재 여부 먼저 확인
    price_map: dict[str, dict] = {}
    actual_inspect_day = inspect_day

    # 데이터가 있는 날짜 탐색
    # API는 매주 금요일 기준이지만 실제로는 목~금요일에 데이터가 올라옴
    # 최근 8주 × 목/금 = 16개 날짜를 탐색
    from datetime import datetime
    candidate_days = []
    base = datetime.strptime(inspect_day, "%Y%m%d")
    for weeks_back in range(8):  # 0~7주 전
        friday = base - timedelta(weeks=weeks_back)
        thursday = friday - timedelta(days=1)
        candidate_days.append(friday.strftime("%Y%m%d"))
        candidate_days.append(thursday.strftime("%Y%m%d"))

    found_day = None
    auth_error = False  # 인증 오류 발생 시 즉시 중단 플래그
    for day in candidate_days:
        # 첫 번째 goodId로 데이터 존재 여부 확인
        if not good_ids:
            break
        try:
            test_prices = get_product_prices(inspect_day=day, good_id=good_ids[0])
            if test_prices:
                found_day = day
                logging.info("[consumer_price] 가격 데이터 발견: %s", day)
                break
        except ConsumerPriceApiError as e:
            err_str = str(e)
            # 인증 오류(코드 90, 30, 31)는 날짜를 바꿔도 해결 안 되므로 즉시 중단
            if any(code in err_str for code in ["오류코드: 90", "오류코드: 30", "오류코드: 31",
                                                  "Invalid Authentication", "등록되지 않은", "기간이 만료"]):
                logging.warning("[consumer_price] 가격 API 인증 오류 - 날짜 탐색 중단: %s", err_str)
                auth_error = True
                break
            continue

    if found_day is None:
        if auth_error:
            logging.warning("[consumer_price] 가격 API 인증 오류로 가격 조회 불가. 상품 목록만 반환.")
        else:
            logging.warning("[consumer_price] 최근 %d주 내 가격 데이터 없음. 상품 목록만 반환.", len(candidate_days))
        found_day = inspect_day

    actual_inspect_day = found_day

    # 4) 전체 goodId에 대해 가격 조회 (병렬 처리로 속도 대폭 개선)
    #    인증 오류 또는 데이터 없음 시 건너뜀
    if not auth_error and found_day is not None and good_ids:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _fetch_one(gid: str):
            try:
                return gid, get_product_prices(inspect_day=actual_inspect_day, good_id=gid)
            except ConsumerPriceApiError as e:
                logging.debug("[consumer_price] goodId=%s 가격 조회 실패: %s", gid, e)
                return gid, []

        MAX_WORKERS = 20
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(_fetch_one, gid) for gid in good_ids]
            for fut in as_completed(futures):
                gid, prices = fut.result()
                for p in prices:
                    pid = _get(p, "goodId", "goodid")
                    if not pid:
                        pid = gid
                    existing = price_map.get(pid)
                    try:
                        new_price = int(_get(p, "goodPrice", "goodprice") or "0")
                    except (ValueError, TypeError):
                        new_price = 0
                    if existing is None:
                        price_map[pid] = p
                    else:
                        try:
                            existing_price = int(_get(existing, "goodPrice", "goodprice") or "0")
                        except (ValueError, TypeError):
                            existing_price = 0
                        if new_price > 0 and (existing_price == 0 or new_price < existing_price):
                            price_map[pid] = p
        logging.info("[consumer_price] 병렬 가격 조회 완료: %d개 상품 중 %d개 가격 확보",
                     len(good_ids), len(price_map))


    # 5) 상품 목록에 가격 정보 병합
    result = []
    for prod in products:
        gid = _get(prod, "goodId", "goodid")
        price_info = price_map.get(gid, {})

        try:
            price_val = int(_get(price_info, "goodPrice", "goodprice") or "0")
        except (ValueError, TypeError):
            price_val = None

        if price_val == 0:
            price_val = None

        merged = {
            "good_id":           gid,
            "good_name":         _get(prod, "goodName",        "goodname"),
            "smlcls_code":       _get(prod, "goodSmlclsCode",  "goodsmlclscode"),
            "unit_div_code":     _get(prod, "goodUnitDivCode", "goodunitdivcode"),
            "base_cnt":          _get(prod, "goodBaseCnt",     "goodbasecnt"),
            "total_cnt":         _get(prod, "goodTotalCnt",    "goodtotalcnt"),
            "total_div_code":    _get(prod, "goodTotalDivCode","goodtotaldivcode"),
            "detail_mean":       _get(prod, "detailMean",      "detailmean"),
            "product_entp_code": _get(prod, "productEntpCode", "productentpcode"),
            "inspect_day":       _get(price_info, "goodInspectDay", "goodinspectday") or actual_inspect_day,
            "price":             price_val,
            "entp_id":           _get(price_info, "entpId",    "entpid"),
            "plus_one_yn":       _get(price_info, "plusoneYn", "plusoneyn"),
            "dc_yn":             _get(price_info, "goodDcYn",  "gooddcyn"),
        }
        result.append(merged)

    return result
