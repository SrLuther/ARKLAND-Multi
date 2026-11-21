/* ARK admin command builder. It only reads live status and generates text; it never executes commands. */
(() => {
  "use strict";
  const state = { catalog: [], servers: [], live: [], selected: null, players: [], currentServer: "", loading: false };
  const byId = id => document.getElementById(id);
  const esc = value => typeof escHtml === "function" ? escHtml(String(value ?? "")) : String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
  const categoryNames = { Player:"Jogador", Dino:"Criatura", "Server Admin":"Administração do servidor", Chat:"Chat", Map:"Mundo e mapa", Teleportation:"Teletransporte", "No Cheat":"Sem autenticação de cheat", Structure:"Estruturas", Destroy:"Destruição", Tribe:"Tribos", Boss:"Chefes", Unknown:"Não documentado", "Skill Tree":"Árvore de habilidades", "Creative Mode":"Modo criativo", Cosmetic:"Aparência", Client:"Cliente", Bugged:"Possível erro", Structures:"Estruturas", Spectator:"Espectador" };
  const categoriesOf = command => String(command.category || "Outros").split(/,\s*/).filter(Boolean).map(category => categoryNames[category] || category);
  const words = {
    Amount:"Quantidade", PlayerID:"ID do jogador (Player ID)", PlayerId:"ID do jogador (Player ID)", SteamID:"SteamID", SteamId:"SteamID",
    HowMuch:"Quantidade", Level:"Nível", NumLevels:"Níveis", Radius:"Raio", Distance:"Distância", Quality:"Qualidade",
    MessageText:"Mensagem", Message:"Mensagem", Name:"Nome", NewName:"Novo nome", PlayerName:"Nome do jogador",
    TribeID:"ID da tribo", TribeId:"ID da tribo", TribeName:"Nome da tribo", CreatureID:"ID da criatura", BlueprintPath:"Blueprint",
    "Creature ID":"Classe/identificador da criatura", "ItemNum":"ID numérico do item", "ColorRegion":"Região de cor", "ColorID":"ID da cor",
    Blueprint:"Blueprint (classe/caminho)", BlueprintPath:"Caminho de Blueprint", PlayerID:"PlayerID numérico", PlayerId:"PlayerID numérico", SteamID:"SteamID64", SteamId:"SteamID64", TribeID:"ID da tribo", TribeId:"ID da tribo",
    Type:"Tipo", ExactMatch:"Correspondência exata", Exact:"Correspondência exata", Value:"Valor", Enable:"Ativar", TrueFalse:"Ativar?",
    X:"Coordenada X", Y:"Coordenada Y", Z:"Coordenada Z", Hour:"Hora", Minute:"Minuto", Password:"Senha", QualityName:"Qualidade"
  };
  function paramLabel(param) {
    const raw = String(param.raw || "Parâmetro").replace(/[<>\[\]"]/g, "").replace(/\s+/g, " ").trim();
    return words[raw.replace(/\s/g, "")] || words[raw] || param.label_pt || raw || "Parâmetro";
  }
  function currentPlayer() {
    const selector = byId("cc-player");
    return state.players.find(player => player.steam_id === selector?.value) || null;
  }
  async function loadCatalog() {
    if (state.catalog.length) return;
    const response = await fetch("/ark_admin_commands.json", { credentials: "same-origin", cache: "no-cache" });
    if (!response.ok) throw new Error("Não foi possível carregar o catálogo de comandos.");
    state.catalog = await response.json();
    const categories = [...new Set(state.catalog.flatMap(categoriesOf))].sort((a,b) => a.localeCompare(b, "pt-BR"));
    byId("cc-category").innerHTML = '<option value="">Todas as categorias</option>' + categories.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
    commandCenterRenderList();
  }
  async function commandCenterLoad() {
    if (!_auth?.is_admin) return;
    try {
      await loadCatalog();
      if (!state.servers.length) await commandCenterRefresh();
    } catch (error) {
      byId("cc-server-state").textContent = error?.message || "Falha ao carregar dados.";
    }
  }
  async function commandCenterRefresh() {
    if (!_auth?.is_admin || state.loading) return;
    state.loading = true;
    const stateEl = byId("cc-server-state");
    if (stateEl) stateEl.textContent = "Atualizando mapa e jogadores via RCON…";
    try {
      const [configured, live] = await Promise.all([
        fetchJson("/api/servers", { timeoutMs: 15000, retries: 0 }),
        fetchJson("/api/admin/map-members/online", { timeoutMs: 25000, retries: 0 })
      ]);
      if (!configured.ok || !Array.isArray(configured.items)) throw new Error(configured.error || "Não foi possível carregar os mapas cadastrados.");
      if (!live.ok || !Array.isArray(live.servers)) throw new Error(live.error || "Não foi possível consultar os jogadores.");
      state.servers = configured.items;
      state.live = live.servers;
      const select = byId("cc-server"), previous = select.value;
      select.innerHTML = state.servers.map(server => {
        const id = String(server.server_id || ""), title = server.label || server.server_map || id;
        const status = state.live.find(row => row.server_id === id)?.status || "sem consulta";
        return `<option value="${esc(id)}">${esc(title)} · ${esc(server.server_map || "mapa não identificado")} · ${esc(status)}</option>`;
      }).join("") || '<option value="">Nenhum mapa cadastrado</option>';
      if (state.servers.some(server => server.server_id === previous)) select.value = previous;
      else if (state.servers.length) select.selectedIndex = 0;
      commandCenterSelectServer();
      stateEl.textContent = `Dados atualizados em ${new Date(live.updated_at || Date.now()).toLocaleString("pt-BR")}. A consulta ao vivo identifica SteamID64; Player ID numérico não é fornecido por ListPlayers.`;
    } catch (error) {
      if (stateEl) stateEl.textContent = error?.message || "Falha ao consultar os mapas.";
      if (typeof toast === "function") toast(stateEl.textContent, "error");
    } finally { state.loading = false; }
  }
  function commandCenterSelectServer() {
    const select = byId("cc-server");
    state.currentServer = select?.value || "";
    const row = state.live.find(server => server.server_id === state.currentServer);
    state.players = row?.players || [];
    const playerSelect = byId("cc-player");
    if (!playerSelect) return;
    const prior = playerSelect.value;
    playerSelect.innerHTML = '<option value="">Nenhum jogador selecionado</option>' + state.players.map(player => `<option value="${esc(player.steam_id)}">${esc(player.name)} · ${esc(player.steam_id)}</option>`).join("");
    if (state.players.some(player => player.steam_id === prior)) playerSelect.value = prior;
    commandCenterSelectPlayer();
    const stateEl = byId("cc-server-state");
    if (row && row.status !== "online") stateEl.textContent = `${row.label || "Mapa"}: ${row.error || `status RCON: ${row.status}`}`;
    else if (row) stateEl.textContent = `${row.label || "Mapa"}: RCON respondeu. ${state.players.length} jogador(es) conectado(s).`;
  }
  function commandCenterSelectPlayer() {
    const player = currentPlayer(), el = byId("cc-player-identifiers");
    if (!el) return;
    el.innerHTML = player
      ? `<strong>${esc(player.name)}</strong><br>SteamID64: <code>${esc(player.steam_id)}</code><br>Player ID numérico: <em>não fornecido pela consulta ao vivo</em>`
      : "Selecione um jogador para ver os identificadores disponíveis.";
    commandCenterRenderDetail();
  }
  function commandCenterRenderList() {
    const query = (byId("cc-search")?.value || "").trim().toLocaleLowerCase("pt-BR");
    const category = byId("cc-category")?.value || "";
    const includeAsa = !!byId("cc-include-asa")?.checked;
    const filtered = state.catalog.filter(command => (includeAsa || (command.compatibility || []).includes("ASE")) && (!category || categoriesOf(command).includes(category)) &&
      (!query || `${command.name} ${command.label_pt} ${command.category} ${categoriesOf(command).join(" ")} ${command.description_pt} ${command.description_en}`.toLocaleLowerCase("pt-BR").includes(query)));
    const count = byId("cc-count"), list = byId("cc-command-list");
    if (count) count.textContent = `${filtered.length} de ${state.catalog.length} comandos`; 
    if (list) list.innerHTML = filtered.map(command => {
      const key = (command.compatibility || []).join("/");
      const selected = state.selected?.name === command.name && (state.selected?.compatibility || []).join("/") === key;
      return `<button type="button" role="option" aria-selected="${selected}" class="cc-command ${selected ? "is-selected" : ""}" onclick="commandCenterChoose('${esc(command.name)}','${esc(key)}')"><strong>${esc(command.name)}</strong><small>${esc(command.label_pt || categoriesOf(command).join(" · "))} · ${esc(key)}</small></button>`;
    }).join("") || '<div class="cc-empty">Nenhum comando encontrado.</div>';
  }
  function commandCenterChoose(name, compatibility) {
    state.selected = state.catalog.find(command => command.name === name && (command.compatibility || []).join("/") === compatibility) || null;
    commandCenterRenderList();
    commandCenterRenderDetail();
  }
  function commandCenterRenderDetail() {
    const command = state.selected, root = byId("cc-command-detail");
    if (!command || !root) return;
    const player = currentPlayer();
    const params = (command.parameters || []).map((param, index) => {
      const label = paramLabel(param), raw = String(param.raw || "");
      const isSteam = /steam\s*id/i.test(raw), isPlayerId = /player\s*id/i.test(raw);
      let value = "";
      if (player && isSteam) value = player.steam_id;
      const booleanOptions = param.allowed_values || ["0", "1", "false", "true"];
      const input = param.type === "booleano"
        ? `<select id="cc-param-${index}"><option value="">Selecione…</option>${booleanOptions.map(option => `<option value="${esc(option)}">${option === "0" ? "Não (0)" : option === "1" ? "Sim (1)" : option === "false" ? "Falso (false)" : "Verdadeiro (true)"}</option>`).join("")}</select>`
        : `<input id="cc-param-${index}" type="${["numero", "inteiro"].includes(param.type) ? "number" : "text"}" ${param.type === "numero" ? "step=any" : param.type === "inteiro" ? "step=1" : ""} value="${esc(value)}" autocomplete="off" />`;
      const hint = isPlayerId ? "Player ID numérico do ARK; não use o SteamID64." : isSteam ? "SteamID será preenchido pelo jogador selecionado." : `Parâmetro nativo: ${raw}`;
      return `<div class="cc-param"><label for="cc-param-${index}">${esc(label)}${param.required ? " *" : ""}</label>${input}<small>${esc(hint)}</small></div>`;
    }).join("");
    const riskClass = command.risk === "alto" ? "cc-tag--high" : "";
    const riskText = command.risk === "alto" ? "Risco alto — revisar antes de copiar" : command.risk === "moderado" ? "Pode alterar o mundo/jogador" : "Baixo risco estimado";
    const compatibility = (command.compatibility || []).join(" / ") || "Compatibilidade não confirmada";
    root.innerHTML = `<h2 class="cc-detail-title">${esc(command.name)}</h2><div class="cc-tags"><span class="cc-tag">${esc(categoriesOf(command).join(" · "))}</span><span class="cc-tag ${riskClass}">${esc(riskText)}</span><span class="cc-tag">${esc(compatibility)}</span></div><div class="cc-description">${esc(command.description_pt || command.description_en || "Sem descrição disponível.")}</div><div class="cc-muted">Sintaxe de referência: <code>${esc(command.syntax)}</code></div>${command.example ? `<div class="cc-muted">Exemplo da fonte: <code>${esc(command.example)}</code></div>` : ""}<div class="cc-param-list">${params || '<div class="cc-muted">Este comando não declara parâmetros no catálogo.</div>'}</div><div id="cc-build-error" class="cc-inline-error" role="alert"></div><code id="cc-output" class="cc-command-output">Configure os parâmetros para gerar o comando.</code><div class="cc-builder-actions"><button class="btn btn-primary" type="button" onclick="commandCenterCopy()">Copiar comando</button></div><div class="cc-muted">A central apenas gera texto. Nada será enviado ao servidor automaticamente.</div>`;
    if (params) root.querySelectorAll(".cc-param input,.cc-param select").forEach(input => input.addEventListener("input", commandCenterBuild));
    commandCenterBuild();
  }
  function commandCenterBuild() {
    const command = state.selected;
    if (!command) return;
    const errorEl = byId("cc-build-error"), output = byId("cc-output");
    const values = [];
    for (let index = 0; index < (command.parameters || []).length; index++) {
      const param = command.parameters[index], input = byId(`cc-param-${index}`), value = String(input?.value || "").trim();
      if (!value && param.required) { errorEl.textContent = `Preencha o parâmetro obrigatório: ${paramLabel(param)}.`; output.textContent = "Comando incompleto."; return false; }
      if (!value) continue;
      if (/[\r\n;\0]/.test(value)) { errorEl.textContent = "O campo contém separador de comando ou caractere inválido."; output.textContent = "Comando inválido."; return false; }
      if (param.type === "inteiro" && !/^-?\d+$/.test(value)) { errorEl.textContent = `${paramLabel(param)} precisa ser um número inteiro.`; output.textContent = "Comando inválido."; return false; }
      if (param.type === "numero" && !/^-?(?:\d+\.?\d*|\.\d+)$/.test(value)) { errorEl.textContent = `${paramLabel(param)} precisa ser numérico.`; output.textContent = "Comando inválido."; return false; }
      if (param.type === "booleano" && !(param.allowed_values || ["0", "1", "false", "true"]).includes(value)) { errorEl.textContent = `${paramLabel(param)} precisa ser um valor booleano permitido.`; output.textContent = "Comando inválido."; return false; }
      const quoted = String(param.raw || "").includes('"') || (param.type === "texto" && /\s/.test(value));
      if (value.includes('"')) { errorEl.textContent = "Aspas não são aceitas neste parâmetro."; return false; }
      if (quoted) {
        values.push(`"${value}"`);
      } else values.push(value);
    }
    errorEl.textContent = "";
    const sourcePrefix = String(command.syntax || "").split(command.name)[0].trim();
    const prefix = sourcePrefix || "cheat";
    output.textContent = [prefix, command.name, ...values].filter(Boolean).join(" ");
    return true;
  }
  async function commandCenterCopy() {
    if (!commandCenterBuild()) return;
    const text = byId("cc-output")?.textContent || "";
    if (!text || text === "Comando inválido." || text === "Comando incompleto.") return;
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
      else { const area = document.createElement("textarea"); area.value = text; document.body.appendChild(area); area.select(); const copied = document.execCommand("copy"); area.remove(); if (!copied) throw new Error("clipboard_unavailable"); }
      try { await fetchJson("/api/admin/command-center/audit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ command_name: state.selected?.name || "", server_id: state.currentServer }), timeoutMs: 5000, retries: 0 }); } catch (_) { /* A falha de auditoria não invalida a cópia manual. */ }
      if (typeof toast === "function") toast("Comando copiado! Cole no console do ARK para executar.", "success");
    } catch (_) { if (typeof toast === "function") toast("Não foi possível copiar automaticamente; selecione o comando e copie manualmente.", "warning"); }
  }
  Object.assign(window, { commandCenterLoad, commandCenterRefresh, commandCenterSelectServer, commandCenterSelectPlayer, commandCenterRenderList, commandCenterChoose, commandCenterCopy });
})();
