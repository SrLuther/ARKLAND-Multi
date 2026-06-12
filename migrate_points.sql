-- ============================================================
--  ARKLAND Shop — Migração de pontos dos jogadores
--
--  ANTES de rodar:
--    1. Substitua  BANCO_ANTIGO  pelo nome real do seu banco antigo
--       (ex: arkshop, customshop, arkland_db, ...)
--    2. Execute como root (precisa ler o banco antigo e escrever no novo):
--         mysql -u root -p < migrate_points.sql
-- ============================================================

-- Descobre bancos disponíveis para ajudar na identificação:
-- SHOW DATABASES;

-- ── Migração principal ────────────────────────────────────
-- Ajuste BANCO_ANTIGO abaixo:
SET @banco_antigo = 'BANCO_ANTIGO';

INSERT INTO arkland_shop.players (steam_id, points)
SELECT steam_id, points
FROM BANCO_ANTIGO.players
WHERE points > 0                   -- ignora jogadores com 0 pontos
ON DUPLICATE KEY UPDATE
  points = GREATEST(arkland_shop.players.points, VALUES(points));

-- ── Resultado ────────────────────────────────────────────
SELECT
  COUNT(*)                         AS jogadores_migrados,
  SUM(points)                      AS total_pontos,
  MAX(points)                      AS maior_saldo,
  MIN(points)                      AS menor_saldo
FROM arkland_shop.players
WHERE points > 0;

SELECT '>>> Migracao de pontos concluida!' AS resultado;
-- ============================================================
