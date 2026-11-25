# Lumo — Central de comunicação

Implementação local da área administrativa Lumo, planejada para o ARKLAND Multi 1.12.25. A funcionalidade integra-se ao portal existente e usa autenticação administrativa Steam.

## Interface

- A página `/admin/lumo` e as APIs `/api/admin/lumo/*` exigem administrador.
- A área traz editor Markdown, prévia segura, contador de limites, toolbar, modelos, rascunho local, filtros de histórico e integração.
- Rascunhos usam `localStorage` apenas para o conteúdo do comunicado; URL e token do webhook nunca são gravados nele.
- O avatar oficial original foi copiado sem alterações para `plugin/arkshop_web/static/lumo-avatar.png`, servido como `https://arkland.com.br/lumo-avatar.png`.

## Configuração do Discord

1. Abra a aba **Configurações** da página Lumo.
2. Informe a URL `https://discord.com/api/webhooks/ID/TOKEN` e salve.
3. Use **Verificar conexão sem publicar**. A verificação lê os metadados do webhook; ela não envia mensagem.
4. Confira o ID do canal reportado e confirme administrativamente que é o destino pretendido.
5. Ao publicar, revise a confirmação explícita. Não foi implementado envio de teste automático.

A URL é persistida em `settings.json` pelo mecanismo existente e criptografada com a chave persistente `ARKSHOP_WEB_SECRET` (ou com a chave resolvida pela instalação). A área recusa gravar a credencial se a chave de criptografia não estiver disponível ou se a rotina não produzir o prefixo cifrado esperado. A substituição e remoção são operações administrativas auditadas. Não existe nova variável de ambiente nem migração SQL.

## Publicação e histórico

Todas as publicações são embeds com nome `Lumo`, avatar oficial, cor `#00FFFF`, rodapé institucional, timestamp UTC e `allowed_mentions.parse=[]`. A URL do webhook só é chamada pelo backend; destinos são limitados a `discord.com`, HTTPS e caminho de webhook válido, sem redirecionamento. O envio usa `wait=true`, timeout finito e chave de idempotência persistente. Em timeout ou resposta ambígua, o painel alerta para conferir o histórico antes de tentar de novo.

O histórico usa a tabela administrativa existente `audit_events`, sem criar tabela ou executar migração. Ele guarda conteúdo e resultado da tentativa, identificadores disponíveis do Discord e administrador responsável; nunca guarda o token. A lista permite busca, filtros por status, administrador e período, paginação, cópia e reutilização no editor. Reutilizar não publica.

Os limites aplicados pelo servidor são título 256, descrição 4.096 e total de 6.000 caracteres textuais do embed (incluindo rodapé). A interface não trunca conteúdo. Erros e falhas são apresentados em português; 429 respeita o `retry_after`/`Retry-After` sem tentativas automáticas.

## Estado e publicação

Os testes locais simulam a API Discord e não enviam mensagens reais. Nenhum webhook foi configurado neste trabalho, portanto a conexão, a publicação e o canal de destino ainda precisam de configuração e validação por um administrador. Esta implementação não foi publicada no site de produção.
