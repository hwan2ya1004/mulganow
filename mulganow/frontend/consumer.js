// consumer.js — 물가나우 생필품 가격 정보 페이지

// ── DOM 참조 ──────────────────────────────────────────────
const cardGrid     = document.getElementById("cardGrid");
const skeletonGrid = document.getElementById("skeletonGrid");
const statusRow    = document.getElementById("statusRow");
const statusText   = document.getElementById("statusText");
const searchInput  = document.getElementById("searchInput");
const searchBtn    = document.getElementById("searchBtn");
const clearBtn     = document.getElementById("clearBtn");
const resetBtn     = document.getElementById("resetBtn");

const modalBackdrop = document.getElementById("modalBackdrop");
const modalBox      = document.getElementById("modalBox");
const modalClose    = document.getElementById("modalClose");
const modalTitle    = document.getElementById("modalTitle");
const modalSub      = document.getElementById("modalSub");
const modalIcon     = document.getElementById("modalIcon");
const priceCompare  = document.getElementById("priceCompare");
const shopSection   = document.getElementById("shopSection");
const shopList      = document.getElementById("shopList");
const shopAdArea    = document.getElementById("shopAdArea");

// ── 상태 ──────────────────────────────────────────────────
let allItems    = [];
let currentCat  = "";
let currentSort = "default";
let currentItem = null;
let inspectDay  = "";   // 실제 조사일 (API 응답에서 추출)

// ── 소분류 코드 → 카테고리명/아이콘 매핑 ─────────────────
// 실제 API 응답의 goodSmlclsCode는 9자리 (예: 030101001)
// 앞 6자리 기준으로 대분류 매핑
const CAT_MAP = {
  // 신선식품 (030101xxx)
  "030101": { name: "신선식품",    icon: "🥩" },
  // 채소·농산물 (030102xxx)
  "030102": { name: "채소·농산물", icon: "🥬" },
  // 수산물 (030103xxx)
  "030103": { name: "수산물",      icon: "🐟" },
  // 가공식품 (030201xxx ~ 030202xxx)
  "030201": { name: "가공식품",    icon: "🍜" },
  "030202": { name: "수산가공품",  icon: "🥫" },
  // 유제품·육가공 (030203xxx)
  "030203": { name: "유제품·육가공", icon: "🥛" },
  // 조미료·양념 (030204xxx)
  "030204": { name: "조미료·양념", icon: "🧂" },
  // 과자·빙과 (030205xxx)
  "030205": { name: "과자·빙과",   icon: "🍬" },
  // 음료·주류 (030206xxx)
  "030206": { name: "음료·주류",   icon: "🧃" },
  // 위생·바디케어 (030301xxx)
  "030301": { name: "위생·바디케어", icon: "🧴" },
  // 생활용품·세제 (030302xxx)
  "030302": { name: "생활용품·세제", icon: "🧹" },
  // 의약외품·뷰티 (030304xxx)
  "030304": { name: "의약외품·뷰티", icon: "💊" },
  // 반려동물 (030305xxx)
  "030305": { name: "반려동물",    icon: "🐾" },
};

function getCatInfo(smlclsCode) {
  if (!smlclsCode) return { name: "기타", icon: "🛒" };
  // 앞 6자리로 매핑
  const prefix6 = smlclsCode.substring(0, 6);
  return CAT_MAP[prefix6] || { name: "기타", icon: "🛒" };
}

// ── 단위 표시 문자열 생성 ─────────────────────────────────
function buildUnitLabel(item) {
  const cnt  = item.total_cnt || item.base_cnt || "";
  const div  = item.total_div_code || item.unit_div_code || "";
  if (!cnt && !div) return "";
  return `${cnt}${div}`.trim();
}

