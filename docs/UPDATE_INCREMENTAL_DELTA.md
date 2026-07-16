# UPDATE_INCREMENTAL_DELTA

## Resumo

Hoje o ARKLAND publica e instala atualizacoes como um pacote completo:

- `src/updater.py` le `version.json` remoto e consome apenas `download_url`
- `arkland_updater.py` baixa o instalador inteiro (`ARKLAND-Multi-Setup-vX.Y.Z.exe`)
- `setup.iss` instala os binarios novamente via Inno Setup
- `_release.ps1` publica uma release GitHub com um unico asset principal: o instalador

Esse fluxo funciona, mas tem um custo alto para patches pequenos:

- redownload completo mesmo quando mudaram poucos arquivos
- tempo maior de atualizacao
- consumo desnecessario de banda
- acoplamento forte entre "instalar do zero" e "atualizar patch"

Objetivo desta proposta: manter o instalador completo para instalacao limpa e compatibilidade, mas adicionar um caminho de **update incremental/delta** em que o cliente baixa apenas os arquivos alterados entre a versao local e a versao remota.


## Estado Atual Observado no Repo

### Pipeline de release

- `_release.ps1`
  - valida changelog e versao
  - atualiza `src/version.py`, `version.json` e `setup.iss`
  - roda `build.bat`
  - faz commit/push
  - cria GitHub Release e envia o instalador completo
- `build.bat`
  - gera `dist\ARKLAND-ServerManager.exe`
  - gera `dist\ARKLAND-Updater.exe`
  - gera `dist\ARKLAND-WebStore.exe`
  - roda o Inno Setup com `setup.iss`
- `setup.iss`
  - instala hoje pelo menos:
    - `dist\ARKLAND-ServerManager.exe`
    - `dist\ARKLAND-Updater.exe`
    - `dist\ARKLAND-WebStore.exe`
    - `setup_db.sql`
    - `setup_db.bat`

### Componentes reais relevantes

O empacotamento atual ja sugere uma divisao natural para update incremental:

- **core app**
  - `dist\ARKLAND-ServerManager.exe`
  - arquivos de apoio empacotados em `ARKLAND-Multi.spec`
- **helper updater**
  - `dist\ARKLAND-Updater.exe`
- **web store**
  - `dist\ARKLAND-WebStore.exe`
  - bundle de `plugin/arkshop_web/static`
  - bundle de `plugin/arkshop_web/data`
- **plugins**
  - `plugin/CustomShop/bin/CustomShop.dll`
  - `plugin/CustomShop/bin/PluginInfo.json`
  - `plugin/CustomDinoDeliver/bin/CustomDinoDeliver.dll`
  - `plugin/CustomDinoDeliver/bin/PluginInfo.json`
  - tambem ha dependencia de `plugin/CustomShop/bin/libmariadb.dll` e `plugin/CustomShop/bin/z.dll`
- **assets/UI**
  - `ig\...`
- **catalogo/assets pesados**
  - `plugin/arkshop_web/static/species/icons/**`
  - `plugin/arkshop_web/static/catalog/**`
  - ha centenas de arquivos nesse grupo, o que o torna o melhor candidato a externalizacao ou versionamento separado

### Semantica atual de update

- `src/config_manager.py` aponta por padrao para `https://raw.githubusercontent.com/SrLuther/ARKLAND-Multi/main/version.json`
- `src/updater.py` espera um JSON simples com:
  - `version`
  - `date`
  - `download_url`
  - `changelog`
- o cliente nao compara arquivos locais vs remotos; ele apenas detecta versao nova e baixa o instalador inteiro


## Problema

O modelo atual trata qualquer mudanca como se exigisse reinstalacao completa. Isso e aceitavel para:

- instalacao inicial
- reparo manual
- fallback de emergencia

Mas e subotimo para atualizacoes frequentes do ARKLAND, especialmente quando:

- apenas `ARKLAND-ServerManager.exe` mudou
- apenas `ARKLAND-WebStore.exe` mudou
- apenas um plugin `.dll` mudou
- apenas assets do catalogo ou imagens de dinos mudaram

Na pratica, o maior desperdicio tende a vir de:

