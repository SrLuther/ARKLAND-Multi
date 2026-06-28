-- ARKLAND: remover os 8 grupos obsoletos (print TEK com moldura vermelha)
-- Banco: ark_permission | Backup antes | TEK > Banco de Dados > SQL

USE ark_permission;

-- Preview
SELECT Id, GroupName FROM permissiongroups WHERE Id IN (6, 7, 10, 11, 12, 13, 29, 70);

START TRANSACTION;

-- Jogadores: VIP* fora; Moderacao* -> Mod (Mod id 69 permanece)
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'VIPBronze,', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',VIPBronze', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'VIPPrata,', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',VIPPrata', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'VIPOuro,', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',VIPOuro', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'VIPDiamante,', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',VIPDiamante', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'VIPDoacao,', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',VIPDoacao', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'Moderacao,', 'Mod,');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',Moderacao,', ',Mod,');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',Moderacao', ',Mod');

UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'VIPBronze,', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',VIPBronze', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'VIPPrata,', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',VIPPrata', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'VIPOuro,', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',VIPOuro', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'VIPDiamante,', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',VIPDiamante', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'VIPDoacao,', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',VIPDoacao', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'Moderacao,', 'Mod,');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',Moderacao,', ',Mod,');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',Moderacao', ',Mod');

-- Os 8 selecionados: 6 Moderacao, 7 Modera????o, 10-13 VIP*, 29 ModeraÃ§Ã£o, 70 VIPDoacao
DELETE FROM permissiongroups WHERE Id IN (6, 7, 10, 11, 12, 13, 29, 70);

SELECT Id, GroupName FROM permissiongroups ORDER BY Id;

COMMIT;
-- ROLLBACK;  se algo estiver errado
