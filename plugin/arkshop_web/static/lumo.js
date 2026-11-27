(() => {
  const DRAFT_KEY = "arkland.lumo.draft.v1";
  const templates = [
    ["Comunicado oficial", "Comunicado oficial", "**Olá, sobreviventes!**\n\n[Escreva aqui o comunicado oficial da comunidade ARKLAND.]\n\nLumo • Assistente oficial da ARKLAND"],
    ["Manutenção programada", "Manutenção programada", "**Olá, sobreviventes!**\n\nRealizaremos uma manutenção programada em nossos servidores.\n\n**Servidor afetado:** [Informar servidor]\n**Data:** [Informar data]\n**Horário:** [Informar horário]\n**Previsão de retorno:** [Informar previsão]\n\nRecomendamos que organizem suas atividades antes do início. Agradecemos pela compreensão!"],
    ["Manutenção emergencial", "Manutenção emergencial", "**Olá, sobreviventes!**\n\nEstamos realizando uma manutenção emergencial em **[servidor afetado]** para corrigir [descrever brevemente].\n\n**Início:** [horário]\n**Previsão de retorno:** [horário ou atualização]\n\nPublicaremos novas informações assim que estiverem disponíveis."],
    ["Servidor disponível", "Servidor disponível", "**O servidor [nome exibido] está disponível novamente.**\n\nA conexão já pode ser realizada pela lista de servidores ou pelos favoritos da Steam.\n\nObrigado pela paciência, sobreviventes!"],
    ["Instabilidade nos servidores", "Instabilidade nos servidores", "**Olá, sobreviventes!**\n\nIdentificamos instabilidade em [servidor/serviço]. Estamos verificando a causa e acompanhando a situação.\n\nCompartilharemos uma atualização quando houver novas informações confirmadas."],
    ["Anúncio de evento", "Evento ARKLAND: [nome]", "**Olá, sobreviventes!**\n\nPreparem-se para **[nome do evento]**!\n\n**Quando:** [data e horário]\n**Onde:** [servidor/mapa]\n**Como participar:** [instruções]\n\nEsperamos vocês na ilha!"],
    ["Atualização de regras", "Atualização das regras", "**Olá, sobreviventes!**\n\nAs regras da comunidade foram atualizadas em [data].\n\nConsulte a versão vigente em [link ou canal] antes de continuar suas atividades. Em caso de dúvida, fale com a equipe pelo canal de suporte."],
    ["Novidades da comunidade", "Novidades da comunidade ARKLAND", "**Olá, sobreviventes!**\n\nConfira as novidades da comunidade:\n• [Novidade 1]\n• [Novidade 2]\n• [Novidade 3]\n\nAcompanhe nossos canais oficiais para não perder os próximos anúncios."],
    ["Orientação aos jogadores", "Orientação aos jogadores", "**Olá, sobreviventes!**\n\nPara [situação], siga estas etapas:\n1. [Etapa 1]\n2. [Etapa 2]\n3. [Etapa 3]\n\nSe o problema continuar, abra um ticket e informe o servidor, o horário aproximado e os detalhes do ocorrido."],
    ["Boas-vindas aos sobreviventes", "Boas-vindas à ARKLAND!", "**Seja bem-vindo à comunidade ARKLAND!**\n\nEsperamos que sua jornada pelas ilhas seja divertida. Leia as regras, escolha seu servidor e, se precisar de ajuda, procure a equipe nos canais de suporte.\n\nBoa sobrevivência!"],
    ["Agradecimento à comunidade", "Obrigado, sobreviventes!", "**Olá, sobreviventes!**\n\nAgradecemos a todos que participaram de [atividade/evento] e ajudaram a fortalecer a comunidade ARKLAND.\n\nNos vemos nas ilhas!"],
  ].map(([name, title, content]) => ({ name, title, content }));

  let integration = null;
  const newRequestId = () => crypto.randomUUID ? crypto.randomUUID() : [...crypto.getRandomValues(new Uint8Array(16))].map((n) => n.toString(16).padStart(2,"0")).join("");
  let requestId = newRequestId();
  let historyOffset = 0;
  let historyMore = false;
  let dirty = false;
  let initial = true;
  const undoStack = [];
  const redoStack = [];
  let beforeInputState = null;
  let assistantConfig = null;
  let pendingAssetDraft = {};
  let lumoAssets = [];

  const $ = (id) => document.getElementById(id);
  const val = (id) => ($(id)?.value || "");
  const setVal = (id, value) => { const el = $(id); if (el) el.value = value || ""; };
  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (ch) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" })[ch]);
  const safeHttps = (value) => { try { const u = new URL(value); return u.protocol === "https:" && !u.username && !u.password ? u.href : ""; } catch { return ""; } };
  const toast = (message, type = "info") => { if (typeof window.toast === "function") window.toast(message, type); else alert(message); };

  function renderMarkdown(source) {
    const codeBlocks = [];
    let html = escapeHtml(source).replace(/```([\s\S]*?)```/g, (_m, code) => `@@CODE${codeBlocks.push(`<pre><code>${code.trim()}</code></pre>`) - 1}@@`);
    html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_m, label, href) => {
      try { const u = new URL(href); if (!/^https?:$/.test(u.protocol)) return label; return `<a href="${escapeHtml(u.href)}" target="_blank" rel="noopener noreferrer">${label}</a>`; } catch { return label; }
    });
    html = html.replace(/\|\|([\s\S]+?)\|\|/g, '<span class="lumo-spoiler" title="Passe o cursor para revelar">$1</span>');
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/__(.+?)__/g, "<u>$1</u>").replace(/~~(.+?)~~/g, "<del>$1</del>").replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>").replace(/(^|[^_])_([^_\n]+)_/g, "$1<em>$2</em>");
    const blocks = html.split(/\n{2,}/).map((block) => {
      const lines = block.split("\n");
      if (lines.every((line) => /^&gt;\s?/.test(line))) return `<blockquote>${lines.map((line) => line.replace(/^&gt;\s?/, "")).join("<br>")}</blockquote>`;
      if (lines.every((line) => /^[-*+]\s+/.test(line))) return `<ul>${lines.map((line) => `<li>${line.replace(/^[-*+]\s+/, "")}</li>`).join("")}</ul>`;
      if (lines.every((line) => /^\d+\.\s+/.test(line))) return `<ol>${lines.map((line) => `<li>${line.replace(/^\d+\.\s+/, "")}</li>`).join("")}</ol>`;
      return `<p>${block.replace(/\n/g, "<br>")}</p>`;
    }).join("");
    return blocks.replace(/@@CODE(\d+)@@/g, (_m, index) => codeBlocks[Number(index)] || "");
  }

  function draftData() { return { title: val("lumo-title"), content: val("lumo-content"), title_url: val("lumo-title-url"), image_url: val("lumo-image-url"), thumbnail_url: val("lumo-thumbnail-url"), image_asset_id: val("lumo-image-asset"), thumbnail_asset_id: val("lumo-thumbnail-asset") }; }
  function saveDraft(showMessage = false) {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ ...draftData(), saved_at: new Date().toISOString() }));
    dirty = false;
    if (showMessage) toast("Rascunho salvo neste navegador. A URL do webhook não é incluída.", "success");
  }
  function restoreDraft() {
    try { const saved = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null"); if (!saved) return; Object.entries(saved).forEach(([key, id]) => { const domId = ({ title:"lumo-title", content:"lumo-content", title_url:"lumo-title-url", image_url:"lumo-image-url", thumbnail_url:"lumo-thumbnail-url" })[key]; if (domId) setVal(domId, id); }); pendingAssetDraft = { image_asset_id:saved.image_asset_id || "", thumbnail_asset_id:saved.thumbnail_asset_id || "" }; }
    catch { localStorage.removeItem(DRAFT_KEY); }
  }
  function updatePreview() {
    const title = val("lumo-title").trim();
    const content = val("lumo-content");
    const titleUrl = val("lumo-title-url").trim();
    const titleEl = $("lumo-preview-title");
    const safeTitleUrl = safeHttps(titleUrl);
    titleEl.innerHTML = title ? (safeTitleUrl ? `<a href="${escapeHtml(safeTitleUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(title)}</a>` : escapeHtml(title)) : "Comunicado oficial";
    $("lumo-preview-body").innerHTML = renderMarkdown(content || "Olá, sobreviventes!\n\nA pré-visualização do comunicado aparece aqui.");
    const image = val("lumo-image-url").trim(); const thumb = val("lumo-thumbnail-url").trim();
    const imageAsset = lumoAssets.find((asset) => asset.id === val("lumo-image-asset")); const thumbAsset = lumoAssets.find((asset) => asset.id === val("lumo-thumbnail-asset"));
    const safeImage = imageAsset ? `/api/admin/lumo/assets/${encodeURIComponent(imageAsset.id)}/preview` : safeHttps(image); const safeThumb = thumbAsset ? `/api/admin/lumo/assets/${encodeURIComponent(thumbAsset.id)}/preview` : safeHttps(thumb);
    $("lumo-preview-image").hidden = !safeImage; if (safeImage) $("lumo-preview-image").src = safeImage;
    $("lumo-preview-thumb").hidden = !safeThumb; if (safeThumb) $("lumo-preview-thumb").src = safeThumb;
    const titleLength = title.length; const descriptionLength = content.length;
    const total = titleLength + descriptionLength + "Lumo • Assistente oficial da ARKLAND".length;
    const counter = $("lumo-counter"); counter.textContent = `Título ${titleLength}/256 · Descrição ${descriptionLength}/4.096 · Total ${total}/6.000`;
    counter.classList.toggle("is-invalid", titleLength > 256 || descriptionLength > 4096 || total > 6000 || !content.trim());
    $("lumo-publish").disabled = titleLength > 256 || descriptionLength > 4096 || total > 6000 || !content.trim();
  }
  function setTab(name) {
    document.querySelectorAll(".lumo-tab").forEach((button) => button.classList.toggle("is-active", button.dataset.lumoTab === name));
    document.querySelectorAll(".lumo-panel").forEach((panel) => panel.classList.toggle("is-active", panel.dataset.lumoPanel === name));
    if (name === "templates") renderTemplates();
    if (name === "history") loadHistory(true);
    if (name === "settings") loadIntegration();
    if (name === "assistant") loadIntegration();
  }
  function applyFormat(kind) {
    const editor = $("lumo-content"); const start = editor.selectionStart; const end = editor.selectionEnd; const selected = editor.value.slice(start, end) || "texto";
    const wrappers = { bold:["**","**"], italic:["*","*"], underline:["__","__"], strike:["~~","~~"], spoiler:["||","||"], code:["`","`"], quote:["> ",""], heading:["## ",""], heading1:["# ",""], bullet:["- ",""], number:["1. ",""] };
    const [before, after] = wrappers[kind] || ["",""];
    if (kind === "link") { const href = prompt("URL HTTPS do link:", "https://"); if (!href || !safeHttps(href)) return; replaceEditorRange(editor, `[${selected}](${safeHttps(href)})`, start, end); editor.focus(); markDirty(); return; }
    if (kind === "codeblock") { replaceEditorRange(editor, "```\n" + selected + "\n```", start, end); editor.focus(); markDirty(); return; }
    const replacement = ["quote","heading","heading1","bullet","number"].includes(kind) ? selected.split("\n").map((line) => before + line).join("\n") : before + selected + after;
    replaceEditorRange(editor, replacement, start, end); editor.focus(); markDirty();
  }
  function updateUndoButtons() { $("lumo-undo").disabled = undoStack.length === 0; $("lumo-redo").disabled = redoStack.length === 0; }
  function pushUndo(state) { undoStack.push(state); if (undoStack.length > 100) undoStack.shift(); redoStack.length = 0; updateUndoButtons(); }
  function replaceEditorRange(editor, replacement, start, end) {
    pushUndo({ value: editor.value, start, end });
    editor.setRangeText(replacement, start, end, "select");
    beforeInputState = null;
    editor.dispatchEvent(new Event("input", { bubbles: true }));
  }
  function replaceEditorText(value) {
    const editor = $("lumo-content");
    pushUndo({ value: editor.value, start: editor.selectionStart, end: editor.selectionEnd });
    editor.value = value || "";
    editor.setSelectionRange(editor.value.length, editor.value.length);
    markDirty();
  }
  function restoreEditorState(source, destination) {
    if (!source.length) return;
    const editor = $("lumo-content");
    destination.push({ value: editor.value, start: editor.selectionStart, end: editor.selectionEnd });
    const state = source.pop();
    editor.value = state.value;
    editor.setSelectionRange(Math.min(state.start, editor.value.length), Math.min(state.end, editor.value.length));
    beforeInputState = null;
    updateUndoButtons();
    markDirty();
    editor.focus();
  }
  function markDirty() { dirty = true; updatePreview(); if (!initial) saveDraft(false); }
  function renderTemplates() {
    const root = $("lumo-templates"); root.innerHTML = templates.map((item, index) => `<article class="lumo-template-card"><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.content.slice(0, 110))}${item.content.length > 110 ? "…" : ""}</p><button class="btn btn-ghost btn-sm" type="button" data-template="${index}">Carregar no editor</button></article>`).join("");
    root.querySelectorAll("[data-template]").forEach((button) => button.addEventListener("click", () => { const item = templates[Number(button.dataset.template)]; setVal("lumo-title", item.title); replaceEditorText(item.content); setTab("communication"); }));
  }
  async function loadIntegration() {
    const badge = $("lumo-connection");
    try {
      const data = await fetchJson("/api/admin/lumo/config", { retries: 0 }); integration = data.integration;
      await loadLumoAssets();
      const labels = { not_configured:"Webhook não configurado", unverified:"Configurado · não verificado", verified:"Conexão verificada", failed:"Falha na integração" };
      badge.dataset.state = integration.status; $("lumo-connection-state").textContent = labels[integration.status] || "Status desconhecido";
      $("lumo-connection-detail").textContent = integration.configured ? `${integration.masked_url}${integration.last_checked_at ? ` · verificado ${new Date(integration.last_checked_at).toLocaleString("pt-BR")}` : ""}` : "Configure uma URL de webhook para começar.";
      $("lumo-saved-webhook").textContent = integration.configured ? `Salvo: ${integration.masked_url}` : "Nenhum webhook configurado.";
      $("lumo-channel-info").textContent = integration.channel_id ? `Canal confirmado pelo Discord: ${integration.channel_id}${integration.guild_id ? ` · servidor ${integration.guild_id}` : ""}. O sistema não presume que este seja o canal principal.` : "O canal será identificado quando a URL for verificada.";
      $("lumo-webhook-error").textContent = integration.last_error || "";
      $("lumo-last-published").textContent = integration.last_published_at ? new Date(integration.last_published_at).toLocaleString("pt-BR") : "Nenhuma publicação registrada.";
      if (data.assistant) {
        assistantConfig = data.assistant;
        const state = assistantConfig.runtime?.state || "stopped";
        const stateEl = $("lumo-assistant-state");
        if (stateEl) { stateEl.dataset.state = state; stateEl.textContent = ({online:"Conectado",starting:"Conectando",reconnecting:"Reconectando",error:"Falha",stopped:"Desconectado"})[state] || state; }
        setVal("lumo-guild-id", assistantConfig.guild_id); setVal("lumo-interaction-channel-id", assistantConfig.interaction_channel_id); setVal("lumo-status-channel-id", assistantConfig.status_channel_id);
        setVal("lumo-game-channel-id", assistantConfig.game_chat_channel_id || ""); setVal("lumo-bot-user-id", assistantConfig.bot_user_id || "");
        $("lumo-game-enabled").checked = !!assistantConfig.game_chat_enabled; $("lumo-game-webhooks").checked = !!assistantConfig.game_chat_webhooks_enabled;
        $("lumo-game-keywords").checked = !!assistantConfig.game_chat_keywords_enabled; $("lumo-game-announcements").checked = !!assistantConfig.game_chat_announcements_enabled;
        document.querySelectorAll("[data-lumo-game-topic]").forEach((input) => { input.checked = assistantConfig.game_chat_topic_enabled?.[input.dataset.lumoGameTopic] !== false; });
        $("lumo-game-general-auto").checked = !!assistantConfig.game_general_announcements_enabled; $("lumo-game-betland-auto").checked = !!assistantConfig.game_auto_betland_enabled; $("lumo-game-polls-auto").checked = !!assistantConfig.game_auto_polls_enabled;
        setVal("lumo-game-greeting-cooldown", assistantConfig.game_chat_greeting_cooldown_seconds ?? 600); setVal("lumo-game-topic-cooldown", assistantConfig.game_chat_topic_cooldown_seconds ?? 120); setVal("lumo-game-user-cooldown", assistantConfig.game_chat_user_topic_cooldown_seconds ?? 300); setVal("lumo-game-global-cooldown", assistantConfig.game_chat_global_cooldown_seconds ?? 5); setVal("lumo-game-max-chars", assistantConfig.game_chat_max_chars ?? 250);
        setVal("lumo-game-aliases", JSON.stringify(assistantConfig.game_chat_trigger_aliases || {}, null, 2));
        setVal("lumo-user-cooldown", assistantConfig.user_cooldown_seconds ?? 15); setVal("lumo-trigger-cooldown", assistantConfig.trigger_cooldown_seconds ?? 20); setVal("lumo-global-cooldown", assistantConfig.global_cooldown_seconds ?? 3); setVal("lumo-global-hourly-limit", assistantConfig.global_hourly_limit ?? 40);
        $("lumo-assistant-enabled").checked = !!assistantConfig.enabled; $("lumo-trigger-status").checked = assistantConfig.trigger_enabled?.STATUS !== false; $("lumo-trigger-betland").checked = assistantConfig.trigger_enabled?.BETLAND !== false; $("lumo-trigger-licenses").checked = assistantConfig.trigger_enabled?.LICENCAS !== false; $("lumo-trigger-polls").checked = assistantConfig.trigger_enabled?.VOTACAO !== false;
        $("lumo-auto-betland").checked = !!assistantConfig.auto_betland_enabled; $("lumo-auto-polls").checked = !!assistantConfig.auto_polls_enabled;
        $("lumo-auto-community").checked = assistantConfig.auto_community_enabled !== false;
        setVal("lumo-trigger-aliases", JSON.stringify(assistantConfig.trigger_aliases || {}, null, 2));
        const runtime = assistantConfig.runtime || {};
        const schedule = [];
        schedule.push("Canal principal: intervalo mínimo de 6 h entre anúncios automáticos (até 4 por dia). Aguarda conversa quando a última mensagem é do Lumo ou de outro bot. Respostas diretas não são afetadas.");
        const mainGate = runtime.main_announcement_gate;
        const mainStates = { cooldown: "intervalo de 6 h em andamento", waiting_for_conversation: "aguardando mensagem de uma pessoa", unavailable: "histórico indisponível; envio adiado", ready: "conversa confirmada", not_checked: "histórico ainda não consultado" };
        if (mainGate) schedule.push(`Situação: ${mainStates[mainGate.state] || mainGate.state}${mainGate.checked_at ? ` · ${new Date(mainGate.checked_at).toLocaleString("pt-BR")}` : ""}.`);
        if (assistantConfig.last_auto_announcement_at) schedule.push(`Intervalo global: próximo anúncio permitido a partir de ${new Date(new Date(assistantConfig.last_auto_announcement_at).getTime() + 6 * 3600000).toLocaleString("pt-BR")}, sujeito à conversa no canal.`);
        if (assistantConfig.auto_betland_enabled) schedule.push(`Bet Land: última ${assistantConfig.auto_betland_last_at ? new Date(assistantConfig.auto_betland_last_at).toLocaleString("pt-BR") : "nenhuma"}; próxima ${assistantConfig.auto_betland_next_at ? new Date(assistantConfig.auto_betland_next_at).toLocaleString("pt-BR") : "a agendar"} (${assistantConfig.auto_betland_last_result || "sem tentativas"})`);
        if (assistantConfig.auto_polls_enabled) schedule.push(`Votações: última ${assistantConfig.auto_polls_last_at ? new Date(assistantConfig.auto_polls_last_at).toLocaleString("pt-BR") : "nenhuma"}; próxima ${assistantConfig.auto_polls_next_at ? new Date(assistantConfig.auto_polls_next_at).toLocaleString("pt-BR") : "a agendar"} (${assistantConfig.auto_polls_last_result || "sem tentativas"})`);
        schedule.push(`Respostas: ${runtime.responses || 0}; anúncios: ${runtime.announcements || 0}; última interação: ${runtime.last_interaction_at ? new Date(runtime.last_interaction_at).toLocaleString("pt-BR") : "nenhuma"}.`);
        if (runtime.last_error) schedule.push(`Falha recente: ${runtime.last_error}`);
        $("lumo-auto-schedule-state").textContent = schedule.join("\n");
        const noticeList = $("lumo-community-notices");
        noticeList.replaceChildren();
        for (const notice of assistantConfig.community_announcements || []) {
          const item = document.createElement("details"), title = document.createElement("summary"), body = document.createElement("p");
          title.textContent = notice.title;
          body.textContent = notice.description;
          body.style.whiteSpace = "pre-wrap";
          body.className = "lumo-muted";
          item.append(title, body); noticeList.append(item);
        }
        const gameSchedule = [];
        if (assistantConfig.game_announcements_not_before) gameSchedule.push(`Intervalo entre avisos enviados: ${(assistantConfig.game_announcement_gap_minutes || [15,20]).join("–")} min; próxima tentativa permitida a partir de ${new Date(assistantConfig.game_announcements_not_before).toLocaleString("pt-BR")}.`);
        const audience = runtime.game_announcement_audience;
        if (audience) {
          const audienceText = audience.state === "present" ? `jogadores confirmados (ao menos ${audience.confirmed_players})` : audience.state === "empty" ? "sem jogadores; aviso pendente" : audience.state === "unavailable" ? "presença não confirmada; aviso pendente" : "presença ainda não consultada";
          gameSchedule.push(`Última verificação do público: ${audienceText}${audience.checked_at ? ` · ${new Date(audience.checked_at).toLocaleString("pt-BR")}` : ""}. Sem público confirmado, nova consulta em 60 s.`);
        }
        if (assistantConfig.game_general_announcements_enabled) gameSchedule.push(`Geral: próxima ${assistantConfig.game_general_next_at ? new Date(assistantConfig.game_general_next_at).toLocaleString("pt-BR") : "a agendar"}`);
        if (assistantConfig.game_auto_betland_enabled) gameSchedule.push(`BetLand: próxima ${assistantConfig.game_auto_betland_next_at ? new Date(assistantConfig.game_auto_betland_next_at).toLocaleString("pt-BR") : "a agendar"}`);
        if (assistantConfig.game_auto_polls_enabled) gameSchedule.push(`Votações: próxima ${assistantConfig.game_auto_polls_next_at ? new Date(assistantConfig.game_auto_polls_next_at).toLocaleString("pt-BR") : "a agendar"}`);
        $("lumo-game-schedule-state").textContent = gameSchedule.join("\n") || "Agendamentos desligados.";
        try {
          const greetings = await fetchJson("/api/admin/lumo/assistant/config", { retries: 0 });
          setVal("lumo-greeting-replies", (greetings.greeting_replies || []).join("\n"));
        } catch (_) {}
      }
    } catch (error) { badge.dataset.state = "failed"; $("lumo-connection-state").textContent = "Falha ao consultar o serviço"; $("lumo-connection-detail").textContent = error.message || "Tente novamente."; }
  }
  async function loadLumoAssets() {
    try {
      const data = await fetchJson("/api/admin/lumo/assets", { retries:0 }); lumoAssets = data.assets || [];
      for (const [selectId, key] of [["lumo-image-asset", "image_asset_id"], ["lumo-thumbnail-asset", "thumbnail_asset_id"]]) {
        const select = $(selectId); if (!select) continue;
        const previous = val(selectId) || pendingAssetDraft[key];
        select.innerHTML = `<option value="">Sem upload selecionado</option>` + lumoAssets.map((asset) => `<option value="${escapeHtml(asset.id)}">${escapeHtml(asset.original_name)} · ${Math.ceil(asset.size/1024)} KB</option>`).join("");
        if (lumoAssets.some((asset) => asset.id === previous)) select.value = previous;
      }
      pendingAssetDraft = {};
      setVal("lumo-asset-retention", data.retention_days || 30);
      $("lumo-assets-state").textContent = `${lumoAssets.length} imagem(ns) armazenada(s) · retenção ${data.retention_days || 30} dias após a última utilização.`;
      updatePreview();
    } catch (error) { $("lumo-assets-state").textContent = error.message || "Não foi possível carregar as imagens."; }
  }
  async function uploadLumoImage(kind) {
    const fileInput = $(kind === "image" ? "lumo-image-file" : "lumo-thumbnail-file");
    const file = fileInput.files?.[0]; if (!file) { toast("Selecione uma imagem antes de enviar.", "error"); return; }
    const form = new FormData(); form.append("file", file);
    try {
      const response = await fetch("/api/admin/lumo/assets", { method:"POST", body:form, credentials:"same-origin", headers: { "X-Requested-With":"XMLHttpRequest" } });
      const data = await response.json(); if (!response.ok || !data.ok) throw new Error(data.error || "Falha no upload.");
      await loadLumoAssets(); setVal(kind === "image" ? "lumo-image-asset" : "lumo-thumbnail-asset", data.asset.id);
      setVal(kind === "image" ? "lumo-image-url" : "lumo-thumbnail-url", ""); fileInput.value = ""; markDirty(); toast("Imagem armazenada com segurança.", "success");
    } catch (error) { toast(error.message || "Falha no upload.", "error"); }
  }
  async function saveAssetRetention() {
    try { const data = await fetchJson("/api/admin/lumo/assets/retention", { method:"POST", body:{ days:Number(val("lumo-asset-retention")) }, retries:0 }); toast(`Retenção definida para ${data.retention_days} dias.`, "success"); await loadLumoAssets(); }
    catch (error) { toast(error.message || "Não foi possível salvar a retenção.", "error"); }
  }
  async function deleteLumoImage(kind) {
    const select = $(kind === "image" ? "lumo-image-asset" : "lumo-thumbnail-asset"); const id = select.value;
    if (!id) { toast("Selecione um arquivo enviado para excluí-lo.", "error"); return; }
    if (!confirm("Excluir este arquivo armazenado? Comunicados já publicados continuarão com o anexo no Discord.")) return;
    try { await fetchJson(`/api/admin/lumo/assets/${encodeURIComponent(id)}`, { method:"DELETE", body:{}, retries:0 }); select.value = ""; markDirty(); await loadLumoAssets(); toast("Arquivo local removido.", "success"); }
    catch (error) { toast(error.message || "Não foi possível excluir o arquivo.", "error"); }
  }
  async function previewGameChat() {
    const target = $("lumo-game-test-result"); target.textContent = "Consultando fonte real sem enviar mensagem…";
    try {
      const data = await fetchJson("/api/admin/lumo/assistant/game-preview", { method:"POST", body:{ text:val("lumo-game-test-input").trim() }, retries:0 });
      target.textContent = data.recognized ? (data.message ? `${data.trigger}: ${data.message}` : `${data.trigger}: ${data.reason}`) : (data.reason || "Nenhum gatilho reconhecido.");
    } catch (error) { target.textContent = error.message || "A simulação falhou."; }
  }
  async function sendGameManual() {
    const text = val("lumo-game-manual-text").trim(); if (!text) { toast("Escreva a mensagem antes de enviar.", "error"); return; }
    if (!confirm("Enviar esta mensagem simples uma vez ao canal da ponte? Todos os mapas ligados ao canal podem recebê-la. O plugin acrescentará o prefixo do chat.")) return;
    try { const data = await fetchJson("/api/admin/lumo/game-chat/send", { method:"POST", body:{ text }, retries:0, timeoutMs:15000 }); toast(data.message || "Mensagem enviada.", "success"); setVal("lumo-game-manual-text", ""); }
    catch (error) { toast(error.message || "Não foi possível enviar ao Chat do Jogo.", "error"); }
  }
  async function saveAssistant() {
    let aliases;
    try { aliases = JSON.parse(val("lumo-trigger-aliases") || "{}"); }
    catch { toast("Aliases inválidos: corrija o JSON antes de salvar.", "error"); return; }
    const body = {
      enabled: $("lumo-assistant-enabled").checked,
      bot_token: val("lumo-bot-token").trim(),
      clear_bot_token: $("lumo-clear-bot-token").checked,
      guild_id: val("lumo-guild-id").trim(), interaction_channel_id: val("lumo-interaction-channel-id").trim(), status_channel_id: val("lumo-status-channel-id").trim(),
      user_cooldown_seconds: Number(val("lumo-user-cooldown")), trigger_cooldown_seconds: Number(val("lumo-trigger-cooldown")), global_cooldown_seconds: Number(val("lumo-global-cooldown")), global_hourly_limit: Number(val("lumo-global-hourly-limit")),
      auto_betland_enabled: $("lumo-auto-betland").checked, auto_polls_enabled: $("lumo-auto-polls").checked,
      auto_community_enabled: $("lumo-auto-community").checked,
      trigger_enabled: { STATUS: $("lumo-trigger-status").checked, BETLAND: $("lumo-trigger-betland").checked, LICENCAS: $("lumo-trigger-licenses").checked, VOTACAO: $("lumo-trigger-polls").checked },
      trigger_aliases: aliases,
    };
    try {
      const result = await fetchJson("/api/admin/lumo/assistant/config", { method:"POST", body, retries:0 });
      setVal("lumo-bot-token", ""); $("lumo-clear-bot-token").checked = false;
      const replies = val("lumo-greeting-replies").split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
      await fetchJson("/api/admin/lumo/assistant/greetings", { method:"PUT", body:{ replies }, retries:0 });
      toast(result.message || "Configuração do Lumo salva.", result.ok ? "success" : "warning");
      await loadIntegration();
    } catch (error) { toast(error.message || "Não foi possível salvar a configuração do Lumo.", "error"); }
  }
  async function saveGameChat() {
    let aliases;
    try { aliases = JSON.parse(val("lumo-game-aliases") || "{}"); }
    catch { toast("JSON de gatilhos inválido.", "error"); return; }
    const body = {
      enabled: $("lumo-assistant-enabled").checked,
      guild_id: val("lumo-guild-id").trim(), interaction_channel_id: val("lumo-interaction-channel-id").trim(), status_channel_id: val("lumo-status-channel-id").trim(),
      game_chat_channel_id: val("lumo-game-channel-id").trim(), bot_user_id: val("lumo-bot-user-id").trim(), game_chat_enabled: $("lumo-game-enabled").checked,
      game_chat_webhooks_enabled: $("lumo-game-webhooks").checked, game_chat_keywords_enabled: $("lumo-game-keywords").checked,
      game_chat_announcements_enabled: $("lumo-game-announcements").checked, game_general_announcements_enabled: $("lumo-game-general-auto").checked,
      game_chat_topic_enabled: Object.fromEntries([...document.querySelectorAll("[data-lumo-game-topic]")].map((input) => [input.dataset.lumoGameTopic, input.checked])),
      game_auto_betland_enabled: $("lumo-game-betland-auto").checked, game_auto_polls_enabled: $("lumo-game-polls-auto").checked,
      game_chat_greeting_cooldown_seconds: Number(val("lumo-game-greeting-cooldown")), game_chat_topic_cooldown_seconds: Number(val("lumo-game-topic-cooldown")),
      game_chat_user_topic_cooldown_seconds: Number(val("lumo-game-user-cooldown")), game_chat_max_chars: Number(val("lumo-game-max-chars")), game_chat_trigger_aliases: aliases,
      game_chat_global_cooldown_seconds: Number(val("lumo-game-global-cooldown")),
    };
    try { const result = await fetchJson("/api/admin/lumo/assistant/config", { method:"POST", body, retries:0 }); toast(result.message || "Configuração do Chat do Jogo salva.", result.ok ? "success" : "warning"); await loadIntegration(); }
    catch (error) { toast(error.message || "Não foi possível salvar o Chat do Jogo.", "error"); }
  }
  async function runAssistantTest() {
    const text = val("lumo-test-input").trim();
    $("lumo-test-result").textContent = "Consultando fontes internas…";
    $("lumo-test-title").textContent = "Consultando…"; $("lumo-test-body").textContent = "";
    try {
      const result = await fetchJson("/api/admin/lumo/assistant/preview", { method:"POST", body:{ text }, retries:0, timeoutMs:20000 });
      if (!result.recognized) { $("lumo-test-result").textContent = result.reason || "Nenhum gatilho reconhecido."; $("lumo-test-title").textContent = "Sem resposta"; return; }
      if (!result.embed) { $("lumo-test-result").textContent = `${result.trigger} · regra ${result.rule} · fonte ${result.source} · ${result.reason}`; $("lumo-test-title").textContent = "Dados indisponíveis"; return; }
      $("lumo-test-result").textContent = `Gatilho: ${result.trigger} · Regra: ${result.rule} · Fonte consultada: ${result.source}. Simulação local; nada foi enviado.`;
      $("lumo-test-title").textContent = result.embed.title || "Lumo"; $("lumo-test-body").innerHTML = renderMarkdown(result.embed.description || "");
    } catch (error) { $("lumo-test-result").textContent = error.message || "O teste falhou."; $("lumo-test-title").textContent = "Falha na consulta"; }
  }
  async function saveWebhook() {
    const webhook = val("lumo-webhook-url").trim();
    if (!webhook && !confirm("Remover a integração do Discord de Lumo?")) return;
    try { await fetchJson("/api/admin/lumo/config", { method:"POST", body:{ webhook_url:webhook }, retries:0 }); setVal("lumo-webhook-url", ""); toast(webhook ? "Webhook salvo com segurança. Verifique a conexão antes de publicar." : "Webhook removido.", "success"); await loadIntegration(); }
    catch (error) { toast(error.message || "Não foi possível salvar o webhook.", "error"); }
  }
  async function verifyWebhook() {
    try { const data = await fetchJson("/api/admin/lumo/verify", { method:"POST", body:{}, retries:0 }); toast(data.message, data.ok ? "success" : "error"); await loadIntegration(); }
    catch (error) { toast(error.message || "A verificação falhou.", "error"); await loadIntegration(); }
  }
  async function publish() {
    if (!integration?.configured || integration.status !== "verified") { toast("Configure e verifique o webhook antes de publicar.", "error"); setTab("settings"); return; }
    const destination = integration.channel_id ? `Canal Discord ${integration.channel_id}` : "o canal associado ao webhook";
    const incomplete = val("lumo-content").match(/\[(?:informar|nome|servidor|data|hor[áa]rio|previs[ãa]o|descrever|instru[çc][õo]es|etapa|novidade|quando|onde|como participar|in[ií]cio|[a-z ]+ afetado)\b[^\]]*\]/i);
    const warning = incomplete ? "\n\nA mensagem ainda contém campos de modelo que parecem não preenchidos. Revise o conteúdo antes de publicar." : "";
    if (!confirm(`Enviar este comunicado como embed do Lumo para ${destination}?\n\nA publicação será real no Discord.${warning}`)) return;
    try {
      const response = await fetchJson("/api/admin/lumo/publish", { method:"POST", timeoutMs:18000, retries:0, body:{ ...draftData(), request_id:requestId } });
      toast(response.message || "Mensagem publicada.", "success"); requestId = newRequestId(); await loadIntegration();
    } catch (error) { if (error?.data?.result === "rate_limited" || error?.data?.result === "rejected") requestId = newRequestId(); toast(error.message || "Falha ao publicar. Seu texto foi preservado; confira o histórico antes de repetir.", "error"); await loadIntegration(); }
  }
  async function loadHistory(reset = false) {
    if (reset) historyOffset = 0;
    const params = new URLSearchParams({ limit:"20", offset:String(historyOffset) });
    const q = val("lumo-history-query").trim(); const status = val("lumo-history-status"); const admin = val("lumo-history-admin").trim(); const from = val("lumo-history-from"); const to = val("lumo-history-to");
    if (q) params.set("q",q); if (status) params.set("status",status); if (admin) params.set("admin",admin); if (from) params.set("from",from); if (to) params.set("to",to);
    try {
      const data = await fetchJson(`/api/admin/lumo/history?${params}`, { retries:0 }); historyMore = data.has_more;
      if (reset) $("lumo-history-list").innerHTML = "";
      const root = $("lumo-history-list");
      root.innerHTML = (reset ? "" : root.innerHTML) + (data.items.length ? data.items.map((item) => {
        const statusLabel = { success:"Publicado", rejected:"Recusado pelo Discord", rate_limited:"Limite temporário", uncertain:"Resultado incerto" }[item.status] || item.status;
        const typeLabel = { lumo_publish:"Comunicado administrativo", lumo_interaction:"Resposta interativa", lumo_automatic_announcement:"Anúncio automático" }[item.type] || "Evento Lumo";
        const jump = item.guild_id && item.channel_id && item.message_id ? `<a target="_blank" rel="noopener noreferrer" href="https://discord.com/channels/${encodeURIComponent(item.guild_id)}/${encodeURIComponent(item.channel_id)}/${encodeURIComponent(item.message_id)}">Abrir no Discord</a>` : "";
        const actor = item.player_id ? `Jogador Discord ${item.player_id}` : `Admin Steam ${item.admin_steam_id || "não identificado"}`;
        const detail = item.content || (item.trigger ? `Gatilho: ${item.trigger}` : item.error || "Evento registrado sem conteúdo de conversa.");
        const actions = item.type === "lumo_publish" && item.content ? `<button class="btn btn-ghost btn-sm" data-reuse="${item.id}">Reutilizar no editor</button><button class="btn btn-ghost btn-sm" data-copy="${item.id}">Copiar conteúdo</button>` : "";
        return `<article class="lumo-history-item"><div class="lumo-history-item__head"><strong>${escapeHtml(item.title || typeLabel)}</strong><span class="lumo-pill">${escapeHtml(statusLabel)}</span></div><div class="lumo-muted">${escapeHtml(item.created_at ? new Date(item.created_at).toLocaleString("pt-BR") : "")} · ${escapeHtml(actor)}</div><p class="lumo-history-item__content">${escapeHtml(detail)}</p><div class="lumo-actions">${actions}${jump}</div></article>`;
      }).join("") : `<p class="lumo-muted">${reset ? "Nenhuma tentativa de publicação encontrada." : "Fim do histórico."}</p>`);
      root.querySelectorAll("[data-reuse]").forEach((button) => button.addEventListener("click", () => { const item = data.items.find((x) => String(x.id) === button.dataset.reuse); if (!item) return; setVal("lumo-title",item.title); replaceEditorText(item.content); setTab("communication"); }));
      root.querySelectorAll("[data-copy]").forEach((button) => button.addEventListener("click", async () => { const item = data.items.find((x) => String(x.id) === button.dataset.copy); if (item) { await navigator.clipboard.writeText(item.content || ""); toast("Conteúdo copiado.","success"); } }));
      $("lumo-history-more").hidden = !historyMore;
    } catch (error) { $("lumo-history-list").innerHTML = `<p role="alert">${escapeHtml(error.message || "Não foi possível carregar o histórico.")}</p>`; }
  }
  function bind() {
    document.querySelectorAll("[data-lumo-tab]").forEach((button) => button.addEventListener("click", () => setTab(button.dataset.lumoTab)));
    ["lumo-title","lumo-title-url","lumo-image-url","lumo-thumbnail-url"].forEach((id) => $(id).addEventListener("input", () => { if (id === "lumo-image-url") setVal("lumo-image-asset", ""); if (id === "lumo-thumbnail-url") setVal("lumo-thumbnail-asset", ""); markDirty(); }));
    $("lumo-image-asset")?.addEventListener("change", () => { if (val("lumo-image-asset")) setVal("lumo-image-url", ""); markDirty(); });
    $("lumo-thumbnail-asset")?.addEventListener("change", () => { if (val("lumo-thumbnail-asset")) setVal("lumo-thumbnail-url", ""); markDirty(); });
    $("lumo-upload-image")?.addEventListener("click", () => uploadLumoImage("image")); $("lumo-upload-thumbnail")?.addEventListener("click", () => uploadLumoImage("thumbnail"));
    $("lumo-save-retention")?.addEventListener("click", saveAssetRetention);
    $("lumo-delete-image")?.addEventListener("click", () => deleteLumoImage("image")); $("lumo-delete-thumbnail")?.addEventListener("click", () => deleteLumoImage("thumbnail"));
    const editor = $("lumo-content");
    editor.addEventListener("beforeinput", () => { beforeInputState = { value: editor.value, start: editor.selectionStart, end: editor.selectionEnd }; });
    editor.addEventListener("input", () => { if (beforeInputState && beforeInputState.value !== editor.value) pushUndo(beforeInputState); beforeInputState = null; markDirty(); });
    $("lumo-undo").addEventListener("click", () => restoreEditorState(undoStack, redoStack));
    $("lumo-redo").addEventListener("click", () => restoreEditorState(redoStack, undoStack));
    document.querySelectorAll("[data-lumo-format]").forEach((button) => button.addEventListener("click", () => applyFormat(button.dataset.lumoFormat)));
    $("lumo-insert-emoji").addEventListener("click", () => { const editor = $("lumo-content"); const start = editor.selectionStart; const end = editor.selectionEnd; replaceEditorRange(editor, "😀", start, end); editor.focus(); markDirty(); });
    $("lumo-publish").addEventListener("click", publish); $("lumo-clear").addEventListener("click", () => { if (confirm("Limpar o conteúdo atual do editor?")) { ["lumo-title","lumo-title-url","lumo-image-url","lumo-thumbnail-url","lumo-image-asset","lumo-thumbnail-asset"].forEach((id) => setVal(id,"")); replaceEditorText(""); } });
    $("lumo-save-draft").addEventListener("click", () => saveDraft(true)); $("lumo-copy-markdown").addEventListener("click", async () => { await navigator.clipboard.writeText(val("lumo-content")); toast("Markdown copiado.","success"); });
    $("lumo-save-webhook").addEventListener("click", saveWebhook); $("lumo-verify-webhook").addEventListener("click", verifyWebhook); $("lumo-reload-history").addEventListener("click", () => loadHistory(true));
    $("lumo-save-assistant")?.addEventListener("click", saveAssistant); $("lumo-reload-assistant")?.addEventListener("click", loadIntegration); $("lumo-run-test")?.addEventListener("click", runAssistantTest);
    $("lumo-game-save")?.addEventListener("click", saveGameChat);
    $("lumo-game-test")?.addEventListener("click", previewGameChat); $("lumo-game-manual-send")?.addEventListener("click", sendGameManual);
    $("lumo-history-more").addEventListener("click", () => { historyOffset += 20; loadHistory(false); });
    $("lumo-history-query").addEventListener("keydown", (event) => { if (event.key === "Enter") loadHistory(true); });
    $("lumo-content").addEventListener("keydown", (event) => { if (!event.ctrlKey) return; const key = event.key.toLowerCase(); if ((key === "z" && !event.shiftKey && undoStack.length) || (key === "y" && redoStack.length) || (key === "z" && event.shiftKey && redoStack.length)) { event.preventDefault(); restoreEditorState(key === "z" && !event.shiftKey ? undoStack : redoStack, key === "z" && !event.shiftKey ? redoStack : undoStack); return; } const map = { b:"bold", i:"italic", u:"underline", "shift+x":"strike", "shift+s":"spoiler" }; const format = map[`${event.shiftKey ? "shift+" : ""}${key}`] || map[key]; if (format) { event.preventDefault(); applyFormat(format); } });
    window.addEventListener("beforeunload", (event) => { if (dirty) { saveDraft(false); event.preventDefault(); event.returnValue = ""; } });
    restoreDraft(); updateUndoButtons(); updatePreview(); initial = false;
  }
  window.loadLumoAdmin = function () {
    if (!$("page-lumo")?.dataset.initialized) { bind(); $("page-lumo").dataset.initialized = "1"; }
    loadIntegration();
  };
})();
