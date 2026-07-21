# -*- coding: utf-8 -*-
"""
app.py
------
물가나우(MulgaNow) MVP 백엔드.

실행 방법:
    1) pip install -r requirements.txt
    2) .env 파일에 KAMIS_CERT_KEY, KAMIS_CERT_ID 입력
    3) python app.py
    4) 브라우저에서 http://localhost:5000 접속
"""

import os
import time
import threading
import tempfile
import urllib.request
import json as json_lib
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()  # .env 파일 로드 (KAMIS_CERT_KEY, KAMIS_CERT_ID)

import kamis_client            # noqa: E402  (load_dotenv 이후 import 해야 환경변수가 반영됨)
import adpick_client            # noqa: E402  (애드픽 커미션 링크 변환)
import consumer_price_client   # noqa: E402  (한국소비자원 생필품 가격 정보)


FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)


# ---------------------------------------------------------------------------
# 한국소비자원 생필품 가격 정보 - 인메모리 캐시 + 파일 캐시
# (가격 조회 API가 상품별 개별 호출이라 느리므로, 최초 1회 조회 후 캐싱하고
#  백그라운드 스레드(병렬 처리)로 갱신합니다. 파일 캐시를 두어 서버 재시작
#  시에도 이전에 조회한 가격 정보를 즉시 사용할 수 있게 합니다.)
# ---------------------------------------------------------------------------
_CONSUMER_CACHE_FILE = os.path.join(tempfile.gettempdir(), "consumer_price_cache.json")

# 저장소에 커밋되는 스냅샷 (GitHub Actions가 주기적으로 갱신 — refresh_consumer_prices.py 참고).
# Vercel처럼 요청마다 새 컨테이너가 뜰 수 있는 서버리스 환경에서는 /tmp 캐시가 비어있는
# 콜드 스타트가 흔하므로, 배포에 포함된 이 스냅샷을 안정적인 기본값으로 사용합니다.
_CONSUMER_SNAPSHOT_FILE = os.path.join(os.path.dirname(__file__), "data", "consumer_prices_snapshot.json")

_CONSUMER_CACHE = {
    "items": None,         # 가격 포함 전체 상품 리스트 (준비되면 채워짐)
    "basic_items": None,   # 가격 없이 상품 목록만 (빠른 최초 응답용)
    "ready": False,
    "loading": False,
    "lock": threading.Lock(),
}


