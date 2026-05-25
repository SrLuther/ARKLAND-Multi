# 🤖 FLUXO DE ATUALIZAÇÃO - BOT OBOBONIC

## Cenário 1: Você faz mudanças em Sergipe

### Passo 1 - Sergipe (Você)
```powershell
cd C:\Users\Ciano\Documents\oBobonicClean

# Fazer suas mudanças
# ...

git add .
git commit -m "Descrição da mudança"
git push origin main
```

### Passo 2 - Bahia (Alguém lá)
Qualquer pessoa lá na Bahia abre o arquivo:
```
ATUALIZAR_BOT_BAHIA.bat
```

E clica 2 vezes. Pronto.

---

## Cenário 2: Você quer ver o que mudou antes de sincronizar

### Em Sergipe (você):
```powershell
git log --oneline -5
```

Vê os commits mais recentes.

### Na Bahia (qualquer um lá):
```powershell
cd C:\Users\ArkServer\Documents\oBobonicClean
git log --online -5
```

Compara os commits.

---

## Tá com dúvida se funciona?

### Na Bahia, rode:
```powershell
cd C:\Users\ArkServer\Documents\oBobonicClean
git status
```

Mostra o que está desatualizado.

---

## Resumo Simples:

✅ **Sergipe**: Faz mudança → git push  
✅ **Bahia**: Clica em `ATUALIZAR_BOT_BAHIA.bat`  
✅ **Pronto**: Bot atualizado

Sem SSH, sem scripts confusos, sem nada.
