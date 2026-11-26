# Chat Arkland — ampliação da homologação para 01–05

## Autorização e checagem anterior

Em 26/11/2026, o administrador solicitou instalação somente nos servidores sem jogadores, preservando os ocupados. O inventário via SSH, processos e agente TEK confirmou 01–04 e 06 parados; RCON confirmou um jogador conectado no 05. O administrador então informou que já havia arquivado o legado e autorizou explicitamente instalar e iniciar **01, 02, 03 e 04**, apenas com Chat Arkland.

No momento da instalação, as pastas KalsCrossChat dos 01–04 já estavam ausentes. O arquivamento foi feito pelo administrador; esta execução não criou, alterou nem certificou os arquivos de backup que ele preparou. Não houve exclusão de pastas legadas nesta etapa.

## Instalação e início

- Chat Arkland 0.1.0 instalado nos quatro destinos, com SHA-256 conferido: `93A1743C73A343E975B5638781D1379AB8D141E2C2DE0F11EBA8741B6E16F3B1`.
- DLL, metadados e configuração ficaram na pasta própria do plugin. Identidade `tek:<UUID>` específica de cada cadastro; API via loopback; `ObserveOnly=false`; arquivo privado protegido por ACL.
- Processo ausente e estado parado foram reconfirmados antes das alterações e de cada início. Os pedidos foram aceitos pelo gerenciador às 13:15, horário de Brasília.
- PIDs iniciais: 01=11724, 02=11816, 03=2476, 04=2616. O 05 permaneceu no PID 6924, com jogador conectado, sem reinstalação ou reinício. O 06 permaneceu desativado, fora do escopo final.
- Nenhuma pasta ou DLL StructureLimits foi instalada nos 01–04. Inspeção dos módulos carregados confirmou ChatArkland presente, KalsCrossChat ausente e StructureLimits ausente nos quatro processos.
- Habilitados somente os mapas 01–04 na revisão central 5, preservando exatamente o objeto de configuração do 05 e mantendo o 06 desabilitado. A revisão 6, publicada posteriormente pela administração, foi observada nos cinco plugins e preservada.

## Verificação

- Logs do ArkApi confirmaram Chat Arkland 0.1.0 e `Loaded all plugins` nos 01–04, sem erro do Chat Arkland.
- Consulta administrativa confirmou 01–05 conectados, sincronizados na revisão 6, `observer=false`, `last_error` vazio.
- O carregamento de mundo é uma etapa separada: heartbeat do worker e processo ativo não comprovam que o ARK já aceita jogadores. A checagem de RCON/listagem continua após a carga da DLL.
- Não foram enviadas mensagens artificiais ao Discord, chats ou jogadores. Global entre mapas, PM, notificações e apresentação visual continuam sujeitos aos testes funcionais com jogadores.

## Serviço central

A WebStore foi encontrada sem processo ativo. Foi retomada a tarefa persistente existente da versão 1.12.34, sem substituição de executável ou migração de banco. A API local, o site e a administração voltaram a responder; o Gateway e as instâncias puderam sincronizar. O agente TEK já respondia normalmente nesta conferência.

Esta etapa foi implantação/configuração do plugin existente. Não houve nova compilação, nova versão do sistema ou implementação da presença rica Discord citada como próxima funcionalidade.
