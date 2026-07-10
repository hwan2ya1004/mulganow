# -*- coding: utf-8 -*-
"""
generate_blog_post.py
----------------------
KAMIS 가격 변동이 큰 품목을 골라, 미리 써둔 후킹멘트 템플릿에 실제 데이터를 채워서
frontend/blog/ 아래에 새 글을 자동 발행합니다. (AI API 비용 없음 — 순수 템플릿 방식)

이미 배포된 물가나우 API(mulganow.vercel.app)를 그대로 호출해서 가격/제휴 데이터를
가져오므로, KAMIS·애드픽 인증키는 이 스크립트에 필요 없습니다. 가격·링크·이미지는
항상 실제 데이터 그대로 사용합니다.

실행: python generate_blog_post.py
필요 환경변수: 없음
"""
import json
import os
import random
import re
from datetime import date

import requests

SITE = "https://mulganow.vercel.app"
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BACKEND_DIR, "..", "frontend")
BLOG_DIR = os.path.join(FRONTEND_DIR, "blog")

TOP_N = 3

# 아래 템플릿들은 particle(이/가/은/는 등 받침에 따라 형태가 바뀌는 조사)을
# {item}에 직접 붙이지 않도록 주의해서 작성되어 있습니다. {item}에는 품목명이
# 그대로 들어가는데, 품목마다 받침 유무가 달라 조사가 자동으로 맞지 않기
# 때문입니다. {item} 뒤에는 항상 공백+고정 단어(가격/값 등)나 쉼표/무변화
# 조사(의/도/만/에)만 오도록 유지해주세요.
TITLE_TEMPLATES_DROP = [
    "{item} 값이 뚝! 한 달 새 {pct}% 내렸어요",
    "지금 안 사면 아쉬운 {item}, {pct}% 저렴해졌습니다",
    "{item} {pct}% 하락 — 장바구니 채우기 좋은 타이밍",
    "요즘 {item} 왜 이렇게 싸졌을까? {pct}% 하락 이유",
    "이번 달 {item} 가격 {pct}% 내려간 이유",
    "{item} 값 뚝 떨어진 지금, 장바구니 채우기 좋아요",
    "{pct}% 하락한 {item}, 오늘 시세 확인하고 사세요",
    "슬쩍 내려간 {item} 가격, 눈치채셨나요? ({pct}% 하락)",
]
TITLE_TEMPLATES_SURGE = [
    "{item}값 또 올랐다... 한 달 새 {pct}% 급등",
    "장바구니 비상! {item} {pct}% 뛰었어요",
    "{item} {pct}% 상승, 미리 알아두면 좋은 것들",
    "요즘 {item} 왜 이렇게 비싸졌을까? {pct}% 상승 이유",
    "{item} 값 어디까지 오르나 — 한 달 새 {pct}%",
    "장보기 전 체크! {item} 가격 {pct}% 상승",
    "{pct}% 오른 {item}, 오늘 시세부터 확인하세요",
    "심상치 않은 {item} 가격, 한 달 새 {pct}% 상승",
]

INTRO_TEMPLATES_DROP = [
    "장 보러 가기 전에 알아두면 좋은 소식이에요. 농산물유통정보(KAMIS) 데이터를 보니 {item} 가격이 눈에 띄게 내려갔습니다.",
    "요즘 물가가 계속 오른다고 느끼셨다면, 오늘은 반가운 소식입니다. {item} 가격이 한 달 전보다 뚝 떨어졌어요.",
    "매번 오르기만 하는 것 같은 장바구니 물가, 이번엔 다릅니다. {item} 가격이 큰 폭으로 내렸어요.",
    "가계부에 도움이 될 소식입니다. KAMIS 시세를 보면 {item} 가격이 최근 뚜렷하게 낮아졌어요.",
    "오늘 {item} 구매를 고민 중이라면 타이밍이 좋습니다. 한 달 사이 가격이 눈에 띄게 내렸거든요.",
    "물가 뉴스에 지칠 때쯤 반가운 소식 하나, {item} 가격이 최근 눈에 띄게 내려왔습니다.",
]
INTRO_TEMPLATES_SURGE = [
    "장 보러 가기 전에 미리 알아두시면 좋을 소식이에요. 농산물유통정보(KAMIS) 데이터를 보니 {item} 가격이 눈에 띄게 올랐습니다.",
    "이번 주 장바구니 물가, 조금 부담스러워질 수 있어요. {item} 가격이 한 달 전보다 크게 뛰었습니다.",
    "'요즘 왜 이렇게 비싸졌지?' 싶으셨다면 이유가 있었습니다. {item} 값이 큰 폭으로 상승했어요.",
    "장보기 계획을 세우신다면 참고하세요. KAMIS 시세를 보면 {item} 가격이 최근 뚜렷하게 높아졌습니다.",
    "오늘 {item} 구매를 고민 중이라면 미리 알아두세요. 한 달 사이 가격이 꽤 많이 올랐거든요.",
    "물가 뉴스가 남 얘기 같지 않죠. {item} 가격도 최근 눈에 띄게 올랐습니다.",
]

HEADING_TEMPLATES_DROP = [
    "📉 {item}, 지금이 살 타이밍",
    "💰 {item}, 이번 주는 저렴해요",
    "🛒 {item} 최저가 챙기기",
    "🔎 {item}, 오늘 시세 확인",
    "✅ {item} 지금 사도 좋은 이유",
    "🧺 {item} 장바구니에 담기 좋은 타이밍",
]
HEADING_TEMPLATES_SURGE = [
    "📈 {item}, 미리 챙겨두세요",
    "⚠️ {item}, 가격 오르기 전에",
    "🛒 {item} 그나마 싸게 사는 법",
    "🧊 {item}, 오르기 전 서둘러 담기",
    "⏰ {item}, 더 오르기 전에",
    "🔍 {item} 대체재도 함께 살펴보기",
]

