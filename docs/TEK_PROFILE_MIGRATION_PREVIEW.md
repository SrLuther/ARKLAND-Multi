# Fase 2A/2B — Compatibilidade e pré-visualização de perfis TEK

Este material descreve a matriz gerada a partir das declarações atuais de `ServerConfig`, `ServerGameSettings`, `ServerAdvancedSettings`, `ClusterConfig` e `AsmServerConfig`, e o utilitário de pré-visualização. A ferramenta não migra perfis e não executa operações do aplicativo.

## Arquivos

- Matriz JSON completa, campo a campo: [TEK_COMPATIBILITY_MATRIX.json](./TEK_COMPATIBILITY_MATRIX.json).
- Leitor de pré-visualização: [tek_migration_preview.py](../src/diagnostics/tek_migration_preview.py).
- Testes isolados: [test_tek_migration_preview.py](../tests/test_tek_migration_preview.py).

A matriz tem uma linha por campo clássico, inclusive os membros das estruturas aninhadas. Cada linha registra caminho, tipo de origem, finalidade indicada no modelo, padrão, destino candidato e tipo esperado, transformação, compatibilidade, risco, dependências e estado da decisão. “Destino candidato” não significa que a conversão foi aprovada.

## Classificações

- `direct_equivalence_validated`: correspondência básica validada por função e tipo no inventário; isso aprova somente o mapeamento, não uma migração real.
- `equivalence_with_transform`: há destino identificado, mas exige transformação e teste.
- `partial_equivalence`: cobre somente parte do comportamento ou muda o escopo dos dados.
- `candidate_requires_review`: há campo de nome igual, mas a semântica ainda precisa ser conferida.
- `no_equivalent`: não foi identificado destino equivalente. Valor não padrão bloqueia uma futura migração segura.

Há 318 linhas na matriz atual: 202 candidatas que exigem revisão, 17 sem equivalente, 67 com transformação, 22 parciais e 10 mapeamentos diretos validados. Isso é intencional: não descartar dados é mais importante que produzir uma elegibilidade otimista.

Exemplos:

| Campo clássico | Destino candidato | Classificação | Motivo |
|---|---|---|---|
| `id` | `id` | Direto validado | Mesmo papel como identificador de perfil; colisões ainda bloqueiam a prévia. |
| `map` | `server_map` | Transformação | Nome do mapa precisa estar normalizado/validado. |
| `backup_enabled` | `ConfigManager.config.backup.auto_backup` | Parcial | O destino TEK atual é global, enquanto a origem é por servidor. |
| `rcon_password` | `admin_password` | Parcial | O bridge TEK usa fallback de senha, mas a equivalência e o tratamento do segredo exigem revisão. |
| `mod_ini_configs` | — | Sem equivalente | O TEK tem INI customizado e manifesto, mas o modelo de propriedade por mod não foi comprovado. |
| `battlemetrics_id` | — | Sem equivalente | O callback TEK `_on_bm_update` não tem implementação funcional identificada. |

## Executar a prévia

Ative o ambiente Python do projeto. A ferramenta exige os caminhos dos dois arquivos; não procura automaticamente dados de produção.

No PowerShell, para exibir JSON na tela:

```powershell
& .\.venv\Scripts\python.exe -m src.diagnostics.tek_migration_preview `
  --classic "$env:APPDATA\ARKLAND-ServerManager\servers.json" `
  --tek "$env:APPDATA\ARKLAND-ServerManager\asm_servers.json"
```

Para escrever um relatório Markdown em um caminho novo já existente:

```powershell
& .\.venv\Scripts\python.exe -m src.diagnostics.tek_migration_preview `
  --classic "$env:APPDATA\ARKLAND-ServerManager\servers.json" `
  --tek "$env:APPDATA\ARKLAND-ServerManager\asm_servers.json" `
  --format markdown `
  --out "$env:TEMP\arkland-tek-preview.md"
```

O caminho de saída precisa ser informado e ainda não existir. A ferramenta não cria pastas e não sobrescreve arquivos. Para gerar somente a matriz atualizada a partir das dataclasses:

```powershell
& .\.venv\Scripts\python.exe -m src.diagnostics.tek_migration_preview `
  --matrix-only --out .\docs\TEK_COMPATIBILITY_MATRIX.json
