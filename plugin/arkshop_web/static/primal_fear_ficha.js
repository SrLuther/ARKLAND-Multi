/* Ficha Primal Fear (documento) e busca/cadastro de blueprints. Admin. */
var _pfFichaData = null;
var _bpIndex = { offset: 0, limit: 40, total: 0, hasMore: false };
var _bpIndexTimer = null;
var _BP_INDEX_KIND = {
  item: "Item",
  dino: "Dino",
  sela: "Sela",
  recurso: "Recurso",
  engrama: "Engrama",
  estrutura: "Estrutura",
  comando: "Comando",
  outro: "Outro"
};
var _BP_INDEX_SOURCE = {
  catalog_items: "Catálogo — itens",
  catalog_kits: "Catálogo — kits",
  catalog_comandos: "Catálogo — comandos",
  catalog_vitrine: "Catálogo — vitrine",
  catalog: "Catálogo",
  market_species_defaults: "Padrões de espécies",
  ark_species_registry: "Registro de espécies",
  mod_catalog_verified: "Mods verificados",
  official_vanilla: "Vanilla oficial",
  market_species: "Banco — espécies",
  market_aliases: "Banco — aliases",
  itensalfa_blueprints: "ItensAlfa — blueprints",
  itensalfa_creatures: "ItensAlfa — criaturas",
  blueprint_matrix: "Matriz de blueprints",
  asm_known_engrams: "ASM — engramas conhecidos",
  asm_engram_entries: "ASM — código de engramas",
  beacon_cache: "Cache Beacon local",
  spawnexact_cache: "Cache SpawnExact",
  servers_json: "servers.json",
  asm_servers: "asm_servers.json",
  manual: "Cadastro manual"
};