BODY_TEMPLATES_DROP = [
    "{item} 가격이 한 달 전 {month_ago}원에서 오늘 {today}원으로 내려갔어요. 아래에서 오늘 기준 최저가를 확인해보세요.",
    "한 달 전 {month_ago}원이었던 {item}, 오늘은 {today}원이에요. 지금 사두면 알뜰하게 장 볼 수 있습니다.",
    "{item} 시세가 한 달 전 {month_ago}원에서 오늘 {today}원까지 내려왔어요. 지금이 상대적으로 저렴하게 살 수 있는 시점입니다.",
    "{month_ago}원이었던 {item} 가격이 오늘은 {today}원까지 내려왔습니다. 아래 최저가 링크에서 오늘 시세를 확인해보세요.",
]
BODY_TEMPLATES_SURGE = [
    "{item} 가격이 한 달 전 {month_ago}원에서 오늘 {today}원으로 올랐어요. 그래도 아래에서 상대적으로 저렴한 곳을 찾아보세요.",
    "한 달 전 {month_ago}원이었던 {item}, 오늘은 {today}원이 됐어요. 오르기 전에 미리 구매해두는 것도 방법입니다.",
    "{item} 시세가 한 달 전 {month_ago}원에서 오늘 {today}원까지 올랐어요. 그래도 아래에서 상대적으로 저렴한 곳을 찾아보세요.",
    "{month_ago}원이었던 {item} 가격이 오늘은 {today}원이 됐습니다. 더 오르기 전에 아래 최저가부터 확인해보세요.",
]

# ---------------------------------------------------------------------------
# 생필품(한국소비자원 참가격) 후킹멘트 템플릿
# 생필품은 KAMIS처럼 "한 달 전 대비" 데이터가 없어서(참가격은 스냅샷 조사),
# 대신 "참가격 대비 실제 최저가가 얼마나 저렴한가"를 후킹 포인트로 씁니다.
# {pct}에는 savings_pct(참가격 대비 절약율)가 들어갑니다.
# ---------------------------------------------------------------------------
TITLE_TEMPLATES_CONSUMER = [
    "{item}, 매장보다 온라인이 {pct}% 저렴해요",
    "이번 주 생필품 특가 — {item} {pct}% 아끼는 법",
    "{item} 살 때 이렇게 사면 {pct}% 절약돼요",
    "매번 사는 {item}, 최저가는 따로 있었습니다 ({pct}% 절약)",
]
INTRO_TEMPLATES_CONSUMER = [
    "매일 쓰는 생필품, 어디서 사느냐에 따라 가격 차이가 꽤 큽니다. 한국소비자원 참가격 데이터와 실시간 최저가를 비교해봤어요.",
    "장바구니에 매번 담는 생필품, 이번엔 최저가부터 확인하고 담아보세요. 참가격 대비 얼마나 저렴한지 정리했습니다.",
    "생필품도 비교하고 사면 확실히 다릅니다. 참가격 조사 데이터를 기준으로 지금 가장 저렴하게 살 수 있는 곳을 찾아봤어요.",
]
HEADING_TEMPLATES_CONSUMER = [
    "🧴 {item}, 최저가로 사는 법",
    "💡 {item} 이렇게 사면 이득",
    "🛍️ {item} 참가격 대비 최저가",
]
BODY_TEMPLATES_CONSUMER = [
    "{item}의 참가격은 {participating}원인데, 지금 온라인 최저가는 {online}원이에요. 아래에서 바로 확인해보세요.",
    "한국소비자원 참가격 기준 {participating}원인 {item}, 지금은 {online}원에도 구매할 수 있어요.",
]

GA_HEAD = """<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-T8KNQN27VH"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-T8KNQN27VH');
</script>"""

VERIFY_HEAD = """<meta name="google-site-verification" content="_ssrX9gXHP9iYfdACZJU4u5T-Jx-iURQmcztFFRcBEY" />
<meta name="naver-site-verification" content="fabc62886e0eb42196604cca71e871032ddc4446" />"""

# 전자상거래법상 통신판매업자 정보 표시 의무 — 사이트 전체 footer(.site-footer)에
# 공통으로 들어가야 합니다. index.html/consumer.html/blog/index.html 등 정적
# 페이지에도 동일한 문구가 들어가 있으니, 내용을 바꿀 땐 그쪽도 함께 갱신해주세요.
BUSINESS_INFO_HTML = """  <p style="margin-top:8px;">
    상호명: 서희연구소 | 대표자: 김성환<br>
    사업자등록번호: 832-29-01692 (간이과세자)<br>
    통신판매업 신고번호: 제2026-화성동탄-2143호<br>
    주소: 경기도 화성시 동탄순환대로17길 15
  </p>"""

