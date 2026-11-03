# Fazenda — persistência e integração Web Store

## Arquitetura vigente

O MySQL é a fonte compartilhada do catálogo e dos uploads da Fazenda. O plugin 0.1.10 lê o bloco `Database` de `ArkApi/Plugins/CustomShop/config.json` e grava diretamente no mesmo database utilizado pela Web Store. O backend do site consulta as tabelas `farm_*` e apresenta metadados em Minha Área. A senha do banco não vai ao navegador.

As tabelas da Nuvem (`player_cloud_inventory`, `player_cloud_items`) continuam isoladas e não são usadas pela Fazenda. A migração correspondente está em `plugin/arkshop_web/migrations/fazenda_mysql.sql`.

## Tabelas

- `farm_resource_catalog`: configuração/revisão publicada pelo plugin (`OutputQuantity`, `IntervalSeconds`, `StackSize`, capacidade, classe e habilitação).
- `farm_uploaded_resources`: blob e metadados do item-base enviado.
- `farm_player_resources`: estado individual e saldo legado sincronizado.
- `farm_produced_items`: esquema previsto para blobs reais por ciclo. A geração desses blobs ainda não está implementada na build 0.1.10.
- `farm_redemptions`, `farm_redemption_deliveries` e `farm_redemption_delivery_items`: pedidos, stacks/histórico e alocação dos blobs reservados. `/fazresgatar` foi conectado a essas linhas e confirma um stack por vez; o caminho ainda precisa de validação in-game.

## Compatibilidade HTTP temporária

As rotas `/api/plugin/farm/*` permanecem no backend para compatibilidade com builds antigas instaladas antes da 0.1.10. A versão 0.1.10 não as usa para persistir catálogo ou uploads. Não considere respostas HTTP 200 dessas rotas como evidência de que a build nova usa o caminho MySQL direto.

## Estado do fluxo

Minha Área já exibe taxas/intervalos do catálogo MySQL, lista uploads e só habilita agendamento quando há estoque com blobs em `farm_produced_items`. O site reserva os blobs por stack e libera reservas em cancelamentos. Como a geração por ciclo ainda não grava blobs em `farm_produced_items`, o fluxo completo e a retirada real ainda não podem ser validados.
