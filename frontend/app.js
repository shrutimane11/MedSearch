/* ── Theme ──────────────────────────────────────────────────────────── */
const THEME_KEY = 'medsearch_theme';
const themeToggle = document.getElementById('themeToggle');

function initTheme() {
    const savedTheme = localStorage.getItem(THEME_KEY) || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem(THEME_KEY, newTheme);
}

if (themeToggle) {
    themeToggle.addEventListener('click', toggleTheme);
}

initTheme();

/* ── Config ─────────────────────────────────────────────────────────── */
const API_BASE = '';

/* ── State ──────────────────────────────────────────────────────────── */
let sortMode    = 'price_asc';
let sliderMin   = 0;
let sliderMax   = 1000;
let debounceTimer = null;

/* ── DOM Refs ───────────────────────────────────────────────────────── */
const searchInput    = document.getElementById('searchInput');
const clearBtn       = document.getElementById('clearBtn');
const mgMinInput     = document.getElementById('mgMin');
const mgMaxInput     = document.getElementById('mgMax');
const numMinInput    = document.getElementById('numMin');
const numMaxInput    = document.getElementById('numMax');
const sliderFill     = document.getElementById('sliderFill');
const mgDisplay      = document.getElementById('mgDisplay');
const sliderMinLabel = document.getElementById('sliderMinLabel');
const sliderMaxLabel = document.getElementById('sliderMaxLabel');
const sortToggle     = document.getElementById('sortToggle');
const resultsGrid    = document.getElementById('resultsGrid');
const statusBar      = document.getElementById('statusBar');
const emptyState     = document.getElementById('emptyState');
const initialState   = document.getElementById('initialState');
const loadingState   = document.getElementById('loadingState');

/* ── Init ───────────────────────────────────────────────────────────── */
async function init() {
  await loadSliderRange();
  doSearch();
}

/* ── Slider range from API ──────────────────────────────────────────── */
async function loadSliderRange() {
  try {
    const res = await fetch(`${API_BASE}/strength-range`);
    if (!res.ok) return;
    const { min, max } = await res.json();
    sliderMin = Math.floor(min);
    sliderMax = Math.ceil(max);

    mgMinInput.min = sliderMin; mgMinInput.max = sliderMax; mgMinInput.value = sliderMin;
    mgMaxInput.min = sliderMin; mgMaxInput.max = sliderMax; mgMaxInput.value = sliderMax;
    
    numMinInput.min = sliderMin; numMinInput.max = sliderMax; numMinInput.value = sliderMin;
    numMaxInput.min = sliderMin; numMaxInput.max = sliderMax; numMaxInput.value = sliderMax;

    sliderMinLabel.textContent = `${sliderMin} mg`;
    sliderMaxLabel.textContent = `${sliderMax} mg`;

    updateSliderFill();
    updateMgPill();
  } catch (e) {
    console.warn('Could not load strength range from API:', e);
  }
}

/* ── Slider fill visuals ────────────────────────────────────────────── */
function updateSliderFill() {
  const range  = sliderMax - sliderMin;
  if (range === 0) return;
  const minPct = ((+mgMinInput.value - sliderMin) / range) * 100;
  const maxPct = ((+mgMaxInput.value - sliderMin) / range) * 100;
  sliderFill.style.left  = `${minPct}%`;
  sliderFill.style.width = `${maxPct - minPct}%`;
}

function updateMgPill() {
  const lo = +mgMinInput.value;
  const hi = +mgMaxInput.value;
  if (lo === sliderMin && hi === sliderMax) {
    mgDisplay.textContent = 'any';
  } else {
    mgDisplay.textContent = `${lo} – ${hi} mg`;
  }
}

