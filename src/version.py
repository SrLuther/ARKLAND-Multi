"""
Versão e changelog do ARKLAND-Multi.
Este arquivo é a única fonte de verdade para a versão do aplicativo.
"""

APP_VERSION: str = "1.0.0"
BUILD_DATE: str = "2026-05-12"

# Cada entrada: version, date, changes (lista de strings)
CHANGELOG: list[dict] = [
    {
        "version": "1.0.0",
        "date": "2026-05-12",
        "changes": [
            "Lançamento inicial do ARKLAND-Multi",
            "Sincronização bidirecional automática de pastas ARK Cluster",
            "Interface moderna com Dashboard, Configurações e Logs",
            "Controle de intervalo de sincronização (1–60 s)",
            "Inicialização automática e modo debug configuráveis",
            "Estatísticas em tempo real no Dashboard (arquivos, erros, último sync)",
            "Sistema de atualização automática integrado",
        ],
    },
]