1. bundling repetido de componentes independentes
2. assets estaticos volumosos do Web Store
3. necessidade de trocar executaveis em uso no Windows


## Objetivos

- Implementar um sistema de update incremental orientado a **manifest + arquivos por componente**
- Baixar somente arquivos alterados entre a versao local e a remota
- Preservar o instalador completo atual como caminho de fallback e instalacao limpa
- Melhorar tempo de patch update e reduzir banda
- Permitir rollback seguro se a aplicacao do patch falhar
- Separar melhor componentes com ciclos de mudanca diferentes
- Preparar externalizacao futura de assets pesados


## Nao Objetivos

- Nao projetar binary diff por bloco estilo `bsdiff` nesta primeira fase
- Nao remover o instalador Inno Setup atual
- Nao reescrever todo o empacotamento PyInstaller agora
- Nao suportar update hot-swap sem fechar processos em uso
- Nao resolver ainda sincronizacao de dados de usuario em `%APPDATA%`
- Nao introduzir obrigatoriamente assinatura de codigo Authenticode nesta fase


## Proposta de Arquitetura

## 1. Manifesto de release por versao

Cada release passa a publicar, alem do instalador completo, um manifesto estruturado por versao, por exemplo:

- `releases/v1.10.48/manifest.json`
  ou
- asset GitHub Release `manifest-v1.10.48.json`

Campos recomendados:

```json
{
  "schema_version": 1,
  "app_id": "arkland-multi",
  "version": "1.10.48",
  "channel": "stable",
  "published_at": "2026-07-16T00:00:00Z",
  "full_installer_url": "https://github.com/.../ARKLAND-Multi-Setup-v1.10.48.exe",
  "bootstrap_min_version": "1.10.48",
  "components": [
    {
      "name": "core",
      "version": "1.10.48",
      "files": [
        {
          "path": "ARKLAND-ServerManager.exe",
          "size": 12345678,
          "sha256": "..."
        },
        {
          "path": "ARKLAND-Updater.exe",
          "size": 2345678,
          "sha256": "..."
        }
      ]
    }
  ]
}
```

Campos por arquivo:

- `path`: caminho relativo no diretorio de instalacao
- `size`
- `sha256`
- `url` opcional por arquivo, se nao for derivado de uma raiz comum
- `component`
- `required`: `true/false`
- `replace_mode`: `inplace`, `restart_required`, `move_on_reboot`

Campos por componente:

- `name`: `core`, `updater`, `webstore`, `plugins-customshop`, `plugins-customdinodeliver`, `assets-ui`, `assets-species`
- `version`
- `channel`
- `base_url` para download dos arquivos
- `files`

### Opiniao

Nao recomendo um manifesto unico "flat" sem componentes. O agrupamento por componente melhora:

- progresso de UX
- futuro cache/CDN
- update parcial
- troubleshooting
- politica de rollback


## 2. Manifesto local no cliente

O cliente deve manter um manifesto local do que esta instalado, separado de `version.json`, por exemplo:

- `%APPDATA%\ARKLAND-ServerManager\installed_manifest.json`

Esse manifesto local nao substitui a versao do app; ele registra o estado material dos arquivos instalados:

- versao instalada
- canal
- lista de arquivos conhecidos
- hash local validado no momento da instalacao/update
- timestamp da ultima atualizacao

### Por que nao confiar apenas na versao?

Porque o usuario pode ter:

- instalacao parcialmente corrompida
- arquivos faltando
- mistura de versoes apos falha/interrupcao
- reinstalacao manual de um unico exe

O manifesto local permite comparar **estado real** e nao apenas `version string`.


## 3. Comparacao local vs remoto

Fluxo de patch update:

1. cliente baixa `manifest.json` remoto
2. cliente carrega `installed_manifest.json` local
3. se o manifesto local nao existir, cai para:
   - reconstruir inventario local por hash dos arquivos conhecidos, ou
   - oferecer full reinstall / full repair
4. cliente compara por `path + sha256`
5. gera plano de update:
   - `download`: arquivo ausente ou hash diferente
   - `skip`: hash igual
   - `delete`: arquivo presente localmente mas removido do manifesto remoto
   - `defer`: arquivo bloqueado e dependente de restart

