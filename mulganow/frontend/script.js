// script.js — 물가나우 MVP 프론트엔드

// ── DOM 참조 ──────────────────────────────────────────────
const cardGrid     = document.getElementById("cardGrid");
const skeletonGrid = document.getElementById("skeletonGrid");
const statusRow    = document.getElementById("statusRow");
const statusText   = document.getElementById("statusText");
const searchInput  = document.getElementById("searchInput");
const searchBtn    = document.getElementById("searchBtn");
const clsInput     = document.getElementById("clsSelect");

const clearBtn       = document.getElementById("clearBtn");
const resetBtn       = document.getElementById("resetBtn");

const modalBackdrop  = document.getElementById("modalBackdrop");
const modalBox       = document.getElementById("modalBox");
const modalClose     = document.getElementById("modalClose");
const modalTitle     = document.getElementById("modalTitle");
const modalSub       = document.getElementById("modalSub");
const modalIcon      = document.getElementById("modalIcon");
const priceCompare   = document.getElementById("priceCompare");
const trendDays      = document.getElementById("trendDays");
const trendHint      = document.getElementById("trendHint");
const shopSection    = document.getElementById("shopSection");
const shopList       = document.getElementById("shopList");
const shopAdArea     = document.getElementById("shopAdArea");

// ── 상태 ──────────────────────────────────────────────────
let allItems      = [];
let currentCat    = "";
let currentSub    = "";   // 두류 서브필터 (data-sub 값, 예: "두류")
let currentSort   = "default";   // "default" | "price-desc" | "price-asc"
let chartInstance = null;
let currentItem   = null;

// ── 두류(콩류) 품목명 키워드 매핑 ────────────────────────
// KAMIS item_name에 포함되는 키워드로 두류 여부 및 세부 종류 판별
const BEAN_KEYWORDS = ["콩", "팥", "녹두", "강낭콩", "완두", "동부", "땅콩", "두류", "대두", "서리태", "흑태", "청태", "백태", "쥐눈이콩", "약콩"];

function isBeanItem(itemName) {
  if (!itemName) return false;
  return BEAN_KEYWORDS.some(kw => itemName.includes(kw));
}

// ── 카테고리 아이콘 매핑 ──────────────────────────────────
const CAT_ICON = {
  "100": "🌾", "200": "🥬", "300": "🌿",
  "400": "🍎", "500": "🥩", "600": "🐟",
};

// 두류 세부 품목 아이콘
const BEAN_ICON = {
  "콩": "🟡", "대두": "🟡", "서리태": "🟡", "흑태": "🟡", "청태": "🟡",
  "백태": "🟡", "쥐눈이콩": "🟡", "약콩": "🟡",
  "팥": "🔴",
  "녹두": "🟢",
  "강낭콩": "🟤",
  "완두": "🫛",
  "동부": "🟠",
  "땅콩": "🥜",
};

function getCatIcon(catCode, itemName) {
  // 두류 서브필터 모드이거나 품목명이 두류 키워드를 포함하면 콩 아이콘
  if (catCode === "100" && itemName && isBeanItem(itemName)) {
    for (const [kw, icon] of Object.entries(BEAN_ICON)) {
      if (itemName.includes(kw)) return icon;
    }
    return "🌱";
  }
  return CAT_ICON[catCode] || "🛒";
}