```

Esse último comando falha se o arquivo existir; para atualização, revise explicitamente o destino e substitua a matriz por um processo controlado fora da análise de perfis.

## O que a ferramenta lê e protege

O utilitário lê os dois JSONs de perfil informados, opcionalmente `clusters.json`, e as declarações Python das dataclasses, por meio de AST. Não importa `ConfigManager`, `AsmConfigManager`, `ServerManager` ou `AsmServerManager`; não abre INIs nem banco, não salva perfil, não inicia/para servidor, não cria diretórios e não importa dados entre repositórios.

O relatório lista valores de caminho, nome e ID porque são necessários para o diagnóstico. Não inclui valores de campos de perfil; lista somente nomes de campos alterados e sinaliza quais são sensíveis. Senhas RCON/admin, tokens, webhooks e campos parecidos não são serializados.

O estado do caminho físico é observado **na máquina em que a prévia roda**. Se o JSON veio de produção e o diretório não está montado no computador de análise, o relatório indicará que não foi possível verificar localmente; não inferirá que a instalação de produção inexiste. Caminhos Windows são normalizados lexicalmente (separadores, caixa e segmentos `.`/`..`); quando acessível, também é tentada a identidade do diretório pelo filesystem. Caminhos relativos permanecem não resolvidos.

Estados da prévia:

- `READY_FOR_FUTURE_MIGRATION`: nenhuma pendência foi encontrada nos campos não padrão analisados. Não autoriza nem executa migração.
- `REVIEW_REQUIRED`: há transformação/semântica pendente ou caminho que não pôde ser validado.
- `BLOCKED`: há colisão, campo obrigatório inválido, campo desconhecido ou valor não padrão sem destino.

Campos desconhecidos e dados TEK não reconhecidos em um perfil correspondente bloqueiam a elegibilidade, evitando descarte silencioso. Uma entrada JSON que não seja objeto é registrada como conflito de formato.

## Exemplo fictício

Entrada de exemplo (conteúdo fictício, fora do arquivo de dados real):

```json
[{"id":"classic-demo","name":"Servidor Demo","install_dir":"C:\\ARK\\Demo","map":"Ragnarok","battlemetrics_id":"12345"}]
```

Trecho representativo do diagnóstico:

```json
{
  "migration_performed": false,
  "classic_profile_previews": [{
    "id": "classic-demo",
    "name": "Servidor Demo",
    "eligibility": "BLOCKED",
    "changed_fields": [
      {"field": "battlemetrics_id", "compatibility": "no_equivalent", "value_included": false},
      {"field": "map", "compatibility": "equivalence_with_transform", "value_included": false}
    ],
    "conflicts_and_pending_items": [
      {"code": "nondefault_field_without_destination:battlemetrics_id", "severity": "blocker"},
      {"code": "nondefault_fields_need_semantic_review", "severity": "review"}
    ]
  }]
}
```

Os valores das configurações não aparecem no relatório. A indicação `BLOCKED` significa que um futuro migrador não deve prosseguir sem resolver o campo sem destino; não significa que a ferramenta alterou qualquer dado.

## Limitações e decisões pendentes

### Repositório compartilhado de clusters

`ConfigManager` mantém os perfis compartilhados em `clusters.json`. A prévia aceita esse arquivo opcional por `--clusters`; quando fornecido, verifica referências `cluster_profile_id` e IDs duplicados sem instanciar o gerenciador. Se houver referência clássica a cluster e o arquivo não for informado, o perfil fica em `REVIEW_REQUIRED`. Um ID referenciado que não exista no arquivo informado bloqueia o perfil.

Exemplo PowerShell:

```powershell
& .\.venv\Scripts\python.exe -m src.diagnostics.tek_migration_preview `
  --classic "$env:APPDATA\ARKLAND-ServerManager\servers.json" `
  --tek "$env:APPDATA\ARKLAND-ServerManager\asm_servers.json" `
  --clusters "$env:APPDATA\ARKLAND-ServerManager\clusters.json"
```

- A matriz é uma avaliação estática do modelo e dos caminhos auditados; não substitui teste funcional de cada configuração em um servidor ARK.
- As 74 correspondências de nome encontradas anteriormente não foram promovidas em massa a equivalências. A ferramenta mantém as não verificadas como revisão.
- O caminho de instalação pode não estar acessível no computador de análise. A comparação textual normalizada não prova identidade física quando os diretórios estão inacessíveis.
- `ConfigManager` ainda é necessário para configurações globais e perfis compartilhados; os campos de backup por servidor não podem ser reduzidos silenciosamente a opções globais.
- `mod_ini_configs`, tarefas agendadas, BattleMetrics e histórico têm lacunas documentadas na matriz.
- A ferramenta não sincroniza nem migra o manifesto INI e não altera `write_ini`, `ArkIniManager`, edição manual, importação ou sincronização de INIs. Esses itens pertencem à futura fase 2D.
- As 15 falhas da Web Store permanecem pendências secundárias; esta implementação não toca nessas regras ou testes.

## Testes e critério de conclusão

Os testes ficam isolados em diretórios temporários e cobrem perfis clássicos/TEK, ausência de correspondência, IDs e caminhos duplicados, normalização Windows, caminho relativo/ausente, campos sem destino ou com transformação, backup, agendamento, cluster, configuração de mod, credenciais, JSON incompleto, hashes dos arquivos antes/depois, ausência de gravação INI, ausência de carregamento de gerenciadores de servidor, determinismo e recusa de sobrescrita.

Esta etapa conclui o mapeamento estrutural e oferece diagnóstico repetível. Não conclui a migração: os mapeamentos pendentes precisam ser decididos e a futura fase 2C precisa comprovar paridade funcional antes de qualquer conversão real.
