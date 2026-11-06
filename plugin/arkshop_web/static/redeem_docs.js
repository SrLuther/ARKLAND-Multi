/**
 * Sistema de documentação automática — Sistema de Resgates ARKLAND.
 * Categorias, licenças e textos gerados por item/kit.
 */
(function (global) {
  "use strict";

  /** Fonte: config.json (licenca_*), TimedPointsReward, LICENSE_TIMED_BONUS, ShopCloudInventory. */
  const LICENSE_DEFAULT_BONUS = 25;
  const LICENSE_CYCLE_MINUTES = 30;

  const LICENSE_TIERS = {
    keyvault: {
      id: "keyvault", label: "Nuvem", permissionGroup: "keyvault", catalogId: "licenca_nuvem",
      durationDays: 30, priceAmber: 5000, timedBonus: 0,
      cloudMaxItems: 250, cloudCooldownSeconds: 30,
      summary: "Cofre de invent\u00e1rio no cluster - /upload, /download e /nuvem (at\u00e9 250 pilhas); obrigat\u00f3ria para enviar ao Mercado P2P.",
      benefits: ["Validade de 30 dias a partir do resgate.", "Sem ganho de \u00c2mbares por tempo de jogo.", "/upload envia pilhas transfer\u00edveis do invent\u00e1rio para o cofre do cluster.", "/download restaura os itens em qualquer mapa; permitido mesmo ap\u00f3s expirar a licen\u00e7a.", "/nuvem consulta quantas pilhas est\u00e3o no cofre.", "Obrigat\u00f3ria para enviar dinos ao Mercado P2P in-game, al\u00e9m das demais regras."],
    },
    keyfarm: {
      id: "keyfarm", label: "Fazenda", permissionGroup: "keyfarm", catalogId: "licenca_fazenda",
      timedBonus: 0,
      summary: "Acesso ao sistema Fazenda de Recursos: envie recursos eleg\u00edveis do invent\u00e1rio e acompanhe produ\u00e7\u00e3o e resgates na Minha \u00c1rea. Exige conta Discord vinculada.",
      benefits: ["Envie recursos configurados do invent\u00e1rio para iniciar a produ\u00e7\u00e3o individual na Fazenda.", "Acompanhe estoque, produ\u00e7\u00e3o e pedidos de retirada na Minha \u00c1rea.", "Use /fazenda para preparar um envio e /fazconfirmar para confirm\u00e1-lo no jogo.", "Use /fazresgatar no jogo ap\u00f3s agendar uma retirada no site.", "A conta Discord precisa estar vinculada ao site para usar a Fazenda."],
    },
  };

  const CATEGORY_DOCS = {
    items: {
      icon: "📦",
      title: "Itens",
      short: "Resgate recursos e equipamentos usando Âmbares conquistados no Arkland.",
      detailed:
        "Na aba Itens você troca Âmbares por materiais, ferramentas, armas e outros recursos " +
        "que ajudam sua sobrevivência e progressão. Cada resgate é registrado e entregue quando " +
        "você estiver online no servidor.",
      notes: [
        "Âmbares vêm de tempo de jogo ou de doações voluntárias — nunca são compra direta de vantagem.",
        "Itens com cadeado exigem uma licen\u00e7a ativa indicada no pr\u00f3prio item.",
        "O nome da licença necessária aparece no card e na confirmação do resgate.",
        "Itens especiais ou restritos mostram requisitos antes de você confirmar.",
      ],
      warnings: [
        "Mantenha espaço no inventário antes de resgatar itens volumosos.",
        "Resgates são definitivos após a entrega no jogo.",
      ],
    },
    kits: {
      icon: "🎁",
      title: "Kits",
      short: "Pacotes prontos com vários recursos para acelerar sua jornada.",
      detailed:
        "Kits são conjuntos pré-montados pela equipe do servidor — úteis para recomeços, " +
        "eventos ou montagem rápida de base. O conteúdo pode ser ajustado conforme o balanceamento do cluster.",
      notes: [
        "Alguns kits exigem licença ativa — verifique o cadeado no card.",
        "Certifique-se de ter espaço suficiente no inventário para todos os itens do kit.",
        "A composição do kit pode mudar em atualizações de balanceamento (o preço em Âmbares reflete o servidor).",
      ],
      warnings: [
        "Kits grandes podem exigir vários slots livres no inventário.",
        "Após entregue, o kit não pode ser desfeito.",
      ],
    },
    dinos: {
      icon: "🦕",
      title: "Dinos",
      short: "Resgate criaturas de vários níveis conforme as regras e limites do servidor.",
      detailed:
        "Dinossauros resgatados seguem as configurações do Arkland: nível, gênero, estatísticas e " +
        "restrições definidas pela administração. Use os chips de «Nível» para filtrar (1, 50, 100, 200…) " +
        "— os níveis disponíveis vêm do catálogo. Cada card mostra o nível (Nv.) e o gênero " +
        "(Macho, Fêmea, Casal ou Aleatório).",
      notes: [
        "Dinos especiais podem exigir uma licen\u00e7a indicada no pr\u00f3prio item.",
        "Limites de tribo, cupos de domesticação e regras PvP do servidor continuam valendo.",
        "Gênero «Aleatório»: o sexo não é fixado pelo catálogo e é sorteado na entrega.",
        "Leia os avisos no card — dinos únicos podem ter condições adicionais.",
      ],
      warnings: [
        "Confirme que há espaço na sua tribo / estabulo antes de resgatar.",
        "Alguns dinos não podem ser transferidos entre mapas — consulte as regras do cluster.",
      ],
    },
    licenses: {
      icon: "📜",
      title: "Licenças",
      short: "Acesso a recursos espec\u00edficos e, conforme a configura\u00e7\u00e3o, b\u00f4nus de \u00c2mbar por tempo online.",
      detailed:
        "Licen\u00e7as s\u00e3o permiss\u00f5es com validade e benef\u00edcios definidos pelo cat\u00e1logo. Elas podem liberar acesso a itens e recursos espec\u00edficos. " +
        "Somente as que concedem b\u00f4nus por tempo aumentam o ganho de \u00c2mbar enquanto voc\u00ea joga. " +
        "N\u00e3o substituem doa\u00e7\u00e3o nem garantem VIP autom\u00e1tico \u2014 consulte o cat\u00e1logo para obter as informa\u00e7\u00f5es vigentes.",
      notes: [
        "Validade, valores e benef\u00edcios dependem do cat\u00e1logo vigente.",
        "Licen\u00e7as com b\u00f4nus por tempo aumentam o ganho de \u00c2mbares enquanto voc\u00ea joga; os valores e acessos seguem o cat\u00e1logo vigente.",
        "Licen\u00e7a Nuvem: cofre de invent\u00e1rio com /upload, /download e /nuvem; tamb\u00e9m necess\u00e1ria para enviar dinos ao Mercado P2P.",
        "Licen\u00e7a Fazenda: produ\u00e7\u00e3o passiva, agendamento de retiradas e resgate no jogo; exige Discord vinculado.",
        "Renova\u00e7\u00e3o restaura limites de resgate dos kits ligados ao grupo da licen\u00e7a, quando aplic\u00e1vel.",
      ],
      warnings: [
        "Quando aplic\u00e1vel, uma licen\u00e7a expirada pode encerrar o b\u00f4nus por tempo e o acesso aos itens ou recursos vinculados a ela.",
        "Na Nuvem, o upload exige licen\u00e7a ativa; o download de itens armazenados continua permitido ap\u00f3s expirar.",
        "Doa\u00e7\u00f5es n\u00e3o concedem licen\u00e7as automaticamente; consulte o cat\u00e1logo para ver as op\u00e7\u00f5es vigentes.",
      ],
      licenseTiers: true,
    },
    available: {
      icon: "✅",
      title: "Disponível",
      short: "Acompanhe resgates pendentes, gratuitos e como recebê-los no jogo.",
      detailed:
        "Aqui você vê o que já comprou e aguarda entrega, pode desistir com reembolso antes " +
        "da entrega, e resgata ofertas gratuitas do servidor. Tudo que for grátis no catálogo aparece nesta aba.",
      notes: [
        "Desistência: cancelar um resgate PENDENTE devolve os Âmbares antes da entrega.",
        "É necessário estar conectado ao servidor para receber o que foi resgatado.",
        "No chat do jogo, use o comando /shop para retirar itens disponíveis na fila.",
        "Resgates pendentes são processados quando você entra no mapa.",
      ],
      warnings: [
        "Após a entrega no servidor, o resgate não pode mais ser cancelado.",
        "Sem conexão ao servidor, itens permanecem na fila até você entrar.",
      ],
    },
    recharge: {
      icon: "💚",
      title: "Doações",
      short: "Apoie o servidor voluntariamente e receba Âmbares como agradecimento simbólico.",
      detailed:
        "Doações via PIX são voluntárias e ajudam a manter o Arkland online. Você não está " +
        "comprando itens ou vantagens — recebe Âmbares proporcionais ao valor doado para usar " +
        "no sistema de resgates, como qualquer jogador que acumula Âmbar jogando.",
      notes: [
        "Doações são definitivas e não reembolsáveis.",
        "Não é venda: você contribui com a manutenção; os Âmbares são brinde descrito em cada pacote.",
        "PIX exige e-mail, nome, CPF e telefone (Mercado Pago). Cartão internacional: e-mail e nome — documento opcional.",
        "Doa\u00e7\u00f5es n\u00e3o concedem licen\u00e7as automaticamente; consulte o cat\u00e1logo para ver as op\u00e7\u00f5es vigentes.",
      ],
      warnings: [
        "Não há conversão de Âmbares em dinheiro real.",
        "Pacotes e valores podem ser atualizados pela administração.",
      ],
    },
  };

  function parsePerms(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw.map(String).map((s) => s.trim()).filter(Boolean);
    return String(raw).split(",").map((s) => s.trim()).filter(Boolean);
  }

  function detectLicenseTier(item) {
    const grant = item.licenseGrant || item.LicenseGrant;
    if (grant && grant.Group && LICENSE_TIERS[grant.Group]) return grant.Group;
    const perms = parsePerms(item.permissions || item.Permissions);
    for (const p of perms) {
      if (LICENSE_TIERS[p]) return p;
    }
    const text = `${item.name || ""} ${item.desc || ""}`.toLowerCase();
    if (/\bnuvem\b/.test(text) || /\bkeyvault\b/.test(text)) return "keyvault";
    return null;
  }

  function resolveItemCategory(item, helpers) {
    if (item.catalogKind === "kit") return "kits";
    const type = String(item.type || "").toLowerCase();
    if (type === "dino" || (helpers && helpers.isDino && helpers.isDino(type))) {
      return "dinos";
    }
    if (helpers && helpers.isLicense && helpers.isLicense(item)) return "licenses";
    return "items";
  }

  function formatCost(price, formatAmber) {
    const p = Number(price) || 0;
    if (p <= 0) return "Grátis (0 Âmbares)";
    const fmt = formatAmber ? formatAmber(p) : String(p);
    return `${fmt} Âmbares`;
  }

  function buildItemRedeemDoc(item, helpers) {
    helpers = helpers || {};
    const category = resolveItemCategory(item, helpers);
    const catDoc = CATEGORY_DOCS[category] || CATEGORY_DOCS.items;
    const name = item.name || item.key || "Item";
    const adminDesc = String(item.desc || "").trim();
    const perms = parsePerms(item.permissions || item.Permissions);
    const price = Number(item.price) || 0;
    const isFree = price <= 0;
    const tier = detectLicenseTier(item);
    const tierInfo = tier ? LICENSE_TIERS[tier] : null;

    const requirements = [];
    if (helpers.authenticated === false) {
      requirements.push("Login com Steam");
    } else {
      requirements.push("Conta Steam vinculada");
    }
    if (!isFree) {
      requirements.push(`Saldo de Âmbares suficientes (${formatCost(price, helpers.formatAmber)})`);
    }
    if (perms.length) {
      requirements.push(`Licença ativa: ${perms.join(" ou ")}`);
    }
    if (category === "kits") {
      requirements.push("Espaço no inventário para todos os itens do kit");
    }
    if (category === "dinos") {
      requirements.push("Conformidade com limites de tribo e regras do servidor");
    }
    if (category === "licenses" && tierInfo) {
      requirements.push(`Âmbares para adquirir licença ${tierInfo.label}`);
    }

    const warnings = [...(catDoc.warnings || [])];
    if (perms.length) {
      warnings.unshift(`Sem licença ${perms.join(" / ")}, o resgate ficará bloqueado.`);
    }
    if (category === "licenses" && tierInfo) {
      if (tierInfo.durationDays) warnings.push(`Licença ${tierInfo.label} expira em ${tierInfo.durationDays} dias.`);
      if (tierInfo.label === "Nuvem") {
        warnings.push("Máximo 250 itens por upload. Use /download antes de um novo /upload.");
        warnings.push("Download permitido mesmo após expirar a licença (itens já armazenados).");
      }
    }
    if (isFree && category !== "licenses") {
      warnings.push("Item gratuito — resgate único conforme regras do servidor.");
    }

    let shortDescription = "";
    let detailedDescription = adminDesc;

    if (category === "items") {
      shortDescription =
        isFree
          ? `${name}: item gratuito do servidor.`
          : `Resgate ${name} com Âmbares e receba direto no jogo.`;
      if (!detailedDescription) {
        detailedDescription =
          `${name} faz parte do catálogo de sobrevivência do Arkland. ` +
          "Use Âmbares conquistados jogando ou apoiando o servidor para obter este recurso.";
      }
    } else if (category === "kits") {
      const highlights = (item.kitSummary && item.kitSummary.highlights) || [];
      const n = item.kitItems || item.itemCount || 0;
      const kitDesc = String(item.kitDescription || "").trim();
      const displayName = String(item.name || name || "Kit").replace(/^Kit\s+/i, "");
      if (highlights.length) {
        shortDescription = `Kit ${displayName} — ${highlights.slice(0, 3).join("; ")}.`;
      } else {
        const countBit = n ? ` (${n} itens)` : "";
        shortDescription = `Kit ${displayName}${countBit} — pacote de recursos para sua base ou aventura.`;
      }
      detailedDescription = kitDesc || adminDesc || detailedDescription;
      if (!detailedDescription) {
        detailedDescription =
          `O kit ${displayName} reúne itens selecionados pela equipe. Ideal para acelerar sua progressão ` +
          "sem perder o espírito de conquista do Arkland.";
      }
    } else if (category === "dinos") {
      shortDescription = `Resgate o dino ${name} conforme configuração do servidor.`;
      if (!detailedDescription) {
        detailedDescription =
          `${name} será entregue seguindo as regras de balanceamento do cluster. ` +
          "Verifique licenças e limites antes de confirmar.";
      }
    } else if (category === "licenses") {
      if (tierInfo) {
        const duration = tierInfo.durationDays ? `- ${tierInfo.durationDays} dias. ` : "- ";
        shortDescription = `Licen\u00e7a ${tierInfo.label} ${duration}${tierInfo.summary}`;
        detailedDescription = tierInfo.summary;
      } else {
        shortDescription = `Licen\u00e7a ${name} - acesso tempor\u00e1rio a conte\u00fados exclusivos.`;
        detailedDescription =
          "Concede acesso a itens e recursos espec\u00edficos e pode aumentar o ganho de \u00c2mbares por tempo de jogo, conforme as configura\u00e7\u00f5es vigentes.";
      }
    }

    if (perms.length && !shortDescription.includes("licença")) {
      shortDescription += ` Requer licença ${perms.join(" ou ")}.`;
    }

    const benefits = [];
    const kitHighlights = (item.kitSummary && item.kitSummary.highlights) || [];
    if (category === "licenses" && tierInfo) {
      if (tierInfo.benefits && tierInfo.benefits.length) {
        benefits.push(...tierInfo.benefits);
      } else {
        if (tierInfo.timedBonus > 0) {
          benefits.push(
            `+${tierInfo.timedBonus} Âmbares a cada ${tierInfo.cycleMinutes || 30} min online (além do Default)`
          );
        }
        benefits.push(`Acesso conforme grupo de permissão ${tierInfo.label}`);
        benefits.push(`Validade de ${tierInfo.durationDays} dias`);
      }
    } else if (category === "kits" && kitHighlights.length) {
      benefits.push(...kitHighlights);
      benefits.push("Entrega após confirmação — retire com /shop no jogo");
    } else if (!isFree) {
      benefits.push("Entrega após confirmação — retire com /shop no jogo");
    } else {
      benefits.push("Sem custo em Âmbares");
    }

    let confirmText = `Confirmo o resgate de "${name}"`;
    if (!isFree) confirmText += ` por ${formatCost(price, helpers.formatAmber)}`;
    if (perms.length) confirmText += ` (licença ${perms.join(" ou ")} necessária)`;
    confirmText += ".";

    return {
      name,
      category,
      categoryLabel: catDoc.title,
      shortDescription,
      detailedDescription,
      adminDescription: adminDesc,
      requirements,
      requiredLicenses: perms,
      licenseTier: tier,
      licenseTierInfo: tierInfo,
      costAmber: price,
      costLabel: formatCost(price, helpers.formatAmber),
      warnings,
      benefits,
      confirmText,
      notes: catDoc.notes || [],
    };
  }

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderDocBlock(title, items, variant) {
    if (!items || !items.length) return "";
    const cls = variant ? ` redeem-doc-block--${variant}` : "";
    const lis = items.map((t) => `<li>${esc(t)}</li>`).join("");
    return `
      <div class="redeem-doc-block${cls}">
        <div class="redeem-doc-block__title">${esc(title)}</div>
        <ul class="redeem-doc-block__list">${lis}</ul>
      </div>`;
  }

  function formatAmberRef(n) {
    const v = Number(n) || 0;
    try {
      return v.toLocaleString("pt-BR");
    } catch (_) {
      return String(v);
    }
  }

  function licenseTimedMeta(t) {
    if (!t) return "";
    return t.timedBonus > 0
      ? "Ganho de \u00c2mbares por tempo de jogo"
      : "Sem ganho de \u00c2mbares por tempo";
  }

  function licenseAccessMeta(t) {
    if (!t) return "";
    if (t.id === "keyvault") return "Cofre de invent\u00e1rio e Mercado P2P";
    if (t.id === "keyfarm") return "Fazenda de Recursos";
    return "Acesso a itens e recursos espec\u00edficos";
  }

  function renderLicenseTiersGrid() {
    const genericCards = [
      {
        title: "Concedem \u00c2mbares por tempo",
        text: "Licen\u00e7as desta categoria aumentam o ganho de \u00c2mbares enquanto voc\u00ea joga e podem liberar acesso a itens e recursos espec\u00edficos. Valores e acessos seguem as configura\u00e7\u00f5es atuais do cat\u00e1logo.",
        className: "redeem-license-group--amber",
      },
      {
        title: "N\u00e3o concedem \u00c2mbares por tempo",
        text: "Licen\u00e7as desta categoria podem liberar funcionalidades ou recursos espec\u00edficos, sem acrescentar b\u00f4nus de \u00c2mbares por tempo. Consulte os detalhes vigentes no cat\u00e1logo.",
        className: "redeem-license-group--special",
      },
    ];
    const specialLicenses = [LICENSE_TIERS.keyvault, LICENSE_TIERS.keyfarm];
    const cards = genericCards.map((card) => `
      <article class="redeem-license-panel ${card.className}">
        <h4 class="redeem-license-panel__title">${esc(card.title)}</h4>
        <p class="redeem-license-panel__summary">${esc(card.text)}</p>
      </article>`).join("");
    const specialCards = specialLicenses.map((license) => `
      <article class="redeem-license-panel">
        <h4 class="redeem-license-panel__title">${esc(license.label)}</h4>
        <div class="redeem-license-panel__chips"><span class="redeem-license-chip">Sem ganho de \u00c2mbares por tempo</span><span class="redeem-license-chip redeem-license-chip--tek">${esc(licenseAccessMeta(license))}</span></div>
        <p class="redeem-license-panel__summary">${esc(license.summary)}</p>
        <ul class="redeem-doc-block__list">${license.benefits.map((benefit) => `<li>${esc(benefit)}</li>`).join("")}</ul>
      </article>`).join("");
    return `<div class="redeem-license-benefits"><div class="redeem-license-panels" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:8px;">${cards}${specialCards}</div></div>`;
  }

  function selectLicenseTierTab(tierId) {
    const root = document.querySelector("[data-redeem-license-benefits]");
    if (!root || !LICENSE_TIERS[tierId]) return;
    root.querySelectorAll(".redeem-license-tab").forEach((btn) => {
      const on = btn.getAttribute("data-license-tier") === tierId;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    root.querySelectorAll(".redeem-license-panel").forEach((panel) => {
      const on = panel.getAttribute("data-license-panel") === tierId;
      panel.classList.toggle("hidden", !on);
      if (on) panel.removeAttribute("hidden");
      else panel.setAttribute("hidden", "");
    });
  }

  function renderCategoryDocHtml(tab) {
    const key = tab === "recharge" ? "recharge" : tab;
    const doc = CATEGORY_DOCS[key];
    if (!doc) return "";

    let body = `
      <p class="redeem-doc-panel__detailed">${esc(doc.detailed)}</p>
      ${renderDocBlock("Como funciona", doc.notes)}
      ${renderDocBlock("Importante", doc.warnings, "warn")}`;

    if (doc.licenseTiers) {
      body += `
        <div class="redeem-doc-block redeem-doc-block--license-benefits">
          <div class="redeem-doc-block__title">Benefícios por licença</div>
          ${renderLicenseTiersGrid()}
        </div>`;
    }

    return `
      <div class="redeem-doc-panel" data-redeem-doc="${esc(key)}">
        <div class="redeem-doc-panel__header">
          <span class="redeem-doc-panel__icon" aria-hidden="true">${doc.icon}</span>
          <div class="redeem-doc-panel__headtext">
            <h3 class="redeem-doc-panel__title">${esc(doc.title)}</h3>
            <p class="redeem-doc-panel__short">${esc(doc.short)}</p>
          </div>
        </div>
        <div class="redeem-doc-panel__body">${body}</div>
      </div>`;
  }

  function renderProductDocHtml(doc) {
    if (!doc) return "";
    const req =
      doc.requiredLicenses && doc.requiredLicenses.length
        ? `<div class="item-card__req">🔒 Licença: ${esc(doc.requiredLicenses.join(" ou "))}</div>`
        : "";
    return `
      <div class="item-card__doc-short">${esc(doc.shortDescription)}</div>
      ${req}`;
  }

  function renderModalDocHtml(doc, extras) {
    extras = extras || {};
    if (!doc) return "";

    const blocks = [];
    blocks.push(
      `<div class="redeem-modal-section">
        <div class="redeem-modal-section__label">Sobre</div>
        <p class="redeem-modal-section__text">${esc(doc.detailedDescription)}</p>
      </div>`
    );

    if (doc.benefits && doc.benefits.length && !doc.licenseTierInfo) {
      blocks.push(renderDocBlock("Benefícios", doc.benefits));
    }
    if (doc.requirements && doc.requirements.length) {
      blocks.push(renderDocBlock("Requisitos", doc.requirements));
    }
    if (doc.warnings && doc.warnings.length) {
      blocks.push(renderDocBlock("Atenção", doc.warnings, "warn"));
    }

    if (doc.licenseTierInfo) {
      const t = doc.licenseTierInfo;
      const benefitLis = (t.benefits || doc.benefits || [])
        .map((b) => `<li>${esc(b)}</li>`)
        .join("");
      blocks.push(`
        <div class="redeem-doc-block redeem-doc-block--license">
          <div class="redeem-doc-block__title">Licença ${esc(t.label)} — benefícios</div>
          <p class="redeem-modal-section__text">${esc(t.summary)}</p>
          <p class="redeem-modal-section__meta">${t.durationDays} dias · ${esc(
            licenseTimedMeta(t)
          )}</p>
          ${
            benefitLis
              ? `<ul class="redeem-doc-block__list" style="margin-top:8px">${benefitLis}</ul>`
              : ""
          }
        </div>`);
    }

    if (extras.balanceWarning) {
      blocks.push(
        `<div class="redeem-doc-block redeem-doc-block--warn">
          <div class="redeem-doc-block__title">Saldo</div>
          <p class="redeem-modal-section__text">${esc(extras.balanceWarning)}</p>
        </div>`
      );
    }
    if (extras.licenseWarning) {
      blocks.push(
        `<div class="redeem-doc-block redeem-doc-block--warn">
          <div class="redeem-doc-block__title">Licença</div>
          <p class="redeem-modal-section__text">${esc(extras.licenseWarning)}</p>
        </div>`
      );
    }

    return `<div class="redeem-modal-docs">${blocks.join("")}</div>`;
  }

  function mountCategoryDoc(tab) {
    const mount = document.getElementById("catalog-category-doc");
    if (!mount) return;
    const html = renderCategoryDocHtml(tab);
    mount.innerHTML = html;
    mount.style.display = html ? "" : "none";
  }

  global.RedeemDocs = {
    CATEGORY_DOCS,
    LICENSE_TIERS,
    LICENSE_DEFAULT_BONUS,
    LICENSE_CYCLE_MINUTES,
    parsePerms,
    detectLicenseTier,
    resolveItemCategory,
    buildItemRedeemDoc,
    renderCategoryDocHtml,
    renderProductDocHtml,
    renderModalDocHtml,
    mountCategoryDoc,
    renderLicenseTiersGrid,
    selectLicenseTierTab,
  };
})(typeof window !== "undefined" ? window : globalThis);
