/**
 * ARK Color IDs — referência estática (creature 1–100, dyes 201–226, especiais).
 * Fonte: https://ark.fandom.com/wiki/Color_IDs
 */
(function (global) {
  "use strict";

  /** @type {{ id: number, name: string, hex: string|null, note?: string }[]} */
  const CREATURE = [
    [1, "Red", "#ff0000"], [2, "Blue", "#0000ff"], [3, "Green", "#00ff00"],
    [4, "Yellow", "#ffff00"], [5, "Cyan", "#00ffff"], [6, "Magenta", "#ff00ff"],
    [7, "Light Green", "#c0ffba"], [8, "Light Grey", "#c8caca"], [9, "Light Brown", "#786759"],
    [10, "Light Orange", "#ffb46c"], [11, "Light Yellow", "#fffa8a"], [12, "Light Red", "#ff756c"],
    [13, "Dark Grey", "#7b7b7b"], [14, "Black", "#3b3b3b"], [15, "Brown", "#593a2a"],
    [16, "Dark Green", "#224900"], [17, "Dark Red", "#812118"], [18, "White", "#ffffff"],
    [19, "Dino Light Red", "#ffa8a8"], [20, "Dino Dark Red", "#592b2b"],
    [21, "Dino Light Orange", "#ffb694"], [22, "Dino Dark Orange", "#88532f"],
    [23, "Dino Light Yellow", "#cacaa0"], [24, "Dino Dark Yellow", "#94946c"],
    [25, "Dino Light Green", "#e0ffe0"], [26, "Dino Medium Green", "#799479"],
    [27, "Dino Dark Green", "#224122"], [28, "Dino Light Blue", "#d9e0ff"],
    [29, "Dino Dark Blue", "#394263"], [30, "Dino Light Purple", "#e4d9ff"],
    [31, "Dino Dark Purple", "#403459"], [32, "Dino Light Brown", "#ffe0ba"],
    [33, "Dino Medium Brown", "#948575"], [34, "Dino Dark Brown", "#594e41"],
    [35, "Dino Darker Grey", "#595959"],
    [36, "Dino Albino", "#ffffff", "≈75% mais claro que White; hex aproximado"],
    [37, "BigFoot0", "#b79683"], [38, "BigFoot4", "#eadad5"], [39, "BigFoot5", "#d0a794"],
    [40, "WolfFur", "#c3b39f"], [41, "DarkWolfFur", "#887666"],
    [42, "DragonBase0", "#a0664b"], [43, "DragonBase1", "#cb7956"], [44, "DragonFire", "#bc4f00"],
    [45, "DragonGreen0", "#79846c"], [46, "DragonGreen1", "#909c79"],
    [47, "DragonGreen2", "#a5a48b"], [48, "DragonGreen3", "#74939c"],
    [49, "WyvernPurple0", "#787496"], [50, "WyvernPurple1", "#b0a2c0"],
    [51, "WyvernBlue0", "#6281a7"], [52, "WyvernBlue1", "#485c75"],
    [53, "Dino Medium Blue", "#5fa4ea"], [54, "Dino Deep Blue", "#4568d4"],
    [55, "NearWhite", "#ededed"], [56, "NearBlack", "#515151"],
    [57, "DarkTurquoise", "#184546"], [58, "MediumTurquoise", "#007060"], [59, "Turquoise", "#00c5ab"],
    [60, "GreenSlate", "#40594c"], [61, "Sage", "#3e4f40"],
    [62, "DarkWarmGray", "#3b3938"], [63, "MediumWarmGray", "#585554"], [64, "LightWarmGray", "#9b9290"],
    [65, "DarkCement", "#525b56"], [66, "LightCement", "#8aa196"],
    [67, "LightPink", "#e8b0ff"], [68, "DeepPink", "#ff119a"],
    [69, "DarkViolet", "#730046"], [70, "DarkMagenta", "#b70042"],
    [71, "BurntSienna", "#7e331e"], [72, "MediumAutumn", "#a93000"], [73, "Vermillion", "#ef3100"],
    [74, "Coral", "#ff5834"], [75, "Orange", "#ff7f00"], [76, "Peach", "#ffa73a"],
    [77, "LightAutumn", "#ae7000"], [78, "Mustard", "#949427"],
    [79, "ActualBlack", "#171717"], [80, "MidnightBlue", "#191d36"], [81, "DarkBlue", "#152b3a"],
    [82, "BlackSands", "#302531"], [83, "LemonLime", "#a8ff44"], [84, "Mint", "#38e985"],
    [85, "Jade", "#008840"], [86, "PineGreen", "#0f552e"], [87, "SpruceGreen", "#005b45"],
    [88, "LeafGreen", "#5b9725"], [89, "DarkLavender", "#5e275f"],
    [90, "MediumLavender", "#853587"], [91, "Lavender", "#bd77be"],
    [92, "DarkTeal", "#0e404a"], [93, "MediumTeal", "#105563"], [94, "Teal", "#14849c"],
    [95, "PowderBlue", "#82a7ff"], [96, "Glacial", "#aceaff"],
    [97, "Cammo", "#505118"], [98, "DryMoss", "#766e3f"], [99, "Custard", "#c0bd5e"],
    [100, "Cream", "#f4ffc0"],
  ].map(function (row) {
    return { id: row[0], name: row[1], hex: row[2], note: row[3] || "" };
  });

  /** @type {{ id: number, name: string, hex: string, equiv?: number }[]} */
  const DYES = [
    [201, "Black Dye", "#1f1f1f"], [202, "Blue Dye", "#0000ff", 2],
    [203, "Brown Dye", "#756147"], [204, "Cyan Dye", "#00ffff", 5],
    [205, "Forest Dye", "#006c00"], [206, "Green Dye", "#00ff00", 3],
    [207, "Purple Dye", "#6c00ba"], [208, "Orange Dye", "#ff8800"],
    [209, "Parchment Dye", "#ffffba"], [210, "Pink Dye", "#ff7be1"],
    [211, "Uncraftable Purple Dye", "#7b00e0"], [212, "Red Dye", "#ff0000"],
    [213, "Royalty Dye", "#7b00a8"], [214, "Silver Dye", "#e0e0e0"],
    [215, "Sky Dye", "#bad4ff"], [216, "Tan Dye", "#ffed82"],
    [217, "Tangerine Dye", "#ad652c"], [218, "White Dye", "#fefefe"],
    [219, "Yellow Dye", "#ffff00"], [220, "Magenta Dye", "#e71fd9"],
    [221, "Brick Dye", "#94341f"], [222, "Cantaloupe Dye", "#ff9a00"],
    [223, "Mud Dye", "#473b2b"], [224, "Navy Dye", "#34346c"],
    [225, "Olive Dye", "#baba59"], [226, "Slate Dye", "#595959", 35],
  ].map(function (row) {
    const entry = { id: row[0], name: row[1], hex: row[2] };
    if (row[3]) entry.equiv = row[3];
    return entry;
  });

  const SPECIAL = [
    {
      id: 0,
      name: "Sem atualização (selvagem / padrão)",
      hex: null,
      note: "Região não alterada — usa cor padrão da espécie. Comum em mutações.",
    },
    {
      id: 227,
      name: "Mutation white",
      hex: "#ffffff",
      note: "Não definido como cor oficial; aparece branco in-game via mutação.",
    },
  ];

  const WIKI_URL = "https://ark.fandom.com/wiki/Color_IDs";

  function escHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function swatchHtml(hex, label) {
    if (!hex) {
      return '<span class="ark-color-swatch ark-color-swatch--empty" title="' + escHtml(label || "Sem cor") + '" aria-hidden="true"></span>';
    }
    return '<span class="ark-color-swatch" style="background:' + escHtml(hex) + ';" title="' + escHtml(hex) + '" aria-hidden="true"></span>';
  }

  function copyColorId(id) {
    const text = String(id);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        if (typeof global.toast === "function") global.toast("ID " + text + " copiado", "success");
      }).catch(function () {
        if (typeof global.toast === "function") global.toast("ID: " + text, "info");
      });
      return;
    }
    if (typeof global.toast === "function") global.toast("ID: " + text, "info");
  }

  function renderRows(entries, query) {
    const q = (query || "").trim().toLowerCase();
    const filtered = entries.filter(function (entry) {
      if (!q) return true;
      return String(entry.id).includes(q) || (entry.name || "").toLowerCase().includes(q);
    });
    if (!filtered.length) {
      return '<tr><td colspan="4" style="color:var(--text2);text-align:center;padding:16px;">Nenhuma cor encontrada.</td></tr>';
    }
    return filtered.map(function (entry) {
      const noteParts = [];
      if (entry.note) noteParts.push(entry.note);
      if (entry.equiv) noteParts.push("equivale ao ID " + entry.equiv);
      const note = noteParts.length ? '<div class="ark-color-ref-note">' + escHtml(noteParts.join(" · ")) + "</div>" : "";
      return (
        '<tr class="ark-color-ref-row" data-color-id="' + entry.id + '" tabindex="0" role="button" title="Clique para copiar ID">' +
        "<td><code>" + entry.id + "</code></td>" +
        "<td>" + swatchHtml(entry.hex, entry.name) + "</td>" +
        "<td>" + escHtml(entry.name) + note + "</td>" +
        "<td><code>" + escHtml(entry.hex || "—") + "</code></td>" +
        "</tr>"
      );
    }).join("");
  }

  function renderSpecialRows(query) {
    const q = (query || "").trim().toLowerCase();
    const filtered = SPECIAL.filter(function (entry) {
      if (!q) return true;
      return String(entry.id).includes(q) || (entry.name || "").toLowerCase().includes(q);
    });
    if (!filtered.length) {
      return '<tr><td colspan="4" style="color:var(--text2);text-align:center;padding:16px;">Nenhum resultado.</td></tr>';
    }
    return filtered.map(function (entry) {
      return (
        '<tr class="ark-color-ref-row" data-color-id="' + entry.id + '" tabindex="0" role="button" title="Clique para copiar ID">' +
        "<td><code>" + entry.id + "</code></td>" +
        "<td>" + swatchHtml(entry.hex, entry.name) + "</td>" +
        "<td>" + escHtml(entry.name) +
        (entry.note ? '<div class="ark-color-ref-note">' + escHtml(entry.note) + "</div>" : "") +
        "</td>" +
        "<td><code>" + escHtml(entry.hex || "—") + "</code></td>" +
        "</tr>"
      );
    }).join("");
  }

  function bindPanel(root) {
    const tabs = root.querySelectorAll("[data-ark-color-tab]");
    const panels = root.querySelectorAll("[data-ark-color-panel]");
    const search = root.querySelector(".ark-color-ref-search");

    function setTab(tab) {
      tabs.forEach(function (btn) {
        const active = btn.dataset.arkColorTab === tab;
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-selected", active ? "true" : "false");
      });
      panels.forEach(function (panel) {
        panel.classList.toggle("hidden", panel.dataset.arkColorPanel !== tab);
      });
    }

    tabs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        setTab(btn.dataset.arkColorTab || "creature");
      });
    });

    function refreshTables() {
      const q = search ? search.value : "";
      root.querySelectorAll("[data-ark-color-tbody]").forEach(function (tbody) {
        const kind = tbody.dataset.arkColorTbody;
        if (kind === "creature") tbody.innerHTML = renderRows(CREATURE, q);
        else if (kind === "dyes") tbody.innerHTML = renderRows(DYES, q);
        else if (kind === "special") tbody.innerHTML = renderSpecialRows(q);
        bindRowClicks(tbody);
      });
    }

    if (search) {
      search.addEventListener("input", refreshTables);
    }

    refreshTables();
    setTab("creature");
  }

  function bindRowClicks(tbody) {
    tbody.querySelectorAll(".ark-color-ref-row").forEach(function (row) {
      row.addEventListener("click", function () {
        copyColorId(row.dataset.colorId);
      });
      row.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          copyColorId(row.dataset.colorId);
        }
      });
    });
  }

  function tableBlock(kind, label) {
    return (
      '<div data-ark-color-panel="' + kind + '" class="ark-color-ref-panel">' +
      '<div class="tbl-scroll-host"><table class="tbl ark-color-ref-table">' +
      "<thead><tr><th>ID</th><th>Amostra</th><th>Nome</th><th>Hex</th></tr></thead>" +
      '<tbody data-ark-color-tbody="' + kind + '"></tbody>' +
      "</table></div>" +
      (label ? '<p class="ark-color-ref-footnote">' + label + "</p>" : "") +
      "</div>"
    );
  }

  /**
   * @param {HTMLElement} container
   * @param {{ compact?: boolean, showIntro?: boolean }} [options]
   */
  function renderPanel(container, options) {
    if (!container) return;
    options = options || {};
    const intro = options.showIntro !== false && !options.compact;
    container.innerHTML =
      (intro
        ? '<p class="ark-color-ref-intro">IDs oficiais de cor de criaturas (1–100) e tintas (201–226). ' +
          'Clique em uma linha para copiar o ID. Fonte: ' +
          '<a href="' + WIKI_URL + '" target="_blank" rel="noopener">ARK Wiki — Color IDs</a>.</p>'
        : "") +
      '<div class="ark-color-ref-toolbar">' +
      '<input type="search" class="ark-color-ref-search" placeholder="Buscar por ID ou nome…" autocomplete="off" aria-label="Buscar cor" />' +
      '<div class="ark-color-ref-tabs" role="tablist">' +
      '<button type="button" class="ark-color-ref-tab active" data-ark-color-tab="creature" role="tab" aria-selected="true">Criaturas (1–100)</button>' +
      '<button type="button" class="ark-color-ref-tab" data-ark-color-tab="dyes" role="tab" aria-selected="false">Tintas (201–226)</button>' +
      '<button type="button" class="ark-color-ref-tab" data-ark-color-tab="special" role="tab" aria-selected="false">Especiais</button>' +
      "</div></div>" +
      tableBlock("creature", "IDs 202, 204, 206 e 226 de tinta equivalem visualmente aos IDs 2, 5, 3 e 35.") +
      tableBlock("dyes") +
      tableBlock("special", "ID 0 mantém a região no padrão selvagem; ID 227 é branco de mutação.");
    bindPanel(container);
  }

  function initMount(containerId) {
    const el = document.getElementById(containerId);
    if (!el || el.dataset.arkColorMounted === "1") return;
    const details = el.closest("details");
    if (details && !details.open) {
      details.addEventListener("toggle", function () {
        if (details.open && el.dataset.arkColorMounted !== "1") {
          renderPanel(el, { compact: containerId !== "ark-color-ids-modal-body" });
          el.dataset.arkColorMounted = "1";
        }
      });
      return;
    }
    renderPanel(el, { compact: containerId !== "ark-color-ids-modal-body" });
    el.dataset.arkColorMounted = "1";
  }

  function openModal() {
    const modal = document.getElementById("ark-color-ids-modal");
    const body = document.getElementById("ark-color-ids-modal-body");
    if (!modal || !body) return;
    if (body.dataset.arkColorMounted !== "1") {
      renderPanel(body, { showIntro: true });
      body.dataset.arkColorMounted = "1";
    }
    modal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    const modal = document.getElementById("ark-color-ids-modal");
    if (!modal) return;
    modal.classList.add("hidden");
    document.body.style.overflow = "";
  }

  function initAllMounts() {
    ["encomenda-color-ids-ref", "dl-deliver-color-ids-ref", "dl-showcase-color-ids-ref"].forEach(initMount);
  }

  global.ARK_COLOR_IDS = {
    CREATURE: CREATURE,
    DYES: DYES,
    SPECIAL: SPECIAL,
    WIKI_URL: WIKI_URL,
    renderPanel: renderPanel,
    initMount: initMount,
    initAllMounts: initAllMounts,
    openModal: openModal,
    closeModal: closeModal,
  };

  global.openArkColorIdsModal = openModal;
  global.closeArkColorIdsModal = closeModal;
})(typeof window !== "undefined" ? window : this);
