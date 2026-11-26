-- REQUER BACKUP. Reverter o esquema remove mensagens, revisões e entregas pendentes.
-- Não executar em produção sem exportar/restaurar chat_arkland_players. Nunca recrie IDs do zero sobre um cluster ativo.
-- O registro de IDs é preservado também no downgrade, evitando reutilização indevida.
DROP TABLE IF EXISTS chat_arkland_schema;
DROP TABLE IF EXISTS chat_arkland_revisions;
DROP TABLE IF EXISTS chat_arkland_messages;
DROP TABLE IF EXISTS chat_arkland_instances;
DROP TABLE IF EXISTS chat_arkland_events;
DROP TABLE IF EXISTS chat_arkland_discord_lease;
DROP TABLE IF EXISTS chat_arkland_deliveries;
DROP TABLE IF EXISTS chat_arkland_config;
