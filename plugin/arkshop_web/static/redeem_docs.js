/**
 * Sistema de documentação automática — Sistema de Resgates ARKLAND.
 * Categorias, licenças e textos gerados por item/kit.
 */
(function (global) {
  "use strict";

  const LICENSE_TIERS = {
    Gamma: {
      label: "Gamma",
      durationDays: 30,
      timedBonus: 25,
      summary: "Licença de entrada — ideal para começar a desbloquear conteúdos exclusivos.",
    },
    Beta: {
      label: "Beta",
      durationDays: 30,
      timedBonus: 50,
      summary: "Licença intermediária — mais bônus por tempo online e acesso ampliado.",
    },
    Alfa: {
      label: "Alfa",
      durationDays: 30,
      timedBonus: 75,
      summary: "Licença avançada — máximo bônus por tempo online e acesso aos conteúdos mais raros.",
    },
    keyvault: {
      label: "Nuvem",
      durationDays: 30,
      timedBonus: 0,
      summary: "Cofre de inventário no cluster — use /upload, /download e /nuvem no chat (até 250 itens).",
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
        "Itens com cadeado exigem uma licença ativa (Gamma, Beta ou Alfa).",
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
      short: "Resgate criaturas conforme as regras e limites do servidor.",
      detailed:
        "Dinossauros resgatados seguem as configurações do Arkland: nível, estatísticas e " +
        "restrições definidas pela administração. Criaturas raras ou especiais trazem descrições " +
        "e avisos extras antes da confirmação.",
      notes: [
        "Dinos especiais podem exigir licença Gamma, Beta ou Alfa.",
        "Limites de tribo, cupos de domesticação e regras PvP do servidor continuam valendo.",
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
      short: "Acesso temporário a conteúdos exclusivos e bônus de Âmbar por tempo online.",
      detailed:
        "Licenças são permissões de 30 dias adquiridas com Âmbares. Elas liberam resgates " +
        "bloqueados e aumentam quanto Âmbar você ganha automaticamente enquanto joga. " +
        "Não substituem doação nem garantem VIP automático — são conquistadas no sistema de resgates.",
      notes: [
        "Validade: 30 dias a partir do resgate.",
        "Três níveis: Gamma (+25), Beta (+50) e Alfa (+75) de bônus por ciclo de tempo online.",
        "Licença Nuvem: armazena até 250 itens do inventário (/upload) e recupera em qualquer mapa (/download).",
        "Vários conteúdos do catálogo só aparecem desbloqueados com a licença correta ativa.",
        "Você pode renovar antes do vencimento resgatando novamente, se disponível no catálogo.",
      ],
      warnings: [
        "Licença expirada remove o bônus e o acesso a itens que dependem dela.",
        "Doações PIX não concedem licença automaticamente — resgate com Âmbares no catálogo.",
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
        "Doação não garante VIP nem licença — resgate Gamma/Beta/Alfa com Âmbares no catálogo.",
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
    if (/\balfa\b/.test(text)) return "Alfa";
    if (/\bbeta\b/.test(text)) return "Beta";
    if (/\bgamma\b/.test(text)) return "Gamma";
    if (/\bnuvem\b/.test(text) || /\bkeyvault\b/.test(text)) return "keyvault";
    return null;
  }

  function resolveItemCategory(item, helpers) {
    if (item.catalogKind === "kit") return "kits";
    const type = String(item.type || "").toLowerCase();
    if (type === "dino" || (helpers && helpers.isDino && helpers.isDino(type))) return "dinos";
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
      warnings.push(`Licença ${tierInfo.label} expira em ${tierInfo.durationDays} dias.`);
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
      const n = item.kitItems ? ` (${item.kitItems} itens)` : "";
      shortDescription = `Kit ${name}${n} — pacote de recursos para sua base ou aventura.`;
      if (!detailedDescription) {
        detailedDescription =
          `O kit ${name} reúne itens selecionados pela equipe. Ideal para acelerar sua progressão ` +
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
        if (tierInfo.timedBonus > 0) {
          shortDescription =
            `Licença ${tierInfo.label} — ${tierInfo.durationDays} dias, +${tierInfo.timedBonus} Âmbar por ciclo online.`;
        } else {
          shortDescription =
            `Licença ${tierInfo.label} — ${tierInfo.durationDays} dias. ${tierInfo.summary}`;
        }
        if (!detailedDescription) detailedDescription = tierInfo.summary;
      } else {
        shortDescription = `Licença ${name} — acesso temporário a conteúdos exclusivos.`;
        if (!detailedDescription) {
          detailedDescription =
            "Licenças liberam resgates bloqueados e aumentam seu ganho de Âmbar por tempo de jogo.";
        }
      }
    }

    if (perms.length && !shortDescription.includes("licença")) {
      shortDescription += ` Requer licença ${perms.join(" ou ")}.`;
    }

    const benefits = [];
    if (category === "licenses" && tierInfo) {
      benefits.push(`+${tierInfo.timedBonus} Âmbares por ciclo de tempo online (além do padrão)`);
      benefits.push(`Acesso a conteúdos que exigem licença ${tierInfo.label}`);
      benefits.push(`Validade de ${tierInfo.durationDays} dias`);
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

  function renderLicenseTiersGrid() {
    const cards = Object.values(LICENSE_TIERS)
      .map(
        (t) => `
      <div class="redeem-license-tier">
        <div class="redeem-license-tier__name">${esc(t.label)}</div>
        <div class="redeem-license-tier__meta">${t.durationDays} dias · +${t.timedBonus} Âmbar/ciclo</div>
        <div class="redeem-license-tier__desc">${esc(t.summary)}</div>
      </div>`
      )
      .join("");
    return `<div class="redeem-license-tiers">${cards}</div>`;
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
        <div class="redeem-doc-block">
          <div class="redeem-doc-block__title">Níveis de licença</div>
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

    if (doc.benefits && doc.benefits.length) {
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
      blocks.push(`
        <div class="redeem-doc-block redeem-doc-block--license">
          <div class="redeem-doc-block__title">Licença ${esc(t.label)}</div>
          <p class="redeem-modal-section__text">${esc(t.summary)}</p>
          <p class="redeem-modal-section__meta">${t.durationDays} dias · +${t.timedBonus} Âmbar por ciclo de tempo online</p>
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
    parsePerms,
    detectLicenseTier,
    resolveItemCategory,
    buildItemRedeemDoc,
    renderCategoryDocHtml,
    renderProductDocHtml,
    renderModalDocHtml,
    mountCategoryDoc,
    renderLicenseTiersGrid,
  };
})(typeof window !== "undefined" ? window : globalThis);
