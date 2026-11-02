# Relatorio: diagnostico do tradutor da Web Store

## Sintomas separados

### Upload manual - HTTP 400

O erro `Selecione um arquivo .argosmodel` acontece quando o backend nao encontra `request.files["file"]`. Essa resposta ocorre antes de abrir ou validar o conteudo do arquivo. Portanto, aquele registro nao prova que o `.argosmodel` seja invalido.

O frontend atual monta `FormData`, adiciona o campo `file` e deixa o navegador criar o cabecalho multipart com seu `boundary`. O envio agora tem teste automatizado que verifica o campo recebido e o sucesso do fluxo multipart. Para o incidente antigo, ainda nao ha evidencias de producao que permitam dizer se houve codigo antigo, cache/service worker, proxy removendo o corpo ou pagina e backend em builds diferentes.

### Verificacao/preparo - HTTP 503

O registro ao vivo de `2026-11-02T00:55:14.036Z` tinha referencia `ff5cfdeb3067`, build de frontend `1.11.20` e falha em `POST /api/translate/models`. O stack mostrado pelo painel era do navegador (`runOnce` -> `fetchJson` -> `supportWidgetModels`) e nao continha traceback Python. Portanto, nao identifica se a falha aconteceu na inicializacao/importacao do Argos, leitura dos modelos, consulta do indice, download, validacao, instalacao ou teste do par.

O HTTP 400 e o HTTP 503 sao falhas distintas e devem continuar sendo investigadas separadamente.

## Alteracoes feitas no checkout local

- O endpoint de upload sem `file` agora gera `UPLOAD_FILE_MISSING`, informa a etapa `multipart_parse`, inclui reference ID e registra metodo, endpoint, content type/length, nomes de campos, versao, data de build e commit (quando `ARKLAND_GIT_COMMIT` estiver configurado). Nao registra conteudo, cookies, tokens ou credenciais.
- As rotas de verificacao, traducao e upload incluem codigos internos, etapa, par quando conhecido e reference ID; traceback/excecao ficam nos logs internos, nao na mensagem tecnica exposta ao usuario.
- O build da aplicacao vem de `version.json`; a data acompanha a versao. O commit vem da variavel `ARKLAND_GIT_COMMIT` se o ambiente de publicacao a fornecer.
- A pasta persistente e resolvida por `webstore_data_dir()/translation/argos-packages`, correspondente ao caminho `%APPDATA%\\ARKLAND-ServerManager\\arkshop_web\\translation\\argos-packages` na instalacao Windows prevista. O Argos e configurado explicitamente para usar essa pasta, e o caminho efetivo e registrado no log interno.
- No inicio, os arquivos `.argosmodel` persistentes sao inspecionados e somente pares ausentes sao instalados. Arquivo invalido nao e apagado silenciosamente; a falha fica registrada para diagnostico. As validacoes de caminho e limite de 500 MiB descompactado permanecem.
- Se os quatro pares ja estiverem instalados e o indice Argos estiver indisponivel, a verificacao continua reportando os modelos instalados como utilizaveis, com aviso `ARGOS_INDEX_UNAVAILABLE`. A interface nao chama isso de atualizacao concluida; informa que os modelos estao disponiveis, mas que nao foi possivel consultar atualizacoes.
- Pacotes baixados sao validados antes da instalacao: estrutura ZIP, caminho interno, tamanho expandido, metadata e par de idiomas. Erros ficam separados por estagio de download, validacao e instalacao.
- Permanecem as protecoes de upload: extensao, 350 MiB, metadata, pares suportados, paths internos e limite de extracao.

## Testes executados

Comando, executado em `plugin/arkshop_web`:

```powershell
pytest tests/test_translation_service.py tests/test_tickets.py -q
```

Resultado: **29 passed**. Os testes cobrem multipart com campo `file`, ausencia do campo com log seguro/reference ID, erros estruturados, fallback quando o indice esta fora e instalacao idempotente de arquivo persistente somente para pares ausentes.

Esses testes comprovam o codigo local e usam fixtures/fakes para Argos. Nao comprovam download dos quatro modelos reais, traducao real nem o comportamento do processo remoto de producao.

## Validacao necessaria no host de producao

### Checagem inicial da publicacao (2026-11-01)

- A pagina oficial consultada com sessao autenticada ainda serve assets com `?v=1.11.20`; o registro selecionado de `/api/translate/models` tambem informa `app_build: 1.11.20` e HTTP 503. Isso confirma o build do frontend observado, nao a versao interna do backend.
- O detalhe da ocorrencia antiga nao contem `error_code`, `stage`, par ou traceback Python. Portanto, nao demonstra que a instrumentacao descrita acima esteja publicada. Nenhum upload, reinstalacao, remocao de modelo ou chamada ao endpoint de verificacao foi executado nesta etapa.
- O `%APPDATA%` acessivel nesta sessao e `C:\\Users\\Ciano\\AppData\\Roaming`, que nao possui a pasta `ARKLAND-ServerManager\\arkshop_web\\translation\\argos-packages`. Este e o ambiente local de desenvolvimento, nao o host Windows de producao (`ArkServer`); esse resultado nao informa a existencia dos modelos no host.
- Nao ha acesso nesta sessao aos logs do processo Web Store, identidade do usuario do servico, filesystem do host, configuracao WSGI/proxy nem `ARKLAND_GIT_COMMIT`. A confirmacao de publicacao completa e o inventario dos pacotes permanecem bloqueados ate esses dados estarem disponiveis.

1. Procurar nos logs do processo Web Store por `reference_id=ff5cfdeb3067`. A instrumentacao atual ainda nao existia quando esse evento ocorreu; por isso e necessario reproduzir depois da publicacao para obter `stage`, `error_code`, `pair`, `build` e traceback.
2. Conferir no log de inicio a versao, data, commit e o caminho efetivo da pasta Argos. Confirmar que os quatro arquivos estao no caminho persistente e que o usuario do servico consegue ler e escrever nele.
3. Testar primeiro pela interface e depois por multipart direto. A rota requer sessao autenticada; exporte uma sessao autenticada para `cookies.txt` e execute no host cliente:

```powershell
curl.exe -v -b cookies.txt -F "file=@C:\\caminho\\translate-en_pb-1_9.argosmodel" https://arkland.com.br/api/translate/models/upload
```

Nao envie cookie em chamado publico ou log compartilhado. O upload pode demorar por causa do tamanho do modelo. Se o multipart direto funcionar e a interface falhar, compare build/cache/service worker e o request capturado no navegador. Se ambos falharem antes da validacao, examine IIS/nginx/Cloudflare (ou proxy utilizado), limite de corpo, timeout, encaminhamento e log WSGI/Flask. Se a resposta chegar a `validation` ou `install`, o log interno indicara a etapa seguinte.

4. Reiniciar a Web Store e verificar que os modelos instalados continuam disponiveis sem download; remover de forma controlada um modelo de teste e verificar se o pacote local persistente e instalado.
5. Testar traducao real en->pt, pt->en, en->es e es->en com mensagens de teste, tanto com acesso ao indice quanto com a saida de rede/indice temporariamente indisponivel.

## Conclusao atual

O checkout local foi endurecido e os testes direcionados passaram. A causa definitiva do HTTP 400 e do HTTP 503 historicos em producao ainda nao esta fechada: para o 400 falta o log do corpo multipart recebido; para o 503 falta o traceback Python do host. A publicacao e a validacao real descrita acima sao necessarias antes de declarar o tradutor resolvido em producao.
