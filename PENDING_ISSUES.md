# Problemas Pendentes — ARKLAND-Multi

> Criado em: 2026-05-15  
> Versão atual em produção: **v1.1.13**

---

## ✅ Problema 1 — Crash "BufferCount=0" ao iniciar servidor com mods — RESOLVIDO em v1.1.13

### Causa raiz

O `mod.info` **não começa com `mapCount`** — começa com o comprimento do nome do mod (`uint32 nameLen` + `char[] modName`), e só depois vem `numMaps`. Nossa implementação anterior tratava o primeiro `uint32` como `mapCount`, lendo tudo errado.

Além disso, o arquivo `.mod` exige um formato completamente diferente do que era gerado, conforme documentado no `arkmanager/doExtractMod` (Perl):

```
uint32  modID_lo               (32 bits baixos)
uint32  modID_hi               (32 bits altos, normalmente 0)
uint32  modNameLen             (inclui null terminator)
char[]  modName                (lido do cabeçalho do mod.info)
uint32  modPathLen             (inclui null terminator)
char[]  modPath                ("../../../ShooterGame/Content/Mods/{modid}\0")
uint32  numMaps
  for each map: uint32 mapFileLen + char[] mapFilePath
bytes   \x33\xFF\x22\xFF\x02\x00\x00\x00\x01  (magic footer)
bytes   conteúdo de modmeta.info (ou padrão ModType=1)
```

### Fix aplicado

`_create_dot_mod_from_mod_info` em `src/mod_manager.py` completamente reescrito em v1.1.13.

### Ação manual ainda necessária no servidor

Remover os `.mod` corrompidos gerados pelas versões anteriores:
```
ShooterGame\Content\Mods\1300713111.mod   ← apagar
ShooterGame\Content\Mods\1404697612.mod   ← apagar
(e qualquer outro .mod com ~48-52 bytes)
```
Depois re-baixar os mods pelo app (v1.1.13+).

---

## ✅ Problema 2 — App não detectou a atualização disponível — INVESTIGADO

### Diagnóstico

A lógica de verificação está correta:
- URL: `https://raw.githubusercontent.com/SrLuther/ARKLAND-Multi/main/version.json`
- Comparação de versão por tuplas numéricas (`(1,1,12) > (1,1,11)` = True) ✓
- Verificação automática 4s após startup + verificação manual disponível ✓

**Causa provável:** O `version.json` no branch `main` do GitHub não foi atualizado para `1.1.12` antes dos usuários instalarem `1.1.11`. É um problema de processo de release, não de código.

### Ação para próximos releases

Garantir que ao publicar um release no GitHub, o `version.json` no branch `main` seja atualizado **antes** de divulgar a nova versão.