### Recomendacao pratica

Primeiro release incremental deve trabalhar com **full-file replacement**, nao com delta binario. Ja entrega o ganho grande, porque o custo maior hoje e baixar o pacote completo.


## 4. Changed-files download only

O cliente baixa apenas os arquivos em `download`.

Ordem recomendada:

1. arquivos de suporte nao executaveis
2. plugins/dlls
3. webstore
4. core executables
5. updater helper por ultimo, com estrategia especial

Downloads devem ir para staging:

- `%LOCALAPPDATA%\ARKLAND\updates\<version>\staging\...`

Cada arquivo baixado deve ser validado por:

- tamanho esperado
- `sha256`

Se qualquer validacao falhar:

- abortar aplicacao
- manter instalacao atual intacta
- oferecer retry ou fallback para full installer


## 5. Staging, integridade, troca atomica e rollback

### Staging

Nunca baixar direto para `{app}`. O fluxo deve ser:

1. baixar para staging
2. validar tudo
3. montar plano de aplicacao
4. aplicar update

### Integridade

Validacoes minimas obrigatorias:

- HTTPS
- `sha256` por arquivo
- tamanho

### Troca atomica

No Windows, "atomico" aqui significa:

- gravar arquivo novo como temporario
- renomear o antigo para backup
- renomear o novo para o nome final

Para um unico arquivo:

1. `foo.exe` atual -> `foo.exe.bak`
2. `foo.exe.new` -> `foo.exe`
3. validar existencia/abertura minima
4. remover backup ao final do update inteiro

### Rollback

Se qualquer arquivo critico falhar durante a fase de aplicacao:

1. parar aplicacao do restante
2. restaurar backups ja substituidos
3. marcar update como falho
4. manter registro de diagnostico

Arquivos de rollback devem ficar em algo como:

- `%LOCALAPPDATA%\ARKLAND\updates\<version>\rollback\...`

### Opiniao

Rollback deve ser por **janela de update**, nao por arquivo isolado. Ou aplica o conjunto inteiro com sucesso, ou reverte tudo o que ja foi trocado.


## 6. Separacao por componentes

Proposta de componentes para o ARKLAND:

### Core App

Escopo inicial:

- `ARKLAND-ServerManager.exe`
- `setup_db.sql`
- possiveis arquivos auxiliares pequenos ligados ao app

### Updater Helper

Escopo:

- `ARKLAND-Updater.exe`

Observacao:

- esse componente merece tratamento especial porque o proprio updater pode estar em execucao durante a troca

### Plugins

Separar pelo menos em:

- `plugins-customshop`
  - `plugins\CustomShop.dll`
  - `plugins\customshop\PluginInfo.json`
  - dependencias como `libmariadb.dll`, `z.dll`
- `plugins-customdinodeliver`
  - `plugins\CustomDinoDeliver.dll`
  - `plugins\customdino\PluginInfo.json`

### Web Store

Separar:

- `ARKLAND-WebStore.exe`
- `static/**`
- `data/**`
- eventualmente `version.json` se continuar sendo empacotado para exibicao interna

### Assets/UI

Separar:

- `ig\...`

### Heavy Assets

Separar fortemente:

- `plugin/arkshop_web/static/species/icons/**`
- `plugin/arkshop_web/static/catalog/**`

Esses assets devem evoluir para:

- componente proprio versionado
- pacote opcional
- ou distribuicao via CDN/static host

### Opiniao

O maior ganho de medio prazo nao vem de otimizar o exe principal; vem de tirar os assets pesados do caminho do patch comum.


## 7. Assets pesados: versionamento separado / pacotes opcionais

Para imagens de dinos e assets similares, a recomendacao e:

### Opcao recomendada

- manifesto principal referencia um componente `assets-species`
- esse componente tem versao propria, por exemplo `species-2026-07-16.1`
- o cliente so baixa quando essa versao muda

### Opcao complementar

- mover esses assets para host estatico/CDN
- `ARKLAND-WebStore.exe` e/ou o servidor web usa URLs de assets externos

### Beneficios

- patches de codigo deixam de carregar centenas de imagens
- invalida cache apenas quando o pacote de assets muda
- caminho mais simples para escalar Web Store