// ══════════════════════════════════════════════════════════
// GSAP 페이지 진입 애니메이션
// ══════════════════════════════════════════════════════════
function initPageAnimation() {
  if (typeof gsap === "undefined") return;

  const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

  tl.to("#topbar",    { opacity: 1, y: 0, duration: 0.6, clearProps: "transform" }, 0);
  tl.from("#brandLogo", { scale: 0, rotation: -30, duration: 0.5, ease: "back.out(1.7)" }, 0.2);
  tl.to("#heroTitle", { opacity: 1, y: 0, duration: 0.7, clearProps: "transform" }, 0.3);
  tl.to("#heroSub",   { opacity: 1, y: 0, duration: 0.6, clearProps: "transform" }, 0.5);
  tl.to("#heroSearch",{ opacity: 1, scale: 1, duration: 0.5, ease: "back.out(1.4)", clearProps: "transform" }, 0.65);
  tl.to("#filterBar", { opacity: 1, y: 0, duration: 0.5, clearProps: "transform" }, 0.8);

  gsap.set("#heroTitle",  { y: 30 });
  gsap.set("#heroSub",    { y: 20 });
  gsap.set("#heroSearch", { scale: 0.92 });
  gsap.set("#filterBar",  { y: 16 });
}

if (typeof gsap !== "undefined") {
  gsap.set("#heroTitle",  { y: 30 });
  gsap.set("#heroSub",    { y: 20 });
  gsap.set("#heroSearch", { scale: 0.92 });
  gsap.set("#filterBar",  { y: 16 });
}

// ── 카드 stagger 애니메이션 ──────────────────────────────
// 카드가 많을수록 stagger 총 시간이 선형으로 늘어나 메인 스레드를 오래 점유하므로
// 처음 일부 카드만 순차 등장시키고 나머지는 바로 최종 상태로 표시한다.
const MAX_STAGGER_CARDS = 30;

function animateCards() {
  if (typeof gsap === "undefined") return;
  const cards = Array.from(document.querySelectorAll(".price-card"));
  const animated = cards.slice(0, MAX_STAGGER_CARDS);
  const rest = cards.slice(MAX_STAGGER_CARDS);

  if (rest.length) {
    gsap.set(rest, { opacity: 1, y: 0, scale: 1, clearProps: "transform" });
  }

  gsap.fromTo(animated,
    { opacity: 0, y: 24, scale: 0.96 },
    { opacity: 1, y: 0, scale: 1, duration: 0.45, stagger: 0.045, ease: "power2.out", clearProps: "transform" }
  );
}

// ── 모달 열기/닫기 ────────────────────────────────────────
function openModal() {
  modalBackdrop.classList.add("open");
  if (typeof gsap === "undefined") return;
  gsap.fromTo(modalBackdrop, { opacity: 0 }, { opacity: 1, duration: 0.25, ease: "power2.out" });
  gsap.fromTo(modalBox, { opacity: 0, scale: 0.88, y: 20 }, { opacity: 1, scale: 1, y: 0, duration: 0.35, ease: "back.out(1.5)" });
}

function closeModal() {
  if (typeof gsap === "undefined") {
    modalBackdrop.classList.remove("open");
    return;
  }
  gsap.to(modalBox, { opacity: 0, scale: 0.92, y: 12, duration: 0.22, ease: "power2.in" });
  gsap.to(modalBackdrop, {
    opacity: 0, duration: 0.25, ease: "power2.in",
    onComplete: () => {
      modalBackdrop.classList.remove("open");
      gsap.set([modalBox, modalBackdrop], { clearProps: "all" });
    },
  });
}

// ── 가격 카운트업 애니메이션 ─────────────────────────────
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
      val: target, duration: 0.8, ease: "power2.out",
      onUpdate() { el.textContent = Math.round(obj.val).toLocaleString("ko-KR") + "원"; },
    });
  });
  gsap.fromTo(
    priceCompare.querySelectorAll(".compare-item"),
    { opacity: 0, y: 12 },
    { opacity: 1, y: 0, duration: 0.35, stagger: 0.07, ease: "power2.out" }
  );
}

// ── 데이터 로드 ───────────────────────────────────────────
let _pricePollingTimer = null;

