-- Migração controlada para instalações com monitoramento herdado em latin1.
-- Fazer backup consistente e conferir contagens/hashes lógicos antes e depois.
-- Não altera saves, configurações ou processos dos mapas.
ALTER TABLE game_players CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE game_player_sessions CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