# ---------------------------------------------------------------------------
# 절기/명절 등 한국 계절 이벤트 테이블 (기획팀 요청 #1)
# ----------------------------------------------------------------------------
# 일반 음력 계산은 하지 않고, 가까운 시일 내 이벤트 날짜를 그냥 하드코딩합니다.
# (복날/명절은 매년 날짜가 바뀌므로 이 목록은 대략 연 1회 정도 최신화가
#  필요합니다 — 다음 갱신 시 검색으로 다음 해 날짜를 확인해서 추가하세요.)
#
# 각 이벤트는 아래 중 하나의 날짜 지정 방식을 가집니다:
#   - "date": 특정 하루 (예: 복날, 명절 당일). "lead_days"일 전부터 발동.
#   - "start"/"end": 기간에 걸친 이벤트 (예: 장마, 김장철). 기간 내내 발동.
#
# keywords          : 농산물(today-prices) item_name에 포함되면 매칭되는 키워드
# consumer_keywords : 생필품(consumer-prices) good_name에 포함되면 매칭되는 키워드
SEASONAL_EVENTS = [
    {
        "name": "초복",
        "date": "2026-07-15",
        "lead_days": 5,
        "keywords": ["닭", "삼계", "마늘", "대추", "황기", "전복", "장어", "인삼"],
        "consumer_keywords": ["삼계탕", "홍삼", "영양제"],
    },
    {
        "name": "중복",
        "date": "2026-07-25",
        "lead_days": 5,
        "keywords": ["닭", "삼계", "마늘", "대추", "황기", "전복", "장어", "인삼"],
        "consumer_keywords": ["삼계탕", "홍삼", "영양제"],
    },
    {
        "name": "말복",
        "date": "2026-08-14",
        "lead_days": 5,
        "keywords": ["닭", "삼계", "마늘", "대추", "황기", "전복", "장어", "인삼"],
        "consumer_keywords": ["삼계탕", "홍삼", "영양제"],
    },
    {
        "name": "장마",
        "start": "2026-06-19",
        "end": "2026-07-25",
        # 장마철엔 엽채류(상추/배추 등)가 출하량 감소로 값이 크게 뛰는 경우가 많아 체감도가 높음
        "keywords": ["상추", "배추", "시금치", "오이", "애호박", "깻잎"],
        "consumer_keywords": ["제습제", "습기제거제", "곰팡이", "우산", "장화"],
    },
    {
        "name": "추석",
        "date": "2026-09-25",
        "lead_days": 10,
        "keywords": ["사과", "배", "밤", "대추", "곶감", "잣", "한과", "쌀", "송편", "소고기"],
        "consumer_keywords": ["선물세트", "참기름", "식용유", "한과"],
    },
    {
        "name": "김장철",
        "start": "2026-11-15",
        "end": "2026-12-10",
        "keywords": ["배추", "무", "마늘", "고춧가루", "생강", "대파", "쪽파", "젓갈"],
        "consumer_keywords": ["고무장갑", "비닐장갑", "소금"],
    },
    {
        "name": "동지",
        "date": "2026-12-22",
        "lead_days": 5,
        "keywords": ["팥", "찹쌀"],
        "consumer_keywords": [],
    },
    {
        "name": "설날",
        "date": "2027-02-07",
        "lead_days": 10,
        "keywords": ["사과", "배", "밤", "대추", "곶감", "잣", "한과", "쌀", "소고기", "동태", "명태"],
        "consumer_keywords": ["선물세트", "참기름", "식용유", "한과"],
    },
]

# 이벤트 날짜가 지정되지 않은 경우(방어적 기본값)에만 쓰이는 리드타임
SEASONAL_LEAD_DAYS_DEFAULT = 5


def active_seasonal_events(today=None):
    """오늘 기준으로 발동 중인(리드타임 이내이거나 기간 내인) 계절 이벤트 목록을 반환합니다."""
    today = today or date.today()
    active = []
    for ev in SEASONAL_EVENTS:
        if "date" in ev:
            ev_date = date.fromisoformat(ev["date"])
            lead = ev.get("lead_days", SEASONAL_LEAD_DAYS_DEFAULT)
            days_until = (ev_date - today).days
            if 0 <= days_until <= lead:
                active.append(ev)
        elif "start" in ev and "end" in ev:
            start = date.fromisoformat(ev["start"])
            end = date.fromisoformat(ev["end"])
            if start <= today <= end:
                active.append(ev)
    return active


# ---------------------------------------------------------------------------
# 생필품(한국소비자원 참가격) 소분류 코드(goodSmlclsCode) → 카테고리명 매핑
# frontend/consumer.js의 CAT_MAP과 동일한 매핑을 그대로 옮겨왔습니다.
# (카테고리 다양성 가드 + 후킹멘트 표시용으로만 쓰이며, 화면 표시와 어긋나지
#  않도록 프론트엔드 쪽 매핑이 바뀌면 이쪽도 함께 갱신해주세요.)
# ---------------------------------------------------------------------------
CONSUMER_CAT_MAP = {
    "030101": "신선식품",
    "030102": "채소·농산물",
    "030103": "수산물",
    "030201": "가공식품",
    "030202": "수산가공품",
    "030203": "유제품·육가공",
    "030204": "조미료·양념",
    "030205": "과자·빙과",
    "030206": "음료·주류",
    "030301": "위생·바디케어",
    "030302": "생활용품·세제",
    "030304": "의약외품·뷰티",
    "030305": "반려동물",
}


def consumer_category_name(smlcls_code):
    if not smlcls_code:
        return "기타"
    return CONSUMER_CAT_MAP.get(smlcls_code[:6], "기타")