/* ── Search ─────────────────────────────────────────────────────────── */
async function doSearch() {
  const q      = searchInput.value.trim();
  const mgMinV = +mgMinInput.value;
  const mgMaxV = +mgMaxInput.value;

  if (q.length === 0) {
    resultsGrid.innerHTML = '';
    emptyState.hidden = true;
    initialState.hidden = false;
    loadingState.hidden = true;
    statusBar.textContent = '';
    return;
  }

  initialState.hidden = true;
  setLoading(true);

  const params = new URLSearchParams({
    q,
    sort: sortMode,
    limit: 100,
  });
  if (mgMinV > sliderMin) params.set('mg_min', mgMinV);
  if (mgMaxV < sliderMax) params.set('mg_max', mgMaxV);

  try {
    const res = await fetch(`${API_BASE}/search?${params}`);
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const { results, total } = await res.json();
    renderResults(results, total, q);
  } catch (err) {
    renderError(err);
  } finally {
    setLoading(false);
  }
}

/* ── Render ─────────────────────────────────────────────────────────── */
function renderResults(results, total, q) {
  resultsGrid.innerHTML = '';
  emptyState.hidden = true;
  initialState.hidden = true;

  if (results.length === 0) {
    emptyState.hidden = false;
    statusBar.textContent = '';
    return;
  }

  statusBar.textContent = `Showing ${results.length} of ${total.toLocaleString()} results${q ? ` for "${q}"` : ''}`;

  results.forEach((med, i) => {
    const card = buildCard(med, i);
    resultsGrid.appendChild(card);
  });
}

function buildCard(med, index) {
  const card = document.createElement('div');
  card.className = 'med-card glass';
  card.style.animationDelay = `${Math.min(index, 20) * 30}ms`;

  const price    = formatPrice(med.price_inr);
  const predRaw  = med.predicted_price ? +med.predicted_price : null;
  const predStr  = predRaw ? formatPrice(predRaw) : null;
  const mg       = med.strength_numeric != null ? `${med.strength_numeric} mg` : med.primary_strength || '';
  const dosage   = med.dosage_form    ? capitalize(med.dosage_form)    : '';
  const ing      = med.primary_ingredient ? capitalize(med.primary_ingredient) : '';
  const cls      = med.therapeutic_class  ? capitalize(med.therapeutic_class)  : '';
  const mfg      = med.manufacturer || '';

  // Determine deal vs premium vs neutral
  let dealBadge = '';
  let savingsMsg = '';
  let savingsClass = '';
  
  if (predRaw && med.price_inr != null) {
    const actual = +med.price_inr;
    const diff = actual - predRaw;
    const percentage = Math.abs(Math.round((diff / predRaw) * 100));
    
    if (actual < predRaw * 0.9) {
      dealBadge = '<span class="deal-badge deal-good">🟢 Great Deal</span>';
      savingsMsg = `🎉 You save ~${percentage}% vs market average!`;
      savingsClass = 'savings-good';
    } else if (actual > predRaw * 1.1) {
      dealBadge = '<span class="deal-badge deal-prem">⬛ Premium Brand</span>';
      savingsMsg = `⚠️ Costs ~${percentage}% more than market average.`;
      savingsClass = 'savings-prem';
    } else {
      dealBadge = '<span class="deal-badge deal-fair">➖ Fair Value</span>';
      savingsMsg = `✅ Priced fairly near market average.`;
      savingsClass = 'savings-fair';
    }
  }

  const comparisonHtml = predStr ? `
    <div class="price-comparison">
      <div class="price-row">
        <div class="price-info">
          <span class="price-title">🛒 Listed Price</span>
          <span class="price-desc">What you pay at the pharmacy</span>
        </div>
        <div class="price-value actual-price">₹${price}</div>
      </div>
      <div class="price-row ai-row">
        <div class="price-info">
          <span class="price-title">🤖 AI Fair Value</span>
          <span class="price-desc">Market average for this composition</span>
        </div>
        <div class="price-value ai-price">₹${predStr}</div>
      </div>
      <div class="savings-banner ${savingsClass}">
        ${savingsMsg}
      </div>
    </div>
  ` : `
    <div class="price-comparison single-price">
      <div class="price-row">
        <div class="price-info">
          <span class="price-title">🛒 Listed Price</span>
          <span class="price-desc">What you pay at the pharmacy</span>
        </div>
        <div class="price-value actual-price">₹${price}</div>
      </div>
    </div>
  `;

  card.innerHTML = `
    <div class="card-header">
      <div>
        <div class="card-name">${escHtml(med.brand_name || '—')} ${dealBadge}</div>
        <div class="card-manufacturer">${escHtml(mfg)}</div>
      </div>
    </div>
    
    <div class="card-tags">
      ${ing     ? `<span class="tag tag-ingredient">${escHtml(ing)}</span>` : ''}
      ${mg      ? `<span class="tag tag-mg">${escHtml(mg)}</span>`          : ''}
      ${dosage  ? `<span class="tag tag-dosage">${escHtml(dosage)}</span>`  : ''}
    </div>
    
    ${comparisonHtml}
    
    ${cls ? `<div class="card-class">🏥 ${escHtml(cls)}</div>` : ''}
  `;
  return card;
}

