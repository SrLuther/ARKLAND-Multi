# Implantação do piloto 05 — 26/11/2026

## Estado entregue

- Plataforma: [release 1.12.33](https://github.com/SrLuther/ARKLAND-Multi/releases/tag/v1.12.33), com versão/changelog atualizados e interface Chat Arkland no site oficial.
- Plugin: Chat Arkland 0.1.0 experimental, somente `E:\Mapas\05\ShooterGame\Binaries\Win64\ArkApi\Plugins\ChatArkland`.
- Arquivos de runtime: DLL, PluginInfo.json e config.json dentro da própria pasta. Nenhuma biblioteca própria foi instalada solta em Win64.
- SHA-256 da DLL: `93A1743C73A343E975B5638781D1379AB8D141E2C2DE0F11EBA8741B6E16F3B1` (761856 bytes).
- Web Store implantada: `C:\Program Files (x86)\ARKLAND-ServerManager\ARKLAND-WebStore.exe`, SHA-256 `385428F2519F283068CB77051876F52166693FDAAB1EC6FE820E23C6C0584B88`.
- ServerKey do piloto: `tek:75f922d3-2dce-4442-9b49-9a70811d315b`. Somente essa chave foi habilitada. API local `http://127.0.0.1:27199`, sem dependência do trajeto público para sincronizar.
- Local.ObserveOnly=false; o Kals já havia sido retirado pelo Ciano antes da instalação. A configuração inclui diagnóstico temporariamente ativado para homologação; filtro permanece desligado e tags ainda exigem aprovação.

## Sequência e verificações

1. SSH confirmou 05 parado, sem KalsCrossChat na pasta de plugins. Nenhum save foi substituído ou movido.
2. Backup consistente do banco e cópias do executável/configurações anteriores foram preservados fora dos mapas, em diretório protegido.
3. MariaDB ajustado para Unicode somente nas tabelas envolvidas. Configuração central criada com participação exclusiva do 05 e arquivo local com a chave interna existente, sem token Discord ou senha MySQL.
4. Arquivos do plugin copiados com o 05 parado e hashes conferidos. Início enviado ao agente somente para o UUID do 05.
5. ArkApi 3.56 registrou carregamento do Chat Arkland 0.1.0. RCON do piloto respondeu e o feed público passou a mostrar o 05 online. Os avisos já existentes de outros plugins não foram tratados como erro de carregamento do Chat Arkland.
6. Release 1.12.33 compilada sem recompilar os plugins oficiais inalterados. Arquivo PYZ do executável conferido para conter o novo ledger de sessões, evitando divergência entre código e binário.
7. A primeira partida direta da Web Store respondeu enquanto a sessão SSH estava aberta, mas não permaneceu ativa ao encerrá-la. A verificação externa detectou HTTP 502. A inicialização foi corrigida usando a tarefa `ARKLAND-WebStore-Update-1.12.33`, com o mesmo principal interativo da tarefa anterior, processo oculto e execução independente do SSH. Chamadas posteriores, em novas conexões, confirmaram serviço persistente e site acessível.
8. O painel oficial abriu autenticado. A configuração corrente foi publicada pela interface como revisão 2; a instância 05 confirmou revisão 2, estado Sincronizado, sem erro, rede disponível e observação desativada.
9. Lumo Gateway conectado, reutilizando os IDs oficiais e o armazenamento existente. Nenhuma mensagem artificial de jogador ou teste manual do Discord foi enviada pelo agente.

## Banco de dados

MariaDB 10.11.9. O banco herdado utilizava latin1. As nove tabelas `chat_arkland_*` foram criadas em InnoDB/utf8mb4_unicode_ci; o ledger correlaciona o snapshot SDK com as sessões canônicas já existentes, sem uma tabela paralela de presença.

Conversão de `game_players` e `game_player_sessions` para utf8mb4 preservou, no instante da migração:

- game_players: 44 registros; SHA-256 lógico antes/depois `858626a26e2dac7f91f9bc50210969ea3bf29d6a767cfb24d8d281edc1fc1e93`.
- game_player_sessions: 398 registros; SHA-256 lógico antes/depois `669453f833306ea8d08cf5b0ebc8bc1e8462059e6503587717462002ea0de023`.
- Hash de jogadores considera identificação, nomes, tribo e mapa; hash de sessões considera chaves, origem e conexão. Campos de heartbeat continuamente atualizados foram excluídos dessa comparação.
- Gravação/leitura de texto com acento e emoji foi validada em transação e revertida. Nenhum registro fictício foi mantido como jogador ou conversa.

## Backup e reversão

Diretório remoto: `E:\ARKLAND_Backups\ChatArkland\v1.12.33-20261126-014203`.

Contém dump anterior do banco (71109567 bytes), executável anterior, configurações anteriores, manifestos e procedimentos operacionais. Há arquivos com credenciais nesse backup: ACL restrita à conta do servidor, Administradores e SYSTEM; não distribuir o diretório nem anexar seu conteúdo ao GitHub.

Uma reversão deve preservar o registro permanente SteamID→ID do chat. Retomar o executável web anterior não exige apagar tabelas novas. Não executar migrações down como limpeza. O chat legado só deve ser recolocado no piloto parado e sem o Chat Arkland encaminhando simultaneamente.

## Escopo e pendências

As únicas chamadas de controle de jogo feitas nesta implantação foram dirigidas ao 05: início e consultas RCON ListPlayers. Nenhuma parada, reinicialização ou edição de configuração de jogo foi enviada aos demais mapas. Mudanças observadas de PID em outros mapas não foram provocadas por comandos desta tarefa.

Ainda dependem dos testes com jogador: apresentação no chat, entrada/saída, ID igual em /online, /pm e /r, mensagens reais nos dois sentidos do Discord/Lumo e privacidade dos canais nativos. Comunicação entre dois mapas novos depende de um segundo piloto autorizado; os demais continuam fora da participação do Chat Arkland.