async function loadPrices() {
  showSkeleton(true);
  setStatus("", false);

  // 기존 폴링 타이머 취소
  if (_pricePollingTimer) {
    clearTimeout(_pricePollingTimer);
    _pricePollingTimer = null;
  }

  const q   = searchInput.value.trim();
  const cat = currentCat;

  // 검색/카테고리 필터가 있으면 fast 모드 사용 안 함 (서버 필터링 필요)
  const useFast = !q;

  let url = `/api/consumer-prices`;
  const params = [];
  if (q)       params.push(`q=${encodeURIComponent(q)}`);
  if (useFast) params.push(`fast=1`);
  if (params.length) url += "?" + params.join("&");

  try {
    const res  = await fetch(url);
    const data = await res.json();

    if (!data.ok) {
      showSkeleton(false);
      const errMsg = data.error || "알 수 없는 오류";
      setStatus(`⚠️ 데이터를 불러오지 못했습니다: ${errMsg}`, true);
      cardGrid.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">⚠️</div>
          <h3>데이터를 불러오지 못했습니다</h3>
          <p style="word-break:keep-all;">${escapeHtml(errMsg)}</p>
        </div>`;
      cardGrid.style.display = "grid";
      return;
    }

    allItems   = data.items;
    inspectDay = data.inspect_day || "";
    renderFiltered();

    // 가격이 아직 준비 안 됐으면 폴링으로 업데이트
    if (useFast && data.prices_ready === false) {
      setStatus("⏳ 상품 목록을 표시했습니다. 가격 정보를 불러오는 중...", false);
      _schedulePriceRefresh();
    }
  } catch (err) {
    showSkeleton(false);
    setStatus("⚠️ 서버에 연결할 수 없습니다. 백엔드(app.py)가 실행 중인지 확인해주세요.", true);
  }
}

// 가격 데이터 준비 여부를 폴링하여 준비되면 카드 업데이트
function _schedulePriceRefresh(attempt = 0) {
  const MAX_ATTEMPTS = 20;  // 최대 20회 (약 2분)
  const INTERVAL_MS  = 6000; // 6초마다

  if (attempt >= MAX_ATTEMPTS) {
    setStatus("⚠️ 가격 정보를 불러오지 못했습니다. 잠시 후 새로고침해주세요.", true);
    return;
  }

  _pricePollingTimer = setTimeout(async () => {
    try {
      const res  = await fetch(`/api/consumer-prices?fast=1`);
      const data = await res.json();

      if (data.ok && data.prices_ready !== false) {
        // 가격 준비 완료 → 카드 업데이트
        allItems   = data.items;
        inspectDay = data.inspect_day || "";
        renderFiltered();
        setStatus("", false);
        // 상태 텍스트는 renderFiltered()에서 설정됨
      } else {
        // 아직 준비 안 됨 → 재시도
        _schedulePriceRefresh(attempt + 1);
      }
    } catch (e) {
      _schedulePriceRefresh(attempt + 1);
    }
  }, INTERVAL_MS);
}

// ── 정렬 ─────────────────────────────────────────────────
function sortItems(items) {
  const arr = [...items];
  if (currentSort === "price-desc") {
    arr.sort((a, b) => (b.price ?? -1) - (a.price ?? -1));
  } else if (currentSort === "price-asc") {
    arr.sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity));
  }
  return arr;
}

// ── 필터 적용 후 렌더 ─────────────────────────────────────
function renderFiltered() {
  let filtered = allItems;

  if (currentCat) {
    filtered = allItems.filter(it =>
      (it.smlcls_code || "").startsWith(currentCat)
    );
  }

  showSkeleton(false);

  if (filtered.length === 0) {
    setStatus("", false);
    cardGrid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <h3>검색 결과가 없습니다</h3>
        <p>다른 상품명이나 카테고리를 선택해보세요.</p>
      </div>`;
    cardGrid.style.display = "grid";
    return;
  }

  filtered = sortItems(filtered);

  const sortLabel = currentSort === "price-desc" ? " · 💰 가격 높은 순 정렬"
                  : currentSort === "price-asc"  ? " · 💸 가격 낮은 순 정렬"
                  : "";

  const dayLabel = inspectDay
    ? ` · 조사일: ${inspectDay.replace(/(\d{4})(\d{2})(\d{2})/, "$1-$2-$3")}`
    : "";

  setStatus(`📦 총 ${filtered.length}개 상품 · 한국소비자원 참가격${dayLabel}${sortLabel}`, false);
  renderCards(filtered);
}

// ── 카드 렌더 ─────────────────────────────────────────────
function renderCards(items) {
  cardGrid.innerHTML = "";
  cardGrid.style.display = "grid";

  const fragment = document.createDocumentFragment();

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "price-card";

    const catInfo  = getCatInfo(item.smlcls_code);
    const unitLabel = buildUnitLabel(item);
    const priceHtml = item.price !== null && item.price !== undefined
      ? `<div class="card-price">${item.price.toLocaleString("ko-KR")}<small>원</small></div>`
      : `<div class="card-price" style="color:var(--muted);font-size:1rem;">가격 정보 없음</div>`;

    const detailHtml = item.detail_mean
      ? `<div class="card-detail">${escapeHtml(item.detail_mean)}</div>`
      : "";

    card.innerHTML = `
      <div class="card-top">
        <span class="card-category">${escapeHtml(catInfo.name)}</span>
      </div>
      <div class="card-name">${escapeHtml(item.good_name || "이름 없음")}</div>
      <div class="card-unit">${escapeHtml(unitLabel)}</div>
      ${priceHtml}
      ${detailHtml}
    `;

    card.addEventListener("click", () => openDetailModal(item, catInfo.icon));
    fragment.appendChild(card);
  });

  cardGrid.appendChild(fragment);

  animateCards();
}

