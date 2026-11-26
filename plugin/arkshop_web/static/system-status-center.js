(function () {
  "use strict";
  const MATURITY = ["NAO_AVALIADO", "PLANEJADO", "EM_DESENVOLVIMENTO", "ALPHA", "BETA", "EM_HOMOLOGACAO", "FINALIZADO", "EM_REFORMULACAO", "DESCONTINUADO"];
  const OPERATIONAL = ["NAO_MONITORADO", "STATUS_DESCONHECIDO", "OPERACIONAL", "PARCIALMENTE_OPERACIONAL", "INSTAVEL", "EM_MANUTENCAO", "INDISPONIVEL", "NAO_DISPONIBILIZADO"];
  const AVAILABILITY = ["", "AVAILABLE", "EXPERIMENTAL", "RESTRICTED", "SUSPENDED", "NOT_RELEASED"];
  const INCIDENT = ["IDENTIFICADO", "EM_INVESTIGACAO", "EM_CORRECAO", "EM_MONITORAMENTO", "RESOLVIDO"];
  const LABEL = {
    NAO_AVALIADO: "Não avaliado", PLANEJADO: "Planejado", EM_DESENVOLVIMENTO: "Em desenvolvimento", ALPHA: "Alpha", BETA: "Beta",
    EM_HOMOLOGACAO: "Em homologação", FINALIZADO: "Finalizado", EM_REFORMULACAO: "Em reformulação", DESCONTINUADO: "Descontinuado",
    NAO_MONITORADO: "Não monitorado", STATUS_DESCONHECIDO: "Status desconhecido", OPERACIONAL: "Operacional",
    PARCIALMENTE_OPERACIONAL: "Parcialmente operacional", INSTAVEL: "Instável", EM_MANUTENCAO: "Em manutenção",
    INDISPONIVEL: "Indisponível", NAO_DISPONIBILIZADO: "Não disponibilizado", AVAILABLE: "Disponível", EXPERIMENTAL: "Experimental",
    RESTRICTED: "Restrito", SUSPENDED: "Suspenso", NOT_RELEASED: "Não lançado", IDENTIFICADO: "Identificado",
    EM_INVESTIGACAO: "Em investigação", EM_CORRECAO: "Em correção", EM_MONITORAMENTO: "Em monitoramento", RESOLVIDO: "Resolvido",
    PARADO: "Parado", INICIANDO: "Iniciando", ATUALIZANDO: "Atualizando", ONLINE: "Online", ONLINE_SEM_LISTAGEM: "Online · sem listagem",
    ONLINE_LAN: "Online · rede local", QUERY_PENDENTE: "Aguardando query"
  };
  let payload = null, adminData = null, selectedAdmin = "", creatingSystem = false, adminLoadPromise = null;
  const byId = id => document.getElementById(id);
  const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
  const label = key => LABEL[key] || String(key || "Não informado").replaceAll("_", " ");
  const tone = key => ["OPERACIONAL", "FINALIZADO", "AVAILABLE", "ONLINE"].includes(key) ? "good" :
    ["PARCIALMENTE_OPERACIONAL", "INSTAVEL", "EM_MANUTENCAO", "EXPERIMENTAL", "RESTRICTED", "EM_DESENVOLVIMENTO", "BETA", "ALPHA", "EM_HOMOLOGACAO", "QUERY_PENDENTE"].includes(key) ? "warn" :
    ["INDISPONIVEL", "SUSPENDED", "DESCONTINUADO", "ONLINE_SEM_LISTAGEM"].includes(key) ? "bad" : "neutral";
  function fmtDate(value) {
    if (!value) return "Não registrado";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("pt-BR", {dateStyle:"short",timeStyle:"short",timeZone:"America/Sao_Paulo"}).format(date) + " (Brasília)";
  }
  async function api(path, options) {
    const response = await fetch(path, Object.assign({credentials:"same-origin", headers:{"Content-Type":"application/json"}}, options || {}));
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `Falha HTTP ${response.status}`);
    return result;
  }
  function listBlock(title, items) {
    if (!Array.isArray(items) || !items.length) return "";
    return `<details><summary>${esc(title)} (${items.length})</summary><ul>${items.map(item => `<li>${esc(item)}</li>`).join("")}</ul></details>`;
  }
  function badge(key) { return `<span class="system-status-badge" data-tone="${tone(key)}">${esc(label(key))}</span>`; }
  function renderCard(system) {
    const instances = Array.isArray(system.instances) ? system.instances : [];
    const incidents = (payload.incidents || []).filter(item => item.system_key === system.system_key && item.state !== "RESOLVIDO");
    const instanceMarkup = instances.map(item => `<div class="system-status-card__instance"><strong>${esc(item.display_name || item.instance_key || "Instância")}</strong> ${badge(item.operational)}<br>${esc(item.map_name || "Mapa não informado")}${item.version ? ` · ${esc(item.version)}` : ""}<br><small>Fonte: ${esc(item.source || "não informada")} · verificado: ${esc(fmtDate(item.checked_at))}</small>${item.details ? `<p>${esc(item.details)}</p>` : ""}</div>`).join("");
    const issueMarkup = incidents.map(item => `<div class="system-status-incident"><h3>${esc(item.title)} · ${esc(label(item.state))}</h3><p>${esc(item.description)}</p><small>Atualizado ${esc(fmtDate(item.updated_at))}</small></div>`).join("");
    const verified = system.verified_at ? `Verificado ${esc(fmtDate(system.verified_at))}` : "Revisão não registrada";
    return `<article class="system-status-card"><div class="system-status-card__head"><div><span class="system-status-category">${esc(system.category)}</span><h2>${esc(system.name)}</h2></div>${system.public_url ? `<a href="${esc(system.public_url)}" target="_blank" rel="noopener noreferrer" aria-label="Abrir ${esc(system.name)}">↗</a>` : ""}</div>
      <p>${esc(system.description)}</p><div class="system-status-badges">${badge(system.maturity)}${badge(system.operational)}${system.availability ? badge(system.availability) : ""}${system.version ? badge(system.version) : ""}</div>
      ${system.player_note ? `<p class="system-status-player-note">${esc(system.player_note)}</p>` : ""}
      ${issueMarkup}${instanceMarkup}${listBlock("Recursos disponíveis",system.implemented)}${listBlock("Em desenvolvimento",system.development)}${listBlock("Limitações",system.limitations)}${listBlock("Problemas conhecidos",system.known_issues)}
      <small>${verified}</small></article>`;
  }
  window.systemStatusRender = function () {
    if (!payload) return;
    const query = (byId("system-status-search")?.value || "").trim().toLocaleLowerCase("pt-BR");
    const category = byId("system-status-category")?.value || "";
    const systems = (payload.systems || []).filter(item => `${item.name} ${item.category} ${item.description}`.toLocaleLowerCase("pt-BR").includes(query) && (!category || item.category === category));
    const list = byId("system-status-list");
    list.innerHTML = systems.length ? systems.map(renderCard).join("") : "<p>Nenhum sistema corresponde à pesquisa.</p>";
    const counts = payload.summary || {};
    byId("system-status-summary").innerHTML = [["total","Sistemas publicados"],["operational","Registrados como operacionais"],["in_development","Em planejamento ou desenvolvimento"],["with_issues","Com condição operacional registrada"]].map(([key,title]) => `<div class="system-status-stat"><strong>${Number(counts[key] || 0)}</strong><span>${title}</span></div>`).join("");
    const categories = [...new Set((payload.systems || []).map(item => item.category).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"pt-BR"));
    const select = byId("system-status-category"), current = select.value;
    select.innerHTML = `<option value="">Todas as categorias</option>` + categories.map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join("");
    if (categories.includes(current)) select.value = current;
    const incidents = (payload.incidents || []).filter(item => item.state !== "RESOLVIDO");
    byId("system-status-incidents").innerHTML = incidents.length ? `<h2>Incidentes e manutenções</h2>${incidents.map(item => `<div class="system-status-incident"><h3>${esc(item.title)} · ${esc(label(item.state))}</h3><p>${esc(item.description)}</p><small>${esc(item.system_key)} · iniciado ${esc(fmtDate(item.identified_at))} · atualizado ${esc(fmtDate(item.updated_at))}</small></div>`).join("")}` : "";
    byId("system-status-updated").textContent = `Dados consultados em ${fmtDate(payload.updated_at)}. A atualização de cada registro pode ter horário diferente.`;
  };
  window.systemStatusLoad = async function (force) {
    const list = byId("system-status-list");
    if (force && list) list.innerHTML = "<p>Atualizando…</p>";
    try {
      payload = await api("/api/public/systems-status" + (force ? `?t=${Date.now()}` : ""));
      window.systemStatusRender();
      await window.systemStatusRefreshAdmin(true);
    } catch (error) { if (list) list.innerHTML = `<p role="alert">Não foi possível carregar a central: ${esc(error.message)}. Tente atualizar novamente.</p>`; }
  };
  function isAdmin() {
    // A sessão do portal é declarada com let; não é uma propriedade de window.
    return typeof _auth !== "undefined" && !!_auth?.authenticated && !!_auth?.is_admin;
  }
  window.systemStatusRefreshAdmin = async function (force = false) {
    const root = byId("system-status-admin"), error = byId("system-status-admin-error");
    if (!root) return;
    if (!isAdmin()) {
      root.hidden = true;
      if (error) error.hidden = true;
      adminData = null;
      return;
    }
    if (!byId("page-system-status")?.classList.contains("active")) return;
    if (adminLoadPromise) return adminLoadPromise;
    if (adminData && !force) return;
    adminLoadPromise = loadAdmin().finally(() => { adminLoadPromise = null; });
    return adminLoadPromise;
  };
  function fillSelect(id, values, allowEmpty) {
    const select = byId(id); if (!select) return;
    select.innerHTML = values.map(value => `<option value="${esc(value)}">${esc(value ? label(value) : "Não informado")}</option>`).join("");
    if (allowEmpty) select.value = "";
  }
  async function loadAdmin() {
    const root = byId("system-status-admin");
    const error = byId("system-status-admin-error");
    try {
      const result = await api("/api/admin/systems-status");
      if (!isAdmin()) { root.hidden = true; return; }
      adminData = result;
    } catch (failure) {
      root.hidden = true;
      if (error && isAdmin()) {
        error.textContent = `Não foi possível carregar a administração da central: ${failure.message}. Clique em Atualizar para tentar novamente.`;
        error.hidden = false;
      }
      return;
    }
    if (error) error.hidden = true;
    root.hidden = false;
    const options = adminData.systems.map(system => `<option value="${esc(system.system_key)}">${esc(system.name)}</option>`).join("");
    byId("ssa-system").innerHTML = options; byId("ssi-system").innerHTML = options;
    fillSelect("ssa-maturity", MATURITY); fillSelect("ssa-operational", OPERATIONAL); fillSelect("ssa-availability", AVAILABILITY, true);
    fillSelect("ssi-state", INCIDENT);
    if (!selectedAdmin || !adminData.systems.some(item => item.system_key === selectedAdmin)) selectedAdmin = adminData.systems[0]?.system_key || "";
    byId("ssa-system").value = selectedAdmin;
    systemStatusAdminSelect();
    const container = byId("system-status-admin-incidents");
    container.innerHTML = (adminData.incidents || []).map(item => `<div class="system-status-admin-incident"><span>${esc(item.title)} · ${esc(item.system_key)} · ${esc(label(item.state))}</span>${item.state !== "RESOLVIDO" ? `<button type="button" class="btn btn-ghost btn-sm" data-resolve-incident="${Number(item.id)}">Marcar resolvido</button>` : ""}</div>`).join("");
    container.querySelectorAll("[data-resolve-incident]").forEach(button => button.addEventListener("click", async () => {
      await api(`/api/admin/systems-status/incidents/${button.dataset.resolveIncident}`, {method:"PATCH",body:JSON.stringify({state:"RESOLVIDO"})}); await systemStatusLoad(true);
    }));
  }
  window.systemStatusAdminSelect = async function () {
    const system = adminData?.systems.find(item => item.system_key === byId("ssa-system")?.value); if (!system) return;
    creatingSystem = false;
    selectedAdmin = system.system_key;
    byId("ssa-key").value = system.system_key; byId("ssa-key").disabled = true;
    const fields = {name:"name",category:"category",version:"version",maturity:"maturity",operational:"operational",availability:"availability",url:"public_url",description:"description",implemented:"implemented",development:"development",limitations:"limitations",issues:"known_issues",note:"player_note"};
    Object.entries(fields).forEach(([id,key]) => { const el = byId("ssa-"+id); if (el) el.value = Array.isArray(system[key]) ? system[key].join("\n") : (system[key] || ""); });
    byId("ssa-public").checked = !!system.is_public; byId("ssa-archived").checked = !!system.is_archived;
    try {
      const audit = await api(`/api/admin/systems-status/${encodeURIComponent(system.system_key)}/audit`);
      byId("system-status-audit").innerHTML = audit.entries.length ? audit.entries.slice(0,20).map(item => `<div class="system-status-admin-incident"><span>${esc(fmtDate(item.changed_at))} · ${esc(item.actor)} · ${esc(Object.keys(item.after || {}).join(", ") || "Atualização")}</span><details><summary>Detalhes</summary><pre>${esc(JSON.stringify({antes:item.before,depois:item.after},null,2))}</pre></details></div>`).join("") : "<p>Nenhuma alteração administrativa registrada.</p>";
    } catch (_) { byId("system-status-audit").textContent = "Não foi possível carregar o histórico."; }
  };
  window.systemStatusAdminNew = function () {
    creatingSystem = true; selectedAdmin = "";
    byId("ssa-key").value = ""; byId("ssa-key").disabled = false;
    ["name","category","version","url","description","implemented","development","limitations","issues","note"].forEach(id => { byId("ssa-"+id).value = ""; });
    byId("ssa-maturity").value = "NAO_AVALIADO"; byId("ssa-operational").value = "NAO_MONITORADO"; byId("ssa-availability").value = "";
    byId("ssa-public").checked = true; byId("ssa-archived").checked = false; byId("ssa-name").focus();
  };
  window.systemStatusAdminSave = async function () {
    const status = byId("ssa-feedback"); status.textContent = "Salvando…";
    const fields = {name:"name",category:"category",version:"version",maturity:"maturity",operational:"operational",availability:"availability",public_url:"url",description:"description",implemented:"implemented",development:"development",limitations:"limitations",known_issues:"issues",player_note:"note"};
    const body = {}; Object.entries(fields).forEach(([key,id]) => { const value = byId("ssa-"+id).value; body[key] = ["implemented","development","limitations","known_issues"].includes(key) ? value.split(/\r?\n/).map(item=>item.trim()).filter(Boolean) : value; });
    body.is_public = byId("ssa-public").checked; body.is_archived = byId("ssa-archived").checked;
    const key = creatingSystem ? byId("ssa-key").value.trim() : selectedAdmin;
    if (!/^[a-z0-9][a-z0-9._-]{1,79}$/.test(key)) { status.textContent = "Informe uma chave válida (2 a 80 caracteres)."; return; }
    try { await api(`/api/admin/systems-status/${encodeURIComponent(key)}`, {method:"PUT",body:JSON.stringify(body)}); selectedAdmin = key; creatingSystem = false; status.textContent = "Alterações salvas e registradas no histórico."; await systemStatusLoad(true); }
    catch (error) { status.textContent = `Não foi possível salvar: ${error.message}`; }
  };
  window.systemStatusIncidentCreate = async function () {
    const key = byId("ssi-system").value, status = byId("ssa-feedback"); status.textContent = "Registrando…";
    const body = {title:byId("ssi-title").value,description:byId("ssi-description").value,state:byId("ssi-state").value,is_public:byId("ssi-public").checked};
    try { await api(`/api/admin/systems-status/${encodeURIComponent(key)}/incidents`, {method:"POST",body:JSON.stringify(body)}); byId("ssi-title").value=""; byId("ssi-description").value=""; status.textContent="Incidente registrado."; await systemStatusLoad(true); }
    catch (error) { status.textContent = `Não foi possível registrar: ${error.message}`; }
  };
  window.systemStatusLoad(false);
})();