// ══════════════════════════════════════════════════════════
// GSAP 페이지 진입 애니메이션
// ══════════════════════════════════════════════════════════
function initPageAnimation() {
  if (typeof gsap === "undefined") return;

  const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

  // 헤더 슬라이드 다운
  tl.to("#topbar", {
    opacity: 1,
    y: 0,
    duration: 0.6,
    clearProps: "transform",
  }, 0);

  // 브랜드 로고 바운스
  tl.from("#brandLogo", {
    scale: 0,
    rotation: -30,
    duration: 0.5,
    ease: "back.out(1.7)",
  }, 0.2);

  // 히어로 타이틀 페이드업
  tl.to("#heroTitle", {
    opacity: 1,
    y: 0,
    duration: 0.7,
    clearProps: "transform",
  }, 0.3);

  // 히어로 서브텍스트
  tl.to("#heroSub", {
    opacity: 1,
    y: 0,
    duration: 0.6,
    clearProps: "transform",
  }, 0.5);

  // 검색창 스케일업
  tl.to("#heroSearch", {
    opacity: 1,
    scale: 1,
    duration: 0.5,
    ease: "back.out(1.4)",
    clearProps: "transform",
  }, 0.65);

  // 필터바 슬라이드업
  tl.to("#filterBar", {
    opacity: 1,
    y: 0,
    duration: 0.5,
    clearProps: "transform",
  }, 0.8);

  // GSAP 초기 위치 설정 (CSS opacity:0 상태에서 시작)
  gsap.set("#heroTitle", { y: 30 });
  gsap.set("#heroSub",   { y: 20 });
  gsap.set("#heroSearch",{ scale: 0.92 });
  gsap.set("#filterBar", { y: 16 });
}

// ── 초기 위치 설정 (GSAP 로드 후 즉시)
if (typeof gsap !== "undefined") {
  gsap.set("#heroTitle", { y: 30 });
  gsap.set("#heroSub",   { y: 20 });
  gsap.set("#heroSearch",{ scale: 0.92 });
  gsap.set("#filterBar", { y: 16 });
}

// ══════════════════════════════════════════════════════════
// 카드 stagger 애니메이션
// ══════════════════════════════════════════════════════════
function animateCards() {
  if (typeof gsap === "undefined") return;

  const cards = document.querySelectorAll(".price-card");
  gsap.fromTo(cards,
    { opacity: 0, y: 24, scale: 0.96 },
    {
      opacity: 1,
      y: 0,
      scale: 1,
      duration: 0.45,
      stagger: 0.045,
      ease: "power2.out",
      clearProps: "transform",
    }
  );
}

// ══════════════════════════════════════════════════════════
// 모달 GSAP 열기 / 닫기
// ══════════════════════════════════════════════════════════
function openModal() {
  modalBackdrop.classList.add("open");

  if (typeof gsap === "undefined") return;

  // backdrop 페이드인
  gsap.fromTo(modalBackdrop,
    { opacity: 0 },
    { opacity: 1, duration: 0.25, ease: "power2.out" }
  );

  // 모달 박스 스케일업
  gsap.fromTo(modalBox,
    { opacity: 0, scale: 0.88, y: 20 },
    { opacity: 1, scale: 1, y: 0, duration: 0.35, ease: "back.out(1.5)" }
  );
}

function closeModal() {
  if (typeof gsap === "undefined") {
    modalBackdrop.classList.remove("open");
    return;
  }

  gsap.to(modalBox, {
    opacity: 0,
    scale: 0.92,
    y: 12,
    duration: 0.22,
    ease: "power2.in",
  });
  gsap.to(modalBackdrop, {
    opacity: 0,
    duration: 0.25,
    ease: "power2.in",
    onComplete: () => {
      modalBackdrop.classList.remove("open");
      gsap.set([modalBox, modalBackdrop], { clearProps: "all" });
    },
  });
}

// ══════════════════════════════════════════════════════════
// 가격 비교 패널 숫자 카운트업 애니메이션
// ══════════════════════════════════════════════════════════
function animateComparePrices() {
  if (typeof gsap === "undefined") return;

  const priceEls = priceCompare.querySelectorAll(".compare-price");
  priceEls.forEach((el) => {
    const raw = el.dataset.raw;
    if (!raw || raw === "-") return;
    const target = parseInt(raw, 10);
    if (isNaN(target)) return;

    const obj = { val: 0 };
    gsap.to(obj, {
      val: target,
      duration: 0.8,
      ease: "power2.out",
      onUpdate() {
        el.textContent = Math.round(obj.val).toLocaleString("ko-KR") + "원";
      },
    });
  });

  // 각 compare-item 순차 등장
  gsap.fromTo(
    priceCompare.querySelectorAll(".compare-item"),
    { opacity: 0, y: 12 },
    { opacity: 1, y: 0, duration: 0.35, stagger: 0.07, ease: "power2.out" }
  );
}

