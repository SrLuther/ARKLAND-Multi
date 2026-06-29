-- ark_permission: concede AllEngrams ao grupo Default (plugin AllEngrams + Permissions.dll)
-- Rode no TEK → Banco de Dados → SQL (banco ark_permission selecionado)
-- Backup antes. Permissions recarrega em ~60s (ClusterSyncTime) — sem restart.

USE ark_permission;

-- Ver estado actual
SELECT Id, GroupName, Permissions FROM permissiongroups WHERE GroupName = 'Default';

-- Nomes oficiais do plugin AllEngrams (ArkApi):
--   AllEngrams.GiveEngrams      → comando /GiveEngrams
--   AllEngrams.AutoGiveEngrams  → desbloqueio automático (se UseAutoPermission no config)
UPDATE permissiongroups
SET Permissions = CONCAT(
    IFNULL(Permissions, ''),
    IF(LOCATE('AllEngrams.GiveEngrams,', CONCAT(IFNULL(Permissions, ''), ',')) > 0, '', 'AllEngrams.GiveEngrams,'),
    IF(LOCATE('AllEngrams.AutoGiveEngrams,', CONCAT(IFNULL(Permissions, ''), ',')) > 0, '', 'AllEngrams.AutoGiveEngrams,')
)
WHERE GroupName = 'Default';

SELECT Id, GroupName, Permissions FROM permissiongroups WHERE GroupName = 'Default';
