# Homologação 0.8-dev — somente servidor 05

## Estado entregue

Esta build conta estruturas observadas e registra colocações concluídas/remoções. Não bloqueia construções. Não remove nem modifica atores existentes. O inventário parcial não é publicado como contagem autoritativa no site e não é usado pelo motor de enforcement.

DLL x64: 750.080 bytes, SHA-256 `52402A843C1E0367DAF90CE59892EDCD6AFB216D10E446E36C4F430F4B576746`.

Instalação: DLL, metadados, configuração, estado derivado e outbox permanecem dentro de `ShooterGame/Binaries/Win64/ArkApi/Plugins/StructureLimits/`. Backup da 0.6-dev preservado fora da pasta do plugin.

## Teste do jogador

1. Conectar ao mapa 05 e executar `/limites`. Registrar a contagem observada inicial.
2. Colocar uma fundação de madeira. Executar `/limites`: a contagem deve aumentar uma unidade.
3. Recolher essa fundação. Executar `/limites`: deve voltar ao valor inicial.
4. Colocar novamente e demolir. Executar `/limites`: deve voltar ao valor inicial novamente.
5. Repetir com outro blueprint vanilla ou modded. Não precisa gastar materiais raros.

Se o inventário inicial ainda estiver varrendo ou a identidade da tribo não tiver sido atribuída, aguardar a primeira varredura após conectar. O comando avisa que a contagem é observada; não interpretar esse valor como inventário completo do save.

## Conferência administrativa

RCON `StructureLimits.Status` retorna versão, instância, número de registros, removidos neste boot, scans concluídos, duplicidade/conflitos, saúde do worker e flags explícitas `complete_inventory=false` / `enforcement=false`.

Para cada ação, comparar IDs no log e eventos duráveis:

- `placement_confirmed`: original `FinalStructurePlacement` retornou sucesso; não usar `final-check` como evidência de construção.
- `removed`: remove somente ID presente; repetição não diminui outro registro nem gera contagem negativa.
- `position`: XYZ, latitude e longitude do SDK. Conferir com GPS no mesmo lugar.
- `actor_steam_id` é a pessoa que colocou quando o controlador está disponível; propriedade histórica não é inventada.
- Ausência em uma coleção residente/stasis não gera remoção. A limpeza do mundo suspende a observação antes do teardown.

## Verificações locais

23 casos standalone passaram com MSVC/C++20, incluindo reservas, licenças, isolamento, snapshots, outbox, novos registros observados, reatribuição e journal assíncrono. A DLL também compilou e vinculou com o SDK do projeto. Esses testes não substituem a sequência em jogo nem validam o consumo de materiais.

## Próximos critérios para fiscalização

- Provar cobertura do save, das estruturas fora da região do jogador e dos estados descarregados.
- Comparar eventos de remoção vanilla/modded e decay com os IDs efetivamente ausentes do mundo.
- Validar veto antes de qualquer consumo e confirmar cancelamento das reservas.
- Conectar o inventário validado ao motor de regras e à sincronização remota com confirmação idempotente.

Nenhuma dessas pendências pode ser contornada marcando artificialmente o snapshot parcial como completo.