# ---------------------------------------------------------------------------
# 픽 개수/다양성/생필품 반영 비율 관련 튜닝 상수 (기획팀 요청 #2, #4)
# ---------------------------------------------------------------------------
# 한 카테고리에서 몇 개까지 뽑을지의 기본 상한. "최고 변동 품목" 취지를 크게
# 해치지 않는 선에서, TOP_N개 중 절반을 살짝 넘는 수준까지만 한 카테고리를
# 허용합니다 (TOP_N=3이면 카테고리당 최대 2개).
DEFAULT_MAX_PER_CATEGORY = max(1, (TOP_N + 1) // 2)

# 생필품은 "참가격 대비 온라인이 이만큼 저렴하다"가 후킹 포인트이므로, 차이가
# 너무 작으면 설득력이 없습니다. 최소 이 비율(%) 이상 저렴한 상품만 후보로 삼습니다.
MIN_CONSUMER_SAVINGS_PCT = 8

# 애드픽 검색 API 호출 비용을 제한하기 위해, 생필품 후보 중 이 개수만 표본
# 조사합니다 (전수조사하면 매 실행마다 수백 건씩 외부 API를 호출하게 됨).
CONSUMER_PROBE_LIMIT = 25

# 이번 실행에서 생필품 데이터를 얼마나 섞을지에 대한 기본 확률.
# (절기 이벤트가 생필품과 직접 연관되는 경우—예: 장마철 제습제—는 이 확률과
#  무관하게 우선 반영됩니다. main()의 관련 로직 참고.)
CONSUMER_ONLY_PROB = 0.2   # 이번 실행을 생필품 단독 포스트로 진행할 확률
CONSUMER_BLEND_PROB = 0.3  # (단독이 아닐 때) 농산물 포스트에 생필품 1개를 섞을 확률


def fetch_today_prices():
    r = requests.get(f"{SITE}/api/today-prices", params={"cls": "01"}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"today-prices 응답 실패: {data}")
    return data["items"]


def fetch_shop_picks(item, limit=2):
    q = item.get("item_name") or ""
    unit = item.get("unit") or "1kg"
    price = item.get("today_price")
    try:
        r = requests.get(
            f"{SITE}/api/shop-prices",
            params={"q": q, "unit": unit, "price": price},
            timeout=20,
        )
    except requests.RequestException:
        return []
    if r.status_code != 200:
        return []
    data = r.json()
    if not data.get("ok"):
        return []
    picks = [it for it in data.get("items", []) if it.get("link") and it.get("image")]
    return picks[:limit]


def fetch_consumer_prices():
    """생필품(한국소비자원 참가격) 목록을 가져옵니다.

    fast=1로 호출하면 서버가 커밋된 스냅샷(GitHub Actions가 주기적으로 최신화)이
    준비돼 있을 때는 바로 가격 포함 데이터를 주고, 아직 아무 캐시도 없을 때만
    가격 없이 상품 목록만 즉시 반환하고 백그라운드 조회를 시작합니다. 이 스크립트는
    1회성 실행이라 백그라운드 조회 완료를 기다릴 수 없으므로, prices_ready가
    False면 이번 실행에서는 생필품 후보를 그냥 건너뜁니다.
    """
    r = requests.get(f"{SITE}/api/consumer-prices", params={"fast": "1"}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"consumer-prices 응답 실패: {data}")
    if not data.get("prices_ready"):
        return []
    return data.get("items", [])


def clean_consumer_name(good_name):
    """'대표 세숫비누(1kg)'처럼 뒤에 붙는 용량/규격 표기를 떼어 표시/검색용 이름을 만듭니다."""
    name = re.sub(r"\s*\([^)]*\)\s*$", "", good_name or "").strip()
    return name or (good_name or "").strip()


def fetch_consumer_shop_picks(name, price, limit=2):
    try:
        r = requests.get(
            f"{SITE}/api/consumer-shop-prices",
            params={"q": name, "price": price},
            timeout=20,
        )
    except requests.RequestException:
        return []
    if r.status_code != 200:
        return []
    data = r.json()
    if not data.get("ok"):
        return []
    picks = [
        it for it in data.get("items", [])
        if it.get("link") and it.get("image") and isinstance(it.get("price"), (int, float))
    ]
    return picks[:limit]


def _diversify_by_category(candidates, n, max_per_category, category_of):
    """카테고리 다양성 가드 (기획팀 요청 #4).

    candidates는 이미 우선순위(절기 매칭 → 등락폭 등) 순으로 정렬돼 있다고 가정합니다.
    카테고리당 max_per_category개까지만 우선 채우고, n개를 못 채웠으면 상한에 걸려
    보류됐던 나머지 후보로 순서대로 백필합니다 (품절/제휴링크 없음 등으로 뽑을 게
    부족한 상황에서도 "다양성 지키려다 아예 글감이 안 나오는" 사태를 막기 위함).
    """
    picked = []
    deferred = []
    category_counts = {}
    for c in candidates:
        if len(picked) >= n:
            break
        cat = category_of(c)
        if category_counts.get(cat, 0) >= max_per_category:
            deferred.append(c)
            continue
        picked.append(c)
        category_counts[cat] = category_counts.get(cat, 0) + 1
    if len(picked) < n:
        for c in deferred:
            if len(picked) >= n:
                break
            picked.append(c)
    return picked


def pick_candidates(items, n=TOP_N, seasonal_keywords=None, max_per_category=None):
    """농산물 후보를 고릅니다.

    기본은 기존과 동일하게 |전월 대비 등락률| 순이지만, seasonal_keywords가 주어지면
    (예: 복날 임박 → 닭/마늘/대추 등) 해당 키워드에 매칭되는 품목을 등락폭과 무관하게
    먼저 후보 풀 앞쪽에 배치합니다 (기획팀 요청 #1). 그 다음 카테고리 다양성 가드를
    적용해 최종 n개를 뽑습니다 (기획팀 요청 #4).
    """
    if max_per_category is None:
        max_per_category = DEFAULT_MAX_PER_CATEGORY

    scored = [it for it in items if isinstance(it.get("month_change_pct"), (int, float))]

    if seasonal_keywords:
        seasonal = [it for it in scored if any(kw in (it.get("item_name") or "") for kw in seasonal_keywords)]
        seasonal_names = {it.get("item_name") for it in seasonal}
        rest = [it for it in scored if it.get("item_name") not in seasonal_names]
    else:
        seasonal, rest = [], scored
    seasonal.sort(key=lambda it: abs(it["month_change_pct"]), reverse=True)
    rest.sort(key=lambda it: abs(it["month_change_pct"]), reverse=True)
    ordered = seasonal + rest

    # 이름 중복 제거 (동일 품목이 등급/단위별로 여러 행일 수 있음)
    deduped = []
    seen_names = set()
    for it in ordered:
        name = it.get("item_name")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        deduped.append(it)

    ranked = _diversify_by_category(
        deduped,
        n=len(deduped),  # 아래에서 제휴링크 유무로 다시 걸러야 하므로 일단 전부 다양화 순서만 정함
        max_per_category=max_per_category,
        category_of=lambda it: it.get("category_name") or "기타",
    )

    enriched = []
    for it in ranked:
        picks = fetch_shop_picks(it)
        if len(picks) < 1:
            continue  # 살 곳이 없으면 제휴 마케팅 글감으로 부적합
        enriched.append({"kind": "produce", "item": it, "picks": picks})
        if len(enriched) >= n:
            break
    return enriched


def pick_consumer_candidates(items, n=TOP_N, keywords=None, max_per_category=None):
    """생필품 후보를 고릅니다 (기획팀 요청 #2).

    KAMIS 농산물과 달리 참가격 API에는 "한 달 전 대비" 같은 시계열 비교 필드가
    없습니다(매주 스냅샷 조사). 그래서 등락률 대신 "참가격 대비 실제 온라인
    최저가가 얼마나 저렴한가(savings_pct)"를 후킹 포인트로 사용합니다 — 이게
    바로 애드픽 클릭으로 이어지는 실질적인 가치이기도 합니다.

    다만 savings_pct는 애드픽 검색을 실제로 해봐야 알 수 있어서, 전체 상품을
    다 조회하면 API 호출이 너무 많아집니다. 그래서 CONSUMER_PROBE_LIMIT개만
    표본 조사합니다 (절기 키워드 매칭 품목을 우선 조사 대상에 넣음).

    keywords가 주어지면 매칭되는 품목만 조사 대상으로 삼습니다(무관한 나머지
    품목으로 채우지 않음). 절기 문맥(예: 복날)을 이유로 이 함수를 호출했는데
    막상 결과가 에스프레소 캡슐처럼 전혀 무관한 품목이면 "절기 특집"이라는
    말이 무색해지기 때문입니다 — 매칭 품목이 부족하면 그냥 n개 미만(또는 0개)을
    반환하고, 호출부(main())가 일반 흐름으로 자연스럽게 폴백하도록 둡니다.
    """
    if max_per_category is None:
        max_per_category = DEFAULT_MAX_PER_CATEGORY

    candidates = [it for it in items if isinstance(it.get("price"), (int, float)) and it.get("price")]
    if not candidates:
        return []

    if keywords:
        ordered = [it for it in candidates if any(kw in (it.get("good_name") or "") for kw in keywords)]
        random.shuffle(ordered)
    else:
        ordered = candidates[:]
        random.shuffle(ordered)

    probed = []
    seen_names = set()
    enough = max(n * 3, 6)  # 다양성 백필까지 고려해 조금 여유 있게 확보되면 조기 종료
    for it in ordered[:CONSUMER_PROBE_LIMIT]:
        if len(probed) >= enough:
            break
        name = clean_consumer_name(it.get("good_name"))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        price = it["price"]
        picks = fetch_consumer_shop_picks(name, price)
        if not picks:
            continue
        prices = [p["price"] for p in picks if isinstance(p.get("price"), (int, float)) and p["price"] > 0]
        if not prices:
            continue
        best = min(prices)
        savings_pct = round((price - best) / price * 100, 1)
        if savings_pct < MIN_CONSUMER_SAVINGS_PCT:
            continue
        probed.append({
            "kind": "consumer",
            "item": {
                "item_name": name,
                "category_name": consumer_category_name(it.get("smlcls_code")),
                "participating_price": price,
                "best_price": best,
                "savings_pct": savings_pct,
            },
            "picks": picks,
        })

    probed.sort(key=lambda e: e["item"]["savings_pct"], reverse=True)

    return _diversify_by_category(
        probed,
        n=n,
        max_per_category=max_per_category,
        category_of=lambda e: e["item"]["category_name"],
    )


def already_posted_today():
    if not os.path.isdir(BLOG_DIR):
        return False
    today = date.today().isoformat()
    return any(f.startswith(today) for f in os.listdir(BLOG_DIR))


def generate_copy(enriched):
    """AI 없이, 실제 데이터를 후킹멘트 템플릿에 채워서 카피를 만듭니다.

    enriched의 각 원소는 "kind"가 "produce"(농산물, KAMIS 등락률 기반) 또는
    "consumer"(생필품, 참가격 대비 절약율 기반)이며, 서로 다른 템플릿 풀을 씁니다.
    """
    primary_e = enriched[0]
    primary = primary_e["item"]

    if primary_e["kind"] == "consumer":
        pct = primary["savings_pct"]
        title = random.choice(TITLE_TEMPLATES_CONSUMER).format(item=primary["item_name"], pct=pct)
        intro = random.choice(INTRO_TEMPLATES_CONSUMER).format(item=primary["item_name"])
        meta_description = f"{primary['item_name']} 참가격 대비 {pct}% 저렴한 최저가 등, 실제로 사기 좋은 생필품을 정리했습니다."
    else:
        primary_pct = primary["month_change_pct"]
        primary_drop = primary_pct < 0
        title_pool = TITLE_TEMPLATES_DROP if primary_drop else TITLE_TEMPLATES_SURGE
        intro_pool = INTRO_TEMPLATES_DROP if primary_drop else INTRO_TEMPLATES_SURGE
        title = random.choice(title_pool).format(item=primary["item_name"], pct=abs(primary_pct))
        intro = random.choice(intro_pool).format(item=primary["item_name"])
        meta_description = f"{primary['item_name']} {abs(primary_pct)}% {'하락' if primary_drop else '상승'} 등, 이번 주 장바구니 물가 변동을 KAMIS 데이터로 정리했습니다."

    items = []
    for e in enriched:
        it = e["item"]
        if e["kind"] == "consumer":
            heading = random.choice(HEADING_TEMPLATES_CONSUMER).format(item=it["item_name"])
            body = random.choice(BODY_TEMPLATES_CONSUMER).format(
                item=it["item_name"],
                participating=f"{it['participating_price']:,}",
                online=f"{it['best_price']:,}",
            )
        else:
            pct = it["month_change_pct"]
            drop = pct < 0
            heading = random.choice(HEADING_TEMPLATES_DROP if drop else HEADING_TEMPLATES_SURGE).format(
                item=it["item_name"]
            )
            body = random.choice(BODY_TEMPLATES_DROP if drop else BODY_TEMPLATES_SURGE).format(
                item=it["item_name"],
                month_ago=f"{it['month_ago_price']:,}",
                today=f"{it['today_price']:,}",
            )
        items.append({"heading": heading, "body": body})

    return {
        "title": title,
        "meta_description": meta_description,
        "intro": intro,
        "items": items,
    }


def slugify_date_prefixed(raw_slug: str = "price-watch") -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", raw_slug.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return f"{date.today().isoformat()}-{slug}"


def render_shop_pick_html(pick):
    title = (pick.get("title") or "").replace("<", "&lt;").replace(">", "&gt;")
    mall = (pick.get("mall") or "").replace("<", "&lt;").replace(">", "&gt;")
    price = pick.get("price")
    price_str = f"{price:,}원" if isinstance(price, (int, float)) else "-"
    return f"""      <a class="shop-pick" href="{pick['link']}" target="_blank" rel="nofollow sponsored noopener">
        <img src="{pick['image']}" alt="{title}">
        <div class="shop-pick-info">
          <div class="shop-pick-mall">{mall}</div>
          <div class="shop-pick-title">{title}</div>
        </div>
        <div class="shop-pick-price">{price_str}</div>
      </a>"""


def render_post_html(meta, enriched, slug):
    today_iso = date.today().isoformat()
    today = date.today().strftime("%Y.%m.%d")
    url = f"{SITE}/blog/{slug}.html"

    has_produce = any(e["kind"] == "produce" for e in enriched)
    has_consumer = any(e["kind"] == "consumer" for e in enriched)

    stat_boxes = []
    sections = []
    for e, ai_item in zip(enriched, meta["items"]):
        it = e["item"]
        if e["kind"] == "consumer":
            stat_boxes.append(f"""      <div class="stat-box">
        <div class="label">{it['item_name']}</div>
        <div class="value">▼ {it['savings_pct']}%</div>
        <div class="sub">참가격 {it['participating_price']:,}원 → 최저가 {it['best_price']:,}원</div>
      </div>""")
        else:
            pct = it["month_change_pct"]
            arrow = "▼" if pct < 0 else "▲"
            stat_boxes.append(f"""      <div class="stat-box">
        <div class="label">{it['item_name']}</div>
        <div class="value">{arrow} {abs(pct)}%</div>
        <div class="sub">{it['month_ago_price']:,}원 → {it['today_price']:,}원</div>
      </div>""")

        picks_html = "\n".join(render_shop_pick_html(p) for p in e["picks"])
        sections.append(f"""    <h2>{ai_item['heading']}</h2>
    <p>{ai_item['body']}</p>
    <div class="shop-pick-list">
{picks_html}
    </div>""")

    stat_row_html = "\n".join(stat_boxes)
    sections_html = "\n\n".join(sections)

    # 이번 글에 포함된 데이터 종류(농산물/생필품)에 따라 출처 표기·안내 문단·CTA를 다르게 구성
    source_notes = []
    if has_produce:
        source_notes.append("소매가 기준, 최근 1개월 대비 · 자료: KAMIS 농산물유통정보")
    if has_consumer:
        source_notes.append("자료: 한국소비자원 참가격")
    source_line = " / ".join(source_notes)

    if has_consumer and not has_produce:
        info_heading = "매주 갱신되는 참가격, 실시간으로 확인하는 법"
        info_body = (
            "여기 나온 참가격은 한국소비자원이 매주 조사해 발표하는 값이고, "
            "온라인 최저가는 오늘 기준입니다. 다른 생필품까지 포함해서 참가격과 "
            "최저가를 한눈에 보고 싶다면 물가나우에서 바로 확인할 수 있어요."
        )
        cta_href = f"{SITE}/consumer"
        cta_label = "🧴 물가나우에서 생필품 최저가 전체 보기"
    else:
        info_heading = "매일 바뀌는 가격, 실시간으로 확인하는 법"
        info_body = (
            "여기 나온 가격은 오늘 기준이고, KAMIS 데이터는 매일 갱신됩니다. "
            "다른 품목까지 포함해서 오늘 시세와 전월·전년 대비 변동률을 한눈에 "
            "보고 싶다면 물가나우에서 바로 확인할 수 있어요."
        )
        cta_href = f"{SITE}/"
        cta_label = "🛒 물가나우에서 오늘 농산물 가격 전체 보기"

    extra_cta = ""
    if has_consumer and has_produce:
        extra_cta = f'\n\n    <a class="app-cta" href="{SITE}/consumer">🧴 물가나우에서 생필품 최저가도 확인하기</a>'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

{GA_HEAD}

<title>{meta['title']} | 물가나우</title>
<meta name="description" content="{meta['meta_description']}">
{VERIFY_HEAD}
<link rel="canonical" href="{url}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%9B%92%3C/text%3E%3C/svg%3E">

<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{meta['title']}">
<meta property="og:description" content="{meta['meta_description']}">
<meta property="og:image" content="{SITE}/og-image.svg">
<meta property="og:site_name" content="물가나우">
<meta property="og:locale" content="ko_KR">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{meta['title']}">
<meta name="twitter:description" content="{meta['meta_description']}">
<meta name="twitter:image" content="{SITE}/og-image.svg">

<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": {json.dumps(meta['title'], ensure_ascii=False)},
  "description": {json.dumps(meta['meta_description'], ensure_ascii=False)},
  "datePublished": "{today_iso}",
  "dateModified": "{today_iso}",
  "author": {{ "@type": "Organization", "name": "물가나우" }},
  "publisher": {{
    "@type": "Organization",
    "name": "물가나우",
    "logo": {{ "@type": "ImageObject", "url": "{SITE}/og-image.svg" }}
  }},
  "mainEntityOfPage": "{url}",
  "inLanguage": "ko-KR"
}}
</script>

