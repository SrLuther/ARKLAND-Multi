# [ARKLAND]-Multi

Ferramenta de **sincronização bidirecional automática** de pastas ARK Cluster entre múltiplas máquinas Windows.

## Funcionalidades

- Sincronização bidirecional em tempo real (intervalo configurável de 1–60 s)
- Interface gráfica moderna (CustomTkinter) com Dashboard, Configurações, Logs e Sobre
- Estatísticas ao vivo: arquivos sincronizados, erros, último sync
- Inicialização automática ao abrir o programa
- Modo debug para logs detalhados
- **Sistema de atualização automática** — verifica, baixa e instala novas versões por URL

## Requisitos

- Windows 10/11
- Python 3.9+
- Dependências: `customtkinter>=5.2.0`, `requests>=2.28.0`

## Instalação (modo desenvolvimento)

```bash
pip install -r requirements.txt
python main.py
```

## Build

```bash
build.bat
```

Gera `dist\ARKLAND-Multi.exe` via PyInstaller.

Para gerar o instalador, abra `setup.iss` no [Inno Setup 6+](https://jrsoftware.org/isinfo.php) e compile.

## Auto-Update

Hospede um `version.json` acessível publicamente com o seguinte formato:

```json
{
  "version": "1.1.0",
  "date": "2026-06-01",
  "download_url": "https://github.com/SrLuther/ARKLAND-Multi/releases/download/v1.1.0/ARKLAND-Multi-Setup-v1.1.0.exe",
  "changelog": ["Nova funcionalidade X", "Correção Y"]
}
```

Configure a URL em **Configurações → Atualizações Automáticas**.

## Changelog

Veja [CHANGELOG.md](CHANGELOG.md).

## Licença

MIT
