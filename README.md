# ARKLAND BR Store

Loja online para venda de kits e itens do ARK: Survival Evolved com:
- Autenticação Steam (OpenID 2.0 via NextAuth)
- Pagamento via PIX, Cartão de Crédito e Débito (MercadoPago)
- Entrega automática no servidor via RCON

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend + Backend | Next.js 15 (App Router) |
| Banco de dados | SQLite via Prisma (troque por PostgreSQL em produção) |
| Autenticação | NextAuth.js v4 + Steam OpenID |
| Pagamentos | MercadoPago |
| Entrega | rcon-client (RCON do servidor ARK) |
| UI | Tailwind CSS v4 + Radix UI |

## Configuração inicial

### 1. Clone e instale as dependências

```bash
npm install
```

### 2. Crie o `.env.local` a partir do exemplo

```bash
cp .env.example .env.local
```

Edite `.env.local` com seus valores reais:

| Variável | Como obter |
|---|---|
| `NEXTAUTH_SECRET` | `openssl rand -base64 32` |
| `STEAM_API_KEY` | https://steamcommunity.com/dev/apikey |
| `MP_ACCESS_TOKEN` | https://www.mercadopago.com.br/developers/panel |
| `MP_PUBLIC_KEY` | Mesmo painel acima |
| `ARK_RCON_HOST` | IP do seu servidor ARK |
| `ARK_RCON_PORT` | Porta RCON (padrão: 27020) |
| `ARK_RCON_PASSWORD` | Definido no `GameUserSettings.ini` |

### 3. Configure o banco de dados

```bash
npm run db:push    # Cria as tabelas
npm run db:seed    # Popula com categorias e produtos de exemplo
```

### 4. Rode em desenvolvimento

```bash
npm run dev
```

Acesse http://localhost:3000

## Configuração do servidor ARK (RCON)

No arquivo `GameUserSettings.ini` do servidor:

```ini
[ServerSettings]
RCONEnabled=True
RCONPort=27020
ServerAdminPassword=SUA_SENHA_AQUI
```

## Comandos RCON dos produtos

Ao cadastrar um produto, use `{steamid}` como placeholder para o SteamID do comprador:

```
GiveItemToPlayer {steamid} "Blueprint'/Game/...'" 1 0 0
AddExperience {steamid} 1000 0 1
```

## Webhooks (Produção)

Configure a URL do webhook no painel do MercadoPago:

```
https://SEU_DOMINIO.com/api/payments/webhook
```

## Usuário Admin

Para tornar um usuário admin, execute no banco:

```sql
UPDATE User SET role = 'ADMIN' WHERE steamId = 'SEU_STEAM_ID';
```

Ou via Prisma Studio:

```bash
npm run db:studio
```

## Scripts disponíveis

| Script | Descrição |
|---|---|
| `npm run dev` | Inicia em desenvolvimento |
| `npm run build` | Gera build de produção |
| `npm run start` | Inicia servidor de produção |
| `npm run db:push` | Aplica schema ao banco |
| `npm run db:migrate` | Cria migration |
| `npm run db:seed` | Popula dados de exemplo |
| `npm run db:studio` | Interface visual do banco |