### Cuidado

Se a Web Store precisa funcionar totalmente offline/local, assets externos nao podem ser a unica fonte. Nesse caso:

- manter modo bundle local como fallback
- ou baixar "asset pack" localmente e cachear


## Fonte de Update / Hospedagem

## Opcao A: GitHub Releases + manifest

### Como ficaria

Cada release publica:

- `ARKLAND-Multi-Setup-vX.Y.Z.exe`
- `manifest-vX.Y.Z.json`
- assets por componente, por exemplo:
  - `core-vX.Y.Z.zip` ou arquivos individuais
  - `webstore-vX.Y.Z.zip`
  - `plugins-customshop-vA.B.C.zip`
  - `assets-species-vN.zip`

### Pros

- menor mudanca no pipeline atual
- `_release.ps1` ja conversa com GitHub Releases
- boa trilha de auditoria por tag/release

### Contras

- GitHub Releases nao e o melhor CDN para milhares de arquivos pequenos
- downloads de arquivo individual podem aumentar latencia se nao houver empacotamento por componente

### Recomendacao

Usar GitHub Releases como **origem inicial**, mas preferir publicar:

- manifesto JSON
- arquivos individuais para componentes pequenos
- ZIP por componente para grupos com muitos arquivos


## Opcao B: CDN / host estatico para assets

Usar CDN/static host para:

- `static/species/icons/**`
- `static/catalog/**`
- possivelmente manifestos de assets

### Pros

- cache melhor
- custo menor por acesso repetido
- isola payload pesado do ciclo de release do app

### Contras

- adiciona mais uma superficie operacional
- invalida cache e versionamento precisam ser disciplinados

### Recomendacao

Nao bloquear o incremental nisso. Primeiro fazer update incremental via GitHub Releases; depois externalizar assets pesados.


## Estrategia Windows para substituicao de arquivos

O Windows e a parte mais sensivel deste projeto.

## Problema

Executaveis em uso nao podem ser sobrescritos diretamente:

- `ARKLAND-ServerManager.exe`
- `ARKLAND-Updater.exe`
- `ARKLAND-WebStore.exe`
- DLLs carregadas por processos vivos

O repo ja lida parcialmente com isso hoje:

- `start_download_update.py` tenta parar a Web Store antes do update
- `arkland_updater.py` espera o PID do app principal encerrar
- `arkland_updater.py` mata processos ARKLAND remanescentes
- `arkland_updater.py` renomeia a si proprio para liberar `ARKLAND-Updater.exe`

### Recomendacao

Manter um **helper updater exe** como aplicador do patch. O app principal:

1. detecta update
2. baixa/compara manifesto
3. prepara staging
4. fecha app e Web Store
5. entrega para `ARKLAND-Updater.exe`
6. updater aplica as trocas
7. updater relanca o app

### Move-on-reboot fallback

Se algum arquivo continuar bloqueado:

- registrar substituicao pendente para reboot
- informar claramente ao usuario que o patch foi preparado, mas requer reinicio do Windows

Isso deve ser excecao, nao caminho principal.

### Opiniao

Nao tentar "atualizacao em processo unico". O helper updater ja existe no produto e deve virar o aplicador oficial do patch incremental.


## Seguranca e Integridade

Obrigatorio:

- HTTPS em todos os downloads
- `sha256` por arquivo
- staging antes de aplicar
- rollback em falha

Recomendado:

- manifesto assinado opcionalmente
- pinning logico de `schema_version`
- rejeitar manifesto de canal inesperado

### Assinatura do manifesto

Fase 1 pode operar sem assinatura criptografica forte se:

- origem for GitHub Releases/Raw via HTTPS
- hashes por arquivo forem validados

Mas a arquitetura deve deixar espaco para:

- `manifest.sig`
- chave publica embutida no app/updater

### Rollback safety

Nunca apagar backup antes de:

1. todos os arquivos terem sido trocados
2. manifesto local ter sido atualizado
3. relancamento minimo do app ter sido considerado bem-sucedido


## UX Proposta

O usuario precisa ver claramente a diferenca entre:

- **Atualizacao de patch**
- **Reinstalacao completa**

### Patch update

Texto sugerido:

- "Atualizacao incremental disponivel"
- "Serao baixados apenas os arquivos alterados"

Mostrar progresso por:

- componente
- arquivo atual
- bytes totais
- numero de arquivos restantes

Exemplo:

- `Core App: 1/2 arquivos`
- `Web Store: 24/24 MB`
- `Plugins: 2 arquivos atualizados`

### Full reinstall / fallback

Texto sugerido:

- "Reparo completo"
- "Baixar instalador completo"

Usar esse caminho quando:

- manifesto local inexistente ou invalido
- many-files mismatch severo
- falha repetida de patch
- `bootstrap_min_version` exigir base minima

### Opiniao

Patch update nao deve usar o mesmo rotulo "Baixar e Instalar" sem contexto. Vale separar semanticamente:

- `Atualizar (patch)`
- `Baixar instalador completo`


## Impacto no Pipeline de Release

O maior ponto de integracao e `_release.ps1`.

## O que ele faz hoje

- atualiza versao
- builda
- gera installer
- publica GitHub Release com installer

## O que precisaria passar a fazer

### Fase incremental minima

1. gerar inventario dos arquivos distribuidos
2. calcular `sha256` e `size`
3. escrever `manifest.json`
4. publicar `manifest.json` junto do installer

### Fase seguinte

5. publicar assets por componente
6. opcionalmente publicar ZIPs por componente
7. manter asset full installer

### Fontes reais a usar para o manifesto

O manifesto deve refletir o layout real instalado hoje por `setup.iss` e pelos `.spec`:

- `setup.iss` define o conjunto minimo instalado pelo instalador
- `ARKLAND-Multi.spec` define binarios/datas do app principal
- `ARKLAND-WebStore.spec` define os dados `static`, `data`, `version.json`, `CustomShop/configs/config.json`
- `ARKLAND-Updater.spec` define o helper updater

### Compatibilidade retroativa

O instalador completo atual deve continuar publicado e funcional.

Em outras palavras:

- update incremental e um caminho novo
- nao substitui o fluxo atual no dia 1


## Compatibilidade com o Fluxo Atual

O sistema incremental deve coexistir com o modelo atual:

- `version.json` pode continuar existindo para o check simples
- ou pode passar a apontar tambem para um `manifest_url`

Exemplo de evolucao compatível:

```json
{
  "version": "1.10.48",
  "date": "2026-07-16",
  "download_url": "https://github.com/.../ARKLAND-Multi-Setup-v1.10.48.exe",
  "manifest_url": "https://github.com/.../manifest-v1.10.48.json",
  "changelog": ["..."]
}
```

Assim:

- clientes antigos continuam usando `download_url`
- clientes novos preferem `manifest_url`
- fallback continua simples


## Plano de Migracao em Fases

## Fase 1. Geracao de manifesto apenas

Escopo:

- `_release.ps1` gera `manifest.json`
- publica manifesto junto do installer
- nenhum cliente consome ainda

Beneficios:

- valida o modelo de inventario
- revela problemas de layout/paths
- zero risco para usuarios

Saida esperada:

- release continua igual
- manifesto passa a existir como artefato paralelo


## Fase 2. Cliente compara e baixa arquivos do core

Escopo:

- `src/updater.py` ou helper correlato passa a consumir `manifest_url`
- comparar apenas componente `core`
- aplicar update incremental de:
  - `ARKLAND-ServerManager.exe`
  - `ARKLAND-Updater.exe`
  - possivelmente `setup_db.sql`

Fallback:

- qualquer erro relevante -> usar `download_url` do instalador completo

Por que comecar pelo core?

- maior impacto com menor complexidade
- poucos arquivos
- UX melhora logo
- exercita staging, hash, rollback e troca de exe em uso


## Fase 3. Separar plugins e componentes

Escopo:

- adicionar componentes de plugins
- adicionar componente `webstore`
- permitir update seletivo por componente

Beneficios:

- patches de plugin deixam de baixar tudo
- Web Store deixa de estar sempre acoplada ao core

Risco principal:

- mapear corretamente o layout instalado final vs layout do repo/build


## Fase 4. Externalizar assets pesados

Escopo:

