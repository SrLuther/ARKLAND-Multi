# 🤖 INICIALIZAÇÃO DO BOT - GUIA DE USO

## 📋 Arquivos de Inicialização

Existem **2 formas principais** para iniciar o bot:

---

## 🐛 MODO DEBUG (COM JANELA VISÍVEL)

### Use quando:
- Precisa acompanhar logs em tempo real
- Está debugando problemas
- Quer monitorar a saúde do bot
- Quer ver mensagens de erro

### Como iniciar:

#### Opção 1: Python (Recomendado)
```bash
python start_bot_debug.py
```

#### Opção 2: Batch (Windows)
```bash
start_bot_debug.bat
```

### Características:
- ✅ Mostra a janela do CMD
- ✅ Logs em tempo real
- ✅ Ctrl+C para para o bot
- ✅ Mostra todos os erros
- ❌ Janela sempre visível

---

## 🌑 MODO OCULTO (SEM JANELA)

### Use quando:
- Bot é para rodar 24/7
- Quer economizar espaço na tela
- Não precisa acompanhar logs em tempo real
- Quer rodar em background

### Como iniciar:

#### Opção 1: Python (Recomendado)
```bash
python start_bot_hidden.py
```

#### Opção 2: Batch (Windows)
```bash
start_bot_hidden.bat
```

### Características:
- ✅ Sem janela visível
- ✅ Roda em background
- ✅ Processo desacoplado
- ✅ Logs salvos em arquivo
- ✅ Menos uso de recursos

### Monitorar logs:
```bash
# PowerShell
Get-Content .bot_hidden.log -Wait

# ou verificar o arquivo diretamente
cat .bot_hidden.log
```

### Parar o bot oculto:
```bash
# Windows - listar processos Python
tasklist /v | find "python"

# Windows - parar processo específico
taskkill /PID <ID> /F

# ou parar todos os Pythons
taskkill /IM python.exe /F
```

---

## 🔄 RESUMO RÁPIDO

| Situação | Use |
|----------|-----|
| 🐛 Debugando | `python start_bot_debug.py` |
| 👀 Acompanhando logs | `python start_bot_debug.py` |
| 🌙 Rodando 24/7 | `python start_bot_hidden.py` |
| 🎮 Testes rápidos | `python start_bot_debug.py` |
| 📊 Verificar saúde | `python start_bot_debug.py` |
| 🚀 Produção | `python start_bot_hidden.py` |

---

## ✅ Pré-requisitos

Ambos os scripts verificam:
- ✅ Arquivo `.env` existe?
- ✅ Ambiente virtual `.venv` existe?
- ✅ Arquivo `bot.py` existe?

Se algo estiver faltando, o script vai avisar antes de iniciar.

---

## 🆘 Troubleshooting

### Erro: "python.exe não encontrado"
```bash
# Instale o ambiente virtual
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Erro: ".env não encontrado"
```bash
# Crie o arquivo .env com:
TOKEN=seu_token_aqui
DISCORD_GUILD_ID=seu_guild_id
# ... outras configurações
```

### Bot não inicia
```bash
# Teste manualmente
python bot.py

# Verifique se há erros
python start_bot_debug.py
```

---

## 📝 Notas

- **Modo Debug**: Ideal para desenvolvimento e troubleshooting
- **Modo Oculto**: Ideal para produção e servidor 24/7
- **Logs**: Modo oculto salva logs em `.bot_hidden.log`
- **Processo**: Use `tasklist` para verificar processos ativos
- **Performance**: Modo oculto usa menos recursos

---

Criado em: 11 de abril de 2026
