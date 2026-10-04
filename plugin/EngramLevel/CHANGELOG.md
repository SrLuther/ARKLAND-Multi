# Changelog — EngramLevel

## [0.1.0] - 2026-10-04

- Plugin novo. No `ServerApplyLevelUp` (level up e reaplicação depois do mindwipe) libera só os engramas cujo nível exigido é o deste clique.
- Enquanto `Enabled` está true, `bAutoUnlockAllEngrams` fica false e `OverridePlayerLevelEngramPoints` >= 999 fica 0. Não voltam no fim do apply (isso rearmava o crash se o hook falhasse). No unload ou com `Enabled: false`, repõe o que leu no load. Se `GetShooterGameMode()` vier nulo, o original não corre sem máscara e a flag não é reativada.
- Não concede o buyout de 999. Não há comando de desbloquear tudo. Se um apply gastar vários pontos, os níveis dessa faixa saem um a um; tek e não tek não partilham o mesmo lote.
- Config: `Enabled`, `UnlockNonTek` (default ligado), `UnlockTotal` (default desligado). Num apply de um ponto, tek só no clique seguinte quando o modo total está ligado. `Engrams` / `ExtraEngrams` / `RemovedEngrams` comparam o nome interno ou o nome mostrado por inteiro, sem diferenciar maiúsculas.
- `/autoengram` liga o automático daquele SteamID (default desligado) e não repõe níveis já gastos. `autoengram.json` grava em ficheiro temporário e troca o nome; JSON inválido mantém a lista em memória. `Enabled: false` desliga o comando.
