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
    Gamma: {
      id: "Gamma",
      label: "Gamma",
      permissionGroup: "Gamma",
      catalogId: "licenca_gamma",
      durationDays: 30,
      priceAmber: 50000,
      timedBonus: 25,
      cycleMinutes: LICENSE_CYCLE_MINUTES,
      defaultBonus: LICENSE_DEFAULT_BONUS,
      accessTiers: ["Gama", "Delta"],
      summary:
        "Licença de entrada — acesso Gama + Delta e +25 Âmbar por ciclo online (total 50 com Default).",
      benefits: [
        "Validade de 30 dias a partir do resgate (SKU licenca_gamma).",
        "Preço de referência: 50.000 Âmbares (prevalece o valor no catálogo no momento do resgate).",
        "Bônus Timed Points: +25 Âmbar a cada 30 min online, somado ao Default (+25) → total 50 Âmbar / ciclo.",
        "Acesso a itens e kits do catálogo com cadeado Permissions que incluem Gamma (Description: Gama + Delta / ItensAlfa).",
        "Ao renovar a licença Gamma, limites de resgate (DefaultAmount) dos kits ligados ao grupo Gamma são restaurados.",
        "Pessoal e intransferível — não substitui doação PIX nem cargos MOD/STAFF.",
      ],
    },
    Beta: {
      id: "Beta",
      label: "Beta",
      permissionGroup: "Beta",
      catalogId: "licenca_beta",
      durationDays: 30,
      priceAmber: 75000,
      timedBonus: 50,
      cycleMinutes: LICENSE_CYCLE_MINUTES,
      defaultBonus: LICENSE_DEFAULT_BONUS,
      accessTiers: ["Beta", "Gama"],
      summary:
        "Licença intermediária — acesso Beta + Gama e +50 Âmbar por ciclo online (total 75 com Default).",
      benefits: [
        "Validade de 30 dias a partir do resgate (SKU licenca_beta).",
        "Preço de referência: 75.000 Âmbares (prevalece o valor no catálogo no momento do resgate).",
        "Bônus Timed Points: +50 Âmbar a cada 30 min online, somado ao Default (+25) → total 75 Âmbar / ciclo.",
        "Acesso a itens e kits do catálogo com cadeado Permissions que incluem Beta (Description: Beta + Gama / ItensAlfa).",
        "Ao renovar a licença Beta, limites de resgate (DefaultAmount) dos kits ligados ao grupo Beta são restaurados.",
        "Pessoal e intransferível — não substitui doação PIX nem cargos MOD/STAFF.",
      ],
    },
    Alfa: {
      id: "Alfa",
      label: "Alfa",
      permissionGroup: "Alfa",
      catalogId: "licenca_alfa",
      durationDays: 30,
      priceAmber: 100000,
      timedBonus: 75,
      cycleMinutes: LICENSE_CYCLE_MINUTES,
      defaultBonus: LICENSE_DEFAULT_BONUS,
      accessTiers: ["Alfa", "Beta"],
      summary:
        "Licença avançada — acesso Alfa + Beta e +75 Âmbar por ciclo online (total 100 com Default).",
      benefits: [
        "Validade de 30 dias a partir do resgate (SKU licenca_alfa).",
        "Preço de referência: 100.000 Âmbares (prevalece o valor no catálogo no momento do resgate).",
        "Bônus Timed Points: +75 Âmbar a cada 30 min online, somado ao Default (+25) → total 100 Âmbar / ciclo.",
        "Acesso a itens e kits do catálogo com cadeado Permissions que incluem Alfa (Description: Alfa + Beta / ItensAlfa).",
        "Ao renovar a licença Alfa, limites de resgate (DefaultAmount) dos kits ligados ao grupo Alfa são restaurados.",
        "Pessoal e intransferível — não substitui doação PIX nem cargos MOD/STAFF.",
      ],
    },
    keyvault: {
      id: "keyvault",
      label: "Nuvem",
      permissionGroup: "keyvault",
      catalogId: "licenca_nuvem",
      durationDays: 30,
      priceAmber: 5000,
      timedBonus: 0,
      cycleMinutes: LICENSE_CYCLE_MINUTES,
      defaultBonus: LICENSE_DEFAULT_BONUS,
      accessTiers: [],
      cloudMaxItems: 250,
      cloudCooldownSeconds: 30,
      summary:
        "Cofre de inventário no cluster — /upload, /download e /nuvem (até 250 pilhas); obrigatória para enviar ao Mercado P2P.",
      benefits: [
        "Validade de 30 dias a partir do resgate (SKU licenca_nuvem, grupo keyvault).",
        "Preço de referência: 5.000 Âmbares (prevalece o valor no catálogo no momento do resgate).",
        "Sem bônus Timed Points — não altera o ganho de Âmbar por tempo online.",
        "/upload — envia até 250 pilhas transferíveis do inventário para o cofre cluster-wide e esvazia o inventário (exige licença ativa).",
        "/download — restaura os itens em qualquer mapa do cluster; permitido mesmo com a licença expirada (política atual do plugin).",
        "/nuvem ou /cloud — consulta quantas pilhas estão no cofre.",
        "Um snapshot por SteamID: novo /upload é recusado enquanto houver itens na nuvem (use /download antes).",
        "Cooldown de 30 s entre operações de nuvem.",
        "Obrigatória para enviar dinos ao Mercado P2P in-game (/enviar → /confirmar), além de imprint 100% e demais regras §8.7.",
      ],
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
      short: "Resgate criaturas nível 1 conforme as regras e limites do servidor.",
      detailed:
        "Dinossauros resgatados seguem as configurações do Arkland: nível, estatísticas e " +
        "restrições definidas pela administração. Esta aba lista apenas dinos de nível 1 (piso). " +
        "Para nível 200, use a aba «Dinos 200».",
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
    dinos200: {
      icon: "🦖",
      title: "Dinos 200",
      short: "Criaturas nível 200 com preço derivado do L1 e do piso de mercado.",
      detailed:
        "Mesmo blueprint do dino L1 correspondente, spawnado no nível 200. O preço usa markup fixo " +
        "k=1,40 sobre o L1, com teto de 75% do root_value (piso de mercado da espécie). " +
        "Espécies sem margem sob o teto não aparecem aqui.",
      notes: [
        "Preço = round(clamp(P_L1 × 1,40, P_L1+1, 0,75 × root_value)).",
        "A aba «Dinos» continua a listar apenas nível 1.",
        "Limites de tribo e licenças aplicam-se da mesma forma que nos dinos L1.",
      ],
      warnings: [
        "Confirme espaço na tribo / estábulo antes de resgatar.",
        "Nem todas as espécies têm par L200 — só quando o teto de mercado permite.",
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
        "Validade típica: 30 dias a partir do resgate (preços e bônus: ver painel Benefícios por licença abaixo).",
        "Gamma / Beta / Alfa: bônus Timed Points a cada 30 min online (+25 / +50 / +75), somados ao Default (+25).",
        "Acesso a itens/kits ItensAlfa e outros com cadeado: Gamma→Gama+Delta, Beta→Beta+Gama, Alfa→Alfa+Beta (Descriptions do catálogo).",
        "Licença Nuvem (keyvault): cofre /upload · /download · /nuvem (até 250 pilhas) e envio ao Mercado P2P.",
        "Renovação restaura limites DefaultAmount dos kits do mesmo grupo de permissão.",
      ],
      warnings: [
        "Licença expirada remove o bônus Timed Points e o acesso a itens/kits que exigem o grupo.",
        "Na Nuvem, upload exige licença ativa; download de itens já guardados permanece permitido após expirar.",
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
    if (type === "dino" || (helpers && helpers.isDino && helpers.isDino(type))) {
      const level = Number(item.dinoLevel ?? item.dino_level ?? 1) || 1;
      return level === 200 ? "dinos200" : "dinos";
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
    if (category === "dinos" || category === "dinos200") {
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
    } else if (category === "dinos" || category === "dinos200") {
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
    if (t.timedBonus > 0) {
      const total = (t.defaultBonus || LICENSE_DEFAULT_BONUS) + t.timedBonus;
      const mins = t.cycleMinutes || LICENSE_CYCLE_MINUTES;
      return `+${t.timedBonus} Âmbar / ${mins} min · total ${total} com Default`;
    }
    return "Sem bônus Timed Points";
  }

  function licenseAccessMeta(t) {
    if (!t) return "";
    if (t.id === "keyvault") return "Cofre cluster + Mercado P2P";
    if (t.accessTiers && t.accessTiers.length) {
      return `Acesso catálogo: ${t.accessTiers.join(" + ")}`;
    }
    return `Grupo ${t.permissionGroup || t.label}`;
  }

  function renderLicenseTierGrid(activeId) {
    const tiers = Object.values(LICENSE_TIERS);
    const selected =
      activeId && LICENSE_TIERS[activeId] ? activeId : tiers[0] ? tiers[0].id : "Gamma";

    const tabs = tiers
      .map((t) => {
        const active = t.id === selected ? " is-active" : "";
        return `
      <button type="button" class="redeem-license-tab${active}"
        role="tab" aria-selected="${t.id === selected ? "true" : "false"}"
        data-license-tier="${esc(t.id)}"
        onclick="RedeemDocs.selectLicenseTierTab('${esc(t.id)}')">
        <span class="redeem-license-tab__name">${esc(t.label)}</span>
        <span class="redeem-license-tab__hint">${
          t.timedBonus > 0 ? `+${t.timedBonus}/ciclo` : "cofre"
        }</span>
      </button>`;
      })
      .join("");

    const panels = tiers
      .map((t) => {
        const hidden = t.id === selected ? "" : " hidden";
        const price =
          t.priceAmber != null
            ? `${formatAmberRef(t.priceAmber)} Âmbares (referência catálogo)`
            : "Preço conforme catálogo";
        const lis = (t.benefits || [])
          .map((b) => `<li>${esc(b)}</li>`)
          .join("");
        return `
      <div class="redeem-license-panel${hidden}" role="tabpanel"
        data-license-panel="${esc(t.id)}" ${t.id === selected ? "" : "hidden"}>
        <div class="redeem-license-panel__head">
          <div class="redeem-license-panel__title">${esc(t.label)}</div>
          <div class="redeem-license-panel__meta">
            ${t.durationDays} dias · ${esc(price)}
          </div>
          <div class="redeem-license-panel__chips">
            <span class="redeem-license-chip">${esc(licenseTimedMeta(t))}</span>
            <span class="redeem-license-chip redeem-license-chip--tek">${esc(
              licenseAccessMeta(t)
            )}</span>
          </div>
          <p class="redeem-license-panel__summary">${esc(t.summary)}</p>
        </div>
        <div class="redeem-license-panel__benefits">
          <div class="redeem-license-panel__benefits-title">Benefícios detalhados</div>
          <ul class="redeem-doc-block__list">${lis}</ul>
        </div>
        <p class="redeem-license-panel__source">Fonte: config.json / TimedPointsReward / regulamento §8.5–8.7</p>
      </div>`;
      })
      .join("");

    return `
      <div class="redeem-license-benefits" data-redeem-license-benefits>
        <div class="redeem-license-tabs" role="tablist" aria-label="Níveis de licença">${tabs}</div>
        <div class="redeem-license-panels">${panels}</div>
      </div>`;
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
