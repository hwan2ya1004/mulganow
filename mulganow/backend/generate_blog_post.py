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

TITLE_TEMPLATES_DROP = [
    "{item} 값이 뚝! 한 달 새 {pct}% 내렸어요",
    "지금 안 사면 아쉬운 {item}, {pct}% 저렴해졌습니다",
    "{item} {pct}% 하락 — 장바구니 채우기 좋은 타이밍",
    "요즘 {item} 왜 이렇게 싸졌을까? {pct}% 하락 이유",
]
TITLE_TEMPLATES_SURGE = [
    "{item}값 또 올랐다... 한 달 새 {pct}% 급등",
    "장바구니 비상! {item} {pct}% 뛰었어요",
    "{item} {pct}% 상승, 미리 알아두면 좋은 것들",
    "요즘 {item} 왜 이렇게 비싸졌을까? {pct}% 상승 이유",
]

INTRO_TEMPLATES_DROP = [
    "장 보러 가기 전에 알아두면 좋은 소식이에요. 농산물유통정보(KAMIS) 데이터를 보니 {item} 가격이 눈에 띄게 내려갔습니다.",
    "요즘 물가가 계속 오른다고 느끼셨다면, 오늘은 반가운 소식입니다. {item} 가격이 한 달 전보다 뚝 떨어졌어요.",
    "매번 오르기만 하는 것 같은 장바구니 물가, 이번엔 다릅니다. {item} 가격이 큰 폭으로 내렸어요.",
]
INTRO_TEMPLATES_SURGE = [
    "장 보러 가기 전에 미리 알아두시면 좋을 소식이에요. 농산물유통정보(KAMIS) 데이터를 보니 {item} 가격이 눈에 띄게 올랐습니다.",
    "이번 주 장바구니 물가, 조금 부담스러워질 수 있어요. {item} 가격이 한 달 전보다 크게 뛰었습니다.",
    "'요즘 왜 이렇게 비싸졌지?' 싶으셨다면 이유가 있었습니다. {item} 값이 큰 폭으로 상승했어요.",
]

HEADING_TEMPLATES_DROP = [
    "📉 {item}, 지금이 살 타이밍",
    "💰 {item}, 이번 주는 저렴해요",
    "🛒 {item} 최저가 챙기기",
]
HEADING_TEMPLATES_SURGE = [
    "📈 {item}, 미리 챙겨두세요",
    "⚠️ {item}, 가격 오르기 전에",
    "🛒 {item} 그나마 싸게 사는 법",
]

BODY_TEMPLATES_DROP = [
    "{item} 가격이 한 달 전 {month_ago}원에서 오늘 {today}원으로 내려갔어요. 아래에서 오늘 기준 최저가를 확인해보세요.",
    "한 달 전 {month_ago}원이었던 {item}, 오늘은 {today}원이에요. 지금 사두면 알뜰하게 장 볼 수 있습니다.",
]
BODY_TEMPLATES_SURGE = [
    "{item} 가격이 한 달 전 {month_ago}원에서 오늘 {today}원으로 올랐어요. 그래도 아래에서 상대적으로 저렴한 곳을 찾아보세요.",
    "한 달 전 {month_ago}원이었던 {item}, 오늘은 {today}원이 됐어요. 오르기 전에 미리 구매해두는 것도 방법입니다.",
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


def pick_candidates(items, n=TOP_N):
    scored = [it for it in items if isinstance(it.get("month_change_pct"), (int, float))]
    scored.sort(key=lambda it: abs(it["month_change_pct"]), reverse=True)

    enriched = []
    seen_names = set()
    for it in scored:
        name = it.get("item_name")
        if not name or name in seen_names:
            continue
        picks = fetch_shop_picks(it)
        if len(picks) < 1:
            continue  # 살 곳이 없으면 제휴 마케팅 글감으로 부적합
        enriched.append({"item": it, "picks": picks})
        seen_names.add(name)
        if len(enriched) >= n:
            break
    return enriched


def already_posted_today():
    if not os.path.isdir(BLOG_DIR):
        return False
    today = date.today().isoformat()
    return any(f.startswith(today) for f in os.listdir(BLOG_DIR))


def generate_copy(enriched):
    """AI 없이, 실제 데이터를 후킹멘트 템플릿에 채워서 카피를 만듭니다."""
    primary = enriched[0]["item"]
    primary_pct = primary["month_change_pct"]
    primary_drop = primary_pct < 0

    title_pool = TITLE_TEMPLATES_DROP if primary_drop else TITLE_TEMPLATES_SURGE
    intro_pool = INTRO_TEMPLATES_DROP if primary_drop else INTRO_TEMPLATES_SURGE

    title = random.choice(title_pool).format(item=primary["item_name"], pct=abs(primary_pct))
    intro = random.choice(intro_pool).format(item=primary["item_name"])

    names = [e["item"]["item_name"] for e in enriched]
    meta_description = f"{names[0]} {abs(primary_pct)}% {'하락' if primary_drop else '상승'} 등, 이번 주 장바구니 물가 변동을 KAMIS 데이터로 정리했습니다."

    items = []
    for e in enriched:
        it = e["item"]
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

    stat_boxes = []
    sections = []
    for e, ai_item in zip(enriched, meta["items"]):
        it = e["item"]
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

    <p>(소매가 기준, 최근 1개월 대비 · 자료: KAMIS 농산물유통정보)</p>

{sections_html}

    <h2>매일 바뀌는 가격, 실시간으로 확인하는 법</h2>
    <p>여기 나온 가격은 오늘 기준이고, KAMIS 데이터는 매일 갱신됩니다. 다른 품목까지 포함해서 오늘 시세와 전월·전년 대비 변동률을 한눈에 보고 싶다면 물가나우에서 바로 확인할 수 있어요.</p>

    <a class="app-cta" href="{SITE}/">🛒 물가나우에서 오늘 농산물 가격 전체 보기</a>

    <div class="disclosure">
      이 포스팅은 애드픽 제휴 마케팅 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받을 수 있습니다.
    </div>
  </div>
</article>

<footer class="site-footer">© {date.today().year} 물가나우(MulgaNow). KAMIS 농산물유통정보 공공데이터 기반.</footer>

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


def main():
    if already_posted_today():
        print("오늘 이미 발행된 글이 있습니다. 건너뜁니다.")
        return

    try:
        items = fetch_today_prices()
        enriched = pick_candidates(items, n=TOP_N)
    except Exception as e:
        print(f"가격/제휴 데이터 수집 실패, 오늘은 건너뜁니다: {e}")
        return

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

    print(f"POSTED::{slug}::{meta['title']}")


if __name__ == "__main__":
    main()