<link rel="stylesheet" href="/style.css">
<link rel="stylesheet" href="/blog/blog.css">
</head>
<body>

<header class="topbar" id="topbar" style="opacity:1;">
  <a href="/" class="brand" style="text-decoration:none;color:inherit;">
    <div class="brand-logo">🛒</div>
    <div class="brand-text">
      <span class="brand-mark">물가나우</span>
      <span class="brand-sub">MulgaNow</span>
    </div>
  </a>
  <div class="topbar-right">
    <nav style="display:flex;align-items:center;gap:4px;">
      <a href="/" class="topbar-nav-btn">🌾 <span class="topbar-nav-label">농산물</span></a>
      <a href="/consumer" class="topbar-nav-btn">🧴 <span class="topbar-nav-label">생필품</span></a>
      <a href="/blog" class="topbar-nav-btn active">📰 <span class="topbar-nav-label">블로그</span></a>
    </nav>
  </div>
</header>

<article class="article">
  <p class="article-meta">{today} · 물가나우 기획팀</p>
  <h1 class="article-title">{meta['title']}</h1>

  <div class="article-body">
    <p>{meta['intro']}</p>

    <div class="stat-row">
{stat_row_html}
    </div>

    <p>({source_line})</p>

{sections_html}

    <h2>{info_heading}</h2>
    <p>{info_body}</p>

    <a class="app-cta" href="{cta_href}">{cta_label}</a>{extra_cta}

    <div class="disclosure">
      이 포스팅은 애드픽 제휴 마케팅 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받을 수 있습니다.
    </div>
  </div>