// ── 상세 모달 열기 ────────────────────────────────────────
function openDetailModal(item, icon) {
  currentItem = item;

  modalIcon.textContent  = icon || "🛒";
  modalTitle.textContent = item.good_name || "상품 상세";

  const unitLabel = buildUnitLabel(item);
  const catInfo   = getCatInfo(item.smlcls_code);
  const dayStr    = item.inspect_day
    ? item.inspect_day.replace(/(\d{4})(\d{2})(\d{2})/, "$1-$2-$3")
    : "";

  modalSub.textContent = [
    catInfo.name,
    unitLabel,
    dayStr ? `조사일: ${dayStr}` : "",
  ].filter(Boolean).join(" · ");

  // 가격 정보 패널
  const makeRow = (label, val, isMain = false) => `
    <div class="compare-item">
      <div class="compare-label">${label}</div>
      <div class="compare-price${isMain ? " today" : ""}"
           data-raw="${val !== null && val !== undefined ? val : ""}">
        ${val !== null && val !== undefined ? val.toLocaleString("ko-KR") + "원" : "-"}
      </div>
    </div>`;

  // 상세 설명 행
  const detailRow = item.detail_mean ? `
    <div class="compare-item" style="grid-column:1/-1;">
      <div class="compare-label">상품 설명</div>
      <div style="font-size:0.85rem;color:var(--ink);padding-top:2px;">${escapeHtml(item.detail_mean)}</div>
    </div>` : "";

  priceCompare.innerHTML =
    makeRow("최저가", item.price, true) +
    makeRow("상품 ID", null) +   // 빈 자리 (레이아웃 균형)
    detailRow;

  // 상품 ID는 숫자가 아니므로 별도 처리
  const idEl = priceCompare.querySelectorAll(".compare-price")[1];
  if (idEl) {
    idEl.dataset.raw = "";
    idEl.textContent = item.good_id || "-";
  }

  openModal();
  animateComparePrices();

  // 애드픽 온라인 최저가 섹션 표시
  shopSection.style.display = "block";
  loadShopPrices(item.good_name, item.price);
}