// ── 데이터 로드 ───────────────────────────────────────────
async function loadPrices() {
  showSkeleton(true);
  setStatus("", false);

  const q   = searchInput.value.trim();
  const cls = clsInput.value;
  const url = `/api/today-prices?cls=${cls}${q ? `&q=${encodeURIComponent(q)}` : ""}`;

  try {
    const res  = await fetch(url);
    const data = await res.json();

    if (!data.ok) {
      showSkeleton(false);
      setStatus(`⚠️ 데이터를 불러오지 못했습니다: ${data.error}`, true);
      return;
    }

    allItems = data.items;
    renderFiltered();
  } catch (err) {
    showSkeleton(false);
    setStatus("⚠️ 서버에 연결할 수 없습니다. 백엔드(app.py)가 실행 중인지 확인해주세요.", true);
  }
}

// ── 정렬 함수 ─────────────────────────────────────────────
function sortItems(items) {
  const arr = [...items];
  if (currentSort === "price-desc") {
    arr.sort((a, b) => (b.today_price ?? -1) - (a.today_price ?? -1));
  } else if (currentSort === "price-asc") {
    arr.sort((a, b) => (a.today_price ?? Infinity) - (b.today_price ?? Infinity));
  }
  return arr;
}

// ── 필터 적용 후 렌더 ─────────────────────────────────────
function renderFiltered() {
  let filtered = allItems;

  // 두류 서브필터 모드
  if (currentSub === "두류") {
    filtered = allItems.filter(it =>
      it.category_code === "100" && isBeanItem(it.item_name)
    );
  } else if (currentCat) {
    filtered = allItems.filter(it => it.category_code === currentCat);
  }

  showSkeleton(false);

  if (filtered.length === 0) {
    setStatus("", false);
    cardGrid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <h3>검색 결과가 없습니다</h3>
        <p>다른 품목명이나 카테고리를 선택해보세요.</p>
      </div>`;
    cardGrid.style.display = "grid";
    return;
  }

  // 정렬 적용
  filtered = sortItems(filtered);

  const cls = clsInput.value === "01" ? "소매가" : "도매가";
  const sortLabel = currentSort === "price-desc" ? " · 💰 가격 높은 순 정렬"
                  : currentSort === "price-asc"  ? " · 💸 가격 낮은 순 정렬"
                  : "";

  const catLabel = currentSub === "두류" ? " · 🌱 두류 전체" : "";
  setStatus(`📦 총 ${filtered.length}개 품목 · ${cls} 기준 · KAMIS 최근일자${catLabel}${sortLabel}`, false);
  renderCards(filtered);
}

// ── 카드 렌더 ─────────────────────────────────────────────
function renderCards(items) {
  cardGrid.innerHTML = "";
  cardGrid.style.display = "grid";

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "price-card";

    const icon    = getCatIcon(item.category_code, item.item_name);
    const badge   = renderChangeBadge(item.month_change_pct);
    const catName = item.category_name || "";

    const unitHintHtml = item.unit_hint
      ? `<div class="card-unit-hint">${escapeHtml(item.unit_hint)}</div>`
      : "";

    card.innerHTML = `
      <div class="card-top">
        <span class="card-category">${escapeHtml(catName)}</span>
      </div>
      <div class="card-name">${escapeHtml(item.item_name || "이름 없음")}</div>
      <div class="card-unit">${escapeHtml(item.unit || "")}${item.unit_hint ? ` <span class="card-unit-hint-inline">(${escapeHtml(item.unit_hint)})</span>` : ""}</div>
      <div class="card-price">${formatPrice(item.today_price)}<small>원</small></div>
      ${badge}
    `;

    card.addEventListener("click", () => openTrendModal(item, icon));
    cardGrid.appendChild(card);
  });

  // GSAP 카드 등장 애니메이션
  animateCards();
}

// ── 변동 배지 ─────────────────────────────────────────────
function renderChangeBadge(pct) {
  if (pct === null || pct === undefined)
    return `<span class="change-badge flat">전월 데이터 없음</span>`;
  if (pct > 0)
    return `<span class="change-badge up">▲ 전월대비 ${pct}%</span>`;
  if (pct < 0)
    return `<span class="change-badge down">▼ 전월대비 ${Math.abs(pct)}%</span>`;
  return `<span class="change-badge flat">전월대비 변동없음</span>`;
}

// ── 유틸 ──────────────────────────────────────────────────
function formatPrice(v) {
  if (v === null || v === undefined) return "-";
  return v.toLocaleString("ko-KR");
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

function setStatus(text, isError) {
  statusText.textContent = text;
  statusRow.classList.toggle("error", !!isError);
}

function showSkeleton(show) {
  skeletonGrid.style.display = show ? "grid" : "none";
  if (show) cardGrid.style.display = "none";
}

// ── 모달 ──────────────────────────────────────────────────
function openTrendModal(item, icon) {
  currentItem = item;

  modalIcon.textContent  = icon || "🛒";
  modalTitle.textContent = item.item_name || "품목 상세";
  const unitLabel = item.unit_hint
    ? `${item.unit || ""} (${item.unit_hint})`
    : (item.unit || "");
  modalSub.textContent   = `${item.category_name || ""} · ${unitLabel}`;

  // 가격 비교 패널 (data-raw 속성으로 카운트업 대상 지정)
  const makeCompare = (label, val, isToday = false) => `
    <div class="compare-item">
      <div class="compare-label">${label}</div>
      <div class="compare-price${isToday ? " today" : ""}"
           data-raw="${val !== null && val !== undefined ? val : ""}">
        ${formatPrice(val)}원
      </div>
    </div>`;

  priceCompare.innerHTML =
    makeCompare("오늘",     item.today_price,    true) +
    makeCompare("1일 전",   item.day_ago_price)  +
    makeCompare("1개월 전", item.month_ago_price)+
    makeCompare("1년 전",   item.year_ago_price);

  // GSAP 모달 열기
  openModal();

  // 가격 카운트업 애니메이션
  animateComparePrices();

  // 소매가(01)일 때만 네이버 쇼핑 최저가 섹션 표시
  if (clsInput.value === "01") {
    shopSection.style.display = "block";
    loadShopPrices(item.item_name, item.unit, item.today_price);
  } else {
    shopSection.style.display = "none";
  }

  // item_code: _normalize_item()에서 명시적으로 노출된 필드 우선 사용
  // category_code도 정규화된 필드에서 직접 읽음
  const categoryCode = item.category_code || (item.raw && item.raw.category_code);
  const itemCode     = item.item_code
                    || (item.raw && (item.raw.item_code || item.raw.productno || item.raw.itemcode || item.raw.item_no));

  if (!categoryCode || !itemCode) {
    trendHint.textContent = "이 품목은 코드 정보가 없어 추이 조회가 제한됩니다.";
    renderEmptyChart();
    return;
  }

  loadTrend(categoryCode, itemCode);
}

// ── 네이버 쇼핑 최저가 캐시 (세션 내 중복 API 호출 방지) ─
// 키: "품목명|단위"  값: 결과 배열
const shopPriceCache = {};

// ── 최저가 로드 (소매가 전용) ────────────────────────────
async function loadShopPrices(itemName, unit, todayPrice) {
  // ── 캐시 확인: 이미 조회한 품목이면 API 호출 없이 바로 렌더 ──
  const cacheKey = `${itemName}|${unit || ""}`;
  if (shopPriceCache[cacheKey]) {
    renderShopItems(shopPriceCache[cacheKey], itemName);
    return;
  }

  // 로딩 상태 표시 (캐시 미스일 때만)
  shopList.innerHTML = `
    <div class="shop-loading" id="shopLoading">
      <span class="shop-spinner"></span> 최저가 검색 중...
    </div>`;
  if (shopAdArea) shopAdArea.innerHTML = "";

  const unitParam  = unit       ? `&unit=${encodeURIComponent(unit)}`        : "";
  const priceParam = todayPrice ? `&price=${encodeURIComponent(todayPrice)}` : "";
  const apiUrl = `/api/shop-prices?q=${encodeURIComponent(itemName)}${unitParam}${priceParam}`;

  // ── 재시도 헬퍼: 애드픽 API가 느릴 때 최대 3회 재시도 ──
  // 빈 결과(count=0)이거나 네트워크 오류 시 1.5초 후 재시도
  const MAX_RETRY = 3;
  const RETRY_DELAY_MS = 1500;

  async function fetchWithRetry(url, attempt) {
    try {
      const res  = await fetch(url);
      const data = await res.json();

      if (data.ok && data.items.length > 0) {
        return data; // 성공
      }

      // 빈 결과: 재시도 가능하면 대기 후 재시도
      if (attempt < MAX_RETRY) {
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS));
        return fetchWithRetry(url, attempt + 1);
      }
      return data; // 최대 재시도 초과 → 빈 결과 반환
    } catch (err) {
      if (attempt < MAX_RETRY) {
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS));
        return fetchWithRetry(url, attempt + 1);
      }
      throw err; // 최대 재시도 초과 → 에러 throw
    }
  }

  try {
    const data = await fetchWithRetry(apiUrl, 1);

    if (!data.ok || data.items.length === 0) {
      shopList.innerHTML = `<div class="shop-error">검색 결과가 없습니다.</div>`;
      renderShopAd(itemName);
      return;
    }

    // 결과를 캐시에 저장 후 렌더
    shopPriceCache[cacheKey] = data.items;
    renderShopItems(data.items, itemName);
  } catch (err) {
    shopList.innerHTML = `<div class="shop-error">최저가 정보를 불러오지 못했습니다.</div>`;
    renderShopAd(itemName);
  }
}

function renderShopItems(items, itemName) {
  const rankClass = (i) => i === 0 ? "top1" : i === 1 ? "top2" : i === 2 ? "top3" : "";
  const rankLabel = (i) => i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `${i + 1}`;

  // 링크 유효성 검증: http(s):// 또는 //로 시작하지 않으면 클릭 불가 처리
  const safeLink = (it) => {
    const link = it.link || "";
    if (link.startsWith("http://") || link.startsWith("https://") || link.startsWith("//")) return link;
    return null; // 유효하지 않은 링크
  };

  shopList.innerHTML = items.map((it, i) => {
    const link = safeLink(it);
    const tag  = link ? "a" : "div";
    const href = link ? `href="${escapeHtml(link)}" target="_blank" rel="noopener sponsored"` : "";
    return `
    <${tag} class="shop-item${link ? "" : " shop-item-disabled"}" ${href}>
      <span class="shop-item-rank ${rankClass(i)}">${rankLabel(i)}</span>
      ${it.image
        ? `<img class="shop-item-img" src="${escapeHtml(it.image)}" alt="" loading="lazy" onerror="this.style.display='none'">`
        : `<div class="shop-item-img"></div>`}
      <div class="shop-item-info">
        <div class="shop-item-title">${escapeHtml(it.title)}</div>
        <div class="shop-item-mall">${escapeHtml(it.mall)}</div>
      </div>
      <div class="shop-item-price">
        ${it.price !== null ? it.price.toLocaleString("ko-KR") : "-"}<small>원</small>
      </div>
      ${link ? `<span class="shop-item-arrow">›</span>` : ""}
    </${tag}>`;
  }).join("");

  // GSAP 등장 애니메이션
  if (typeof gsap !== "undefined") {
    gsap.fromTo(
      shopList.querySelectorAll(".shop-item"),
      { opacity: 0, x: -10 },
      { opacity: 1, x: 0, duration: 0.3, stagger: 0.06, ease: "power2.out" }
    );
  }

  // 최저가 카드 아래 광고 렌더
  renderShopAd(itemName || "");
}

// ── 제휴 쇼핑몰 배너 렌더 ────────────────────────────────
// 애드픽 제휴 링크 8개 쇼핑몰 버튼 표시
const AFFILIATE_MALLS = [
  { name: "11번가",       icon: "🛍️", link: "https://bitl.bz/lrxjLn" },
  { name: "SSG",          icon: "🛒", link: "https://bitl.bz/yJP4tM" },
  { name: "컬리",         icon: "🥦", link: "https://bitl.bz/EJGpp1" },
  { name: "GS SHOP",      icon: "🏪", link: "https://bitl.bz/qygyWP" },
  { name: "이마트몰",     icon: "🏬", link: "https://bitl.bz/Ro8mNH" },
  { name: "Hmall",        icon: "🎁", link: "https://bitl.bz/bJ4MJW" },
  { name: "CJ THE MARKET",icon: "🍱", link: "https://bitl.bz/VuyZaB" },
  { name: "롯데홈쇼핑",   icon: "📦", link: "https://bitl.bz/kOT087" },
];

function renderShopAd(keyword) {
  if (!shopAdArea) return;

  const mallButtons = AFFILIATE_MALLS.map(m => `
    <a class="shop-mall-btn" href="${escapeHtml(m.link)}" target="_blank" rel="noopener sponsored">
      <span class="shop-mall-icon">${m.icon}</span>
      <span class="shop-mall-name">${escapeHtml(m.name)}</span>
    </a>`).join("");

  shopAdArea.innerHTML = `
    <div class="shop-mall-section">
      <div class="shop-mall-title">🛍️ 제휴 쇼핑몰에서 구매하기</div>
      <div class="shop-mall-grid">${mallButtons}</div>
    </div>`;

  // GSAP 등장 애니메이션
  if (typeof gsap !== "undefined") {
    gsap.fromTo(
      shopAdArea.querySelectorAll(".shop-mall-btn"),
      { opacity: 0, y: 8, scale: 0.92 },
      { opacity: 1, y: 0, scale: 1, duration: 0.3, stagger: 0.04, ease: "power2.out" }
    );
  }
}

// ── 추이 차트 ─────────────────────────────────────────────
async function loadTrend(categoryCode, itemCode) {
  trendHint.textContent = "추이 데이터를 불러오는 중...";
  const days = trendDays.value;
  const cls  = clsInput.value;
  const url  = `/api/trend?category=${categoryCode}&item=${itemCode}&days=${days}&cls=${cls}`;

  try {
    const res  = await fetch(url);
    const data = await res.json();

    if (!data.ok || data.points.length === 0) {
      trendHint.textContent = "추이 데이터가 없습니다.";
      renderEmptyChart();
      return;
    }

    trendHint.textContent = `${data.count}개 데이터 포인트`;
    renderChart(data.points);
  } catch (err) {
    trendHint.textContent = "추이 데이터를 불러오지 못했습니다.";
    renderEmptyChart();
  }
}

function renderChart(points) {
  const ctx = document.getElementById("trendChart").getContext("2d");
  if (chartInstance) chartInstance.destroy();

  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: points.map((p) => p.date),
      datasets: [{
        label: "가격(원)",
        data: points.map((p) => p.price),
        borderColor: "#2563eb",
        backgroundColor: "rgba(37,99,235,0.08)",
        fill: true,
        tension: 0.3,
        pointRadius: 3,
        pointBackgroundColor: "#2563eb",
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      animation: { duration: 700, easing: "easeInOutQuart" },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.parsed.y.toLocaleString("ko-KR")}원`,
          },
        },
      },
      scales: {
        x: {
          ticks: { maxTicksLimit: 6, font: { size: 11 } },
          grid: { display: false },
        },
        y: {
          ticks: {
            callback: (v) => v.toLocaleString("ko-KR"),
            font: { size: 11 },
          },
          grid: { color: "rgba(0,0,0,0.05)" },
        },
      },
    },
  });
}

