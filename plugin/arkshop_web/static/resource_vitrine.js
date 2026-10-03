/* Vitrine de Recursos — mercado P2P de recursos (somente Âmbar).
 *
 * Contrato: docs/VITRINE_RECURSOS_SPEC.md e resource_vitrine_routes.py. Rotas usadas (todas sob RV_API):
 *   GET  /api/market/resources/catalog | /listings | /my
 *   PUT  /api/market/resources/my/stock/<resource_id>/listing
 *   POST /api/market/resources/my/withdraw
 *   POST /api/market/resources/listings/<stock_id>/purchase
 *   GET|PUT /api/market/resources/admin/catalog · DELETE /api/market/resources/admin/catalog/<id>
 *   PUT  /api/market/resources/admin/settings · POST /api/market/resources/admin/claims/expire-stale
 *
 * Carregado por <script defer> no index.html; usa helpers globais do portal (fetchJson, toast, escHtml,
 * refreshPlayerBalance, updateBalanceDisplays, promptLogin, copyIngameCmd, amberIconHtml, fmtDate, _auth).
 * Todos os nomes públicos usam o prefixo `rv` / `RV_` para não colidir com a vitrine de dinos.
 * O backend é a fonte da verdade: as validações aqui são só conveniência de UX.
 * Estilos: resource_vitrine.css (prefixo rv-).
 */
"use strict";

const RV_API = "/api/market/resources";
const RV_PAGE_SIZE = 24;
const RV_MAX_LOT_SIZE = 1000000;
const RV_MAX_LOT_PRICE = 100000000;
const RV_MAX_LOTS_PER_PURCHASE = 1000;
const RV_MAX_STACK_SIZE = 1000000;

const RV = {
  tab: "explore",
  catalog: [],
  listings: [],
  offset: 0,
  hasMore: false,
  listSeq: 0,
  mine: null,
  mineSeq: 0,
  buy: null,
  busy: false,
  admin: null,
  adminEdit: null,
  withdraw: null,
  countdownTimer: null,
  lastFocus: null,
};

// ── Utilidades ───────────────────────────────────────────────────────────────

