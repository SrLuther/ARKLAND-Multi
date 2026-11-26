-- Correlação do snapshot SDK com sessões já existentes do monitoramento.
-- Não cria outro cadastro ou outra tabela de presença de jogadores.
SET @ca_has_snapshot = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='chat_arkland_instances' AND column_name='snapshot_json');
SET @ca_snapshot_ddl = IF(@ca_has_snapshot=0, 'ALTER TABLE chat_arkland_instances ADD COLUMN snapshot_json LONGTEXT NOT NULL DEFAULT ''{}''', 'SELECT ''Snapshot ledger já presente''');
PREPARE ca_snapshot_stmt FROM @ca_snapshot_ddl;
EXECUTE ca_snapshot_stmt;
DEALLOCATE PREPARE ca_snapshot_stmt;