function renderEmptyChart() {
  const ctx = document.getElementById("trendChart").getContext("2d");
  if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
}

// ── 이벤트 바인딩 ─────────────────────────────────────────

// 소매/도매 토글
document.querySelectorAll(".cls-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".cls-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    clsInput.value = btn.dataset.val;

    // 버튼 클릭 피드백 애니메이션
    if (typeof gsap !== "undefined") {
      gsap.fromTo(btn,
        { scale: 0.9 },
        { scale: 1, duration: 0.3, ease: "back.out(2)" }
      );
    }

    loadPrices();
  });
});

// 카테고리 필터
document.querySelectorAll(".filter-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentCat = btn.dataset.cat;
    currentSub = btn.dataset.sub || "";

    // 필터 버튼 클릭 피드백
    if (typeof gsap !== "undefined") {
      gsap.fromTo(btn,
        { scale: 0.88 },
        { scale: 1, duration: 0.3, ease: "back.out(2)" }
      );
    }

    renderFiltered();
  });
});

// 검색
searchBtn.addEventListener("click", () => {
  // 검색 버튼 클릭 애니메이션
  if (typeof gsap !== "undefined") {
    gsap.fromTo(searchBtn,
      { scale: 0.93 },
      { scale: 1, duration: 0.25, ease: "back.out(2)" }
    );
  }
  loadPrices();
});

searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadPrices();
});

// 추이 기간 변경
trendDays.addEventListener("change", () => {
  if (!currentItem) return;
  const categoryCode = currentItem.category_code || (currentItem.raw && currentItem.raw.category_code);
  const itemCode     = currentItem.item_code
                    || (currentItem.raw && (currentItem.raw.item_code || currentItem.raw.productno || currentItem.raw.itemcode || currentItem.raw.item_no));
  if (categoryCode && itemCode) loadTrend(categoryCode, itemCode);
});

// 모달 닫기
modalClose.addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", (e) => {
  if (e.target === modalBackdrop) closeModal();
});

// 정렬 버튼
document.querySelectorAll(".sort-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".sort-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentSort = btn.dataset.sort;

    // 버튼 클릭 피드백
    if (typeof gsap !== "undefined") {
      gsap.fromTo(btn,
        { scale: 0.88 },
        { scale: 1, duration: 0.28, ease: "back.out(2)" }
      );
    }

    renderFiltered();
  });
});

// ESC 키로 모달 닫기
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && modalBackdrop.classList.contains("open")) closeModal();
});

// ── 검색어 입력 시 X 버튼 표시/숨김 ──────────────────────
searchInput.addEventListener("input", () => {
  clearBtn.style.display = searchInput.value ? "flex" : "none";
});