function renderError(err) {
  statusBar.textContent = '⚠️ Could not connect to the API. Is the backend running?';
  resultsGrid.innerHTML = '';
  emptyState.hidden = true;
  initialState.hidden = true;
  console.error(err);
}

/* ── Helpers ────────────────────────────────────────────────────────── */
function setLoading(on) {
  loadingState.hidden = !on;
  if (on) {
    resultsGrid.innerHTML = '';
    emptyState.hidden     = true;
    initialState.hidden   = true;
    statusBar.textContent = '';
  }
}

function formatPrice(v) {
  if (v == null) return '—';
  return (+v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function triggerSearch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(doSearch, 300);
}

/* ── Event Listeners ────────────────────────────────────────────────── */

// Search input
searchInput.addEventListener('input', () => {
  clearBtn.hidden = searchInput.value.length === 0;
  triggerSearch();
});

// Clear button
clearBtn.addEventListener('click', () => {
  searchInput.value = '';
  clearBtn.hidden = true;
  triggerSearch();
});

// Sort toggle
sortToggle.addEventListener('click', (e) => {
  const btn = e.target.closest('.sort-btn');
  if (!btn) return;
  document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  sortMode = btn.dataset.sort;
  doSearch();
});

// Dual range slider
function handleSlider() {
  const lo = +mgMinInput.value;
  const hi = +mgMaxInput.value;

  // Enforce min < max
  if (lo > hi) {
    if (this === mgMinInput) mgMinInput.value = hi;
    else                     mgMaxInput.value = lo;
  }
  
  // Sync with number inputs
  numMinInput.value = mgMinInput.value;
  numMaxInput.value = mgMaxInput.value;

  updateSliderFill();
  updateMgPill();
  triggerSearch();
}

// Number inputs
function handleNumberInput() {
  let val = +this.value;
  
  // Clamp to bounds
  if (val < sliderMin) val = sliderMin;
  if (val > sliderMax) val = sliderMax;
  this.value = val;

  // Enforce min < max
  const lo = +numMinInput.value;
  const hi = +numMaxInput.value;
  
  if (lo > hi) {
    if (this === numMinInput) numMinInput.value = hi;
    else                      numMaxInput.value = lo;
  }

  // Sync with sliders
  mgMinInput.value = numMinInput.value;
  mgMaxInput.value = numMaxInput.value;

  updateSliderFill();
  updateMgPill();
  triggerSearch();
}

mgMinInput.addEventListener('input', handleSlider);
mgMaxInput.addEventListener('input', handleSlider);
numMinInput.addEventListener('input', handleNumberInput);
numMaxInput.addEventListener('input', handleNumberInput);

/* ── Boot ───────────────────────────────────────────────────────────── */
init();

/* ── Boot ───────────────────────────────────────────────────────────── */
init();
