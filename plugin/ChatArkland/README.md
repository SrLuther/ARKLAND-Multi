# Chat Arkland 0.1.0 — experimental

Plugin independente para ArkApi ASE x64. Este pacote precisa do backend Chat Arkland da Web Store da mesma revisão de código. O portal público atualmente publicado não passa a suportá-lo apenas com a cópia da DLL.

## Conteúdo e dependências

- `ChatArkland.dll`, `PluginInfo.json` e um único `config.json`, todos na pasta `ArkApi/Plugins/ChatArkland`.
- ArkServerAPI ASE 3.54 ou compatível. Windows x64, API interna autenticada e banco central MySQL/MariaDB da Web Store.
- Permissions é opcional para grupos administrativos: quando indisponível, só o grupo Default é utilizado. Licenças são consultadas na infraestrutura central existente.
- Não depende de CustomShop.dll nem KalsCrossChat.dll. O SDK compartilhado é uma dependência de compilação, não de operação.
- Discord usa exclusivamente o Gateway/token central existente do Lumo. Não existe token Discord nos mapas, cliente Discord por mapa ou biblioteca MySQL distribuída ao lado do executável do ARK.

## Estado

Implementação experimental; compilação e testes automatizados não comprovam comportamento dentro do ARK. Não substituir o chat de produção sem cumprir a homologação de [testes](../../docs/CHAT_ARKLAND/TESTES.md) e a [migração](../../docs/CHAT_ARKLAND/INSTALACAO_E_MIGRACAO.md).

O modelo inicia em observação. O plugin também força observação se encontrar KalsCrossChat.dll carregada: não consome mensagens/comandos nem transmite conversas. Nenhum plugin antigo é removido ou desativado automaticamente.

## Compilação independente

No ambiente do projeto, defina `CHAT_PYTHON` com o caminho do Python configurado e `CHAT_SDK_ROOT` com o SDK ASE. Execute `build_cl.bat`. O script gera o contrato de configuração, compila somente este plugin, executa os testes C++ do núcleo e produz `bin/ChatArkland.dll`.

Alternativamente, use CMake com `-A x64 -DCHAT_SDK_ROOT=<SDK ASE>` e `cmake --build <diretorio> --config Release`. Os assets gerados são versionados; após alterações do contrato Python, execute `generate_assets.py` antes. CMake recompila somente os objetos alterados. Não há build de outros plugins.

Execute `package.py` com o mesmo ambiente Python para produzir o ZIP experimental com manifesto SHA-256. O empacotador utiliza o modelo vazio de configuração, nunca o arquivo local com credenciais.

## Documentação

- [Configuração, identidade e comandos](../../docs/CHAT_ARKLAND/CONFIGURACAO_E_COMANDOS.md).
- [Integrações e investigação](../../docs/CHAT_ARKLAND/INVESTIGACAO.md).
- [Correspondência das chaves originais](../../docs/CHAT_ARKLAND/MATRIZ_CHAVES.md).
- [Instalação, atualização e reversão](../../docs/CHAT_ARKLAND/INSTALACAO_E_MIGRACAO.md).
- [Testes e limitações de homologação](../../docs/CHAT_ARKLAND/TESTES.md).

No ZIP, consulte essas mesmas páginas dentro de `documentacao/`.