// ── X 버튼: 검색어만 클리어 ──────────────────────────────
clearBtn.addEventListener("click", () => {
  searchInput.value = "";
  clearBtn.style.display = "none";
  searchInput.focus();
  loadPrices();
});

// ── 전체 초기화 함수 ──────────────────────────────────────
function resetAll() {
  // 상태 변수 초기화
  searchInput.value = "";
  clearBtn.style.display = "none";
  currentCat  = "";
  currentSub  = "";
  currentSort = "default";

  // 필터 버튼 active 초기화
  document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
  document.querySelector('.filter-btn[data-cat=""]').classList.add("active");

  // 정렬 버튼 active 초기화
  document.querySelectorAll(".sort-btn").forEach(b => b.classList.remove("active"));
  document.querySelector('.sort-btn[data-sort="default"]').classList.add("active");

  // GSAP 회전 피드백
  if (typeof gsap !== "undefined") {
    gsap.fromTo(resetBtn,
      { rotation: -180, scale: 0.85 },
      { rotation: 0, scale: 1, duration: 0.45, ease: "back.out(2)" }
    );
  }

  loadPrices();
}

// ── 초기화 버튼 이벤트 ───────────────────────────────────
resetBtn.addEventListener("click", resetAll);

// ── 브랜드 로고 클릭 → 홈으로 (전체 초기화 + 맨 위 스크롤) ──
const brandHome = document.getElementById("brandHome");
brandHome.addEventListener("click", () => {
  // GSAP 로고 바운스 피드백
  if (typeof gsap !== "undefined") {
    gsap.fromTo("#brandLogo",
      { scale: 0.75, rotation: -20 },
      { scale: 1, rotation: 0, duration: 0.45, ease: "back.out(2)" }
    );
  }

  // 전체 초기화
  resetAll();

  // 페이지 맨 위로 부드럽게 스크롤
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// 키보드 접근성: Enter / Space 키로도 동작
brandHome.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    brandHome.click();
  }
});

// ── 초기 실행 ─────────────────────────────────────────────
initPageAnimation();
loadPrices();