def _load_consumer_cache_from_file():
    """서버 시작 시 캐시가 있으면 읽어서 인메모리 캐시에 채웁니다.

    우선순위: 1) /tmp 런타임 캐시(같은 프로세스가 이미 실시간 조회에 성공한 경우)
             2) 저장소에 커밋된 스냅샷(콜드 스타트에서도 항상 사용 가능한 기본값)
    """
    import logging
    try:
        if os.path.exists(_CONSUMER_CACHE_FILE):
            with open(_CONSUMER_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json_lib.load(f)
            items = data.get("items")
            if items:
                _CONSUMER_CACHE["items"] = items
                _CONSUMER_CACHE["ready"] = True
                logging.info("[consumer] 런타임 캐시에서 %d개 상품 로드 완료", len(items))
                return
    except Exception as e:  # noqa: BLE001
        logging.warning("[consumer] 런타임 캐시 로드 실패: %s", e)

    try:
        if os.path.exists(_CONSUMER_SNAPSHOT_FILE):
            with open(_CONSUMER_SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                data = json_lib.load(f)
            items = data.get("items")
            if items:
                _CONSUMER_CACHE["items"] = items
                _CONSUMER_CACHE["ready"] = True
                logging.info("[consumer] 커밋된 스냅샷에서 %d개 상품 로드 완료", len(items))
    except Exception as e:  # noqa: BLE001
        logging.warning("[consumer] 스냅샷 로드 실패: %s", e)


def _save_consumer_cache_to_file(items):
    """가격 조회 완료 후 파일 캐시에 저장합니다 (다음 서버 재시작 시 즉시 사용)."""
    import logging
    try:
        with open(_CONSUMER_CACHE_FILE, "w", encoding="utf-8") as f:
            json_lib.dump({"items": items}, f, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logging.warning("[consumer] 파일 캐시 저장 실패: %s", e)


# 서버 시작 시 파일 캐시 즉시 로드 (있으면 바로 가격 표시 가능)
_load_consumer_cache_from_file()



def _consumer_get(d: dict, *keys: str, default=""):
    """대소문자 무관 딕셔너리 접근 헬퍼."""
    for k in keys:
        v = d.get(k) or d.get(k.lower()) or d.get(k.upper())
        if v is not None:
            return v
    return default


def _get_consumer_basic_items():
    """가격 없이 상품 목록만 빠르게 조회 (캐시 적용)."""
    if _CONSUMER_CACHE["basic_items"] is not None:
        return _CONSUMER_CACHE["basic_items"]

    products = consumer_price_client.get_all_products()
    basic = []
    for p in products:
        basic.append({
            "good_id":           _consumer_get(p, "goodId", "goodid"),
            "good_name":         _consumer_get(p, "goodName", "goodname"),
            "smlcls_code":       _consumer_get(p, "goodSmlclsCode", "goodsmlclscode"),
            "unit_div_code":     _consumer_get(p, "goodUnitDivCode", "goodunitdivcode"),
            "base_cnt":          _consumer_get(p, "goodBaseCnt", "goodbasecnt"),
            "total_cnt":         _consumer_get(p, "goodTotalCnt", "goodtotalcnt"),
            "total_div_code":    _consumer_get(p, "goodTotalDivCode", "goodtotaldivcode"),
            "detail_mean":       _consumer_get(p, "detailMean", "detailmean"),
            "product_entp_code": _consumer_get(p, "productEntpCode", "productentpcode"),
            "price":             None,
            "inspect_day":       None,
        })
    _CONSUMER_CACHE["basic_items"] = basic
    return basic


def _load_consumer_full_items_bg():
    """백그라운드 스레드에서 가격 포함 전체 목록을 조회하여 캐시에 채우고 파일에 저장합니다."""
    import logging
    with _CONSUMER_CACHE["lock"]:
        if _CONSUMER_CACHE["loading"]:
            return
        _CONSUMER_CACHE["loading"] = True
    try:
        full = consumer_price_client.get_products_with_prices()
        _CONSUMER_CACHE["items"] = full
        _CONSUMER_CACHE["ready"] = True
        _save_consumer_cache_to_file(full)
    except Exception as e:  # noqa: BLE001 - 백그라운드 작업이므로 광범위 예외 처리
        logging.exception("[consumer] 가격 목록 로드 실패: %s", e)
    finally:
        _CONSUMER_CACHE["loading"] = False


# 서버 시작 시: 캐시(런타임 캐시 또는 커밋된 스냅샷)가 전혀 없을 때만 백그라운드
# 가격 조회를 시작합니다. 스냅샷은 GitHub Actions가 주기적으로 최신화하므로, 매 콜드
# 스타트마다 실시간 조회를 또 시도할 필요가 없습니다(서버리스 환경에서는 완료되지도
# 않고, 외부 API에 불필요한 부하만 줍니다).
# (Flask debug 모드의 reloader가 모듈을 두 번 로드하므로, 실제 서빙 프로세스에서만
#  1회 실행되도록 WERKZEUG_RUN_MAIN 환경변수로 가드합니다.)
def _start_consumer_background_refresh():
    t = threading.Thread(target=_load_consumer_full_items_bg, daemon=True)
    t.start()


if not _CONSUMER_CACHE["ready"] and (os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug):
    _start_consumer_background_refresh()




# ---------------------------------------------------------------------------
# 프론트엔드 정적 파일 서빙
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/consumer")
def consumer_page():
    """생필품(한국소비자원 참가격) 페이지."""
    return send_from_directory(FRONTEND_DIR, "consumer.html")


@app.route("/blog")
@app.route("/blog/")
def blog_index():
    return send_from_directory(FRONTEND_DIR, "blog/index.html")


@app.route("/blog/<path:filename>")
def blog_post(filename):
    """블로그 글/에셋. blog/ 하위 파일만 허용 (경로 이탈 방지)."""
    if ".." in filename or filename.startswith("/"):
        return "Not found", 404
    return send_from_directory(os.path.join(FRONTEND_DIR, "blog"), filename)



# ---------------------------------------------------------------------------
# API: 오늘의 가격 (전체 품목, 당일/1일전/1개월전/1년전 비교 포함)
# ---------------------------------------------------------------------------
@app.route("/api/today-prices")
def today_prices():
    """
    KAMIS '최근일자 도·소매가격정보'를 가져와
    프론트엔드에서 쓰기 쉬운 형태로 가공해서 반환합니다.

    Query Params:
        cls (str): '01' 소매 / '02' 도매 (기본값 '02')
        q (str): 품목명 검색 키워드 (선택)
    """
    cls_code = request.args.get("cls", "02")
    keyword = request.args.get("q", "").strip()

    try:
        raw = kamis_client.get_daily_sales(product_cls_code=cls_code)
    except kamis_client.KamisApiError as e:
        return jsonify({"ok": False, "error": str(e)}), 502

    # KAMIS dailySalesList는 p_product_cls_code를 무시하고 소매+도매 전체를 반환함.
    # 응답 내 product_cls_code 필드로 직접 필터링해야 함.
    items = _extract_items(raw)

    result = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # 소매/도매 필터링 (product_cls_code: '01'=소매, '02'=도매)
        if it.get("product_cls_code") != cls_code:
            continue
        name = it.get("item_name") or it.get("productName") or ""
        if keyword and keyword not in name:
            continue
        result.append(_normalize_item(it))

    return jsonify({"ok": True, "count": len(result), "items": result})


# ---------------------------------------------------------------------------
# API: 특정 품목의 기간별 가격 추이
# ---------------------------------------------------------------------------
@app.route("/api/trend")
def trend():
    """
    Query Params (모두 KAMIS 코드표 기준):
        category (str): 품목 분류 코드, 필수 (예: '200')
        item (str): 품목 코드, 필수 (예: '212')
        kind (str): 품종 코드, 기본 '00'
        rank (str): 등급 코드, 기본 '04'
        days (int): 조회 기간(일), 기본 30
        cls (str): '01' 소매 / '02' 도매, 기본 '02'
    """
    category = request.args.get("category")
    item = request.args.get("item")
    if not category or not item:
        return jsonify({"ok": False, "error": "category, item 파라미터는 필수입니다."}), 400

    kind = request.args.get("kind", "00")
    rank = request.args.get("rank", "04")
    days = int(request.args.get("days", 30))
    cls_code = request.args.get("cls", "02")

    from datetime import date, timedelta
    end_day = date.today().isoformat()
    start_day = (date.today() - timedelta(days=days)).isoformat()

    try:
        raw = kamis_client.get_period_trend(
            item_category_code=category,
            item_code=item,
            kind_code=kind,
            product_rank_code=rank,
            start_day=start_day,
            end_day=end_day,
            product_cls_code=cls_code,
        )
    except kamis_client.KamisApiError as e:
        return jsonify({"ok": False, "error": str(e)}), 502

    points = _extract_trend_points(raw)
    return jsonify({"ok": True, "count": len(points), "points": points})


# ---------------------------------------------------------------------------
# 응답 가공 헬퍼
# ---------------------------------------------------------------------------
def _extract_items(raw: dict):
    """KAMIS dailySalesList 응답에서 품목 리스트를 안전하게 추출합니다."""
    if not isinstance(raw, dict):
        return []

    # 실제 KAMIS 응답: 최상위 "price" 키에 리스트가 있음
    price = raw.get("price")
    if isinstance(price, list):
        return price
    if isinstance(price, dict):
        return [price]

    # 구버전/대안 응답 구조 처리
    data = raw.get("data")
    if isinstance(data, dict):
        item = data.get("item")
        if isinstance(item, list):
            return item
        if isinstance(item, dict):
            return [item]
    if isinstance(data, list):
        return data

    item = raw.get("item")
    if isinstance(item, list):
        return item
    return []


# ---------------------------------------------------------------------------
# KAMIS 공식 품목명 → 소비자 친화적 표시명 변환 매핑
# 카드/모달에 표시되는 item_name을 일반인이 알아볼 수 있는 이름으로 변환합니다.
# 키: KAMIS item_name에 포함되는 키워드 → 대체 표시명 접두어
# ---------------------------------------------------------------------------
DISPLAY_NAME_MAP = {
    "참다래":   "키위",
    "만감류":   "한라봉",
    "금감":     "금귤",
    "숙주":     "숙주나물",
    "명태":     "동태(명태)",
    "쇠고기":   "소고기",
    "계란":     "달걀",
    "보리":     "보리쌀",
}


def _apply_display_name(item_name: str) -> str:
    """KAMIS 공식 품목명을 소비자 친화적 표시명으로 변환합니다."""
    if not item_name:
        return item_name
    for kamis_kw, display_kw in DISPLAY_NAME_MAP.items():
        if kamis_kw in item_name:
            # 예: "참다래/그린 뉴질랜드" → "키위/그린 뉴질랜드"
            return item_name.replace(kamis_kw, display_kw, 1)
    return item_name


# ---------------------------------------------------------------------------
# 품목별 단위 참고 중량 매핑
# KAMIS API는 "1포기", "10개" 등 개수 단위만 반환하므로,
# 소비자가 실제 중량을 가늠할 수 있도록 참고 중량을 병기합니다.
# 키: (품목명에 포함되는 키워드, KAMIS unit 값) → 참고 중량 문자열
# ---------------------------------------------------------------------------
UNIT_WEIGHT_HINT = {
    # 채소류 - 포기/개 단위
    ("배추",   "1포기"):  "약 2~3kg",
    ("배추",   "10kg"):   None,          # kg 단위는 그대로
    ("절임배추", "10kg"): None,
    ("양배추", "1포기"):  "약 1.5~2kg",
    ("양배추", "1개"):    "약 1.5~2kg",
    ("상추",   "100g"):   None,
    ("시금치", "1kg"):    None,
    ("무",     "1개"):    "약 800g~1.2kg",
    ("무",     "20kg"):   None,
    ("열무",   "1kg"):    None,
    ("총각무", "1kg"):    None,
    ("당근",   "1kg"):    None,
    ("당근",   "10개"):   "개당 약 100~150g",
    ("오이",   "10개"):   "개당 약 100~150g",
    ("오이",   "1개"):    "약 100~150g",
    ("호박",   "1개"):    "약 400~600g",
    ("애호박", "1개"):    "약 400~500g",
    ("단호박", "1개"):    "약 1~1.5kg",
    ("파",     "1kg"):    None,
    ("대파",   "1kg"):    None,
    ("쪽파",   "1kg"):    None,
    ("양파",   "1kg"):    None,
    ("양파",   "20kg"):   None,
    ("마늘",   "1kg"):    None,
    ("마늘",   "10kg"):   None,
    ("생강",   "1kg"):    None,
    ("고추",   "1kg"):    None,
    ("풋고추", "1kg"):    None,
    ("피망",   "1kg"):    None,
    ("파프리카", "1kg"):  None,
    ("토마토", "1kg"):    None,
    ("방울토마토", "1kg"): None,
    ("가지",   "1kg"):    None,
    ("브로콜리", "1개"):  "약 300~500g",
    ("브로콜리", "1kg"):  None,
    ("콜리플라워", "1개"): "약 500~800g",
    ("깻잎",   "100g"):   None,
    ("미나리", "1kg"):    None,
    ("부추",   "1kg"):    None,
    ("셀러리", "1kg"):    None,
    ("아스파라거스", "1kg"): None,
    # 과일류
    ("사과",   "10개"):   "개당 약 250~350g",
    ("사과",   "1개"):    "약 250~350g",
    ("배",     "10개"):   "개당 약 400~600g",
    ("배",     "1개"):    "약 400~600g",
    ("감",     "10개"):   "개당 약 150~200g",
    ("단감",   "10개"):   "개당 약 150~200g",
    ("귤",     "10개"):   "개당 약 80~120g",
    ("귤",     "1kg"):    None,
    ("오렌지", "10개"):   "개당 약 200~300g",
    ("레몬",   "10개"):   "개당 약 100~150g",
    ("포도",   "1송이"):  "약 400~600g",
    ("포도",   "1kg"):    None,
    ("딸기",   "1kg"):    None,
    ("수박",   "1개"):    "약 7~10kg",
    ("참외",   "1개"):    "약 400~600g",
    ("참외",   "10개"):   "개당 약 400~600g",
    ("복숭아", "1개"):    "약 200~300g",
    ("복숭아", "10개"):   "개당 약 200~300g",
    ("자두",   "1kg"):    None,
    ("키위",   "1개"):    "약 80~120g",
    ("키위",   "10개"):   "개당 약 80~120g",
    ("바나나", "1kg"):    None,
    ("망고",   "1개"):    "약 200~400g",
    ("멜론",   "1개"):    "약 1.5~2.5kg",
    ("블루베리", "1kg"):  None,
    # 식량작물
    ("쌀",     "20kg"):   None,
    ("쌀",     "10kg"):   None,
    ("찹쌀",   "10kg"):   None,
    ("현미",   "10kg"):   None,
    ("보리",   "1kg"):    None,
    ("밀",     "1kg"):    None,
    ("옥수수", "1개"):    "약 200~300g",
    ("옥수수", "10개"):   "개당 약 200~300g",
    ("감자",   "1kg"):    None,
    ("감자",   "20kg"):   None,
    ("고구마", "1kg"):    None,
    ("고구마", "10kg"):   None,
    # 축산물
    ("쇠고기", "1kg"):    None,
    ("돼지고기", "1kg"):  None,
    ("닭고기", "1kg"):    None,
    ("계란",   "30개"):   "개당 약 60g",
    ("계란",   "10개"):   "개당 약 60g",
    ("우유",   "1L"):     None,
    # 수산물
    ("고등어", "1마리"):  "약 300~500g",
    ("고등어", "1kg"):    None,
    ("갈치",   "1마리"):  "약 300~600g",
    ("갈치",   "1kg"):    None,
    ("오징어", "1마리"):  "약 200~350g",
    ("오징어", "1kg"):    None,
    ("새우",   "1kg"):    None,
    ("꽃게",   "1kg"):    None,
    ("조기",   "1마리"):  "약 200~400g",
    ("명태",   "1마리"):  "약 300~500g",
    ("참치",   "1kg"):    None,
    ("전복",   "1kg"):    None,
}


def _get_unit_hint(item_name: str, unit: str) -> str | None:
    """품목명과 단위를 보고 참고 중량 힌트를 반환합니다. 없으면 None."""
    if not item_name or not unit:
        return None
    for (kw, u), hint in UNIT_WEIGHT_HINT.items():
        if kw in item_name and u == unit:
            return hint
    return None


def _normalize_item(it: dict):
    """가격 카드 UI에 맞게 필드를 정리합니다."""
    def to_int(v):
        try:
            return int(str(v).replace(",", ""))
        except (TypeError, ValueError):
            return None

    # KAMIS dailySalesList dpr 필드 실제 의미:
    # dpr1=당일, dpr2=1일전, dpr3=1개월전, dpr4=1년전
    today_price = to_int(it.get("dpr1") or it.get("price"))
    day_ago     = to_int(it.get("dpr2"))
    month_ago   = to_int(it.get("dpr3"))
    year_ago    = to_int(it.get("dpr4"))

    item_name_raw = it.get("item_name") or it.get("productName")
    item_name     = _apply_display_name(item_name_raw)   # 소비자 친화적 표시명으로 변환
    unit          = it.get("unit")

    # kind_name(품종명)과 rank_name(등급명)을 item_name에 병기하여 카드 구분
    # 예: "마른멸치/마른멸치" + kind_name="대" → "마른멸치/마른멸치(대)"
    # 단, kind_name이 "00"(전체) 또는 item_name에 이미 포함된 경우 생략
    kind_name = (it.get("kind_name") or "").strip()
    rank_name = (it.get("rank_name") or "").strip()
    # 의미없는 기본값 제거
    SKIP_KIND = {"00", "0", "", "전체", "-"}
    SKIP_RANK = {"00", "0", "", "전체", "-", "평균"}
    suffix_parts = []
    if kind_name and kind_name not in SKIP_KIND and kind_name not in (item_name or ""):
        suffix_parts.append(kind_name)
    if rank_name and rank_name not in SKIP_RANK and rank_name not in (item_name or ""):
        suffix_parts.append(rank_name)
    if suffix_parts:
        item_name = f"{item_name}({'/'.join(suffix_parts)})"

    change_pct = None
    if today_price and month_ago:
        change_pct = round((today_price - month_ago) / month_ago * 100, 1)

    # 원본(KAMIS) 이름으로 먼저 조회하고, 못 찾으면 소비자 친화적 표시명으로도 조회합니다.
    # UNIT_WEIGHT_HINT는 "키위"/"한라봉"/"금귤"/"숙주나물"/"동태"처럼 DISPLAY_NAME_MAP
    # 변환 후의 이름을 키로 등록해둔 항목이 있어서, 원본 이름("참다래"/"만감류"/"금감"/
    # "숙주"/"명태")만으로 조회하면 이 항목들의 힌트가 영영 매칭되지 않았습니다.
    unit_hint     = _get_unit_hint(item_name_raw, unit) or _get_unit_hint(item_name, unit)

    # KAMIS dailySalesList 응답에서 품목 코드 추출
    # 실제 필드명: item_code (일부 응답에서는 productno)
    item_code = (
        it.get("item_code")
        or it.get("productno")
        or it.get("itemcode")
        or it.get("item_no")
    )

    return {
        "item_name": item_name,
        "item_code": item_code,   # 추이 조회에 사용되는 품목 코드
        "unit": unit,
        "unit_hint": unit_hint,   # 참고 중량 (예: "약 2~3kg"), 없으면 null
        "category_code": it.get("category_code"),
        "category_name": it.get("category_name"),
        "today_price": today_price,
        "day_ago_price": day_ago,
        "week_ago_price": None,
        "month_ago_price": month_ago,
        "year_ago_price": year_ago,
        "month_change_pct": change_pct,
        "raw": it,  # 디버깅/확장을 위해 원본도 함께 전달
    }


def _extract_trend_points(raw: dict):
    """KAMIS periodProductList 응답에서 (날짜, 가격) 포인트 리스트를 추출합니다.

    KAMIS periodProductList 실제 응답 구조:
      { "data": { "item": [ { "regday": "2024/01/01", "price": "1,234", ... }, ... ] } }
    또는 에러 시:
      { "data": "-1" }  또는  { "data": null }
    """
    import logging

    if not isinstance(raw, dict):
        logging.warning("[trend] raw 응답이 dict가 아님: %s", type(raw))
        return []

    data = raw.get("data")

    # KAMIS 에러 응답: data가 "-1" 문자열이거나 None인 경우
    if data is None or data == "-1" or data == -1:
        logging.warning("[trend] KAMIS 응답 data 없음 또는 에러: %s", data)
        return []

    items = []
    if isinstance(data, dict):
        candidate = data.get("item")
        if isinstance(candidate, list):
            items = candidate
        elif isinstance(candidate, dict):
            items = [candidate]
        else:
            logging.warning("[trend] data.item 필드 없음. data 키: %s", list(data.keys()))
    elif isinstance(data, list):
        items = data
    else:
        logging.warning("[trend] data 타입 예상 외: %s, 값: %s", type(data), str(data)[:200])

    points = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # KAMIS 필드명: regday (날짜), price (가격)
        date_val  = it.get("regday") or it.get("date") or it.get("yyyy") 
        price_val = it.get("price") or it.get("value") or it.get("dpr1")
        if date_val is None or price_val is None:
            continue
        # 가격이 "-" 또는 빈 문자열인 경우 스킵
        price_str = str(price_val).replace(",", "").strip()
        if not price_str or price_str == "-":
            continue
        try:
            price_num = int(price_str)
        except ValueError:
            continue
        points.append({"date": date_val, "price": price_num})

    points.sort(key=lambda p: p["date"])
    return points


# ---------------------------------------------------------------------------
# 중량 필터링 헬퍼
# ---------------------------------------------------------------------------
def _parse_weight_g(text: str):
    """
    문자열에서 중량(g 단위로 환산)을 추출합니다.
    예: "20kg" → 20000, "500g" → 500, "1.5kg" → 1500
    인식 불가 시 None 반환.
    """
    import re
    if not text:
        return None
    text = text.replace(",", "").replace(" ", "")
    # kg 단위
    m = re.search(r"(\d+(?:\.\d+)?)\s*kg", text, re.IGNORECASE)
    if m:
        return float(m.group(1)) * 1000
    # g 단위
    m = re.search(r"(\d+(?:\.\d+)?)\s*g(?!r)", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def _filter_by_weight(items: list, kamis_unit: str) -> list:
    """
    KAMIS 단위(예: "20kg")에서 기준 중량을 추출하고,
    상품 제목에 명시된 중량이 현저히 다른 상품을 제외합니다.

    허용 범위:
      - 기준 중량의 0.4배 ~ 3배 이내 (예: 20kg → 8kg~60kg)
      - 단, 기준 중량이 kg 단위가 아니거나 추출 불가 시 필터링 안 함
    """
    import re

    ref_g = _parse_weight_g(kamis_unit)
    if ref_g is None or ref_g <= 0:
        return items  # 중량 단위가 아니면 필터링 안 함

    result = []
    for it in items:
        title = it.get("title") or ""
        item_g = _parse_weight_g(title)

        if item_g is None:
            # 상품 제목에 중량 표기가 없으면 통과 (중량 미표기 상품 허용)
            result.append(it)
            continue

        # 허용 범위: 기준의 0.4배 ~ 3배
        low  = ref_g * 0.4
        high = ref_g * 3.0
        if low <= item_g <= high:
            result.append(it)

    # 필터 후 결과가 너무 적으면 원본 사용 (최소 2개 보장)
    return result if len(result) >= 2 else items


# ---------------------------------------------------------------------------
# API: 최저가 상품 검색 (소매가 전용, 애드픽 /search API 사용)
# ---------------------------------------------------------------------------
@app.route("/api/shop-prices")
def shop_prices():
    """
    애드픽 상품 검색 API를 통해 품목의 최저가 상품 목록을 반환합니다.
    소매가(cls=01) 모달에서만 사용합니다.

    Query Params:
        q (str): 검색 품목명, 필수 (예: "쌀/20kg", "사과/10개")
        unit (str): 단위 (선택, 예: "1L", "100g")
    """
    import re

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"ok": False, "error": "q 파라미터는 필수입니다."}), 400

    adpick_key = os.environ.get("ADPICK_API_KEY", "")
    if not adpick_key:
        return jsonify({"ok": False, "error": "ADPICK_API_KEY가 설정되지 않았습니다."}), 500

    # KAMIS 오늘 가격 (가격 범위 필터링에 사용)
    kamis_price_raw = request.args.get("price", "")
    try:
        kamis_price = int(kamis_price_raw) if kamis_price_raw else None
    except (ValueError, TypeError):
        kamis_price = None

    # ── KAMIS 품목명 → 소비자 검색어 변환 ──────────────────────────────────
    # "/" 기준으로 분리 (예: "쌀/20kg" → ["쌀", "20kg"])
    parts = re.split(r"[/·,]+", query)
    first_part = parts[0].strip()
    second_part = parts[1].strip() if len(parts) > 1 else ""

    def strip_parens(s):
        return re.sub(r"\s*\(.*?\)", "", s).strip()

    first_part_clean  = strip_parens(first_part)
    second_part_clean = strip_parens(second_part)

    # KAMIS 공식 품목명 → 소비자 검색어 별칭 매핑
    ITEM_ALIAS_MAP = {
        "참다래":   "키위",
        "만감류":   "한라봉",
        "금감":     "금귤",
        "숙주":     "숙주나물",
        "콩나물":   "콩나물",
        "고구마줄기": "고구마순",
        "명태":     "동태",
        "물오징어": "오징어",
        "배추":     "배추",   # 배추/봄 등 → "배추" 검색 (봄은 SKIP_SECOND_WORDS에 있음)
        "봄":       "배추",   # 혹시 봄이 first_part가 되는 경우 대비
        "꽁치":     "꽁치",   # 꽁치 → 그대로 "꽁치" 검색
        "건다시마": "다시마", # 건다시마/완도산 → "다시마" 검색
        "다시마":   "다시마", # 다시마 → 그대로 "다시마" 검색
        "삼치":     "삼치",   # 삼치/냉장 → "삼치" 검색
        "수입조기": "조기",   # 수입조기/부세수입 → "조기" 검색 (부세는 조기 종류)
        "안깐홍합": "홍합",
        "임연수":   "임연수어",
        "쇠고기":   "소고기",
        "소":       "소고기",   # 소/안심, 소/등심 등 → "소고기" 검색
        "돼지":     "돼지고기", # 돼지/삼겹살, 돼지/앞다리 등 → "돼지고기" 검색
        "닭":       "닭고기",   # 닭/목계, 닭/육계 등 → "닭고기" 검색
        "계란":     "달걀",
        "보리":     "보리쌀",
        "밀":       "밀가루",
    }

    # 두 번째 파트가 숫자를 포함하면 단위 (예: "20kg", "10개")
    has_unit_in_second = bool(re.search(r"[0-9]", second_part))

    # 두 번째 파트가 더 구체적인 품목명인 경우 사용 (예: "호박/애호박" → "애호박")
    # 단, 단위·계절·처리방식 키워드는 제외
    SKIP_SECOND_WORDS = {
        "봄", "여름", "가을", "겨울", "햇", "조생", "만생", "중생",
        "무세척", "세척", "수입", "수입산", "국산", "냉동", "냉장", "건조", "절임", "가공",
        "중국", "중국산", "국내산", "미국", "호주", "칠레", "베트남",
        "완도산", "통영산", "거제산", "제주산", "여수산", "남해산", "서해산", "동해산",
        "연근해", "원양", "근해", "양식", "자연산", "활", "선어", "생물",
        "일반계", "찰", "특", "상", "중", "하",
        # 색상/품종 접두어 (단독 검색 시 엉뚱한 결과 방지)
        "청",    # 피망/청 → "청" 단독 검색 방지 (제이청 등 의류 브랜드 노출)
        "홍",    # 피망/홍 → "홍" 단독 검색 방지
        "녹",    # 녹색 계열
        "황",    # 황피망 등
        "백",    # 백색 계열
        "백색",  # 참깨/백색 → "백색" 단독 검색 방지 (참깨가 우선)
        # 품종명 (단독으로 검색어로 쓰면 엉뚱한 결과가 나오는 품종)
        "밤",   # 고구마/밤 → "밤" 단독 검색 방지
        "호박",  # 고구마/호박 등
        "자색",  # 고구마/자색
        "물",   # 고구마/물
        "흑",   # 흑마늘 등 색상 접두어
        "적",   # 적양파 등
        "황",   # 황태 등
        # 감자 품종명 (단독 검색 시 엉뚱한 결과 방지)
        "수미",  # 감자/수미(노지) → "수미" 단독 검색 방지 (수미푸드 등 무관 상품 노출)
        "대지",  # 감자/대지
        "두백",  # 감자/두백
        "하령",  # 감자/하령
        "남작",  # 감자/남작
        "노지",  # 감자/수미(노지) 등 재배방식
        "시설",  # 시설재배
        # 오이 품종명 (단독 검색 시 엉뚱한 결과 방지)
        "가시계통",  # 오이/가시계통 → "가시계통" 단독 검색 방지 (예초기날 등 무관 상품 노출)
        "가시",      # "가시" 단독 검색 방지
        "취청",      # 오이/취청
        "다다기",    # 오이/다다기
        "백다다기",  # 오이/백다다기
        # 사과 품종명 (단독 검색 시 엉뚱한 결과 방지)
        "후지",   # 사과/후지 → "후지" 단독 검색 방지 (후지필름 등 무관 상품 노출)
        "홍로",   # 사과/홍로
        "아오리", # 사과/아오리
        "감홍",   # 사과/감홍
        "양광",   # 사과/양광
        "홍옥",   # 사과/홍옥
        "쓰가루", # 사과/쓰가루
        # 배 품종명 (단독 검색 시 엉뚱한 결과 방지)
        "신고",   # 배/신고 → "신고" 단독 검색 방지 (신고서·신고식 등 무관 상품 노출)
        "원황",   # 배/원황
        "화산",   # 배/화산
        "추황",   # 배/추황
        "만풍",   # 배/만풍
        # 소/돼지 공통 부위명 (단독 검색 시 엉뚱한 결과 방지 → "소고기/돼지고기"로 검색)
        "안심",   # 소/안심 → "안심" 단독 검색 방지 (안심하세요 등 무관 상품 노출)
        "등심",   # 소/등심
        "채끝",   # 소/채끝
        "양지",   # 소/양지
        "사태",   # 소/사태
        "갈비",   # 소/갈비, 돼지/갈비
        "갈비살", # 소/갈비살, 돼지/갈비살 (갈비와 다른 부위)
        "목심",   # 소/목심, 돼지/목심
        "앞다리", # 소/앞다리, 돼지/앞다리
        "우둔",   # 소/우둔
        "설도",   # 소/설도
        "업진",   # 소/업진
        "제비추리", # 소/제비추리
        "삼겹살", # 돼지/삼겹살
        "항정살", # 돼지/항정살
        "뒷다리", # 돼지/뒷다리
        "등뼈",   # 돼지/등뼈
        # 닭 품종명 (단독 검색 시 엉뚱한 결과 방지 → "닭고기"로 검색)
        "육계",  # 닭/육계 → "육계" 단독 검색 방지
        "토종닭", # 닭/토종닭
        "삼계",  # 닭/삼계
        # 기타 품종/재배방식 키워드
        "일반",  # 일반재배
        "유기",  # 유기농
        "무농약",
        "친환경",
    }
    # second_part_clean에 SKIP_SECOND_WORDS 단어가 포함되어 있으면 스킵
    # 예: "부세수입" → "수입" 포함 → 스킵 (first_part_clean 기준으로 검색)
    _has_skip_word = any(skip in second_part_clean for skip in SKIP_SECOND_WORDS)

    use_second = (
        bool(second_part_clean)
        and not has_unit_in_second
        and not _has_skip_word
        and not second_part_clean.startswith("햇")
        and second_part_clean != first_part_clean
        and second_part_clean not in first_part_clean
    )

    if use_second:
        search_keyword = ITEM_ALIAS_MAP.get(second_part_clean, second_part_clean)
    else:
        search_keyword = ITEM_ALIAS_MAP.get(first_part_clean, first_part_clean)

    # 소고기/돼지고기 부위명 원본 보존 (검색어 및 필터링에 사용)
    # 예: "소/안심(1++등급)" → beef_cut_filter = "안심"
    # 예: "돼지/앞다리" → pork_cut_filter = "앞다리"
    beef_cuts = {
        "안심", "등심", "채끝", "양지", "사태", "갈비", "갈비살",
        "목심", "앞다리", "우둔", "설도", "업진", "제비추리",
    }
    pork_cuts = {
        "삼겹살", "목심", "앞다리", "뒷다리", "갈비", "갈비살", "항정살",
        "등뼈", "사태", "안심",
    }

    # first_part_clean으로 소/돼지 구분
    # "수입 소고기", "수입쇠고기" 등 수입 소고기도 포함
    is_beef_item  = (
        first_part_clean in {"소", "쇠고기", "한우", "육우"}
        or "쇠고기" in first_part_clean
        or "소고기" in first_part_clean
    )
    is_pork_item  = first_part_clean in {"돼지", "돼지고기"} or "돼지" in first_part_clean

    beef_cut_filter = second_part_clean if (is_beef_item and second_part_clean in beef_cuts) else None
    pork_cut_filter = second_part_clean if (is_pork_item and second_part_clean in pork_cuts) else None

    # 소고기 부위명이 있으면 검색어를 "소고기 {부위명}"으로 변경하여 검색 결과 확보
    # 예: "소/안심(1++등급)" → search_keyword = "소고기 안심"
    if beef_cut_filter and search_keyword == "소고기":
        search_keyword = f"소고기 {beef_cut_filter}"

    # 돼지고기 부위명이 있으면 검색어를 "돼지고기 {부위명}"으로 변경
    # 예: "돼지/앞다리" → search_keyword = "돼지고기 앞다리"
    if pork_cut_filter and search_keyword == "돼지고기":
        search_keyword = f"돼지고기 {pork_cut_filter}"

    # 국산/수입 소고기 구분
    # KAMIS에서 국산 소고기: "소/안심", "쇠고기/안심" 등 (first_part_clean = "소" 또는 "쇠고기")
    # KAMIS에서 수입 소고기: "수입쇠고기/안심" 등 (first_part_clean에 "수입" 포함)
    is_imported_beef = (
        beef_cut_filter is not None
        and any(kw in first_part_clean for kw in ["수입", "미국", "호주", "칠레", "뉴질랜드"])
    )

    # 수입 소고기 원산지 추출 (괄호 안 또는 first_part_clean에서)
    # 예: "수입 소고기/갈비(미국산)" → origin_filter = "미국"
    # 예: "수입 소고기/갈비(호주산)" → origin_filter = "호주"
    ORIGIN_MAP = {
        "미국산": "미국", "미국": "미국",
        "호주산": "호주", "호주": "호주",
        "칠레산": "칠레", "칠레": "칠레",
        "뉴질랜드산": "뉴질랜드", "뉴질랜드": "뉴질랜드",
    }
    origin_filter = None
    if is_imported_beef:
        # 괄호 안 원산지 우선 (예: "갈비(미국산)" → "미국산")
        paren_match = re.search(r"\(([^)]+)\)", second_part)
        if paren_match:
            paren_text = paren_match.group(1)
            for kw, origin in ORIGIN_MAP.items():
                if kw in paren_text:
                    origin_filter = origin
                    break
        # 괄호 없으면 first_part_clean에서 추출
        if not origin_filter:
            for kw, origin in ORIGIN_MAP.items():
                if kw in first_part_clean:
                    origin_filter = origin
                    break

    # ── 배추 전용: 검색어를 "포기배추"로 변환 ──────────────────────────────
    # 애드픽 API에서 "배추" 단독 검색 시 결과가 전부 배추김치임.
    # "포기배추"로 검색하면 채소 배추 상품이 나옴.
    # 단, "알배추"는 KAMIS에 별도 카드가 있으므로 변환하지 않음.
    if search_keyword == "배추":
        search_keyword = "포기배추"

    # 애드픽 상품 검색 (커미션 링크 포함)
    items = adpick_client.search_products(search_keyword, limit=20, api_key=adpick_key)

    if not items:
        return jsonify({"ok": True, "count": 0, "items": []})

    # ── 품목명 포함 필터링 ───────────────────────────────────────────────────
    # 검색 결과 상품 제목에 검색 키워드(또는 원본 품목명)가 포함된 상품만 허용합니다.
    # 예: "배추" 검색 → 제목에 "배추"가 없는 토르티야·부리또 등 제외
    # 키: 검색 키워드  값: 제목에 반드시 포함되어야 하는 키워드 목록 (OR 조건)
    ITEM_MUST_INCLUDE = {
        "배추":      ["배추"],
        "포기배추":  ["배추"],   # "배추" → "포기배추" 검색 시에도 "배추" 포함 상품만 허용
        "양배추": ["양배추"],
        "무":     ["무", "총각무", "열무"],
        "상추":   ["상추"],
        "시금치": ["시금치"],
        "깻잎":   ["깻잎"],
        "부추":   ["부추"],
        "미나리": ["미나리"],
        "쑥갓":   ["쑥갓"],
        "대파":   ["대파", "파"],
        "쪽파":   ["쪽파", "파"],
        "양파":   ["양파"],
        "마늘":   ["마늘"],
        "생강":   ["생강"],
        "고추":   ["고추"],
        "풋고추": ["풋고추", "고추"],
        "피망":   ["피망"],
        "파프리카": ["파프리카"],
        "오이":   ["오이"],
        "호박":   ["호박"],
        "애호박": ["애호박", "호박"],
        "단호박": ["단호박", "호박"],
        "가지":   ["가지"],
        "브로콜리": ["브로콜리"],
        "당근":   ["당근"],
        "토마토": ["토마토"],
        "방울토마토": ["방울토마토", "토마토"],
        "감자":   ["감자"],
        "고구마": ["고구마"],
        "옥수수": ["옥수수"],
        "사과":   ["사과"],
        "배":     ["배"],
        "귤":     ["귤"],
        "오렌지": ["오렌지"],
        "딸기":   ["딸기"],
        "수박":   ["수박"],
        "참외":   ["참외"],
        "포도":   ["포도"],
        "복숭아": ["복숭아"],
        "자두":   ["자두"],
        "키위":   ["키위"],
        "한라봉": ["한라봉"],
        "금귤":   ["금귤"],
        "멜론":   ["멜론"],
        "망고":   ["망고"],
        "바나나": ["바나나"],
        "블루베리": ["블루베리"],
        "쌀":     ["쌀"],
        "찹쌀":   ["찹쌀"],
        "현미":   ["현미"],
        "보리쌀": ["보리쌀", "보리"],
        "밀가루": ["밀가루"],
        "달걀":   ["달걀", "계란"],
        "소고기": ["소고기", "쇠고기", "한우", "육우"],
        # 소고기 부위별 필터 (부위명 + 소고기 관련 키워드 모두 포함해야 함)
        # 주의: "안심"/"등심"/"채끝"/"양지"/"사태"/"갈비"는 이 dict 아래쪽에
        # (부위명 + 소고기/쇠고기/한우 키워드) 형태로 다시 정의되어 있습니다.
        # 여기서는 그 외 부위(목심, 앞다리, 우둔, 설도, 업진, 제비추리)만 둡니다.
        "목심":   ["목심"],
        "앞다리": ["앞다리"],
        "우둔":   ["우둔"],
        "설도":   ["설도"],
        "업진":   ["업진"],
        "제비추리": ["제비추리"],
        "돼지고기": ["돼지고기", "삼겹살", "목살", "항정살"],
        "닭고기": ["닭고기", "닭", "치킨"],
        "우유":   ["우유"],
        "고등어": ["고등어"],
        "갈치":   ["갈치"],
        "오징어": ["오징어"],
        "새우":   ["새우"],
        "꽃게":   ["꽃게", "게"],
        "꽁치":   ["꽁치", "과메기"],  # 꽁치 수입산 포함, 과메기(꽁치로 만듦)도 허용
        "조기":   ["조기", "부세"],
        "동태":   ["동태", "명태"],
        "홍합":   ["홍합"],
        "전복":   ["전복"],
        "숙주나물": ["숙주나물", "숙주"],
        "콩나물": ["콩나물"],
        "고구마순": ["고구마순", "고구마줄기"],
        "참깨":   ["참깨"],
        "다시마":  ["다시마"],
        "삼치":   ["삼치"],
        "안심":   ["안심", "소고기", "쇠고기", "한우"],
        "등심":   ["등심", "소고기", "쇠고기", "한우"],
        "채끝":   ["채끝", "소고기", "쇠고기", "한우"],
        "양지":   ["양지", "소고기", "쇠고기", "한우"],
        "사태":   ["사태", "소고기", "쇠고기", "한우"],
        "갈비":   ["갈비", "소고기", "쇠고기", "한우"],
    }

    def _cut_match(title: str, cut: str) -> bool:
        """
        부위명 정확 매칭 헬퍼.
        "갈비"는 "갈비살"을 포함하지 않도록 처리.
        "갈비살"은 "갈비살"만 매칭.
        즉, cut이 title에 포함되되, cut 뒤에 다른 한글 글자가 이어지지 않아야 함.
        예외: "갈비살" 검색 시 "갈비살"은 OK, "갈비"만 있는 상품은 제외.
        """
        import re as _re
        # cut 뒤에 한글 글자가 오지 않는 경우만 매칭 (단어 경계)
        pattern = _re.escape(cut) + r"(?![가-힣])"
        return bool(_re.search(pattern, title))

    # 소고기 부위명이 있으면 부위명 필터 우선 적용
    # 국산 소고기: 부위명 AND (한우 OR 국내산 OR 소고기 OR 쇠고기) 포함 상품만
    # 수입 소고기: 부위명 + 원산지 필터
    # 돼지고기 부위명: 부위명 AND (돼지고기 OR 돼지 OR 국내산) 포함 상품만
    if beef_cut_filter and not is_imported_beef:
        domestic_keywords = ["한우", "국내산", "국산", "소고기", "쇠고기", "육우"]
        items = [
            it for it in items
            if _cut_match(it.get("title") or "", beef_cut_filter)
            and any(kw in (it.get("title") or "") for kw in domestic_keywords)
        ]
        must_include = []  # 이미 필터링 완료
    elif beef_cut_filter and is_imported_beef:
        # 수입 소고기: 부위명 + 원산지 필터
        # origin_filter가 있으면 해당 원산지 상품만 허용 (예: 미국산이면 미국산만)
        # origin_filter가 없으면 부위명만 필터
        if origin_filter:
            items = [
                it for it in items
                if _cut_match(it.get("title") or "", beef_cut_filter)
                and origin_filter in (it.get("title") or "")
            ]
            must_include = []  # 이미 필터링 완료
        else:
            items = [it for it in items if _cut_match(it.get("title") or "", beef_cut_filter)]
            must_include = []
    elif pork_cut_filter:
        # 돼지고기 부위명: 부위명 AND (돼지고기 OR 돼지 OR 국내산) 포함 상품만
        pork_keywords = ["돼지고기", "돼지", "국내산", "국산"]
        items = [
            it for it in items
            if _cut_match(it.get("title") or "", pork_cut_filter)
            and any(kw in (it.get("title") or "") for kw in pork_keywords)
        ]
        must_include = []  # 이미 필터링 완료
    else:
        must_include = ITEM_MUST_INCLUDE.get(search_keyword, [])

    if must_include:
        include_filtered = [
            it for it in items
            if any(kw in (it.get("title") or "") for kw in must_include)
        ]
        # 품목명 포함 필터는 핵심 필터: 결과가 0개여도 원본 사용하지 않음
        # (예: "오이" 검색 시 "오이"가 없는 반지·화장품 등 비식품 상품 차단)
        items = include_filtered

    # ── 국산/수입 필터링 ────────────────────────────────────────────────────
    # KAMIS 품목명에 수입 관련 키워드가 없으면 → 국산 품목으로 간주
    # 상품 제목에 수입산 키워드가 포함된 경우 제외
    IMPORT_TITLE_KEYWORDS = [
        "수입", "중국산", "중국", "미국산", "호주산", "칠레산", "베트남산",
        "태국산", "페루산", "뉴질랜드산", "필리핀산", "인도산", "imported",
    ]
    # KAMIS 품목명 자체가 수입품인 경우 (수입 필터 적용 안 함)
    IMPORT_ITEM_KEYWORDS = ["수입", "뉴질랜드", "미국", "호주", "칠레", "베트남", "중국"]
    is_import_item = any(kw in query for kw in IMPORT_ITEM_KEYWORDS) or is_imported_beef

    # 꽁치는 국내 유통 대부분이 수입산이므로 수입 필터 적용 안 함
    # (제휴몰에 수입산 꽁치 상품이 없어 빈 결과가 나오는 문제 방지)
    if search_keyword == "꽁치":
        is_import_item = False

    if not is_import_item:
        # 국산 품목: 상품 제목에 수입산 키워드가 있으면 제외
        filtered = []
        for it in items:
            title = (it.get("title") or "").lower()
            if any(kw in title for kw in IMPORT_TITLE_KEYWORDS):
                continue
            filtered.append(it)
        # 필터 후 결과가 너무 적으면 원본 사용 (최소 2개 보장)
        items = filtered if len(filtered) >= 2 else items
    else:
        # 수입 품목: 상품 제목에 수입산 키워드 OR 원산지명이 있는 상품만 허용
        # 예: "고등어/수입산" → 노르웨이산, 수입, 수입산 등이 포함된 상품만
        # 단, 수입 소고기(is_imported_beef)는 이미 origin_filter로 처리했으므로 제외
        IMPORT_POSITIVE_KEYWORDS = [
            "수입", "수입산", "노르웨이", "노르웨이산",
            "중국", "중국산", "미국", "미국산",
            "호주", "호주산", "칠레", "칠레산",
            "베트남", "베트남산", "태국", "태국산",
            "페루", "페루산", "뉴질랜드", "뉴질랜드산",
            "필리핀", "필리핀산", "인도", "인도산",
            "imported", "해외",
        ]
        if not is_imported_beef:
            import_filtered = [
                it for it in items
                if any(kw in (it.get("title") or "") for kw in IMPORT_POSITIVE_KEYWORDS)
            ]
            # 필터 후 결과가 너무 적으면 원본 사용 (최소 2개 보장)
            items = import_filtered if len(import_filtered) >= 2 else items

    # ── 주머니 단위 상품 필터링 ─────────────────────────────────────────────
    # "1주머니", "한 주머니" 등 주머니 단위로 판매되는 상품 제외
    # (소포장 주머니 단위는 KAMIS 기준 단위와 맞지 않아 가격 비교가 부적절)
    POUCH_KEYWORDS = ["주머니", "한주머니", "1주머니", "2주머니", "3주머니"]
    pouch_filtered = []
    for it in items:
        title = (it.get("title") or "")
        if any(kw in title for kw in POUCH_KEYWORDS):
            continue
        pouch_filtered.append(it)
    # 필터 후 결과가 너무 적으면 원본 사용 (최소 2개 보장)
    items = pouch_filtered if len(pouch_filtered) >= 2 else items

    # ── 품목별 가공식품 제외 키워드 매핑 ────────────────────────────────────
    # 원재료를 검색할 때 해당 재료로 만든 가공식품이 나오지 않도록 제외합니다.
    # 키: 검색 키워드(search_keyword)  값: 제목에서 제외할 키워드 목록
    ITEM_EXCLUDE_KEYWORDS = {
        "배추":      ["김치", "깍두기", "총각김치", "열무김치", "백김치", "동치미"],
        "포기배추":  ["김치", "깍두기", "총각김치", "열무김치", "백김치", "동치미"],
        "무":     ["깍두기", "동치미", "무말랭이", "무김치", "단무지"],
        "애호박": ["단호박", "밤호박", "미니호박", "늙은호박", "청둥호박"],
        "오이":   ["오이소박이", "오이김치", "오이피클",
                   "바디로션", "바디크림", "바디워시", "바디오일", "바디버터", "바디스크럽",
                   "샴푸", "린스", "컨디셔너", "트리트먼트", "헤어팩", "헤어오일",
                   "선크림", "선스크린", "자외선차단", "마스크팩", "시트마스크",
                   "클렌징", "폼클렌저", "클렌징오일", "핸드크림", "핸드로션",
                   "플라워테라피", "아로마테라피", "테라피"],
        "피망":   [
            # 비식품 (장난감·모형·책·케이스·인테리어·원예용품)
            "모형", "인조", "장식", "장난감", "피규어", "미니어처",
            "그림책", "동화책", "스티커", "색칠", "교구", "학습",
            "케이스", "커버", "파우치", "스마트폰", "휴대폰", "아이폰",
            "도어쿠션", "쿠션커버", "인테리어",
            "지지대", "지지끈", "원예", "정원", "식물지지",
            "스프레드", "잼", "소스", "드레싱",
            "시뮬레이션", "가짜", "조화",
        ],
        "고추":   ["고추장", "고춧가루", "고추기름", "고추소스"],
        "마늘":   ["마늘장아찌", "마늘소스", "마늘분말", "흑마늘즙", "흑마늘진액"],
        "생강":   ["생강청", "생강즙", "생강차", "생강분말"],
        "양파":   ["양파즙", "양파분말", "양파장아찌"],
        "대파":   ["파김치"],
        "쪽파":   ["파김치"],
        "콩":     ["두부", "콩나물", "된장", "간장", "청국장", "두유", "콩기름", "콩가루"],
        "팥":     ["팥앙금", "팥소", "팥죽", "팥빙수"],
        "쌀":     ["쌀가루", "쌀국수", "쌀과자", "쌀밥", "쌀죽", "쌀떡"],
        "보리":   ["보리차", "보리음료"],
        "밀":     ["밀가루", "밀국수", "밀떡"],
        "감자":   ["감자칩", "감자전분", "감자튀김"],
        "고구마": ["고구마말랭이", "고구마칩", "고구마전분"],
        "사과":   ["사과즙", "사과주스", "사과식초", "사과잼"],
        "배":     ["배즙", "배주스", "배청"],
        "포도":   ["포도주스", "포도주", "와인"],
        "딸기":   ["딸기잼", "딸기주스", "딸기청"],
        "토마토": ["토마토주스", "토마토소스", "토마토케첩", "케첩"],
        "당근":   ["당근주스"],
        "시금치": ["시금치즙"],
        "쇠고기": ["육포", "소고기장조림", "소고기국"],
        "돼지고기": ["돼지고기장조림", "삼겹살구이"],
        "닭고기": [
            "닭강정", "닭볶음탕", "닭볶음",
            # KAMIS "닭/육계(kg)"는 손질 전 생닭(육계) 소매가 기준인데, 애드픽
            # 제휴몰(11번가/SSG/컬리/GS SHOP/Hmall/CJ더마켓/롯데홈쇼핑) 재고에는
            # 생닭 자체가 없고 특정 부위·가공품만 있어 지금까지 부위/조리 상태가
            # 다른 상품이 오매칭되어 왔음(예: 닭목살 안주, 간장닭 다리살 스테이크,
            # 옛날통닭). 부위명·가공/조리 키워드를 제외해 생닭과 다른 상품은
            # 아예 매칭되지 않도록 함 (결과가 0개면 아래에서 폴백 없이 그대로 0개
            # 유지 — "살 곳이 없으면 글감으로 부적합"이라는 기존 원칙 그대로 적용).
            "닭가슴살", "닭다리살", "닭목살", "닭날개", "닭발", "닭꼬치",
            "훈제", "스테이크", "술안주", "안주", "튀김", "너겟", "까스", "커틀릿",
            "통닭", "치킨", "후라이드", "양념치킨",
        ],
        "계란":   ["계란찜", "계란말이", "계란장조림"],
        "고등어": ["고등어통조림", "고등어조림"],
        "갈치":   ["갈치조림"],
        "오징어": ["오징어채", "오징어볶음", "오징어젓"],
    }

    # 현재 검색 키워드에 해당하는 가공식품 제외 키워드 적용
    item_exclude = ITEM_EXCLUDE_KEYWORDS.get(search_keyword, [])
    if item_exclude:
        exclude_filtered = []
        for it in items:
            title = (it.get("title") or "")
            if any(kw in title for kw in item_exclude):
                continue
            exclude_filtered.append(it)
        # 가공식품 제외는 핵심 필터이므로 결과가 1개여도 유지 (0개면 원본 사용).
        # 단, "닭고기"는 예외 — 애드픽 재고에 생닭 자체가 없어 제외 후 0개가
        # 정상적인 결과이므로(폴백하면 매번 부위 다른 가공품이 다시 섞여 들어옴),
        # 원본으로 되돌리지 않고 0개를 그대로 유지한다.
        if search_keyword == "닭고기":
            items = exclude_filtered
        else:
            items = exclude_filtered if len(exclude_filtered) >= 1 else items

    # ── 먹을 수 없는 제품 필터링 ────────────────────────────────────────────
    # 식품 사이트이므로 비식품 키워드가 제목에 포함된 상품 제외
    NON_FOOD_KEYWORDS = [
        # 생활용품/주방용품 - 조리기구
        "냄비", "프라이팬", "도마", "칼", "그릇", "접시", "컵", "머그",
        "용기", "보관함", "밀폐용기", "지퍼백", "랩", "호일",
        "바구니", "채반", "체", "강판", "믹서", "블렌더",
        # 볼/믹싱볼류
        "믹싱볼", "스텐볼", "볼세트", "샐러드볼", "보울", "스텐레스볼",
        # 조리도구
        "집게", "주걱", "국자", "뒤집개", "거품기", "스패츌라",
        "냄비받침", "냄비뚜껑", "냄비세트", "냄비뚜껑",
        "조리도구", "주방도구", "주방용품", "주방기구",
        "수저", "젓가락", "포크", "스푼", "나이프",
        "도시락", "도시락통", "찜기", "압력솥", "솥",
        "전기밥솥", "에어프라이어", "전자레인지",
        # 농업/원예용품 및 농기구
        "씨앗", "종자", "모종", "비료", "농약", "살충제", "제초제",
        "화분", "화분받침", "원예", "텃밭", "재배키트",
        "예초기", "예초기날", "나일론날", "예초날", "잔디깎기", "잔디깎이",
        "낫", "호미", "삽", "괭이", "쇠스랑", "갈퀴",
        "분무기", "스프레이건", "물뿌리개",
        # 의류/패션
        "앞치마", "장갑", "토시",
        # 반려동물 사료 (단, 사람이 먹는 것과 구분)
        "사료", "펫푸드", "강아지간식", "고양이간식",
        # 문구/사무용품/종이류
        "바람지", "색지", "도화지", "A4", "복사지", "노트", "스케치북",
        "크레파스", "색연필", "사인펜", "볼펜", "연필", "지우개",
        "인의예지", "한지", "습자지", "화선지", "켄트지", "모조지",
        "문구", "사무용", "팬시", "학용품",
        # 가공식품/즉석식품/완제품 (원재료가 아닌 완제품)
        "삼계탕", "갈비탕", "설렁탕", "곰탕", "육개장", "순대국",
        "빈대떡", "파전", "전병", "부침개",
        "즉석밥", "즉석국", "즉석죽", "레토르트", "간편식",
        "통조림", "햄", "소시지", "어묵", "맛살",
        "라면", "냉면", "우동", "파스타",
        "과자", "스낵", "쿠키", "비스킷", "초콜릿", "사탕", "젤리",
        "음료", "주스", "탄산", "커피", "두유",
        "요거트", "아이스크림", "빙과",
        # 조명/전기용품
        "전구", "꼬마전구", "LED", "조명", "램프", "형광등", "백열등",
        "스탠드", "무드등", "야간등", "취침등", "수면등",
        # 인테리어/장식품 (예: "닭고기 벽걸이장식 철판액자" 같은 정보성 장식품이
        # 재료명을 제목에 포함해 식재료 검색에 잘못 걸리는 경우 방지)
        "벽걸이", "액자", "인테리어소품", "포스터액자", "월데코",
        # 화장품/바디케어/뷰티
        "바디로션", "바디크림", "바디워시", "바디오일", "바디버터", "바디스크럽",
        "샴푸", "린스", "컨디셔너", "트리트먼트", "헤어팩", "헤어오일",
        "선크림", "선스크린", "자외선차단", "비비크림", "파운데이션",
        "립밤", "립스틱", "마스카라", "아이섀도", "블러셔",
        "마스크팩", "시트마스크", "클렌징", "폼클렌저", "클렌징오일",
        "향수", "퍼퓸", "데오도란트",
        "핸드크림", "핸드로션", "풋크림",
        "치약", "칫솔", "구강청결제",
        "버블바스",
        "플라워테라피", "아로마테라피", "테라피로션",
        # 패션/주얼리/악세서리
        "반지", "목걸이", "귀걸이", "팔찌", "발찌", "브로치", "헤어핀", "헤어밴드",
        "시계", "벨트", "지갑", "가방", "파우치", "클러치", "백팩", "숄더백",
        "신발", "구두", "운동화", "슬리퍼", "샌들", "부츠",
        "티셔츠", "셔츠", "바지", "치마", "원피스", "자켓", "코트", "패딩",
        "양말", "스타킹", "레깅스", "속옷", "브라", "팬티",
        "모자", "비니", "캡", "선글라스", "안경",
        "스카프", "머플러", "넥타이",
        # 기타 비식품
        "방향제", "탈취제", "세제", "주방세제",
    ]
    food_filtered = []
    for it in items:
        title = (it.get("title") or "").lower()
        if any(kw in title for kw in NON_FOOD_KEYWORDS):
            continue
        food_filtered.append(it)
    # 필터 후 결과가 너무 적으면 원본 사용
    items = food_filtered if len(food_filtered) >= 2 else items

    # ── 링크 없는 상품 제외 ─────────────────────────────────────────────────
    items = [it for it in items if it.get("link")]

    # ── 해외 상품 제외 ───────────────────────────────────────────────────────
    # 제목에 "[해외]" 태그가 붙거나 알리익스프레스 등 해외 쇼핑몰 상품 제외
    OVERSEAS_TITLE_KEYWORDS = ["[해외]", "해외직구", "알리익스프레스", "aliexpress", "알리"]
    OVERSEAS_MALL_KEYWORDS  = ["알리익스프레스", "aliexpress", "알리", "taobao", "타오바오",
                                "아마존", "amazon", "ebay", "이베이", "위시", "wish",
                                "큐텐", "qoo10", "지마켓글로벌"]
    overseas_filtered = []
    for it in items:
        title = (it.get("title") or "")
        mall  = (it.get("mall")  or "").lower()
        if any(kw in title for kw in OVERSEAS_TITLE_KEYWORDS):
            continue
        if any(kw.lower() in mall for kw in OVERSEAS_MALL_KEYWORDS):
            continue
        overseas_filtered.append(it)
    # 해외 상품은 결과 수와 무관하게 항상 제외 (fallback 없음)
    items = overseas_filtered

    # ── 제휴 쇼핑몰 필터링 ──────────────────────────────────────────────────
    # 애드픽 제휴 쇼핑몰 8개 내에서만 결과를 표시합니다.
    # 실제 애드픽 API cp_name 반환값 기준으로 매핑합니다.
    # (확인된 실제 값: 'GS SHOP', 'Hmall', 'SSG', '롯데홈쇼핑', '11번가', '컬리', 'CJ THE MARKET')
    AFFILIATE_MALL_NAMES = {
        # 실제 API 반환값 (정확한 이름)
        "11번가",
        "SSG",
        "컬리",
        "GS SHOP",
        "Hmall",
        "CJ THE MARKET",
        "롯데홈쇼핑",
        # 변형 표기 대비
        "SSG.COM", "마켓컬리", "GS샵", "이마트몰", "이마트",
        "H몰", "현대홈쇼핑", "CJ더마켓", "CJ온마트", "롯데ON",
    }

    def _is_affiliate_mall(mall_name: str) -> bool:
        if not mall_name:
            return False
        mall_strip = mall_name.strip()
        for affiliate in AFFILIATE_MALL_NAMES:
            if affiliate.lower() in mall_strip.lower() or mall_strip.lower() in affiliate.lower():
                return True
        return False

    affiliate_filtered = [it for it in items if _is_affiliate_mall(it.get("mall", ""))]
    # 제휴몰 필터 후 결과가 1개 이상이면 유지 (0개면 원본 사용)
    items = affiliate_filtered if len(affiliate_filtered) >= 1 else items

    # ── 중량 필터링 ─────────────────────────────────────────────────────────
    # KAMIS 단위(예: "20kg")에서 기준 중량을 추출하여
    # 상품 제목에 명시된 중량이 현저히 다른 상품을 제외합니다.
    # 예: "쌀/20kg" → 4kg, 2kg 상품 제외 / 20kg, 10kg×2포 등은 허용
    items = _filter_by_weight(items, second_part_clean if has_unit_in_second else "")

    # ── KAMIS 가격 대비 범위 필터링 ─────────────────────────────────────────
    # KAMIS 가격이 있을 때: 0.1배 ~ 30배 범위 밖 상품 제외
    # 배율을 넓게 설정하는 이유:
    #   - KAMIS 단위와 쇼핑몰 판매 단위가 다를 수 있음
    #     예) 피망: KAMIS=100g 기준 1,567원 / 쇼핑몰=1~5kg 단위 판매
    #   - 30배 허용 시: 1,567원 × 30 = 47,010원 → 피망 3kg 상품까지 포함
    if kamis_price and kamis_price > 0:
        price_min = kamis_price * 0.1
        price_max = kamis_price * 30.0
        price_filtered = [
            it for it in items
            if it.get("price") is None
            or (price_min <= it["price"] <= price_max)
        ]
        # 필터 후 결과가 너무 적으면 원본 사용
        items = price_filtered if len(price_filtered) >= 2 else items

    if not items:
        return jsonify({"ok": True, "count": 0, "items": []})

    # 가격 오름차순 정렬 후 상위 5개 반환
    items.sort(key=lambda x: x["price"] if x["price"] is not None else 999999999)

    return jsonify({"ok": True, "count": len(items[:5]), "items": items[:5]})


# ---------------------------------------------------------------------------
# API: 생필품(한국소비자원 참가격) 전체 목록 + 가격
# ---------------------------------------------------------------------------
@app.route("/api/consumer-prices")
def consumer_prices():
    """
    한국소비자원 생필품 가격 정보를 반환합니다.

    Query Params:
        q (str): 상품명 검색 키워드 (선택)
        fast (str): "1"이면 가격 조회를 기다리지 않고 상품 목록만 즉시 반환하고,
                     백그라운드에서 가격 정보를 채웁니다.
                     (준비 완료 전까지는 응답에 prices_ready: false 포함)
    """
    keyword = request.args.get("q", "").strip()
    fast = request.args.get("fast", "") == "1"

    try:
        if _CONSUMER_CACHE["ready"] and _CONSUMER_CACHE["items"] is not None:
            # 이미 가격까지 준비된 캐시가 있으면 그대로 사용
            items = _CONSUMER_CACHE["items"]
            prices_ready = True
            inspect_day = ""
            for it in items:
                if it.get("inspect_day"):
                    inspect_day = it["inspect_day"]
                    break
        elif fast:
            # 빠른 응답: 가격 없이 상품 목록만 반환하고 백그라운드에서 가격 로드 시작
            items = _get_consumer_basic_items()
            prices_ready = False
            inspect_day = ""
            if not _CONSUMER_CACHE["loading"]:
                t = threading.Thread(target=_load_consumer_full_items_bg, daemon=True)
                t.start()
        else:
            # 동기 방식: 가격까지 포함해 전체 조회 (느릴 수 있음)
            items = consumer_price_client.get_products_with_prices()
            _CONSUMER_CACHE["items"] = items
            _CONSUMER_CACHE["ready"] = True
            prices_ready = True
            inspect_day = ""
            for it in items:
                if it.get("inspect_day"):
                    inspect_day = it["inspect_day"]
                    break
    except consumer_price_client.ConsumerPriceApiError as e:
        return jsonify({"ok": False, "error": str(e)}), 502

    if keyword:
        items = [it for it in items if keyword in (it.get("good_name") or "")]

    return jsonify({
        "ok": True,
        "count": len(items),
        "items": items,
        "prices_ready": prices_ready,
        "inspect_day": inspect_day,
    })


# ---------------------------------------------------------------------------
# API: 생필품 온라인 최저가 검색 (애드픽 /search API 사용)
# ---------------------------------------------------------------------------
@app.route("/api/consumer-shop-prices")
def consumer_shop_prices():
    """
    애드픽 상품 검색 API를 통해 생필품의 온라인 최저가 상품 목록을 반환합니다.

    Query Params:
        q (str): 검색 상품명, 필수
        price (str): 참가격(원), 선택 - 가격 범위 필터링에 사용
    """
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"ok": False, "error": "q 파라미터는 필수입니다."}), 400

    adpick_key = os.environ.get("ADPICK_API_KEY", "")
    if not adpick_key:
        return jsonify({"ok": False, "error": "ADPICK_API_KEY가 설정되지 않았습니다."}), 500

    ref_price_raw = request.args.get("price", "")
    try:
        ref_price = int(ref_price_raw) if ref_price_raw else None
    except (ValueError, TypeError):
        ref_price = None

    items = adpick_client.search_products(query, limit=20, api_key=adpick_key)

    if not items:
        return jsonify({"ok": True, "count": 0, "items": []})

    # 링크 없는 상품 제외
    items = [it for it in items if it.get("link")]

    # 참가격 대비 범위 필터링 (0.3배 ~ 5배) - 과도하게 동떨어진 가격 제외
    if ref_price and ref_price > 0:
        price_min = ref_price * 0.3
        price_max = ref_price * 5.0
        price_filtered = [
            it for it in items
            if it.get("price") is None or (price_min <= it["price"] <= price_max)
        ]
        items = price_filtered if len(price_filtered) >= 2 else items

    if not items:
        return jsonify({"ok": True, "count": 0, "items": []})

    items.sort(key=lambda x: x["price"] if x["price"] is not None else 999999999)

    return jsonify({"ok": True, "count": len(items[:5]), "items": items[:5]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