- destacar `assets-species` e `assets-catalog`
- opcionalmente mover para CDN/static host
- adicionar versionamento proprio desses pacotes

Beneficio:

- maior reducao de banda no longo prazo


## Riscos e Perguntas em Aberto

### 1. Layout instalado vs layout de build

Pergunta:

- o manifesto sera gerado a partir do repositorio, do `dist\`, de um staging do installer, ou do diretorio final instalado?

Opiniao:

- idealmente gerar a partir de um staging que reflita exatamente o layout final instalado

### 2. ZIP por componente vs arquivos individuais

Trade-off:

- arquivos individuais facilitam reuse/cache fino
- ZIP por componente reduz quantidade de requests

Opiniao:

- componentes pequenos: arquivos individuais
- assets pesados / muitos arquivos: ZIP por componente

### 3. Como tratar remocoes de arquivo

Se um arquivo existia antes e foi removido do produto:

- o manifesto precisa marcar delecao esperada
- o cliente deve remover com seguranca

### 4. Quando cair para full installer

Precisamos definir limiares claros:

- sem manifesto local
- versao muito antiga
- update interrompido
- hash mismatch repetido
- schema incompatível

### 5. Assinatura do manifesto

Pode ser adiada, mas deve ficar prevista no schema.

### 6. Web Store e assets offline

Se assets forem externos:

- o produto precisa aceitar dependencia de rede?
- ou continuara exigindo cache/pacote local?


## Caminho Recomendado

## Recomendacao principal

O caminho mais rapido e de maior impacto e:

1. **manter o instalador completo atual intocado**
2. **adicionar manifesto por release**
3. **implementar patch incremental apenas para o componente core primeiro**
4. **usar o `ARKLAND-Updater.exe` como aplicador oficial**
5. **deixar plugins e Web Store para a iteracao seguinte**
6. **externalizar assets pesados depois, sem bloquear o core incremental**

### Por que esse caminho

- minimiza risco de release
- aproveita a infraestrutura ja existente
- resolve o maior problema perceptivel do usuario cedo
- evita prematuramente complexidade de delta binario
- mantem fallback simples para o instalador completo

### Em resumo

Para o ARKLAND, a melhor primeira entrega nao e "delta binario sofisticado". E:

- manifesto confiavel
- comparacao local/remota
- download so do que mudou
- staging + hash
- helper updater aplicando troca e rollback

Isso ja muda a semantica de update de "reinstalar tudo" para "baixar so o patch", sem quebrar o pipeline atual.


## Proposta de Estrutura de Artefatos

Exemplo pratico de como uma release futura poderia ficar:

```text
GitHub Release v1.10.49
|- ARKLAND-Multi-Setup-v1.10.49.exe
|- manifest-v1.10.49.json
|- core/
|  |- ARKLAND-ServerManager.exe
|  |- ARKLAND-Updater.exe
|  \- setup_db.sql
|- plugins-customshop/
|  |- CustomShop.dll
|  |- libmariadb.dll
|  |- z.dll
|  \- PluginInfo.json
|- plugins-customdinodeliver/
|  |- CustomDinoDeliver.dll
|  \- PluginInfo.json
|- webstore/
|  |- ARKLAND-WebStore.exe
|  |- data.zip
|  \- static.zip
\- assets-ui/
   \- ig.zip
```

Nao e necessario implementar exatamente esse layout, mas ele traduz bem a divisao natural que o repositorio atual ja sugere.


## Decisoes Recomendadas Agora

- adotar **manifesto por release** como base da arquitetura
- preservar `version.json` como camada de compatibilidade
- usar `sha256` por arquivo desde o inicio
- usar `ARKLAND-Updater.exe` como aplicador do patch
- tratar `core` como primeira vertical incremental
- tratar `plugin/arkshop_web/static/**` como candidato explicito a pacote separado
- manter o full installer como fallback oficial


## Fora de Escopo Deste Documento

Este documento nao implementa:

- mudancas em `_release.ps1`
- mudancas em `build.bat`
- mudancas em `setup.iss`
- mudancas em `src/updater.py`
- mudancas em `arkland_updater.py`

Ele define apenas a direcao tecnica recomendada para a evolucao do sistema de update incremental/delta do ARKLAND.
