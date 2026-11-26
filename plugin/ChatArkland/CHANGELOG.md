# Changelog — Chat Arkland

## Serviço central 1.12.35 — 26/11/2026

- Captura imutável das mensagens novas de humanos e do Lumo no canal configurado, incluindo autoria estável e horário, com apresentação nos blocos do chat do jogo.
- Fila durável, envio idempotente ao jogo, anexos copiados antes da exclusão e originais removidos somente após confirmação da cópia completa. Resultados ambíguos preservam o original, sem repetição cega; falhas de exclusão repetem somente a exclusão.
- Diagnóstico de permissões e fila na administração; migração aditiva 004 em InnoDB/utf8mb4. Não reorganiza o histórico anterior. Mantém a DLL 0.1.0 e não exige reiniciar mapas.

## 0.1.0 — experimental — 26/11/2026

- Homologação ampliada aos mapas 01–04 por autorização do administrador, depois de confirmar que estavam parados e vazios. O administrador arquivou o KalsCrossChat; as pastas legadas estavam ausentes antes da instalação. DLL verificada por SHA-256, identidades por instância, revisão central distribuída e carga confirmada nos quatro processos. Servidor 05 ocupado preservado, sem reinstalação ou reinício; 06 desativado preservado. StructureLimits não foi instalado nos 01–04. Esta ampliação não declara concluídos os testes funcionais entre jogadores/mapas.

- DLL ASE x64 independente, callbacks públicos de chat/tick, worker de rede e observação segura com o chat legado presente.
- Hub central autenticado, configurações revisionadas, publicação concorrente protegida e restauração de revisão.
- ID público permanente por SteamID, chat global, mensagens privadas por destinatário com confirmação, /r, /online e /joinleave.
- Unicode, horários de Brasília em 24 horas, grupos administrativos, licenças aprovadas, cores RGBA e censura por asteriscos.
- Transporte no Gateway existente do Lumo, bloqueio de outros bots/webhooks, deduplicação e proteção contra ciclos.
- Administração web em português, bootstrap protegido, descoberta de tags pendentes e diagnóstico da sincronização.
- Migrações, build próprio, pacote com manifesto e procedimentos de instalação/reversão. Homologação dentro do jogo pendente.
