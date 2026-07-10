# -*- coding: utf-8 -*-
"""
generate_blog_post.py
----------------------
KAMIS 가격 변동이 큰 품목을 골라, 클로드(Anthropic API)로 후킹멘트 카피를 써서
frontend/blog/ 아래에 새 글을 자동 발행합니다.

이미 배포된 물가나우 API(mulganow.vercel.app)를 그대로 호출해서 가격/제휴 데이터를
가져오므로, KAMIS·애드픽 인증키는 이 스크립트에 필요 없습니다. 오직 실제 데이터만
카피에 반영하고(가격·링크·이미지는 절대 AI가 지어내지 않음), 문구만 AI가 작성합니다.

실행: python generate_blog_post.py
필요 환경변수: ANTHROPIC_API_KEY
"""
import json
import os
import re
import sys
from datetime import date, datetime, timezone

import requests
from anthropic import Anthropic

SITE = "https://mulganow.vercel.app"
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BACKEND_DIR, "..", "frontend")
BLOG_DIR = os.path.join(FRONTEND_DIR, "blog")

TOP_N = 3
MODEL = "claude-sonnet-5"

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


def call_claude(enriched):
    client = Anthropic()  # ANTHROPIC_API_KEY 환경변수 자동 사용

    lines = []
    for i, e in enumerate(enriched, 1):
        it = e["item"]
        pct = it["month_change_pct"]
        direction = "상승" if pct > 0 else "하락"
        lines.append(
            f"{i}. {it['item_name']} ({it.get('category_name', '')}) - "
            f"오늘 {it['today_price']:,}원, 한 달 전 {it['month_ago_price']:,}원, "
            f"{direction} {abs(pct)}% (단위: {it.get('unit', '')})"
        )
    data_block = "\n".join(lines)

    prompt = f"""당신은 '물가나우'라는 장바구니 물가 비교 서비스의 블로그 카피라이터입니다.
아래 실제 KAMIS(농산물유통정보) 가격 데이터를 바탕으로, 클릭을 유도하는 후킹멘트 스타일의
블로그 글을 작성해주세요.

[실제 데이터 - 숫자와 품목명은 절대 바꾸지 말고 그대로 사용]
{data_block}

[요구사항]
- 사실(숫자·품목명)은 반드시 그대로 사용. 과장·허위 정보 절대 금지.
- 표시광고법을 준수하는 선에서, 궁금증 유발·손해회피 심리를 자극하는 후킹멘트 톤.
- "무조건 최저가", "국내 유일" 같은 근거 없는 배타적 최상급 표현 금지.
- 친근한 존댓말체.
- 아래 JSON 형식으로만 응답하세요. 다른 설명이나 마크다운 없이 순수 JSON만 출력.

{{
  "slug": "영문 kebab-case, 5단어 이내, 이번 글 핵심을 나타내는 슬러그",
  "title": "후킹멘트가 담긴 제목 (30자 내외)",
  "meta_description": "검색결과에 노출될 요약 (100자 이내)",
  "intro": "글의 도입부 2~3문장. 궁금증을 유발하는 후킹 문장으로 시작.",
  "items": [
    {{"heading": "이모지로 시작하는 소제목 (품목별로 하나씩, 데이터 순서와 동일하게)", "body": "1~2문장 설명"}}
  ]
}}

items 배열은 반드시 위 데이터와 같은 순서, 같은 개수({len(enriched)}개)로 작성하세요."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()

    # 혹시 코드블록으로 감싸서 응답한 경우 벗겨내기
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())

    meta = json.loads(text)
    if len(meta.get("items", [])) != len(enriched):
        raise ValueError(
            f"AI 응답 items 개수({len(meta.get('items', []))})가 "
            f"입력 데이터 개수({len(enriched)})와 다릅니다."
        )
    return meta


def slugify_date_prefixed(raw_slug: str) -> str:
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
    today = date.today().isoformat()
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
  "datePublished": "{today}",
  "dateModified": "{today}",
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
  <p class="article-meta">{today} · 물가나우 편집팀</p>
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

    today = date.today().isoformat()
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
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

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

    try:
        meta = call_claude(enriched)
    except Exception as e:
        print(f"AI 카피 생성 실패, 오늘은 건너뜁니다: {e}")
        return

    slug = slugify_date_prefixed(meta["slug"])
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