function _pfEsc(value) {
  if (typeof escHtml === "function") return escHtml(value);
  return String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function _pfFilterFicha() {
  var q = (document.getElementById("pf-ficha-q") || {}).value || "";
  q = String(q).trim().toLowerCase();
  document.querySelectorAll("#pf-ficha-root [data-pf-hit]").forEach(function (el) {
    var hay = (el.getAttribute("data-pf-hit") || "").toLowerCase();
    el.classList.toggle("kb-hidden", !!q && hay.indexOf(q) === -1);
  });
}

function _pfRenderFicha(data) {
  var root = document.getElementById("pf-ficha-root");
  if (!root) return;
  var toc = (data.sheets || []).map(function (sheet) {
    return '<a href="#pf-sheet-' + _pfEsc(sheet.id) + '">' + _pfEsc(sheet.title) + "</a>";
  }).join("");
  var body = (data.sheets || []).map(function (sheet) {
    var inner = "";
    if (sheet.kind === "dinos") {
      inner = (sheet.groups || []).map(function (group) {
        var cards = (group.dinos || []).map(function (dino) {
          var hit = [group.title, dino.name].concat((dino.fields || []).map(function (field) {
            return field.label + " " + field.value;
          })).join(" ");
          var fields = (dino.fields || []).map(function (field) {
            var code = /spawn|blueprint|cheat|entity|entidade|tag/i.test(field.label);
            return '<div class="kb-field"><span class="kb-field-k">' + _pfEsc(field.label) +
              '</span><span class="kb-field-v' + (code ? " kb-code" : "") + '">' +
              _pfEsc(field.value) + "</span></div>";
          }).join("");
          return '<article class="kb-dino" data-pf-hit="' + _pfEsc(hit) + '"><h3 class="kb-h4">' +
            _pfEsc(dino.name) + "</h3>" + fields + "</article>";
        }).join("");
        return '<section class="kb-sec"><h3 class="kb-h3">' + _pfEsc(group.title) + "</h3>" + cards + "</section>";
      }).join("");
    } else {
      inner = (sheet.blocks || []).map(function (block) {
        if (block.type === "h2") return '<h3 class="kb-h3">' + _pfEsc(block.text) + "</h3>";
        if (block.type === "p") {
          return '<p class="kb-p" data-pf-hit="' + _pfEsc(block.text) + '">' +
            _pfEsc(block.text).replace(/\n/g, "<br>") + "</p>";
        }
        var rows = block.rows || [];
        if (!rows.length) return "";
        var head = rows[0];
        var useHead = head.every(function (cell) {
          return cell.length < 48 && !/cheat|blueprint'|admincheat/i.test(cell);
        });
        var bodyRows = useHead ? rows.slice(1) : rows;
        var html = '<div class="kb-table-wrap"><table class="kb-table">';
        if (useHead) {
          html += "<thead><tr>" + head.map(function (cell) {
            return "<th>" + _pfEsc(cell) + "</th>";
          }).join("") + "</tr></thead>";
        }
        html += "<tbody>" + bodyRows.map(function (row) {
          var hit = row.join(" ");
          return '<tr data-pf-hit="' + _pfEsc(hit) + '">' + row.map(function (cell) {
            var code = /blueprint'|cheat |admincheat/i.test(cell);
            return '<td class="' + (code ? "kb-code" : "") + '">' + _pfEsc(cell) + "</td>";
          }).join("") + "</tr>";
        }).join("") + "</tbody></table></div>";
        return html;
      }).join("");
    }
    return '<section class="kb-sec" id="pf-sheet-' + _pfEsc(sheet.id) + '">' +
      '<p class="kb-kicker">' + _pfEsc(sheet.sheet) + "</p>" +
      '<h2 class="kb-h2">' + _pfEsc(sheet.title) + "</h2>" + inner + "</section>";
  }).join("");
  root.innerHTML = '<nav class="kb-toc" aria-label="Ficha Primal Fear">' + toc + "</nav>" + body;
  var links = root.querySelectorAll(".kb-toc a");
  var hash = (location.hash || "");
  var current = null;
  links.forEach(function (link) {
    if (link.getAttribute("href") === hash) current = link;
    link.addEventListener("click", function () { _pfSetActiveTab(link); });
  });
  _pfSetActiveTab(current || links[0]);
  _pfFilterFicha();
}

function _pfSetActiveTab(link) {
  var nav = document.querySelector("#pf-ficha-root .kb-toc");
  if (!nav) return;
  nav.querySelectorAll("a").forEach(function (a) {
    var on = a === link;
    a.classList.toggle("is-active", on);
    if (on) a.setAttribute("aria-current", "location");
    else a.removeAttribute("aria-current");
  });
}

async function openPrimalFearFicha() {
  var root = document.getElementById("pf-ficha-root");
  if (!root) return;
  if (_pfFichaData) {
    _pfRenderFicha(_pfFichaData);
    return;
  }
  root.textContent = "Carregando a ficha…";
  try {
    var response = await fetch("primal_fear_ficha.json?v=" + (document.querySelector('meta[name="arkland-web-build"]') || {}).content, { credentials: "same-origin" });
    if (!response.ok) throw new Error("Não foi possível abrir a ficha.");
    _pfFichaData = await response.json();
    _pfRenderFicha(_pfFichaData);
  } catch (err) {
    root.textContent = err.message || "Não foi possível abrir a ficha.";
  }
}

function goBlueprintIndex() {
  var el = document.querySelector('.nav-item[data-page="blueprint-index"]');
  if (el && typeof nav === "function") nav(el);
}

function goPrimalFearFicha() {
  var el = document.querySelector('.nav-item[data-page="primal-fear-ficha"]');
  if (el && typeof nav === "function") nav(el);
}

function scheduleBlueprintIndexQuery(immediate) {
  _bpIndex.offset = 0;
  clearTimeout(_bpIndexTimer);
  if (immediate) {
    queryBlueprintIndex();
    return;
  }
  _bpIndexTimer = setTimeout(queryBlueprintIndex, 250);
}

function prevBlueprintIndexPage() {
  if (typeof stepTablePage === "function" && stepTablePage(_bpIndex, -1)) queryBlueprintIndex();
}
function nextBlueprintIndexPage() {
  if (typeof stepTablePage === "function" && stepTablePage(_bpIndex, 1)) queryBlueprintIndex();
}

function blueprintClassFrom(raw) {
  var text = String(raw || "").trim();
  if (text.length >= 2 && (text.charAt(0) === '"' || text.charAt(0) === "'") && text.charAt(text.length - 1) === text.charAt(0)) {
    text = text.slice(1, -1).trim();
  }
  var wrapped = text.match(/Blueprint'([^']+)'/i);
  if (wrapped) text = wrapped[1].trim();
  text = text.replace(/^["']|["']$/g, "");
  if (/^(?:EngramEntry_|PrimalItem_)[A-Za-z0-9_]+_C$/.test(text)) return text;
  var segment = (text.split("/").pop() || "").replace(/^["']|["']$/g, "");
  if (/^(?:EngramEntry_|PrimalItem_)[A-Za-z0-9_]+_C$/.test(segment)) return segment;
  if (segment.indexOf(".") >= 0) segment = segment.split(".").pop() || "";
  return segment;
}

function fillBlueprintClass() {
  var box = document.getElementById("bidx-class");
  var raw = (document.getElementById("bidx-id") || {}).value || "";
  if (box) box.value = blueprintClassFrom(raw);
}

function cancelBlueprintIndexEdit() {
  var norm = document.getElementById("bidx-edit-norm");
  var title = document.getElementById("bidx-form-title");
  var save = document.getElementById("bidx-save");
  var cancel = document.getElementById("bidx-cancel");
  ["bidx-name", "bidx-mod", "bidx-id", "bidx-class", "bidx-note"].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.value = "";
  });
  var kind = document.getElementById("bidx-new-kind");
  if (kind) {
    kind.value = "";
    if (kind._kbMenuSync) kind._kbMenuSync();
  }
  if (norm) norm.value = "";
  if (title) title.textContent = "Cadastrar";
  if (save) save.textContent = "Cadastrar";
  if (cancel) cancel.style.display = "none";
}

function editBlueprintIndex(btn) {
  if (!btn) return;
  var norm = document.getElementById("bidx-edit-norm");
  var title = document.getElementById("bidx-form-title");
  var save = document.getElementById("bidx-save");
  var cancel = document.getElementById("bidx-cancel");
  var set = function (id, value) {
    var el = document.getElementById(id);
    if (el) el.value = value || "";
  };
  if (norm) norm.value = btn.getAttribute("data-norm") || "";
  set("bidx-name", btn.getAttribute("data-name"));
  set("bidx-mod", btn.getAttribute("data-mod"));
  set("bidx-id", btn.getAttribute("data-path"));
  var kind = document.getElementById("bidx-new-kind");
  if (kind) {
    kind.value = btn.getAttribute("data-kind") || "";
    if (kind._kbMenuSync) kind._kbMenuSync();
  }
  set("bidx-note", btn.getAttribute("data-note"));
  fillBlueprintClass();
  if (title) title.textContent = "Editar cadastro";
  if (save) save.textContent = "Salvar";
  if (cancel) cancel.style.display = "";
  var form = document.getElementById("bidx-name");
  if (form && form.scrollIntoView) form.scrollIntoView({ block: "center" });
}

async function deleteBlueprintIndex(btn) {
  var msg = document.getElementById("bidx-form-msg");
  var norm = (btn && btn.getAttribute("data-norm")) || "";
  if (!norm) return;
  if (msg) msg.textContent = "Excluindo…";
  try {
    await fetchJson("/api/admin/blueprint-index", {
      method: "DELETE",
      body: { ident_norm: norm },
      retries: 0
    });
    var editing = document.getElementById("bidx-edit-norm");
    if (editing && editing.value === norm) cancelBlueprintIndexEdit();
    if (msg) msg.textContent = "Cadastro excluído.";
    scheduleBlueprintIndexQuery(true);
  } catch (err) {
    if (msg) msg.textContent = err.message || "Não foi possível excluir.";
  }
}

function copyBlueprintIndexPath(btn) {
  var text = (btn && btn.getAttribute("data-path")) || "";
  if (!text) return;
  var done = function () { if (typeof toast === "function") toast("Caminho copiado", "success"); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(function () { done(); });
    return;
  }
  done();
}

async function openBlueprintIndex() {
  var el = document.getElementById("blueprint-index-list");
  var syncEl = document.getElementById("blueprint-index-sync");
  if (!el) return;
  _bpIndex.offset = 0;
  if (typeof setTableLoading === "function") setTableLoading(el, "Atualizando o índice do projeto…");
  try {
    var refreshed = await fetchJson("/api/admin/blueprint-index/refresh", {
      method: "POST", body: {}, timeoutMs: 120000, retries: 0
    });
    var count = refreshed.data && refreshed.data.count;
    var warning = (refreshed.data && refreshed.data.warning) || "";
    if (syncEl) {
      syncEl.textContent = (count != null ? count + " caminhos no índice." : "") + (warning ? " " + warning : "");
    }
  } catch (err) {
    if (typeof isStaleTableAbort === "function" && isStaleTableAbort(err)) return;
    if (syncEl) syncEl.textContent = err.message || "Falha ao atualizar o índice";
  }
  await queryBlueprintIndex();
}

async function queryBlueprintIndex() {
  var el = document.getElementById("blueprint-index-list");
  if (!el) return;
  var q = (document.getElementById("bidx-q") || {}).value || "";
  q = String(q).trim();
  var kind = (document.getElementById("bidx-kind") || {}).value || "";
  var params = new URLSearchParams();
  params.set("limit", String(_bpIndex.limit));
  params.set("offset", String(_bpIndex.offset));
  if (q) params.set("q", q);
  if (kind) params.set("kind", kind);
  if (typeof setTableLoading === "function") setTableLoading(el, "Buscando…");
  var ctrl = typeof beginTablePageFetch === "function" ? beginTablePageFetch("blueprint-index") : null;
  try {
    var data = await fetchJson("/api/admin/blueprint-index?" + params.toString(), {
      signal: ctrl ? ctrl.signal : undefined, retries: 0
    });
    var payload = data.data || {};
    var rows = payload.rows || [];
    _bpIndex.total = Number(payload.total || 0);
    _bpIndex.hasMore = _bpIndex.offset + rows.length < _bpIndex.total;
    if (typeof setTablePageInfo === "function") {
      setTablePageInfo("blueprint-index-page-info", {
        offset: _bpIndex.offset, limit: _bpIndex.limit, total: _bpIndex.total,
        hasMore: _bpIndex.hasMore, count: rows.length
      });
    }
    if (!rows.length) {
      el.innerHTML = '<div class="kb-p">Nenhum caminho com esse filtro.</div>';
      return;
    }
    el.innerHTML = '<div class="kb-table-wrap"><table class="kb-table"><thead><tr>' +
      '<th class="kb-col-name">Nome</th><th class="kb-col-mod">Mod</th><th class="kb-col-kind">Tipo</th>' +
      '<th class="kb-col-path">Blueprint</th><th class="kb-col-class">Classe</th>' +
      '<th class="kb-col-note">Observações</th><th>Origem</th><th></th>' +
      "</tr></thead><tbody>" + rows.map(function (row) {
        var sources = (row.sources || []).map(function (id) { return _BP_INDEX_SOURCE[id] || id; }).join(", ");
        var actions = '<button type="button" class="btn btn-ghost btn-sm" data-path="' +
          _pfEsc(row.identifier || "") + '" onclick="copyBlueprintIndexPath(this)">Copiar</button>';
        if (row.editable) {
          actions += ' <button type="button" class="btn btn-ghost btn-sm" data-norm="' +
            _pfEsc(row.ident_norm || "") + '" data-path="' + _pfEsc(row.identifier || "") +
            '" data-name="' + _pfEsc(row.display_name || "") + '" data-mod="' +
            _pfEsc(row.mod_name || "") + '" data-kind="' + _pfEsc(row.kind || "") +
            '" data-note="' + _pfEsc(row.note || "") +
            '" onclick="editBlueprintIndex(this)">Editar</button>' +
            ' <button type="button" class="btn btn-ghost btn-sm" data-norm="' +
            _pfEsc(row.ident_norm || "") + '" onclick="deleteBlueprintIndex(this)">Excluir</button>';
        }
        return '<tr><td class="kb-col-name">' + _pfEsc(row.display_name || "—") + '</td><td class="kb-col-mod">' +
          _pfEsc(row.mod_name || "—") + '</td><td class="kb-col-kind">' +
          _pfEsc(_BP_INDEX_KIND[row.kind] || row.kind || "") + '</td><td class="kb-code kb-col-path">' +
          _pfEsc(row.identifier || "") + '</td><td class="kb-code kb-col-class">' +
          _pfEsc(row.class_name || "—") + '</td><td class="kb-col-note">' + _pfEsc(row.note || "—") +
          "</td><td>" + _pfEsc(sources || "—") + "</td><td>" + actions + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  } catch (err) {
    if (typeof isStaleTableAbort === "function" && isStaleTableAbort(err)) return;
    el.innerHTML = '<div class="kb-p">' + _pfEsc(err.message || "Erro") + "</div>";
  }
}

async function submitBlueprintIndex(event) {
  if (event) event.preventDefault();
  var msg = document.getElementById("bidx-form-msg");
  var identifier = String((document.getElementById("bidx-id") || {}).value || "").trim();
  var kind = (document.getElementById("bidx-new-kind") || {}).value || "";
  var displayName = String((document.getElementById("bidx-name") || {}).value || "").trim();
  var modName = String((document.getElementById("bidx-mod") || {}).value || "").trim();
  var note = String((document.getElementById("bidx-note") || {}).value || "").trim();
  var editing = String((document.getElementById("bidx-edit-norm") || {}).value || "").trim();
  fillBlueprintClass();
  if (!displayName) {
    if (msg) msg.textContent = "Informe o nome.";
    return;
  }
  if (!modName) {
    if (msg) msg.textContent = "Informe o mod.";
    return;
  }
  if (!kind) {
    if (msg) msg.textContent = "Escolha o tipo.";
    return;
  }
  if (!identifier) {
    if (msg) msg.textContent = "Informe a blueprint.";
    return;
  }
  if (msg) msg.textContent = "Salvando…";
  var body = {
    identifier: identifier,
    kind: kind,
    display_name: displayName,
    mod_name: modName,
    note: note
  };
  if (editing) body.ident_norm = editing;
  try {
    var data = await fetchJson("/api/admin/blueprint-index", {
      method: editing ? "PATCH" : "POST",
      body: body,
      retries: 0
    });
    if (msg) {
      msg.textContent = editing
        ? "Cadastro atualizado."
        : "Cadastro salvo. Ele permanece quando o índice do projeto atualizar.";
    }
    cancelBlueprintIndexEdit();
    var box = document.getElementById("bidx-q");
    if (box && data.data) box.value = data.data.display_name || displayName;
    scheduleBlueprintIndexQuery(true);
  } catch (err) {
    if (msg) msg.textContent = err.message || "Não foi possível cadastrar.";
  }
}

function closeKbMenus(except) {
  document.querySelectorAll(".kb-menu").forEach(function (menu) {
    if (except && menu === except) return;
    var list = menu.querySelector(".kb-menu-list");
    var button = menu.querySelector(".kb-menu-btn");
    if (list) list.hidden = true;
    if (button) button.setAttribute("aria-expanded", "false");
  });
}

function mountKbMenu(select) {
  if (!select || select.closest(".kb-menu")) return;
  var wrap = document.createElement("div");
  wrap.className = "kb-menu";
  select.parentNode.insertBefore(wrap, select);
  wrap.appendChild(select);
  select.classList.add("kb-select-native");
  select.tabIndex = -1;
  select.setAttribute("aria-hidden", "true");

  var button = document.createElement("button");
  button.type = "button";
  button.className = "kb-menu-btn";
  button.id = select.id ? select.id + "-btn" : "";
  button.setAttribute("aria-haspopup", "listbox");
  button.setAttribute("aria-expanded", "false");
  var label = document.createElement("span");
  label.className = "kb-menu-label";
  var caret = document.createElement("span");
  caret.className = "kb-menu-caret";
  caret.setAttribute("aria-hidden", "true");
  button.appendChild(label);
  button.appendChild(caret);

  var list = document.createElement("div");
  list.className = "kb-menu-list";
  list.id = select.id ? select.id + "-list" : "";
  list.setAttribute("role", "listbox");
  list.hidden = true;
  button.setAttribute("aria-controls", list.id);
  var focusIndex = 0;

  Array.prototype.forEach.call(select.options, function (opt) {
    var item = document.createElement("button");
    item.type = "button";
    item.className = "kb-menu-opt";
    item.setAttribute("role", "option");
    item.setAttribute("data-value", opt.value);
    item.textContent = opt.textContent;
    item.addEventListener("click", function () { choose(opt.value); });
    list.appendChild(item);
  });

  function items() {
    return list.querySelectorAll(".kb-menu-opt");
  }

  function paint() {
    var value = select.value;
    var text = "";
    items().forEach(function (item, index) {
      var on = item.getAttribute("data-value") === value;
      item.classList.toggle("is-selected", on);
      item.setAttribute("aria-selected", on ? "true" : "false");
      if (on) {
        text = item.textContent;
        focusIndex = index;
      }
    });
    if (!text && select.options.length) text = select.options[0].textContent;
    label.textContent = text || "";
  }

  function openMenu() {
    closeKbMenus(wrap);
    paint();
    list.hidden = false;
    button.setAttribute("aria-expanded", "true");
    var current = items()[focusIndex];
    if (current) current.focus();
  }

  function closeMenu(restoreFocus) {
    list.hidden = true;
    button.setAttribute("aria-expanded", "false");
    if (restoreFocus) button.focus();
  }

  function choose(value) {
    var previous = select.value;
    select.value = value;
    paint();
    closeMenu(true);
    if (previous !== value) select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  button.addEventListener("click", function () {
    if (list.hidden) openMenu();
    else closeMenu(false);
  });
  button.addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openMenu();
    }
  });
  list.addEventListener("keydown", function (event) {
    var all = items();
    if (event.key === "Escape") {
      event.preventDefault();
      closeMenu(true);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusIndex = Math.min(all.length - 1, focusIndex + 1);
      if (all[focusIndex]) all[focusIndex].focus();
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      focusIndex = Math.max(0, focusIndex - 1);
      if (all[focusIndex]) all[focusIndex].focus();
      return;
    }
    if (event.key === "Home") {
      event.preventDefault();
      focusIndex = 0;
      if (all[0]) all[0].focus();
      return;
    }
    if (event.key === "End") {
      event.preventDefault();
      focusIndex = all.length - 1;
      if (all[focusIndex]) all[focusIndex].focus();
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      var current = document.activeElement;
      if (current && current.getAttribute("data-value") != null) choose(current.getAttribute("data-value"));
      return;
    }
    if (event.key === "Tab") closeMenu(false);
  });

  select._kbMenuSync = paint;
  wrap.appendChild(button);
  wrap.appendChild(list);
  paint();
}

function mountKbMenus() {
  document.querySelectorAll("#page-blueprint-index select.kb-select, #page-primal-fear-ficha select.kb-select").forEach(mountKbMenu);
}

document.addEventListener("click", function (event) {
  if (event.target && event.target.closest && event.target.closest(".kb-menu")) return;
  closeKbMenus();
});
document.addEventListener("keydown", function (event) {
  if (event.key === "Escape") closeKbMenus();
});
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountKbMenus);
else mountKbMenus();