</article>

<footer class="site-footer">
  <p>© {date.today().year} 물가나우(MulgaNow). KAMIS 농산물유통정보·한국소비자원 참가격 공공데이터 기반.</p>
{BUSINESS_INFO_HTML}
</footer>

</body>
</html>
"""
    return html


def update_index(meta, slug):
    index_path = os.path.join(BLOG_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    today = date.today().strftime("%Y.%m.%d")
    card = f"""  <a class="blog-card" href="/blog/{slug}.html">
    <div class="blog-card-date">{today}</div>
    <div class="blog-card-title">{meta['title']}</div>
    <div class="blog-card-excerpt">{meta['meta_description']}</div>
  </a>
"""
    marker = '<main class="blog-list">\n'
    if marker not in content:
        raise RuntimeError("blog/index.html에서 <main class=\"blog-list\"> 마커를 찾지 못했습니다.")
    content = content.replace(marker, marker + card, 1)

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)


def update_sitemap(slug):
    sitemap_path = os.path.join(FRONTEND_DIR, "sitemap.xml")
    with open(sitemap_path, "r", encoding="utf-8") as f:
        content = f.read()

    entry = f"""  <url>
    <loc>{SITE}/blog/{slug}.html</loc>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
</urlset>"""
    if "</urlset>" not in content:
        raise RuntimeError("sitemap.xml 형식이 예상과 다릅니다.")
    content = content.replace("</urlset>", entry, 1)

    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# 홍보팀 #1: 네이버 블로그용 원고를 메일로 발송
# 네이버 블로그는 공개 포스팅 API가 없어서(2024.02 서비스 종료) 자동 발행이
# 불가능합니다. 대신 매번 사람이 붙여넣기만 하면 되도록, 발행된 글과 같은
# 내용을 네이버 블로그에 바로 쓸 수 있는 형태(이모지 유지, 마크다운 없는
# 순수 텍스트, 해시태그 포함)로 정리해서 메일로 보냅니다.
# ---------------------------------------------------------------------------
NAVER_DRAFT_RECIPIENT = "seohilab@naver.com"


def render_naver_draft(meta, enriched, cta_href, cta_label):
    lines = [meta["title"], "", meta["intro"], ""]

    for e, ai_item in zip(enriched, meta["items"]):
        it = e["item"]
        if e["kind"] == "consumer":
            stat = f"🧴 {it['item_name']} 참가격 대비 {it['savings_pct']}% 저렴 (참가격 {it['participating_price']:,}원 → 최저가 {it['best_price']:,}원)"
        else:
            pct = it["month_change_pct"]
            arrow = "▼" if pct < 0 else "▲"
            stat = f"{arrow} {it['item_name']} {abs(pct)}% ({it['month_ago_price']:,}원 → {it['today_price']:,}원)"
        lines.append(stat)
    lines.append("")

    has_produce = any(e["kind"] == "produce" for e in enriched)
    has_consumer = any(e["kind"] == "consumer" for e in enriched)
    source_notes = []
    if has_produce:
        source_notes.append("KAMIS 농산물유통정보")
    if has_consumer:
        source_notes.append("한국소비자원 참가격")
    lines.append(f"(자료: {' · '.join(source_notes)})")
    lines.append("")

    for ai_item in meta["items"]:
        lines.append(ai_item["heading"])
        # 본문 템플릿은 "사실 문장. 아래에서 확인하세요." 2문장 구조인데, 이 메일에는
        # 구매 링크 목록("아래")이 없어서 그 문장만 빼고 첫 문장(사실)만 씁니다.
        first_sentence = ai_item["body"].split(". ", 1)[0].rstrip(".") + "."
        lines.append(first_sentence)
        lines.append("")

    lines.append(f"👉 {cta_label}")
    lines.append(cta_href)
    lines.append("")

    hashtags = ["#물가정보", "#물가나우", "#장바구니물가"]
    for e in enriched:
        name = re.sub(r"[/().,·]", " ", e["item"]["item_name"]).split()
        if name:
            hashtags.append(f"#{name[0]}")
    lines.append(" ".join(dict.fromkeys(hashtags)))  # 순서 유지하며 중복 제거

    return "\n".join(lines)


def send_naver_draft_email(subject, body):
    """Gmail SMTP로 네이버 블로그 원고를 발송합니다.

    GMAIL_ADDRESS / GMAIL_APP_PASSWORD 환경변수가 없으면(로컬 테스트 등)
    조용히 건너뜁니다 — 이 실패가 블로그 발행 자체를 막으면 안 되므로
    main()에서도 예외를 삼키고 로그만 남깁니다.
    """
    import smtplib
    from email.mime.text import MIMEText

    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not gmail_app_password:
        print("GMAIL_ADDRESS/GMAIL_APP_PASSWORD가 설정되지 않아 메일 발송을 건너뜁니다.")
        return False

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = NAVER_DRAFT_RECIPIENT

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, [NAVER_DRAFT_RECIPIENT], msg.as_string())
    return True


def main():
    if already_posted_today():
        print("오늘 이미 발행된 글이 있습니다. 건너뜁니다.")
        return

    events = active_seasonal_events()
    event_names = [ev["name"] for ev in events]
    produce_keywords = [kw for ev in events for kw in ev.get("keywords", [])]
    consumer_keywords = [kw for ev in events for kw in ev.get("consumer_keywords", [])]
    if event_names:
        print(f"발동 중인 절기 이벤트: {', '.join(event_names)}")

    try:
        items = fetch_today_prices()
        enriched = pick_candidates(items, n=TOP_N, seasonal_keywords=produce_keywords or None)
    except Exception as e:
        print(f"가격/제휴 데이터 수집 실패, 오늘은 건너뜁니다: {e}")
        return

    # 생필품(참가격) 데이터를 섞을지 결정 (기획팀 요청 #2).
    # 1) 발동 중인 절기 이벤트가 생필품과 직접 연관되면(예: 장마→제습제) 확률과
    #    무관하게 우선 반영합니다 — 계절 문맥이 있을 때가 가장 설득력 있는 타이밍이라서요.
    # 2) 그 외에는 CONSUMER_ONLY_PROB로 생필품 단독 포스트를, 그것도 아니면
    #    CONSUMER_BLEND_PROB로 농산물 포스트에 생필품 1개를 섞습니다.
    # 3) 매번 강제로 섞지 않는 이유: 농산물 "최고 변동 품목" 포스트가 이 블로그의
    #    기본 정체성이므로, 생필품은 어디까지나 보조 소재로 다룹니다.
    mode = "produce"
    try:
        consumer_items = fetch_consumer_prices()
    except Exception as e:
        consumer_items = []
        print(f"생필품 데이터 수집 실패, 이번 실행은 농산물로만 진행합니다: {e}")

    if consumer_items:
        if consumer_keywords:
            seasonal_consumer = pick_consumer_candidates(consumer_items, n=TOP_N, keywords=consumer_keywords)
            if len(seasonal_consumer) >= 2:
                enriched = seasonal_consumer
                mode = "consumer(seasonal)"

        if mode == "produce":
            roll = random.random()
            if roll < CONSUMER_ONLY_PROB:
                candidate = pick_consumer_candidates(consumer_items, n=TOP_N)
                if len(candidate) >= 2:
                    enriched = candidate
                    mode = "consumer"
            elif roll < CONSUMER_ONLY_PROB + CONSUMER_BLEND_PROB and len(enriched) >= 2:
                blend = pick_consumer_candidates(consumer_items, n=1)
                if blend:
                    enriched = enriched[: max(1, TOP_N - 1)] + blend
                    mode = "mixed"

    if len(enriched) < 2:
        print(f"제휴 링크가 있는 글감이 {len(enriched)}개뿐이라 오늘은 건너뜁니다.")
        return

    meta = generate_copy(enriched)

    slug = slugify_date_prefixed()
    if os.path.exists(os.path.join(BLOG_DIR, f"{slug}.html")):
        slug = f"{slug}-2"

    html = render_post_html(meta, enriched, slug)
    with open(os.path.join(BLOG_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)

    update_index(meta, slug)
    update_sitemap(slug)

    print(f"POSTED::{slug}::{meta['title']}::mode={mode}::events={','.join(event_names) or 'none'}")

    # 홍보팀 #1: 네이버 블로그용 원고 메일 발송 (실패해도 발행 자체는 이미 끝났으므로 무시)
    has_consumer_only = all(e["kind"] == "consumer" for e in enriched)
    if has_consumer_only:
        cta_href, cta_label = f"{SITE}/consumer", "🧴 물가나우에서 생필품 최저가 전체 보기"
    else:
        cta_href, cta_label = f"{SITE}/", "🛒 물가나우에서 오늘 농산물 가격 전체 보기"
    try:
        draft = render_naver_draft(meta, enriched, cta_href, cta_label)
        sent = send_naver_draft_email(f"[물가나우] 네이버 블로그 원고 - {meta['title']}", draft)
        print(f"네이버 원고 메일 발송: {'성공' if sent else '건너뜀(계정 미설정)'}")
    except Exception as e:
        print(f"네이버 원고 메일 발송 실패(발행 자체는 정상 완료): {e}")


if __name__ == "__main__":
    main()
