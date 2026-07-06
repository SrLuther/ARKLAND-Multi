# Dino Lab — Guia completo (ARKLAND)

| Campo | Valor |
|-------|-------|
| **Público** | Donos, admins, staff de suporte, operadores do cluster |
| **Versão** | 1.0 (MVP operacional) |
| **Atualizado** | 2026-07-06 |
| **Spec técnica** | [`DINO_LAB_SPEC.md`](DINO_LAB_SPEC.md) |
| **Plugin** | [`plugin/CustomDinoDeliver/`](../plugin/CustomDinoDeliver/) |

---

## Sumário

1. [O que é o Dino Lab](#1-o-que-é-o-dino-lab)
2. [Para quem serve](#2-para-quem-serve)
3. [Como funciona (visão geral)](#3-como-funciona-visão-geral)
4. [Pré-requisitos](#4-pré-requisitos)
5. [Instalação e configuração inicial](#5-instalação-e-configuração-inicial)
6. [Uso na Web Store (staff)](#6-uso-na-web-store-staff)
7. [Experiência do jogador](#7-experiência-do-jogador)
8. [Configurações e flags](#8-configurações-e-flags)
9. [Plugin CustomDinoDeliver](#9-plugin-customdinodeliver)
10. [Comandos RCON e reload](#10-comandos-rcon-e-reload)
11. [Estados do pedido e fila](#11-estados-do-pedido-e-fila)
12. [Compensações e tickets](#12-compensações-e-tickets)
13. [Cores e espécies](#13-cores-e-espécies)
14. [Troubleshooting](#14-troubleshooting)
15. [API (referência rápida)](#15-api-referência-rápida)
16. [O que está no MVP vs roadmap](#16-o-que-está-no-mvp-vs-roadmap)
17. [FAQ](#17-faq)

---

## 1. O que é o Dino Lab

O **Dino Lab** é a ferramenta **exclusiva para staff** do cluster ARKLAND que permite entregar dinossauros **customizados** a jogadores específicos — com nível, sexo, castração e **seis regiões de cor** — **fora** do catálogo da loja e **fora** do mercado P2P (Genoma).

| Canal | Quem usa | Cobra Âmbares? | Cores custom? |
|-------|----------|----------------|---------------|
| Loja web (`/shop`) | Jogadores | Sim | Não |
| Mercado P2P (Genoma) | Jogadores | Sim | Depende do listing |
| **Dino Lab** | **Staff** | **Não** | **Sim** |

Casos de uso típicos:

- Compensação de suporte (dino perdido por bug, rollback, etc.)
- Prêmio de evento PvP/PvE
- Entrega pontual acordada com a equipe
- Testes de breeding/cores em ambiente controlado

O jogador **não** monta o dino na web. Apenas um admin autenticado na Web Store preenche o formulário e enfileira a entrega.

---

## 2. Para quem serve

### Admin / dono do cluster

- Ativar o recurso, instalar o plugin em todos os mapas, sincronizar API keys
- Revisar histórico de entregas e volume por staff
- Definir políticas (ticket obrigatório, limites, etc.)

### Staff / moderador de suporte

- Criar pedidos vinculados a tickets de compensação
- Acompanhar status (`PENDENTE` → `ENTREGUE` / `FALHA`)
- Confirmar com o jogador que o cryopod chegou com as cores corretas

### Jogador receptor

- Precisa estar **online no mapa** onde o plugin está ativo (ou entrar no servidor depois)
- Recebe notificação in-game e cryopod no inventário (padrão)
- **Não** acessa o Dino Lab na web

---

## 3. Como funciona (visão geral)

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ Staff (Web)     │     │  arkshop_web     │     │ CustomDinoDeliver   │
│ Menu Dino Lab   │────▶│  fila MySQL      │◀────│ poll a cada ~60s    │
│ Nova entrega    │     │  orders          │     │ + ao logar jogador  │
└─────────────────┘     └────────┬─────────┘     └──────────┬──────────┘
                                 │                          │
                                 ▼                          ▼
                        item_type=custom_dino        Spawn + 6 cores
                        payload_json (spec)          + cryopod → jogador
```

**Importante:** o **CustomShop** (`CustomShop.dll`) **não** processa pedidos do Dino Lab. O plugin dedicado **`CustomDinoDeliver.dll`** usa rotas HTTP separadas (`/api/pending/custom-dino/*`).

Fluxo resumido:

1. Staff cria pedido na web → status `PENDENTE`
2. Plugin no servidor faz **claim** atômico → `ENTREGANDO`
3. Plugin spawna o dino, aplica cores, coloca em **cryopod** e entrega no inventário
4. Plugin confirma → `ENTREGUE` (ou `FALHA` + retry manual)

---

## 4. Pré-requisitos

| Componente | Obrigatório | Observação |
|------------|-------------|------------|
| **ARKLAND Multi** (app TEK) | Sim | Instalação de plugins e sync |
| **Web Store** (`arkshop_web`) | Sim | Banco MySQL/MariaDB com tabela `orders` |
| **CustomShop.dll** | Sim* | *Não entrega Dino Lab, mas compartilha API key e infra da loja |
| **CustomDinoDeliver.dll** | Sim | Um por mapa/servidor ASE |
| **ArkApi (ASE Server API)** | Sim | Base para qualquer plugin |
| **RCON** habilitado | Recomendado | Reload de config sem reiniciar mapa |
| Jogador online | Sim (na prática) | Pedido fica `PENDENTE` até o jogador estar no mapa |

---

## 5. Instalação e configuração inicial

### 5.1 Primeira vez — checklist

1. **Compilar ou obter** `CustomDinoDeliver.dll`  
   - Desenvolvimento: `plugin\CustomDinoDeliver\build_cl.bat`  
   - Release: incluído no build do ARKLAND Multi (`build.bat`)

2. **No app TEK** → aba **Loja / CustomShop**:
   - Clique em **🦕 Instalar Dino Lab** — copia a DLL para `ArkApi/Plugins/CustomDinoDeliver/` em **todos** os servidores cadastrados
   - Clique em **🔄 Aplicar em todos os plugins** — grava `WebApiUrl` e `WebApiKey` no `config.json` de cada mapa
   - Com servidores **rodando**, use **♻ Sync + Reload RCON (todos)** — envia `Shop.Reload` + `DinoDeliver.Reload`

3. **Na Web Store** → **Configurações**:
   - Marque **Ativar Dino Lab** (`custom_dino_enabled`)
   - Salve

4. **Verifique** na aba **Plugins** do TEK que cada servidor mostra `CustomDinoDeliver` instalado.

### 5.2 Estrutura no disco do servidor

```
ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomDinoDeliver/
├── CustomDinoDeliver.dll
├── PluginInfo.json
└── config.json          ← WebApiUrl, WebApiKey, poll, fallback
```

### 5.3 `config.json` do plugin (por mapa)

```json
{
  "WebApiUrl": "http://127.0.0.1:5177",
  "WebApiKey": "sua-chave-igual-ao-customshop",
  "PollIntervalSeconds": 60,
  "GroundFallbackOnFullInventory": true,
  "CryoItemPath": ""
}
```

| Campo | Descrição |
|-------|-----------|
| `WebApiUrl` | URL da Web Store acessível **do servidor de jogo** (mesma do CustomShop) |
| `WebApiKey` | Header `X-API-Key` — **mesma chave** do cluster (`settings.json` / loja) |
| `PollIntervalSeconds` | Intervalo do poll automático (mín. 15s; padrão 60) |
| `GroundFallbackOnFullInventory` | Se cryopod falhar (inventário cheio), spawna o dino ao lado do jogador |
| `CryoItemPath` | Blueprint do cryopod (vazio = cryopod vanilla Extinction) |

O TEK sincroniza `WebApiUrl` / `WebApiKey` ao usar **Aplicar em todos os plugins**. Não edite manualmente em cada mapa se já usa o sync.

---

## 6. Uso na Web Store (staff)

### 6.1 Acessar o Dino Lab

1. Faça login como **admin** na Web Store
2. No menu lateral (área admin), clique em **🧬 Dino Lab**
3. Se aparecer banner amarelo *“Dino Lab desabilitado”*, vá em **Configurações** e ative `custom_dino_enabled`

### 6.2 Nova entrega — passo a passo

Aba **Nova entrega**:

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| **Jogador (Steam ID64)** | Sim | 17 dígitos, começa com `7656119…` |
| **Ticket** | Condicional* | Ex.: `4521` ou `#4521` — vincula à compensação |
| **Espécie** | Sim | Lista vanilla homologada (catálogo de espécies do cluster) |
| **Nível** | Sim | 1–450 (padrão 150) |
| **Sexo** | Sim | Macho ou fêmea |
| **Castrado** | Não | Checkbox |
| **Cores (6 regiões)** | Sim | Índices **Obelisk** 0–255 por região |
| **Motivo** | Sim | Mínimo 10 caracteres — aparece no histórico e auditoria |

\* Se `custom_dino_require_ticket` estiver `true` em `settings.json`, o ticket passa a ser obrigatório.

Botões:

- **🚚 Entregar agora** — valida, enfileira pedido `PENDENTE` e mostra `order_id` (prefixo `cd_`)
- **Pré-visualizar JSON** — chama `/api/admin/custom-dino/validate` sem gravar

### 6.3 Histórico

Aba **Histórico** lista as últimas entregas com:

- Data, ID do pedido, Steam ID, espécie, cores, **status**, motivo

Status comuns: `PENDENTE`, `ENTREGANDO`, `ENTREGUE`, `FALHA`.

### 6.4 Limites

- **30 entregas por hora** por admin (rate limit no backend)
- Espécie sem blueprint homologado é **rejeitada** na validação
- Pedidos duplicados acidentais: cada clique em “Entregar” gera um **novo** `order_id`

---

## 7. Experiência do jogador

1. Staff enfileira o pedido enquanto o jogador está **offline** → pedido permanece `PENDENTE`
2. Quando o jogador **entra no mapa**:
   - Após ~8 segundos do login, o plugin tenta entregar
   - O poll automático também roda a cada ~60 segundos
3. Em caso de sucesso:
   - Mensagem verde: *“Dino customizado entregue em cryopod no seu inventário.”*
   - Notificação `[Dino Lab] N dino(s) customizado(s) entregue(s)!`
4. Inventário cheio:
   - Com fallback ativo: dino spawnado **ao lado** com aviso amarelo
   - Sem fallback: entrega falha; staff vê `FALHA` no histórico e pode reenviar

O jogador **não** precisa usar `/shop` nem resgatar na web — a entrega é **automática in-game**, diferente de itens de catálogo que passam pela fila do CustomShop.

---

## 8. Configurações e flags

Arquivo: `plugin/arkshop_web/settings.json` (ou via UI parcial).

| Flag | Padrão | UI | Efeito |
|------|--------|-----|--------|
| `custom_dino_enabled` | `false` | ✅ Checkbox em Configurações | Liga/desliga todo o Dino Lab |
| `custom_dino_require_ticket` | `false` | ❌ Só JSON | Exige `ticket_id` em toda entrega |
| `custom_dino_ground_fallback` | `true` | ❌ Só JSON | Propagado ao plugin no sync (`GroundFallbackOnFullInventory`) |
| `custom_dino_spawn_exact` | `false` | ❌ Só JSON | Bloqueia payloads com SpawnExact stats (fase futura) |

Exemplo para exigir ticket em compensações:

```json
{
  "custom_dino_enabled": true,
  "custom_dino_require_ticket": true,
  "custom_dino_ground_fallback": true
}
```

Salve o arquivo e reinicie a Web Store se necessário.

---

## 9. Plugin CustomDinoDeliver

### 9.1 Responsabilidades

| Função | Detalhe |
|--------|---------|
| Poll HTTP | `POST /api/pending/custom-dino/claim` |
| Spawn | `ArkApi::SpawnDino` com nível, tame, castração |
| Cores | 6 regiões via `ColorSetIndices` + `MulticastUpdateAllColorSets` |
| Entrega | Cryopod no inventário (mesmo layout de dados do mercado/cryo) |
| Confirmação | `POST .../delivered` ou `release` em falha |

### 9.2 O que o plugin **não** faz (MVP)

- SpawnExact (stats wild/tamed, imprint %) — planejado fase 3–4
- Presets salvos (“Rex evento vermelho”)
- Preview visual de cores (swatches Obelisk) — UI usa números 0–255
- Entrega em mapa diferente do que o jogador está online

### 9.3 Comandos in-game (debug)

| Comando | Quem | Efeito |
|---------|------|--------|
| `DinoDeliver.Reload` | Console / RCON | Recarrega `config.json` |
| `/dinopoll` | Chat (admin) | Força uma verificação de fila para o jogador |

### 9.4 Logs

ArkApi grava em log do servidor com prefixo `CustomDinoDeliver` / `DinoHttpClient` / `DinoDeliver`. Procure por:

- `claimed N custom dino order(s)`
- `delivered order cd_…`
- `failed to spawn` / `inventory full`

---

## 10. Comandos RCON e reload

Após alterar catálogo, API key ou `config.json` do Dino Lab:

1. **TEK** → **♻ Sync + Reload RCON (todos)**  
   Envia:
   - `Shop.Reload` (CustomShop)
   - `DinoDeliver.Reload` (CustomDinoDeliver)

2. Ou manualmente por servidor (RCON):
   ```
   DinoDeliver.Reload
   ```

Requisitos RCON no TEK: servidor com RCON habilitado, senha configurada, servidor **em execução** (o reload ignora mapas parados por padrão).

---

## 11. Estados do pedido e fila

```
PENDENTE ──claim──▶ ENTREGANDO ──sucesso──▶ ENTREGUE
     ▲                    │
     │                    └──falha──▶ release ──▶ PENDENTE (retry)
     │                    └──falha persistente ──▶ FALHA
```

| Status | Significado |
|--------|-------------|
| `PENDENTE` | Na fila; aguardando jogador online + plugin |
| `ENTREGANDO` | Plugin reservou; spawn em andamento |
| `ENTREGUE` | Cryopod/chão entregue; confirmado na API |
| `FALHA` | Erro registrado em `last_error`; staff deve investigar |

Cada pedido usa `item_type = custom_dino` e `order_id` com prefixo `cd_`. O payload completo fica em `payload_json` na tabela `orders`.

---

## 12. Compensações e tickets

### Playbook recomendado

1. Jogador abre ticket (perda de dino, bug, etc.)
2. Staff valida identidade e acordo (espécie, cores, nível)
3. No Dino Lab: preenche Steam ID, espécie, cores, **motivo** citando o ticket
4. Campo **Ticket**: número do ticket (ex. `4521`)
5. Pede ao jogador entrar no servidor e confirmar cryopod
6. Fecha o ticket referenciando o `order_id` (`cd_…`)

Com `custom_dino_require_ticket: true`, o passo 4 torna-se obrigatório.

O sistema pode gravar `original_order_id = ticket:#4521` no banco para busca reversa.

---

## 13. Cores e espécies

### Cores

- São **índices da paleta Obelisk/ASB**, não RGB hexadecimal
- **6 regiões** por espécie (corpo, detalhes, etc.)
- Valores válidos: **0–255** (MVP valida na web; espécie pode ter menos swatches visíveis in-game)
- Para descobrir índices: use [ARK Smart Breeding](https://github.com/cadon/ARKStatsExtractor) ou referência Obelisk do TEK

### Espécies

- Lista vem do catálogo homologado (`market_economy` + fallback do catálogo CustomShop)
- Apenas espécies com **blueprint_path** válido aparecem no select
- Mods: suporte futuro via allowlist; MVP foca **vanilla**

### Diferença vs “entrega admin” da loja

| | Jogadores & Entregas | Dino Lab |
|--|----------------------|----------|
| Rota | `/api/admin/deliver` | `/api/admin/custom-dino/deliver` |
| Item | ID do catálogo | Payload JSON custom |
| Plugin | CustomShop | CustomDinoDeliver |
| Cores | Não | Sim |

**Não** use a entrega genérica de itens para compensar dino colorido — use sempre o Dino Lab.

---

## 14. Troubleshooting

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| Banner “Dino Lab desabilitado” | Flag off | Configurações → ativar Dino Lab |
| Pedido eterno `PENDENTE` | Jogador offline ou plugin ausente | Jogador online no mapa; instalar DLL; ver logs |
| Pedido `PENDENTE` em um mapa só | Plugin não instalado **nesse** mapa | **Instalar Dino Lab** no TEK para todos os servidores |
| `401` / claim vazio | API key errada | Sync plugins; conferir `WebApiKey` no `config.json` |
| Cores erradas | Índice inválido para espécie | Conferir índices ASB; região pode estar `PreventColorization` |
| Cryopod não aparece | Inventário cheio | Esvaziar inventário ou ativar ground fallback |
| `rate_limit_exceeded` | >30 entregas/h por admin | Aguardar ou escalar com dono |
| `custom_dino_disabled` na API | Flag off | Ativar em settings |
| Reload não aplica | RCON off ou servidor parado | Ligar RCON; iniciar mapa; `DinoDeliver.Reload` |

### Verificação rápida

1. `CustomDinoDeliver.dll` existe em `Plugins/CustomDinoDeliver/`?
2. `config.json` tem URL e API key corretas?
3. `custom_dino_enabled: true` na web?
4. Jogador online no mapa certo?
5. Log do servidor mostra poll/claim?

---

## 15. API (referência rápida)

### Admin (sessão admin + Dino Lab ativo)

| Método | Rota | Uso |
|--------|------|-----|
| `POST` | `/api/admin/custom-dino/deliver` | Criar pedido |
| `POST` | `/api/admin/custom-dino/validate` | Validar payload sem gravar |
| `GET` | `/api/admin/custom-dino/species` | Listar espécies (`?vanilla_only=1`) |
| `GET` | `/api/admin/custom-dino/orders` | Histórico (`page`, `page_size`, `status`, `steam_id`) |
| `GET` | `/api/admin/custom-dino/orders/<id>` | Detalhe do pedido |
| `GET` | `/api/admin/custom-dino/meta` | Flags e status do módulo |

### Plugin (`X-API-Key`)

| Método | Rota | Uso |
|--------|------|-----|
| `POST` | `/api/pending/custom-dino/claim` | Body: `{"steam_id": "…"}` |
| `POST` | `/api/pending/custom-dino/delivered` | Body: `steam_id`, `order_ids`, `failures[]` |
| `POST` | `/api/pending/custom-dino/release` | Reabre pedidos após falha de spawn |

### Exemplo — criar entrega (curl)

```bash
curl -X POST "http://127.0.0.1:5177/api/admin/custom-dino/deliver" \
  -H "Cookie: session=…" \
  -H "Content-Type: application/json" \
  -d '{
    "steam_id": "76561198000000000",
    "species_key": "rex",
    "level": 150,
    "gender": "female",
    "neutered": false,
    "colors": [14, 14, 14, 0, 0, 0],
    "deliver_as": "cryopod",
    "note": "Compensação suporte ticket #4521 — Rex vermelho",
    "ticket_id": "4521"
  }'
```

---

## 16. O que está no MVP vs roadmap

### ✅ Disponível hoje (MVP)

- Web: menu Dino Lab, formulário, histórico, flag `custom_dino_enabled`
- Backend: fila `custom_dino`, `payload_json`, claim/delivered/release, auditoria
- Plugin: spawn, 6 cores, cryopod, fallback chão, poll + login
- TEK: instalar em todos os servidores, sync config, reload RCON conjunto

### 🚧 Roadmap (spec)

| Fase | Recurso |
|------|---------|
| 3 | Swatches visuais Obelisk, presets, mods allowlist |
| 4 | SpawnExact (stats/imprint), notificações avançadas, health check de pedidos presos |
| — | Botão “Enviar para Dino Lab” a partir do TEK SpawnExact |
| — | Integração ticket com pré-preenchimento na UI |

Detalhes de produto e arquitetura: [`DINO_LAB_SPEC.md`](DINO_LAB_SPEC.md).

---

## 17. FAQ

**O jogador paga Âmbares?**  
Não. É entrega administrativa gratuita.

**Posso usar `/api/admin/deliver` com item de dino do catálogo?**  
Isso entrega via CustomShop **sem** cores custom. Para compensação colorida, use o Dino Lab.

**Preciso reiniciar o servidor após instalar?**  
Recomendado reiniciar ou carregar o plugin via ArkApi na primeira instalação. Para mudanças de URL/key, `DinoDeliver.Reload` via RCON basta.

**Funciona com jogador em outro mapa do cluster?**  
O pedido é claimado pelo plugin do mapa onde o jogador está **online**. Se o cluster tem vários mapas, **todos** precisam do plugin instalado.

**Quantos dinos por pedido?**  
Um por `order_id`. Para vários dinos, crie vários pedidos.

**O histórico é auditável?**  
Sim — eventos `custom_dino_deliver` e `custom_dino_deliver_failed` em `audit_events`, além da tabela `orders`.

**Qual a diferença para SpawnExact no TEK?**  
SpawnExact no TEK é ferramenta manual/local. Dino Lab enfileira para o jogador receber automaticamente via web + plugin, com histórico centralizado.

---

## Documentos relacionados

| Documento | Conteúdo |
|-----------|----------|
| [`DINO_LAB_SPEC.md`](DINO_LAB_SPEC.md) | Spec de produto, arquitetura, fases, APIs completas |
| [`dino_custom_colors_delivery_spec.md`](dino_custom_colors_delivery_spec.md) | Pesquisa técnica ARK API / cryopod |
| [`plugin/CustomDinoDeliver/README.md`](../plugin/CustomDinoDeliver/README.md) | Build e endpoints do plugin |
| [`PROJETO_SISTEMA_SUPORTE_TICKETS.md`](PROJETO_SISTEMA_SUPORTE_TICKETS.md) | Fluxo de tickets e compensações |

---

*Dúvidas operacionais: confira logs do plugin no mapa e o histórico Dino Lab na web antes de reenviar o mesmo pedido.*