// ── 생필품 상품명 → 검색어 변환 ──────────────────────────
// "해표 꽃소금(1kg)" → "해표 꽃소금"
// "서울우유 흰우유(1L)" → "서울우유 흰우유"
// "무(줄기 없는 무, 1.5kg)" → "무(줄기 없는 무, 1.5kg)" (그대로 사용 - 짧은 단어 방지)
function buildShopKeyword(goodName) {
  if (!goodName) return "";
  // 괄호 및 괄호 안 내용 제거
  const cleaned = goodName.replace(/\s*[\(（][^)）]*[\)）]/g, "").trim();
  // 결과가 너무 짧으면(2글자 이하) 원본 상품명 그대로 사용
  if (cleaned.length <= 2) return goodName;
  return cleaned;
}

// ── 최저가 캐시 (세션 내 중복 API 호출 방지) ─────────────
const shopPriceCache = {};

// ── 애드픽 최저가 로드 ────────────────────────────────────
async function loadShopPrices(goodName, todayPrice) {
  const keyword  = buildShopKeyword(goodName);
  const cacheKey = keyword;

  // 캐시 히트: 바로 렌더
  if (shopPriceCache[cacheKey]) {
    renderShopItems(shopPriceCache[cacheKey]);
    return;
  }

  // 로딩 상태
  shopList.innerHTML = `
    <div class="shop-loading" id="shopLoading">
      <span class="shop-spinner"></span> 최저가 검색 중...
    </div>`;
  if (shopAdArea) shopAdArea.innerHTML = "";

  const priceParam = todayPrice ? `&price=${encodeURIComponent(todayPrice)}` : "";
  const apiUrl = `/api/consumer-shop-prices?q=${encodeURIComponent(keyword)}${priceParam}`;

  // 재시도 헬퍼
  const MAX_RETRY = 3;
  const RETRY_DELAY_MS = 1500;

  async function fetchWithRetry(url, attempt) {
    try {
      const res  = await fetch(url);
      const data = await res.json();
      if (data.ok && data.items && data.items.length > 0) return data;
      if (attempt < MAX_RETRY) {
        await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
        return fetchWithRetry(url, attempt + 1);
      }
      return data;
    } catch (err) {
      if (attempt < MAX_RETRY) {
        await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
        return fetchWithRetry(url, attempt + 1);
      }
      throw err;
    }
  }

  try {
    const data = await fetchWithRetry(apiUrl, 1);
    if (!data.ok || !data.items || data.items.length === 0) {
      shopList.innerHTML = `<div class="shop-error">온라인 최저가 정보가 없습니다.</div>`;
      renderShopAd(keyword);
      return;
    }
    shopPriceCache[cacheKey] = data.items;
    renderShopItems(data.items);
  } catch (err) {
    shopList.innerHTML = `<div class="shop-error">최저가 정보를 불러오지 못했습니다.</div>`;
    renderShopAd(keyword);
  }
}