function rvEsc(v) {
  return typeof escHtml === "function"
    ? escHtml(String(v == null ? "" : v))
    : String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function rvFmt(n) {
  return Number(n || 0).toLocaleString("pt-BR");
}

function rvAmberIcon(size) {
  return typeof amberIconHtml === "function" ? amberIconHtml(size || 16) : "";
}

function rvAmber(n) {
  return `${rvAmberIcon(16)} ${rvFmt(n)}`;
}

function rvRequestId() {
  return "rv" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
}

function rvAuthed() {
  return !!(typeof _auth !== "undefined" && _auth && _auth.authenticated);
}

function rvMySteamId() {
  return String((typeof _auth !== "undefined" && _auth && _auth.steam_id) || "");
}

function rvShortSteam(id) {
  const s = String(id || "");
  return s.length > 6 ? "…" + s.slice(-6) : s || "—";
}

function rvById(id) {
  return document.getElementById(id);
}

function rvAnnounce(msg) {
  const el = rvById("rv-live");
  if (el) el.textContent = String(msg || "");
}

function rvIconFor(res) {
  const t = `${(res && res.name) || ""} ${(res && res.blueprint) || ""}`.toLowerCase();
  const map = [
    [/metal|ingot|lingote/, "🔩"],
    [/stone|pedra/, "🪨"],
    [/wood|madeira|log/, "🪵"],
    [/fiber|fibra/, "🌿"],
    [/thatch|palha/, "🌾"],
    [/hide|couro/, "🟫"],
    [/pelt|pele/, "🐺"],
    [/flint|silex|sílex/, "🔥"],
    [/crystal|cristal/, "💎"],
    [/obsidian|obsidiana/, "🖤"],
    [/oil|óleo|oleo/, "🛢️"],
    [/sulfur|enxofre/, "🟡"],
    [/gunpowder|p[óo]lvora/, "💥"],
    [/polymer|pol[íi]mero/, "🧪"],
    [/element|elemento/, "⚛️"],
    [/pearl|p[ée]rola/, "⚪"],
    [/silica/, "🔮"],
    [/charcoal|carv[ãa]o/, "⚫"],
    [/berry|berries|baga/, "🫐"],
    [/meat|carne/, "🥩"],
  ];
  for (const [re, icon] of map) if (re.test(t)) return icon;
  return "📦";
}

function rvIconHtml(res) {
  return `<div class="rv-icon" aria-hidden="true">${rvIconFor(res)}</div>`;
}

/** Normaliza o erro de fetchJson em {code, message, data, status}. */
function rvErrInfo(e) {
  const d = (e && e.data) || {};
  return {
    code: String(d.code || ""),
    message: String(d.error || (e && e.message) || "Erro inesperado"),
    data: d,
    status: (e && e.status) || 0,
  };
}

function rvApi(path, opts) {
  const o = Object.assign({ retries: 0, timeoutMs: 20000 }, opts || {});
  return fetchJson(RV_API + path, o);
}

function rvHoursText(expiresAtIso, hoursFallback) {
  let ms = null;
  if (expiresAtIso) {
    const t = Date.parse(expiresAtIso);
    if (!isNaN(t)) ms = t - Date.now();
  }
  if (ms == null && hoursFallback != null) ms = Number(hoursFallback) * 3600000;
  if (ms == null) return "—";
  if (ms <= 0) return "expirando";
  const totalMin = Math.floor(ms / 60000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return h > 0 ? `${h}h ${String(m).padStart(2, "0")}min` : `${m}min`;
}

function rvTickCountdowns() {
  document.querySelectorAll("[data-rv-exp]").forEach((el) => {
    el.textContent = rvHoursText(el.getAttribute("data-rv-exp"), null);
  });
}

function rvEnsureTimer() {
  if (RV.countdownTimer) return;
  RV.countdownTimer = setInterval(rvTickCountdowns, 30000);
}

// ── Modal acessível (reaproveita .modal-backdrop/.modal do portal) ───────────

function rvModalEl(id) {
  let el = rvById(id);
  if (el) return el;
  el = document.createElement("div");
  el.id = id;
  el.className = "modal-backdrop rv-modal hidden";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-modal", "true");
  el.setAttribute("aria-labelledby", id + "-title");
  el.addEventListener("mousedown", (ev) => {
    if (ev.target === el && !RV.busy) rvCloseModal(id);
  });
  document.body.appendChild(el);
  return el;
}

function rvOpenModal(id, { title, body, footer, wide }) {
  const el = rvModalEl(id);
  const wasHidden = el.classList.contains("hidden");
  el.classList.toggle("rv-modal--wide", !!wide);
  el.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <div class="modal-title" id="${id}-title">${rvEsc(title)}</div>
        <button type="button" class="modal-close" aria-label="Fechar" onclick="rvCloseModal('${id}')">✕</button>
      </div>
      <div id="${id}-body">${body}</div>
      <div class="modal-footer" id="${id}-footer">${footer}</div>
    </div>`;
  if (wasHidden) RV.lastFocus = document.activeElement;
  el.classList.remove("hidden");
  const first = el.querySelector("input:not([disabled]), select:not([disabled]), textarea:not([disabled])")
    || el.querySelector(".modal-footer .btn-primary, .modal-footer .btn-success, .modal-footer .btn");
  if (first) setTimeout(() => { try { first.focus(); } catch (_) {} }, 30);
}

function rvCloseModal(id) {
  const el = rvById(id);
  if (!el) return;
  el.classList.add("hidden");
  RV.busy = false;
  try {
    if (RV.lastFocus && document.contains(RV.lastFocus)) RV.lastFocus.focus();
  } catch (_) {}
}

document.addEventListener("keydown", (ev) => {
  if (ev.key !== "Escape" || RV.busy) return;
  document.querySelectorAll(".rv-modal:not(.hidden)").forEach((el) => rvCloseModal(el.id));
});

// ── Aba do Comércio: sub-abas ────────────────────────────────────────────────

function rvOnTabShown() {
  rvEnsureTimer();
  rvSetTab(RV.tab || "explore");
}

function rvSetTab(name) {
  RV.tab = name === "mine" ? "mine" : "explore";
  document.querySelectorAll("[data-rv-tab]").forEach((btn) => {
    const on = btn.getAttribute("data-rv-tab") === RV.tab;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
    btn.setAttribute("tabindex", on ? "0" : "-1");
  });
  const ex = rvById("rv-sub-explore");
  const mi = rvById("rv-sub-mine");
  if (ex) ex.classList.toggle("active", RV.tab === "explore");
  if (mi) mi.classList.toggle("active", RV.tab === "mine");
  if (RV.tab === "explore") {
    rvLoadCatalog();
    rvLoadListings();
  } else {
    rvLoadMine();
  }
}

function rvReload() {
  if (RV.tab === "mine") rvLoadMine();
  else rvLoadListings();
}

function rvTabKey(ev) {
  if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
  ev.preventDefault();
  rvSetTab(RV.tab === "explore" ? "mine" : "explore");
  const btn = document.querySelector(`[data-rv-tab="${RV.tab}"]`);
  if (btn) btn.focus();
}

// ── Explorar ─────────────────────────────────────────────────────────────────

async function rvLoadCatalog() {
  try {
    const d = await rvApi("/catalog", { method: "GET", retries: 1 });
    RV.catalog = Array.isArray(d.resources) ? d.resources : [];
    const sel = rvById("rv-filter-resource");
    if (sel) {
      const cur = sel.value;
      sel.innerHTML = '<option value="">Todos os recursos</option>'
        + RV.catalog.map((r) => `<option value="${Number(r.id)}">${rvEsc(r.name)}</option>`).join("");
      if (cur && RV.catalog.some((r) => String(r.id) === cur)) sel.value = cur;
    }
  } catch (_) {
    /* filtro é opcional; a lista mostra o erro próprio */
  }
}

function rvFilterChanged() {
  RV.offset = 0;
  rvLoadListings();
}

let _rvSellerTimer = null;
function rvSellerInput() {
  clearTimeout(_rvSellerTimer);
  _rvSellerTimer = setTimeout(() => {
    const v = (rvById("rv-filter-seller")?.value || "").trim();
    if (/^\d{17}$/.test(v) || v === "") {
      rvFilterChanged(); // SteamID64 → filtro no servidor
    } else {
      rvRenderListings(); // nome → filtro local na página atual
    }
  }, 250);
}

function rvPrevPage() {
  RV.offset = Math.max(0, RV.offset - RV_PAGE_SIZE);
  rvLoadListings();
}

function rvNextPage() {
  if (RV.hasMore) {
    RV.offset += RV_PAGE_SIZE;
    rvLoadListings();
  }
}

async function rvLoadListings() {
  const grid = rvById("rv-grid");
  if (!grid) return;
  const seq = ++RV.listSeq;
  grid.innerHTML = '<div class="rv-loading" role="status">Carregando recursos à venda…</div>';
  const empty = rvById("rv-empty");
  if (empty) empty.style.display = "none";
  const params = new URLSearchParams();
  params.set("limit", String(RV_PAGE_SIZE + 1));
  params.set("offset", String(RV.offset));
  const rid = rvById("rv-filter-resource")?.value || "";
  if (rid) params.set("resource_id", rid);
  const seller = (rvById("rv-filter-seller")?.value || "").trim();
  if (/^\d{17}$/.test(seller)) params.set("seller_steam_id", seller);
  try {
    const d = await rvApi("/listings?" + params.toString(), { method: "GET", retries: 1 });
    if (seq !== RV.listSeq) return;
    const rows = Array.isArray(d.listings) ? d.listings : [];
    RV.hasMore = rows.length > RV_PAGE_SIZE;
    RV.listings = rows.slice(0, RV_PAGE_SIZE);
    rvRenderListings();
  } catch (e) {
    if (seq !== RV.listSeq || (e && e.stale)) return;
    const info = rvErrInfo(e);
    grid.innerHTML = `<div class="rv-error" style="grid-column:1/-1;" role="alert">${rvEsc(info.message)}</div>`;
  }
}

function rvRenderListings() {
  const grid = rvById("rv-grid");
  if (!grid) return;
  const seller = (rvById("rv-filter-seller")?.value || "").trim().toLowerCase();
  let rows = RV.listings;
  if (seller && !/^\d{17}$/.test(seller)) {
    rows = rows.filter((l) => `${l.seller_display_name || ""} ${l.seller_steam_id || ""}`.toLowerCase().includes(seller));
  }
  const empty = rvById("rv-empty");
  if (!rows.length) {
    grid.innerHTML = "";
    if (empty) empty.style.display = "";
  } else {
    if (empty) empty.style.display = "none";
    grid.innerHTML = rows.map(rvCardHtml).join("");
  }
  const page = Math.floor(RV.offset / RV_PAGE_SIZE) + 1;
  const info = rvById("rv-page-info");
  if (info) info.textContent = `Pág. ${page} · ${rows.length} anúncio(s)${RV.hasMore ? " · há mais →" : ""}`;
  const prev = rvById("rv-prev");
  const next = rvById("rv-next");
  if (prev) prev.disabled = RV.offset <= 0;
  if (next) next.disabled = !RV.hasMore;
  rvAnnounce(`${rows.length} anúncio(s) de recursos encontrados.`);
}

function rvCardHtml(l) {
  const res = l.resource || {};
  const name = res.name || "Recurso";
  const seller = l.seller_display_name || rvShortSteam(l.seller_steam_id);
  const mine = rvMySteamId() && String(l.seller_steam_id) === rvMySteamId();
  const unit = l.unit_price != null ? Number(l.unit_price) : (l.lot_size ? l.lot_price / l.lot_size : 0);
  const unitTxt = unit >= 1 ? rvFmt(Math.round(unit * 100) / 100) : String(Math.round(unit * 10000) / 10000).replace(".", ",");
  const action = mine
    ? '<span class="rv-badge rv-badge--warn">Seu anúncio</span>'
    : `<button type="button" class="btn btn-primary btn-sm" style="width:100%;" onclick="rvOpenBuy(${Number(l.stock_id)})" aria-label="Comprar lotes de ${rvEsc(name)} de ${rvEsc(seller)}">🛒 Comprar</button>`;
  return `
    <article class="card rv-card" aria-label="${rvEsc(name)} — ${rvEsc(seller)}">
      <div class="rv-card__top">
        ${rvIconHtml(res)}
        <div class="rv-card__main">
          <div class="rv-card__name">${rvEsc(name)}</div>
          <div class="rv-card__seller">🏪 Vendedor: <strong>${rvEsc(seller)}</strong></div>
        </div>
      </div>
      <div class="rv-card__price">${rvAmberIcon(18)} ${rvFmt(l.lot_price)} <small>por lote</small></div>
      <div class="rv-stats">
        <div>Tamanho do lote: <strong>${rvFmt(l.lot_size)} un.</strong></div>
        <div>Lotes disponíveis: <strong>${rvFmt(l.lots_available)}</strong></div>
        <div>Estoque total: <strong>${rvFmt(l.stock_quantity)} un.</strong></div>
        <div>Unitário: <strong>≈ ${unitTxt}</strong> Â</div>
      </div>
      ${action}
    </article>`;
}

// ── Compra ───────────────────────────────────────────────────────────────────

function rvOpenBuy(stockId) {
  if (!rvAuthed()) {
    if (typeof promptLogin === "function") promptLogin("comprar na Vitrine de Recursos");
    return;
  }
  const l = RV.listings.find((x) => Number(x.stock_id) === Number(stockId));
  if (!l) {
    toast("Anúncio não encontrado. Atualize a lista.", "warning");
    return;
  }
  const res = l.resource || {};
  RV.buy = { listing: l, reqKey: "", reqId: "" };
  const body = `
    <div class="rv-card__top">
      ${rvIconHtml(res)}
      <div class="rv-card__main">
        <div class="rv-card__name">${rvEsc(res.name || "Recurso")}</div>
        <div class="rv-card__seller">🏪 Vendedor: <strong>${rvEsc(l.seller_display_name || rvShortSteam(l.seller_steam_id))}</strong></div>
      </div>
    </div>
    <div class="rv-modal__sum">
      <div class="rv-modal__sum-row"><span>Tamanho do lote</span><strong>${rvFmt(l.lot_size)} un.</strong></div>
      <div class="rv-modal__sum-row"><span>Preço por lote</span><strong>${rvAmber(l.lot_price)}</strong></div>
      <div class="rv-modal__sum-row"><span>Lotes disponíveis</span><strong>${rvFmt(l.lots_available)}</strong></div>
    </div>
    <div class="rv-form-group">
      <label for="rv-buy-lots">Quantidade de lotes (apenas lotes inteiros)</label>
      <input id="rv-buy-lots" class="rv-input" type="number" inputmode="numeric" min="1" max="${Math.min(Number(l.lots_available) || 1, RV_MAX_LOTS_PER_PURCHASE)}" step="1" value="1" oninput="rvBuyUpdate()" onkeydown="if(event.key==='Enter'){event.preventDefault();rvConfirmBuy();}" aria-describedby="rv-buy-err" />
    </div>
    <div class="rv-modal__sum" aria-live="polite">
      <div class="rv-modal__sum-row"><span>Quantidade total de itens</span><strong id="rv-buy-items">—</strong></div>
      <div class="rv-modal__sum-row rv-modal__sum-row--total"><span>Total em Âmbares</span><strong id="rv-buy-total">—</strong></div>
      <div class="rv-modal__sum-row" id="rv-buy-balance-row"><span>Seu saldo</span><strong id="rv-buy-balance">—</strong></div>
    </div>
    <div class="rv-callout">
      ⏳ Depois da compra, resgate <strong>no jogo</strong> com <strong>/mercado</strong> em até <strong>24 horas</strong>.
      Se o prazo expirar, o pagamento é <strong>reembolsado automaticamente</strong> e o recurso volta ao estoque do vendedor.
    </div>
    <div class="rv-err" id="rv-buy-err" role="alert" aria-live="assertive"></div>`;
  const footer = `
    <button type="button" class="btn btn-ghost" onclick="rvCloseModal('rv-modal-buy')">Cancelar</button>
    <button type="button" class="btn btn-primary" id="rv-buy-confirm" onclick="rvConfirmBuy()">Confirmar compra</button>`;
  rvOpenModal("rv-modal-buy", { title: "🛒 Comprar recurso", body, footer });
  rvBuyUpdate();
  if (typeof refreshPlayerBalance === "function") {
    Promise.resolve(refreshPlayerBalance()).then(rvBuyUpdate).catch(() => {});
  }
}

function rvBuyLots() {
  const raw = (rvById("rv-buy-lots")?.value || "").trim();
  if (!/^\d+$/.test(raw)) return { ok: false, reason: raw ? "Apenas lotes inteiros (número inteiro ≥ 1)." : "Informe a quantidade de lotes." };
  const n = parseInt(raw, 10);
  const l = RV.buy && RV.buy.listing;
  const maxLots = Math.min(Number(l?.lots_available) || 0, RV_MAX_LOTS_PER_PURCHASE);
  if (n < 1) return { ok: false, reason: "Mínimo de 1 lote." };
  if (n > maxLots) return { ok: false, reason: `Máximo disponível: ${rvFmt(maxLots)} lote(s).` };
  return { ok: true, lots: n };
}

function rvBuyUpdate() {
  if (!RV.buy) return;
  const l = RV.buy.listing;
  const lots = rvBuyLots();
  const items = rvById("rv-buy-items");
  const total = rvById("rv-buy-total");
  const bal = rvById("rv-buy-balance");
  const row = rvById("rv-buy-balance-row");
  const err = rvById("rv-buy-err");
  const btn = rvById("rv-buy-confirm");
  const balance = typeof window._playerBalance === "number" && isFinite(window._playerBalance) ? window._playerBalance : null;
  if (bal) bal.innerHTML = balance == null ? "—" : rvAmber(balance);
  if (!lots.ok) {
    if (items) items.textContent = "—";
    if (total) total.textContent = "—";
    if (err) err.textContent = lots.reason;
    if (btn) btn.disabled = true;
    if (row) row.classList.remove("rv-modal__sum-row--bad");
    return;
  }
  const sumPrice = lots.lots * Number(l.lot_price);
  const sumItems = lots.lots * Number(l.lot_size);
  if (items) items.textContent = `${rvFmt(sumItems)} un. (${rvFmt(lots.lots)} × ${rvFmt(l.lot_size)})`;
  if (total) total.innerHTML = rvAmber(sumPrice);
  const short = balance != null && balance < sumPrice;
  if (row) row.classList.toggle("rv-modal__sum-row--bad", short);
  if (err) err.textContent = short ? `Saldo insuficiente: faltam ${rvFmt(sumPrice - balance)} Âmbares.` : "";
  if (btn) btn.disabled = short || RV.busy;
}

async function rvConfirmBuy() {
  if (RV.busy || !RV.buy) return;
  const lots = rvBuyLots();
  if (!lots.ok) {
    rvBuyUpdate();
    return;
  }
  const l = RV.buy.listing;
  const price = lots.lots * Number(l.lot_price);
  const key = `${l.stock_id}:${lots.lots}:${price}`;
  if (RV.buy.reqKey !== key) {
    RV.buy.reqKey = key;
    RV.buy.reqId = rvRequestId(); // mesmo request_id em re-tentativa idêntica = idempotente no servidor
  }
  const btn = rvById("rv-buy-confirm");
  const err = rvById("rv-buy-err");
  RV.busy = true;
  if (btn) { btn.disabled = true; btn.textContent = "Comprando…"; }
  if (err) err.textContent = "";
  try {
    const d = await rvApi(`/listings/${Number(l.stock_id)}/purchase`, {
      method: "POST",
      body: { lots: lots.lots, request_id: RV.buy.reqId, expected_price: price },
    });
    RV.busy = false;
    rvBuyDone(d, l, lots.lots);
  } catch (e) {
    RV.busy = false;
    if (btn) btn.textContent = "Confirmar compra";
    rvBuyFail(e, l);
  }
}

function rvBuyDone(d, l, lots) {
  const paid = d.price_paid != null ? d.price_paid : lots * Number(l.lot_price);
  const qty = d.quantity != null ? d.quantity : lots * Number(l.lot_size);
  const bal = Number(d.buyer_balance);
  if (isFinite(bal) && typeof updateBalanceDisplays === "function") updateBalanceDisplays(bal);
  if (typeof refreshPlayerBalance === "function") refreshPlayerBalance({ force: true });
  const name = (l.resource && l.resource.name) || "recurso";
  const body = `
    <div class="rv-callout rv-callout--ok" role="status">
      ✅ <strong>${d.duplicate ? "Compra já registrada." : "Compra concluída!"}</strong><br>
      ${rvFmt(qty)} un. de <strong>${rvEsc(name)}</strong> (${rvFmt(d.lots || lots)} lote(s)) por ${rvAmber(paid)} Âmbares.
    </div>
    <div class="rv-callout">
      Entre no jogo e digite <strong>/mercado</strong> em até <strong>24 horas</strong> para receber os itens
      (inventário com espaço). Se expirar, você é reembolsado automaticamente.
    </div>
    <div class="rv-chips">
      <button type="button" class="ingame-cmds__chip" onclick="copyIngameCmd('/mercado', this)" title="Copiar /mercado">/mercado</button>
      ${isFinite(bal) ? `<span class="rv-hint">Saldo atual: ${rvAmber(bal)}</span>` : ""}
    </div>`;
  rvOpenModal("rv-modal-buy", {
    title: "✅ Compra realizada",
    body,
    footer: '<button type="button" class="btn btn-primary" onclick="rvCloseModal(\'rv-modal-buy\')">Fechar</button>',
  });
  toast("Compra concluída! Resgate no jogo com /mercado em até 24h.", "success");
  RV.buy = null;
  rvLoadListings();
}

function rvBuyFail(e, l) {
  const info = rvErrInfo(e);
  const err = rvById("rv-buy-err");
  let msg = info.message;
  let refresh = false;
  let close = false;
  switch (info.code) {
    case "insufficient_balance":
      msg = "Saldo insuficiente para esta compra. " + info.message;
      if (typeof refreshPlayerBalance === "function") refreshPlayerBalance({ force: true });
      break;
    case "insufficient_stock": {
      const av = Number(info.data.available);
      msg = isFinite(av) ? `O estoque mudou: restam apenas ${av} lote(s). Ajuste a quantidade.` : "O estoque mudou. Atualize e tente de novo.";
      if (isFinite(av) && RV.buy) {
        RV.buy.listing.lots_available = av;
        const inp = rvById("rv-buy-lots");
        if (inp) inp.max = String(Math.max(av, 1));
        if (av < 1) close = true;
      }
      refresh = true;
      break;
    }
    case "price_changed":
      msg = "O preço ou o lote mudou enquanto você comprava. A lista foi atualizada — revise e tente novamente.";
      refresh = true;
      close = true;
      break;
    case "self_purchase":
      msg = "Você não pode comprar da sua própria vitrine.";
      break;
    case "not_found":
      msg = "Este anúncio não está mais disponível.";
      refresh = true;
      close = true;
      break;
    default:
      if (info.status === 401) {
        if (typeof promptLogin === "function") promptLogin("comprar na Vitrine de Recursos");
        msg = "Sessão expirada — entre com Steam novamente.";
      } else if (info.status === 429) {
        msg = "Muitas compras em pouco tempo. Aguarde um minuto e tente de novo.";
      }
  }
  if (err) err.textContent = msg;
  toast(msg, "error");
  rvAnnounce(msg);
  if (refresh) rvLoadListings();
  if (close) setTimeout(() => rvCloseModal("rv-modal-buy"), 1800);
  else rvBuyUpdate();
}

// ── Minha vitrine ────────────────────────────────────────────────────────────

async function rvLoadMine() {
  const gate = rvById("rv-mine-gate");
  const content = rvById("rv-mine-content");
  if (!gate || !content) return;
  if (!rvAuthed()) {
    gate.style.display = "";
    content.style.display = "none";
    return;
  }
  gate.style.display = "none";
  content.style.display = "";
  const root = rvById("rv-mine-root");
  const seq = ++RV.mineSeq;
  if (root && !RV.mine) root.innerHTML = '<div class="rv-loading" role="status">Carregando sua vitrine…</div>';
  try {
    const d = await rvApi("/my", { method: "GET", retries: 1 });
    if (seq !== RV.mineSeq) return;
    RV.mine = d;
    rvRenderMine();
  } catch (e) {
    if (seq !== RV.mineSeq || (e && e.stale)) return;
    if (root) root.innerHTML = `<div class="rv-error" role="alert">${rvEsc(rvErrInfo(e).message)}</div>`;
  }
}

function rvStateBadge(st) {
  switch (st) {
    case "active": return '<span class="rv-badge rv-badge--ok">● Ativo</span>';
    case "paused": return '<span class="rv-badge">⏸ Pausado</span>';
    case "no_lot_defined": return '<span class="rv-badge rv-badge--warn">Defina lote e preço</span>';
    case "no_full_lot": return '<span class="rv-badge rv-badge--warn">Sem lote completo (oculto em Explorar)</span>';
    case "resource_disabled": return '<span class="rv-badge rv-badge--bad">Recurso desativado</span>';
    default: return `<span class="rv-badge">${rvEsc(st || "—")}</span>`;
  }
}

function rvRangeHint(res) {
  const lo = res.min_lot_price, hi = res.max_lot_price;
  if (lo != null && hi != null) return `Preço permitido por lote: ${rvFmt(lo)} a ${rvFmt(hi)} Âmbares.`;
  if (lo != null) return `Preço mínimo por lote: ${rvFmt(lo)} Âmbares.`;
  if (hi != null) return `Preço máximo por lote: ${rvFmt(hi)} Âmbares.`;
  return "Preço livre (sem faixa definida pela administração).";
}

function rvLotBreakdown(qty, lot) {
  if (!lot) return "Defina o tamanho do lote para ver os lotes completos.";
  const full = Math.floor(qty / lot);
  const rest = qty % lot;
  return `${rvFmt(full)} lote(s) completo(s) · sobra ${rvFmt(rest)} un.`;
}

function rvStockCardHtml(s) {
  const res = s.resource || {};
  const rid = Number(s.resource_id);
  const qty = Number(s.quantity) || 0;
  const lot = s.lot_size ? Number(s.lot_size) : null;
  const priceVal = s.lot_price ? Number(s.lot_price) : "";
  const full = lot ? Math.floor(qty / lot) : 0;
  const rest = lot ? qty % lot : qty;
  const activeNow = !!s.active;
  const toggleBtn = activeNow
    ? `<button type="button" class="btn btn-ghost btn-sm" onclick="rvPauseListing(${rid})">⏸ Pausar</button>`
    : `<button type="button" class="btn btn-success btn-sm" onclick="rvSaveListing(${rid}, true)">▶ Salvar e ativar</button>`;
  return `
    <article class="card rv-card" id="rv-stock-${rid}" aria-label="Estoque de ${rvEsc(res.name)}">
      <div class="rv-card__top">
        ${rvIconHtml(res)}
        <div class="rv-card__main">
          <div class="rv-card__name">${rvEsc(res.name || "Recurso")}</div>
          <div style="margin-top:4px;">${rvStateBadge(s.state)}</div>
        </div>
      </div>
      <div class="rv-stats">
        <div>Quantidade total: <strong>${rvFmt(qty)} un.</strong></div>
        <div>Lotes completos: <strong>${rvFmt(full)}</strong></div>
        <div>Sobra: <strong>${rvFmt(rest)} un.</strong></div>
        <div>Stack no jogo: <strong>${rvFmt(res.stack_size)}</strong></div>
      </div>
      <div class="rv-lot-form">
        <div>
          <label for="rv-lot-size-${rid}">Tamanho do lote (un.)</label>
          <input id="rv-lot-size-${rid}" class="rv-input" type="number" inputmode="numeric" min="1" max="${RV_MAX_LOT_SIZE}" step="1" value="${lot || ""}" placeholder="ex.: 1000" oninput="rvLotPreview(${rid})" />
        </div>
        <div>
          <label for="rv-lot-price-${rid}">Preço do lote (Âmbares)</label>
          <input id="rv-lot-price-${rid}" class="rv-input" type="number" inputmode="numeric" min="${res.min_lot_price != null ? Number(res.min_lot_price) : 1}" max="${res.max_lot_price != null ? Number(res.max_lot_price) : RV_MAX_LOT_PRICE}" step="1" value="${priceVal}" placeholder="ex.: 500" oninput="rvLotPreview(${rid})" />
        </div>
      </div>
      <div class="rv-hint" id="rv-lot-preview-${rid}" aria-live="polite">${rvLotBreakdown(qty, lot)}</div>
      <div class="rv-hint">${rvEsc(rvRangeHint(res))}</div>
      <div class="rv-err" id="rv-err-${rid}" role="alert"></div>
      <div class="rv-actions">
        <button type="button" class="btn btn-primary btn-sm" onclick="rvSaveListing(${rid}, null)">💾 Salvar</button>
        ${toggleBtn}
        <button type="button" class="btn btn-ghost btn-sm" onclick="rvOpenWithdraw(${rid})" ${qty > 0 ? "" : "disabled"} aria-label="Retirar estoque de ${rvEsc(res.name)}">📤 Retirar</button>
      </div>
    </article>`;
}

function rvLotPreview(rid) {
  const s = (RV.mine?.stock || []).find((x) => Number(x.resource_id) === rid);
  if (!s) return;
  const lot = parseInt(rvById(`rv-lot-size-${rid}`)?.value || "", 10);
  const price = parseInt(rvById(`rv-lot-price-${rid}`)?.value || "", 10);
  const el = rvById(`rv-lot-preview-${rid}`);
  if (!el) return;
  const qty = Number(s.quantity) || 0;
  let txt = rvLotBreakdown(qty, lot > 0 ? lot : null);
  if (lot > 0 && price > 0) txt += ` · ≈ ${rvFmt(Math.round((price / lot) * 10000) / 10000)} Âmbar/un.`;
  if (lot > 0 && lot > qty) txt += " ⚠ Lote maior que o estoque: ficará oculto em Explorar até haver quantidade suficiente.";
  el.textContent = txt;
}

function rvReadLot(rid) {
  const res = (RV.mine?.stock || []).find((x) => Number(x.resource_id) === rid)?.resource || {};
  const rawSize = (rvById(`rv-lot-size-${rid}`)?.value || "").trim();
  const rawPrice = (rvById(`rv-lot-price-${rid}`)?.value || "").trim();
  if (!/^\d+$/.test(rawSize) || parseInt(rawSize, 10) < 1) return { error: "Informe o tamanho do lote (inteiro ≥ 1)." };
  if (!/^\d+$/.test(rawPrice) || parseInt(rawPrice, 10) < 1) return { error: "Informe o preço do lote em Âmbares (inteiro ≥ 1)." };
  const size = parseInt(rawSize, 10);
  const price = parseInt(rawPrice, 10);
  if (size > RV_MAX_LOT_SIZE) return { error: `Tamanho do lote máximo: ${rvFmt(RV_MAX_LOT_SIZE)}.` };
  if (price > RV_MAX_LOT_PRICE) return { error: `Preço do lote máximo: ${rvFmt(RV_MAX_LOT_PRICE)}.` };
  if (res.min_lot_price != null && price < Number(res.min_lot_price)) return { error: `Preço mínimo por lote: ${rvFmt(res.min_lot_price)} Âmbares.` };
  if (res.max_lot_price != null && price > Number(res.max_lot_price)) return { error: `Preço máximo por lote: ${rvFmt(res.max_lot_price)} Âmbares.` };
  return { size, price };
}

function rvSetCardError(rid, msg) {
  const el = rvById(`rv-err-${rid}`);
  if (el) el.textContent = msg || "";
}

async function rvPutListing(rid, payload) {
  const d = await rvApi(`/my/stock/${rid}/listing`, { method: "PUT", body: payload });
  if (d.stock && RV.mine && Array.isArray(RV.mine.stock)) {
    const i = RV.mine.stock.findIndex((x) => Number(x.resource_id) === rid);
    if (i >= 0) RV.mine.stock[i] = d.stock;
  }
  return d;
}

async function rvSaveListing(rid, activate) {
  if (RV.busy) return;
  const s = (RV.mine?.stock || []).find((x) => Number(x.resource_id) === rid);
  if (!s) return;
  const lot = rvReadLot(rid);
  if (lot.error) {
    rvSetCardError(rid, lot.error);
    return;
  }
  rvSetCardError(rid, "");
  const active = activate === null ? !!s.active : !!activate;
  RV.busy = true;
  try {
    await rvPutListing(rid, { lot_size: lot.size, lot_price: lot.price, active });
    toast(active ? "Anúncio salvo e ativo." : "Configuração do lote salva.", "success");
    rvRenderMine();
  } catch (e) {
    const info = rvErrInfo(e);
    rvSetCardError(rid, info.message);
    toast(info.message, "error");
  } finally {
    RV.busy = false;
  }
}

async function rvPauseListing(rid) {
  if (RV.busy) return;
  const s = (RV.mine?.stock || []).find((x) => Number(x.resource_id) === rid);
  if (!s) return;
  RV.busy = true;
  try {
    // Mantém lote/preço já salvos; só muda o estado.
    await rvPutListing(rid, { lot_size: s.lot_size, lot_price: s.lot_price, active: false });
    toast("Anúncio pausado.", "success");
    rvRenderMine();
  } catch (e) {
    const info = rvErrInfo(e);
    rvSetCardError(rid, info.message);
    toast(info.message, "error");
  } finally {
    RV.busy = false;
  }
}

function rvRenderMine() {
  const root = rvById("rv-mine-root");
  const d = RV.mine;
  if (!root || !d) return;
  const stock = Array.isArray(d.stock) ? d.stock : [];
  const pending = Array.isArray(d.pending_claims) ? d.pending_claims : [];
  const totalUnits = stock.reduce((a, s) => a + (Number(s.quantity) || 0), 0);
  const totalLots = stock.reduce((a, s) => a + (s.lot_size ? Math.floor((Number(s.quantity) || 0) / Number(s.lot_size)) : 0), 0);
  const withStock = stock.filter((s) => Number(s.quantity) > 0).length;
  const summary = `
    <div class="rv-summary">
      <div class="rv-sum-item"><strong>${rvFmt(d.type_count != null ? d.type_count : withStock)} / ${rvFmt(d.max_types || 0)}</strong>Tipos de recurso na vitrine</div>
      <div class="rv-sum-item"><strong>${rvFmt(totalUnits)}</strong>Unidades em estoque</div>
      <div class="rv-sum-item"><strong>${rvFmt(totalLots)}</strong>Lotes completos à venda</div>
      <div class="rv-sum-item"><strong>${rvFmt(pending.length)}</strong>Entregas pendentes</div>
    </div>`;
  const stockHtml = stock.length
    ? `<div class="rv-grid">${stock.map(rvStockCardHtml).join("")}</div>`
    : '<div class="rv-empty">Você ainda não tem recursos na vitrine. Use <strong>/vitrine</strong> no jogo (veja acima).</div>';
  const withdrawAll = withStock > 0
    ? `<button type="button" class="btn btn-ghost btn-sm" onclick="rvOpenWithdrawAll()">📤 Retirar todo o estoque</button>`
    : "";
  root.innerHTML = `
    ${summary}
    <div class="rv-section-title" style="margin-top:0;display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
      <span>📦 Meu estoque na vitrine</span>${withdrawAll}
    </div>
    ${stockHtml}
    <div class="rv-section-title">⏳ Entregas pendentes (resgate no jogo com /mercado)</div>
    ${rvPendingHtml(pending)}
    <div class="rv-section-title">📜 Histórico</div>
    ${rvHistoryHtml(Array.isArray(d.history) ? d.history : [])}`;
  rvEnsureTimer();
}

function rvPendingHtml(claims) {
  if (!claims.length) return '<p class="rv-hint">Nenhuma entrega pendente.</p>';
  const rows = claims.map((c) => {
    const kind = c.kind === "WITHDRAW" ? "Retirada" : "Compra";
    const st = c.status === "CLAIMED" ? "Em entrega" : "Aguardando resgate";
    return `<tr>
      <td>${rvEsc(c.name)}</td>
      <td>${rvFmt(c.quantity)} un.</td>
      <td>${kind}</td>
      <td>${st}</td>
      <td><span data-rv-exp="${rvEsc(c.expires_at || "")}">${rvEsc(rvHoursText(c.expires_at, c.hours_remaining))}</span></td>
    </tr>`;
  }).join("");
  return `
    <div class="rv-table-wrap"><table class="rv-table">
      <thead><tr><th>Recurso</th><th>Qtd.</th><th>Origem</th><th>Status</th><th>Expira em</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    <p class="rv-hint">No jogo, digite <strong>/mercado</strong> (inventário com espaço). Se expirar: compras são reembolsadas; retiradas voltam ao estoque.</p>`;
}

const RV_CLAIM_STATUS = {
  PENDENTE: "Aguardando resgate (/mercado)",
  CLAIMED: "Em entrega",
  DELIVERED: "Entregue",
  EXPIRADO: "Expirado — voltou ao estoque",
  REEMBOLSADO: "Reembolsado",
};

function rvHistoryRow(ev) {
  const when = typeof fmtDate === "function" ? fmtDate(ev.at) : (ev.at || "");
  const who = ev.counterparty ? `<code>${rvEsc(rvShortSteam(ev.counterparty))}</code>` : "—";
  let kind = "";
  let detail = "";
  let status = "";
  switch (ev.type) {
    case "sale":
      kind = "💰 Venda";
      detail = `${rvFmt(ev.lots)} lote(s) · ${rvFmt(ev.quantity)} un. · comprador ${who}`;
      status = ev.amount != null ? `+${rvFmt(ev.amount)} Â` : "";
      if (ev.status === "REFUNDED") status += " (estornada)";
      break;
    case "purchase":
      kind = "🛒 Compra";
      detail = `${rvFmt(ev.lots)} lote(s) · ${rvFmt(ev.quantity)} un. · vendedor ${who}`;
      status = ev.amount != null ? `−${rvFmt(ev.amount)} Â` : "";
      if (ev.status === "REFUNDED") status += " (reembolsada)";
      break;
    case "refund":
      kind = "↩️ Expirado";
      detail = rvEsc(ev.label || "Resgate expirado");
      status = ev.amount != null ? `${rvFmt(ev.amount)} Â` : "";
      break;
    case "withdraw":
      kind = "📤 Retirada";
      detail = `${rvFmt(ev.quantity)} un.`;
      status = RV_CLAIM_STATUS[ev.status] || ev.status || "";
      break;
    case "upload":
      kind = "📥 Envio do jogo";
      detail = `${rvFmt(ev.quantity)} un.`;
      status = "Creditado";
      break;
    default:
      kind = rvEsc(ev.type || "—");
  }
  return `<tr data-rv-type="${rvEsc(ev.type)}">
    <td style="white-space:nowrap;">${rvEsc(when)}</td>
    <td>${kind}</td>
    <td>${rvEsc(ev.resource || "—")}</td>
    <td>${detail}</td>
    <td>${rvEsc(status)}</td>
  </tr>`;
}

function rvHistoryHtml(history) {
  if (!history.length) return '<p class="rv-hint">Sem movimentações ainda.</p>';
  return `
    <div class="rv-toolbar">
      <div class="rv-field">
        <label for="rv-hist-filter">Filtrar histórico</label>
        <select id="rv-hist-filter" onchange="rvFilterHistory()">
          <option value="">Tudo</option>
          <option value="sale">Vendas</option>
          <option value="purchase">Compras</option>
          <option value="withdraw">Retiradas</option>
          <option value="refund">Expirados / reembolsos</option>
          <option value="upload">Envios do jogo</option>
        </select>
      </div>
    </div>
    <div class="rv-table-wrap"><table class="rv-table" id="rv-hist-table">
      <thead><tr><th>Data</th><th>Tipo</th><th>Recurso</th><th>Detalhe</th><th>Valor / status</th></tr></thead>
      <tbody>${history.map(rvHistoryRow).join("")}</tbody>
    </table></div>`;
}

function rvFilterHistory() {
  const f = rvById("rv-hist-filter")?.value || "";
  document.querySelectorAll("#rv-hist-table tbody tr").forEach((tr) => {
    tr.style.display = !f || tr.getAttribute("data-rv-type") === f ? "" : "none";
  });
}

// ── Retirada ─────────────────────────────────────────────────────────────────

function rvOpenWithdraw(rid) {
  const s = (RV.mine?.stock || []).find((x) => Number(x.resource_id) === rid);
  if (!s || !(Number(s.quantity) > 0)) return;
  const qty = Number(s.quantity);
  const name = (s.resource && s.resource.name) || "recurso";
  RV.withdraw = { rid, qty, reqId: rvRequestId(), all: false, lastQty: null };
  const body = `
    <p style="font-size:13px;color:var(--text2);margin:0 0 10px;">Retirar <strong>${rvEsc(name)}</strong> da sua vitrine. Disponível: <strong>${rvFmt(qty)} un.</strong></p>
    <div class="rv-form-group">
      <label for="rv-wd-qty">Quantidade a retirar (unidades)</label>
      <input id="rv-wd-qty" class="rv-input" type="number" inputmode="numeric" min="1" max="${qty}" step="1" value="${qty}" onkeydown="if(event.key==='Enter'){event.preventDefault();rvConfirmWithdraw();}" aria-describedby="rv-wd-err" />
    </div>
    <div class="rv-callout">
      A retirada gera uma <strong>entrega pendente</strong>: resgate <strong>no jogo</strong> com <strong>/mercado</strong> em até
      <strong>24 horas</strong>. Se expirar, os itens <strong>voltam ao estoque</strong> da vitrine (sem Âmbar envolvido).
    </div>
    <div class="rv-err" id="rv-wd-err" role="alert"></div>`;
  const footer = `
    <button type="button" class="btn btn-ghost" onclick="rvCloseModal('rv-modal-wd')">Cancelar</button>
    <button type="button" class="btn btn-primary" id="rv-wd-confirm" onclick="rvConfirmWithdraw()">Retirar</button>`;
  rvOpenModal("rv-modal-wd", { title: "📤 Retirar estoque", body, footer });
}

function rvOpenWithdrawAll() {
  const stock = (RV.mine?.stock || []).filter((s) => Number(s.quantity) > 0);
  if (!stock.length) return;
  RV.withdraw = { rid: null, qty: 0, reqId: rvRequestId(), all: true, lastQty: null };
  const list = stock.map((s) => `<li>${rvEsc(s.resource?.name)}: <strong>${rvFmt(s.quantity)} un.</strong></li>`).join("");
  const body = `
    <p style="font-size:13px;color:var(--text2);margin:0 0 6px;">Retirar <strong>todo o estoque</strong> da sua vitrine:</p>
    <ul style="font-size:13px;margin:0 0 10px 1.2em;">${list}</ul>
    <div class="rv-callout">
      Serão criadas entregas pendentes para resgatar <strong>no jogo</strong> com <strong>/mercado</strong> em até
      <strong>24 horas</strong>. Se expirar, os itens voltam ao estoque (sem Âmbar).
    </div>
    <div class="rv-err" id="rv-wd-err" role="alert"></div>`;
  const footer = `
    <button type="button" class="btn btn-ghost" onclick="rvCloseModal('rv-modal-wd')">Cancelar</button>
    <button type="button" class="btn btn-danger" id="rv-wd-confirm" onclick="rvConfirmWithdraw()">Retirar tudo</button>`;
  rvOpenModal("rv-modal-wd", { title: "📤 Retirar todo o estoque", body, footer });
}

async function rvConfirmWithdraw() {
  if (RV.busy || !RV.withdraw) return;
  const w = RV.withdraw;
  const err = rvById("rv-wd-err");
  const payload = { request_id: w.reqId };
  if (!w.all) {
    const raw = (rvById("rv-wd-qty")?.value || "").trim();
    if (!/^\d+$/.test(raw) || parseInt(raw, 10) < 1) {
      if (err) err.textContent = "Informe uma quantidade inteira ≥ 1.";
      return;
    }
    const q = parseInt(raw, 10);
    if (q > w.qty) {
      if (err) err.textContent = `Máximo disponível: ${rvFmt(w.qty)} un.`;
      return;
    }
    payload.resource_id = w.rid;
    payload.quantity = q;
    // Nova quantidade ⇒ novo request_id (mesma tentativa repetida continua idempotente).
    if (w.lastQty !== q) { w.lastQty = q; w.reqId = rvRequestId(); payload.request_id = w.reqId; }
  }
  const btn = rvById("rv-wd-confirm");
  RV.busy = true;
  if (btn) btn.disabled = true;
  if (err) err.textContent = "";
  try {
    const d = await rvApi("/my/withdraw", { method: "POST", body: payload });
    RV.busy = false;
    rvCloseModal("rv-modal-wd");
    toast(d.message || "Retirada solicitada. Resgate no jogo com /mercado em até 24h.", "success");
    RV.withdraw = null;
    rvLoadMine();
  } catch (e) {
    RV.busy = false;
    if (btn) btn.disabled = false;
    const info = rvErrInfo(e);
    let msg = info.message;
    if (info.status === 429) msg = "Muitas retiradas em pouco tempo. Aguarde um minuto.";
    if (err) err.textContent = msg;
    toast(msg, "error");
    if (info.code === "insufficient_stock") rvLoadMine();
  }
}

// ── Admin: Recursos (vitrine) ────────────────────────────────────────────────

async function rvAdminLoad() {
  const root = rvById("rv-admin-root");
  if (!root) return;
  root.innerHTML = '<div class="rv-loading" role="status">Carregando recursos autorizados…</div>';
  try {
    const d = await rvApi("/admin/catalog", { method: "GET", retries: 1 });
    RV.admin = d;
    rvAdminRender();
  } catch (e) {
    root.innerHTML = `<div class="rv-error" role="alert">${rvEsc(rvErrInfo(e).message)}</div>`;
  }
}

function rvAdminRender() {
  const root = rvById("rv-admin-root");
  const d = RV.admin;
  if (!root || !d) return;
  const lim = d.limits || {};
  const minT = lim.min_max_types || 1;
  const maxT = lim.max_max_types || 50;
  const resources = Array.isArray(d.resources) ? d.resources : [];
  const rows = resources.map((r) => {
    const range = (r.min_lot_price != null || r.max_lot_price != null)
      ? `${r.min_lot_price != null ? rvFmt(r.min_lot_price) : "—"} / ${r.max_lot_price != null ? rvFmt(r.max_lot_price) : "—"}`
      : "livre";
    const toggle = r.enabled
      ? `<button type="button" class="btn btn-danger btn-sm" onclick="rvAdminDisable(${Number(r.id)})">Remover</button>`
      : `<button type="button" class="btn btn-success btn-sm" onclick="rvAdminEnable(${Number(r.id)})">Reativar</button>`;
    return `<tr>
      <td>${rvIconFor(r)} <strong>${rvEsc(r.name)}</strong></td>
      <td><code>${rvEsc(r.blueprint)}</code></td>
      <td>${rvFmt(r.stack_size)}</td>
      <td>${rvEsc(range)}</td>
      <td>${r.enabled ? '<span class="rv-badge rv-badge--ok">Ativo</span>' : '<span class="rv-badge rv-badge--bad">Desativado</span>'}</td>
      <td>${rvFmt(r.owners || 0)} jogador(es) · ${rvFmt(r.quantity || 0)} un.</td>
      <td><div class="rv-actions">
        <button type="button" class="btn btn-ghost btn-sm" onclick="rvAdminOpenForm(${Number(r.id)})">✏️ Editar</button>
        ${toggle}
      </div></td>
    </tr>`;
  }).join("");
  root.innerHTML = `
    <div class="rv-admin-grid">
      <div class="card">
        <div class="card-title">⚙️ Limite de tipos por jogador</div>
        <p class="rv-hint" style="margin:0 0 10px;">Quantos recursos <em>diferentes</em> cada jogador pode ter ao mesmo tempo na vitrine (${minT}–${maxT}). Envios que excedam são rejeitados.</p>
        <div class="rv-admin-settings">
          <div class="rv-form-group">
            <label for="rv-admin-max-types">Máx. de tipos por jogador</label>
            <input id="rv-admin-max-types" class="rv-input" type="number" inputmode="numeric" min="${minT}" max="${maxT}" step="1" value="${Number(d.max_types_per_player) || ""}" />
          </div>
          <button type="button" class="btn btn-primary" onclick="rvAdminSaveSettings()">💾 Salvar limite</button>
        </div>
        <div class="rv-err" id="rv-admin-settings-err" role="alert"></div>
      </div>
      <div class="card">
        <div class="card-title" style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
          <span>💎 Recursos autorizados</span>
          <span class="rv-actions">
            <button type="button" class="btn btn-ghost btn-sm" onclick="rvAdminExpireStale()" title="Processa agora resgates expirados (reembolsos / devoluções ao estoque)">⏱ Processar expirados</button>
            <button type="button" class="btn btn-primary btn-sm" onclick="rvAdminOpenForm(null)">+ Novo recurso</button>
          </span>
        </div>
        <p class="rv-hint" style="margin:0 0 10px;">
          Só recursos cadastrados aqui podem ser enviados com <strong>/vitrine</strong>. Cadastre o <strong>stack real do jogo</strong>.
          A faixa de preço (mín/máx) vale para o <strong>preço do lote</strong> definido pelo jogador (não por unidade).
          «Remover» apenas desativa (nunca apaga se houver estoque ou resgates).
        </p>
        ${resources.length ? `<div class="rv-table-wrap"><table class="rv-table">
          <thead><tr><th>Recurso</th><th>Blueprint</th><th>Stack</th><th>Preço lote mín / máx</th><th>Status</th><th>Estoque</th><th>Ações</th></tr></thead>
          <tbody>${rows}</tbody></table></div>` : '<div class="rv-empty">Nenhum recurso cadastrado ainda. Clique em «+ Novo recurso».</div>'}
      </div>
    </div>`;
}

async function rvAdminSaveSettings() {
  const raw = (rvById("rv-admin-max-types")?.value || "").trim();
  const lim = (RV.admin && RV.admin.limits) || {};
  const minT = lim.min_max_types || 1;
  const maxT = lim.max_max_types || 50;
  const err = rvById("rv-admin-settings-err");
  if (!/^\d+$/.test(raw) || parseInt(raw, 10) < minT || parseInt(raw, 10) > maxT) {
    if (err) err.textContent = `Informe um inteiro entre ${minT} e ${maxT}.`;
    return;
  }
  if (err) err.textContent = "";
  try {
    const d = await rvApi("/admin/settings", { method: "PUT", body: { max_types_per_player: parseInt(raw, 10) } });
    toast(`Limite salvo: ${d.max_types_per_player} tipo(s) por jogador.`, "success");
    if (RV.admin) RV.admin.max_types_per_player = d.max_types_per_player;
  } catch (e) {
    const msg = rvErrInfo(e).message;
    if (err) err.textContent = msg;
    toast(msg, "error");
  }
}

function rvNormalizeBlueprint(raw) {
  const t = String(raw || "").trim();
  if (!t || t.length > 400) return "";
  const m = t.match(/(\/(?:Game|Script|Engine)\/[A-Za-z0-9_./\-]+)/);
  if (!m) return "";
  let p = m[1].replace(/[/.]+$/, "");
  if (p.endsWith("_C")) p = p.slice(0, -2);
  const last = p.split("/").pop();
  if (!last) return "";
  if (!last.includes(".")) p = `${p}.${last}`;
  if (p.length > 255 || p.includes("..")) return "";
  return p;
}

function rvAdminOpenForm(id) {
  const cur = id == null ? null : ((RV.admin && RV.admin.resources) || []).find((r) => Number(r.id) === Number(id));
  RV.adminEdit = cur ? Number(cur.id) : null;
  const v = (x) => (x == null ? "" : rvEsc(x));
  const body = `
    <div class="rv-form-group">
      <label for="rv-f-blueprint">Blueprint (ex.: /Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Stone.PrimalItemResource_Stone)</label>
      <input id="rv-f-blueprint" class="rv-input" type="text" value="${v(cur && cur.blueprint)}" autocomplete="off" spellcheck="false" oninput="rvAdminFormPreview()" />
      <div class="rv-hint" id="rv-f-bp-preview" aria-live="polite"></div>
    </div>
    <div class="rv-form-group">
      <label for="rv-f-name">Nome de exibição (até 80 caracteres)</label>
      <input id="rv-f-name" class="rv-input" type="text" maxlength="80" value="${v(cur && cur.name)}" autocomplete="off" />
    </div>
    <div class="rv-form-row">
      <div class="rv-form-group">
        <label for="rv-f-stack">Tamanho do stack no jogo</label>
        <input id="rv-f-stack" class="rv-input" type="number" inputmode="numeric" min="1" max="${RV_MAX_STACK_SIZE}" step="1" value="${cur ? Number(cur.stack_size) : 100}" />
      </div>
      <div class="rv-form-group">
        <label for="rv-f-enabled">Status</label>
        <select id="rv-f-enabled" class="rv-input">
          <option value="1"${!cur || cur.enabled ? " selected" : ""}>Ativo</option>
          <option value="0"${cur && !cur.enabled ? " selected" : ""}>Desativado</option>
        </select>
      </div>
    </div>
    <div class="rv-form-row">
      <div class="rv-form-group">
        <label for="rv-f-min">Preço mín. por lote (opcional)</label>
        <input id="rv-f-min" class="rv-input" type="number" inputmode="numeric" min="1" max="${RV_MAX_LOT_PRICE}" step="1" value="${v(cur && cur.min_lot_price)}" placeholder="livre" />
      </div>
      <div class="rv-form-group">
        <label for="rv-f-max">Preço máx. por lote (opcional)</label>
        <input id="rv-f-max" class="rv-input" type="number" inputmode="numeric" min="1" max="${RV_MAX_LOT_PRICE}" step="1" value="${v(cur && cur.max_lot_price)}" placeholder="livre" />
      </div>
    </div>
    <div class="rv-err" id="rv-f-err" role="alert"></div>`;
  const footer = `
    <button type="button" class="btn btn-ghost" onclick="rvCloseModal('rv-modal-admin')">Cancelar</button>
    <button type="button" class="btn btn-success" id="rv-f-save" onclick="rvAdminSaveForm()">✔ Salvar</button>`;
  rvOpenModal("rv-modal-admin", { title: cur ? "Editar recurso" : "Novo recurso autorizado", body, footer, wide: true });
  rvAdminFormPreview();
}

function rvAdminFormPreview() {
  const el = rvById("rv-f-bp-preview");
  if (!el) return;
  const raw = rvById("rv-f-blueprint")?.value || "";
  if (!raw.trim()) { el.textContent = ""; return; }
  const n = rvNormalizeBlueprint(raw);
  el.textContent = n ? `Blueprint normalizado: ${n}` : "Blueprint inválido — use o caminho /Game/.../Nome.Nome";
  el.className = "rv-hint" + (n ? "" : " rv-hint--warn");
}

async function rvAdminSaveForm() {
  if (RV.busy) return;
  const err = rvById("rv-f-err");
  const bp = rvNormalizeBlueprint(rvById("rv-f-blueprint")?.value || "");
  const name = (rvById("rv-f-name")?.value || "").trim();
  const stackRaw = (rvById("rv-f-stack")?.value || "").trim();
  const minRaw = (rvById("rv-f-min")?.value || "").trim();
  const maxRaw = (rvById("rv-f-max")?.value || "").trim();
  const fail = (m) => { if (err) err.textContent = m; };
  if (!bp) return fail("Blueprint inválido — use o caminho /Game/.../Nome.Nome");
  if (!name || name.length > 80 || /[\x00-\x1f\x7f<>]/.test(name)) return fail("Nome inválido (1–80 caracteres, sem < > nem controle).");
  if (!/^\d+$/.test(stackRaw) || parseInt(stackRaw, 10) < 1 || parseInt(stackRaw, 10) > RV_MAX_STACK_SIZE) return fail(`Stack inválido (1–${rvFmt(RV_MAX_STACK_SIZE)}).`);
  const okPrice = (s) => /^\d+$/.test(s) && parseInt(s, 10) >= 1 && parseInt(s, 10) <= RV_MAX_LOT_PRICE;
  if (minRaw && !okPrice(minRaw)) return fail("Preço mínimo inválido.");
  if (maxRaw && !okPrice(maxRaw)) return fail("Preço máximo inválido.");
  if (minRaw && maxRaw && parseInt(minRaw, 10) > parseInt(maxRaw, 10)) return fail("Preço mínimo não pode ser maior que o máximo.");
  const payload = {
    blueprint: bp,
    name,
    stack_size: parseInt(stackRaw, 10),
    min_lot_price: minRaw ? parseInt(minRaw, 10) : null,
    max_lot_price: maxRaw ? parseInt(maxRaw, 10) : null,
    enabled: rvById("rv-f-enabled")?.value !== "0",
  };
  if (RV.adminEdit != null) payload.id = RV.adminEdit;
  fail("");
  RV.busy = true;
  const btn = rvById("rv-f-save");
  if (btn) btn.disabled = true;
  try {
    await rvApi("/admin/catalog", { method: "PUT", body: payload });
    RV.busy = false;
    rvCloseModal("rv-modal-admin");
    toast(RV.adminEdit != null ? "Recurso atualizado." : "Recurso cadastrado.", "success");
    rvAdminLoad();
  } catch (e) {
    RV.busy = false;
    if (btn) btn.disabled = false;
    fail(rvErrInfo(e).message);
  }
}

async function rvAdminDisable(id) {
  const r = ((RV.admin && RV.admin.resources) || []).find((x) => Number(x.id) === Number(id));
  if (!r) return;
  if (!confirm(`Remover «${r.name}» da vitrine?\n\nO recurso será DESATIVADO (nada é apagado): novos envios e anúncios ficam bloqueados; estoque e resgates existentes são preservados.`)) return;
  try {
    const d = await rvApi(`/admin/catalog/${Number(id)}`, { method: "DELETE" });
    toast(d.has_dependents ? "Recurso desativado (há estoque/resgates preservados)." : "Recurso desativado.", "success");
    rvAdminLoad();
  } catch (e) {
    toast(rvErrInfo(e).message, "error");
  }
}

async function rvAdminEnable(id) {
  const r = ((RV.admin && RV.admin.resources) || []).find((x) => Number(x.id) === Number(id));
  if (!r) return;
  try {
    await rvApi("/admin/catalog", {
      method: "PUT",
      body: {
        id: r.id,
        blueprint: r.blueprint,
        name: r.name,
        stack_size: r.stack_size,
        min_lot_price: r.min_lot_price,
        max_lot_price: r.max_lot_price,
        enabled: true,
      },
    });
    toast("Recurso reativado.", "success");
    rvAdminLoad();
  } catch (e) {
    toast(rvErrInfo(e).message, "error");
  }
}

async function rvAdminExpireStale() {
  if (!confirm("Processar agora os resgates expirados da Vitrine de Recursos? (reembolsa compradores e devolve recursos ao estoque)")) return;
  try {
    const d = await rvApi("/admin/claims/expire-stale", { method: "POST", body: {} });
    toast(`Expirados processados: ${rvFmt(d.processed || 0)}.`, "success");
    rvAdminLoad();
  } catch (e) {
    toast(rvErrInfo(e).message, "error");
  }
}

// Hooks já referenciados pelo index.html (setMarketTab / nav): nomes mantidos por compatibilidade.
window.rvOpenTab = rvOnTabShown;
window.rvLoadAdmin = rvAdminLoad;