// ── 최저가 상품 목록 렌더 ─────────────────────────────────
function renderShopItems(items) {
  const rankClass = (i) => i === 0 ? "top1" : i === 1 ? "top2" : i === 2 ? "top3" : "";
  const rankLabel = (i) => i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `${i + 1}`;

  const safeLink = (it) => {
    const link = it.link || "";
    if (link.startsWith("http://") || link.startsWith("https://") || link.startsWith("//")) return link;
    return null;
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

  if (typeof gsap !== "undefined") {
    gsap.fromTo(
      shopList.querySelectorAll(".shop-item"),
      { opacity: 0, x: -10 },
      { opacity: 1, x: 0, duration: 0.3, stagger: 0.06, ease: "power2.out" }
    );
  }

  renderShopAd();
}

// ── 제휴 쇼핑몰 배너 렌더 ────────────────────────────────
const AFFILIATE_MALLS = [
  { name: "11번가",        icon: "🛍️", link: "https://bitl.bz/lrxjLn" },
  { name: "SSG",           icon: "🛒", link: "https://bitl.bz/yJP4tM" },
  { name: "컬리",          icon: "🥦", link: "https://bitl.bz/EJGpp1" },
  { name: "GS SHOP",       icon: "🏪", link: "https://bitl.bz/qygyWP" },
  { name: "이마트몰",      icon: "🏬", link: "https://bitl.bz/Ro8mNH" },
  { name: "Hmall",         icon: "🎁", link: "https://bitl.bz/bJ4MJW" },
  { name: "CJ THE MARKET", icon: "🍱", link: "https://bitl.bz/VuyZaB" },
  { name: "롯데홈쇼핑",    icon: "📦", link: "https://bitl.bz/kOT087" },
];

function renderShopAd() {
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

  if (typeof gsap !== "undefined") {
    gsap.fromTo(
      shopAdArea.querySelectorAll(".shop-mall-btn"),
      { opacity: 0, y: 8, scale: 0.92 },
      { opacity: 1, y: 0, scale: 1, duration: 0.3, stagger: 0.04, ease: "power2.out" }
    );
  }
}

// ── 유틸 ──────────────────────────────────────────────────
function escapeHtml(str) {
  if (!str) return "";
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

// ── 전체 초기화 ───────────────────────────────────────────
function resetAll() {
  searchInput.value = "";
  clearBtn.style.display = "none";
  currentCat  = "";
  currentSort = "default";

  document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
  document.querySelector('.filter-btn[data-cat=""]').classList.add("active");

  document.querySelectorAll(".sort-btn").forEach(b => b.classList.remove("active"));
  document.querySelector('.sort-btn[data-sort="default"]').classList.add("active");

  if (typeof gsap !== "undefined") {
    gsap.fromTo(resetBtn,
      { rotation: -180, scale: 0.85 },
      { rotation: 0, scale: 1, duration: 0.45, ease: "back.out(2)" }
    );
  }

  loadPrices();
}

// ── 이벤트 바인딩 ─────────────────────────────────────────

// 카테고리 필터
document.querySelectorAll(".filter-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentCat = btn.dataset.cat || "";

    if (typeof gsap !== "undefined") {
      gsap.fromTo(btn, { scale: 0.88 }, { scale: 1, duration: 0.3, ease: "back.out(2)" });
    }

    // 카테고리 필터는 클라이언트 사이드에서 처리 (이미 전체 데이터 로드됨)
    renderFiltered();
  });
});

// 검색
searchBtn.addEventListener("click", () => {
  if (typeof gsap !== "undefined") {
    gsap.fromTo(searchBtn, { scale: 0.93 }, { scale: 1, duration: 0.25, ease: "back.out(2)" });
  }
  loadPrices();
});

searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadPrices();
});

// 검색어 X 버튼
searchInput.addEventListener("input", () => {
  clearBtn.style.display = searchInput.value ? "flex" : "none";
});

clearBtn.addEventListener("click", () => {
  searchInput.value = "";
  clearBtn.style.display = "none";
  searchInput.focus();
  loadPrices();
});

// 초기화 버튼
resetBtn.addEventListener("click", resetAll);

// 정렬 버튼
document.querySelectorAll(".sort-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".sort-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentSort = btn.dataset.sort;

    if (typeof gsap !== "undefined") {
      gsap.fromTo(btn, { scale: 0.88 }, { scale: 1, duration: 0.28, ease: "back.out(2)" });
    }

    renderFiltered();
  });
});

// 모달 닫기
modalClose.addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", (e) => {
  if (e.target === modalBackdrop) closeModal();
});

// ESC 키
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && modalBackdrop.classList.contains("open")) closeModal();
});

// 브랜드 로고 클릭 → 초기화
const brandHome = document.getElementById("brandHome");
brandHome.addEventListener("click", () => {
  if (typeof gsap !== "undefined") {
    gsap.fromTo("#brandLogo",
      { scale: 0.75, rotation: -20 },
      { scale: 1, rotation: 0, duration: 0.45, ease: "back.out(2)" }
    );
  }
  resetAll();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

brandHome.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    brandHome.click();
  }
});

// ── 초기 실행 ─────────────────────────────────────────────
initPageAnimation();
loadPrices();
