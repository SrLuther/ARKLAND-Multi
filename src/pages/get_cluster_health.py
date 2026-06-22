from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def get_cluster_health(app: "ARKServerManagerApp", srv: "ServerConfig") -> list:
    """Retorna lista de (status, título, detalhe, sugestão) para o diagnóstico de cluster.

    status: "ok" | "warn" | "error"
    sugestão: string com passos concretos de como corrigir o problema (vazia para "ok").
    """
    from pathlib import Path as _P
    from ..server_config import ClusterProfile

    # Tupla: (status, título, detalhe, sugestão)
    results: list[tuple[str, str, str, str]] = []
    cl  = srv.cluster
    adv = srv.advanced_settings

    # ── Resolve perfil ativo vs. configuração manual ──────────────────
    prof: "ClusterProfile | None" = None
    if srv.cluster_profile_id:
        prof = app.config_manager.get_cluster(srv.cluster_profile_id)

    using_profile  = prof is not None
    effective_cid  = (prof.cluster_id  if prof else cl.cluster_id).strip()
    effective_cdir = (prof.cluster_dir if prof else cl.cluster_dir_override).strip()
    net_mode       = (prof.mode == "network") if prof else False

    # ── Cluster habilitado ────────────────────────────────────────────
    if cl.enabled:
        results.append(("ok", "Cluster habilitado", "", ""))
    else:
        results.append(("error", "Cluster não habilitado",
                        "O Cross-ARK está desativado para este servidor.",
                        "Abra a aba Avançado → seção Cross-ARK → marque "
                        "'Habilitar Cluster (Cross-ARK)' → clique em Salvar."))

    # ── Perfil vinculado ──────────────────────────────────────────────
    if using_profile:
        results.append(("ok",
                        f"Perfil de cluster ativo: {prof.name}",  # type: ignore[union-attr]
                        f"Modo: {'Rede' if net_mode else 'Local'}",
                        ""))
    else:
        results.append(("warn", "Sem perfil de cluster vinculado",
                        "Configuração manual é isolada — mudanças precisam ser "
                        "replicadas manualmente em cada servidor.",
                        "Vá em Clusters (menu lateral) → crie um novo perfil → "
                        "volte à aba Avançado deste servidor → selecione o perfil "
                        "no campo 'Perfil de Cluster'. Um perfil centraliza ID, "
                        "pasta e restrições para todos os servidores de uma vez."))

    # ── Cluster ID ───────────────────────────────────────────────────
    if effective_cid:
        results.append(("ok", "Cluster ID configurado", effective_cid, ""))
    else:
        results.append(("error", "Cluster ID vazio",
                        "Sem ID o ARK não reconhece os servidores como parte do mesmo cluster.",
                        "Abra a aba Avançado → seção Cross-ARK → campo 'ID do Cluster': "
                        "insira qualquer texto único (ex: MeuCluster2024). "
                        "Todos os servidores do cluster devem usar exatamente o mesmo ID."))

    # ── Pasta do cluster ─────────────────────────────────────────────
    if effective_cdir:
        is_unc          = effective_cdir.startswith("\\\\")
        is_local_abs    = (len(effective_cdir) >= 2 and effective_cdir[1] == ":"
                           and effective_cdir[0].isalpha())
        is_network_path = is_unc or (not is_local_abs)

        if net_mode and not is_unc and is_local_abs:
            results.append(("warn",
                            "Pasta do Cluster parece ser caminho local (modo Rede ativo)",
                            f"'{effective_cdir}' — servidores em outras máquinas não "
                            "terão acesso a este caminho local.",
                            "Use um caminho UNC: \\\\NomeDaOutraMaquina\\ARKCluster\n"
                            "Ou mapeie a pasta como unidade de rede (ex: Z:\\ARKCluster) "
                            "em todas as máquinas do cluster.\n"
                            "No perfil de cluster (Clusters → perfil), troque o modo para "
                            "'Rede' e atualize o campo 'Pasta de Dados de Viagem'."))
        elif net_mode and is_unc:
            results.append(("ok", "Caminho UNC configurado (modo rede)", effective_cdir, ""))
        elif net_mode and not is_local_abs:
            results.append(("ok", "Unidade de rede mapeada configurada", effective_cdir, ""))

        if _P(effective_cdir).exists():
            results.append(("ok", "Pasta do Cluster acessível", effective_cdir, ""))
        else:
            sev = "error" if net_mode else "warn"
            if net_mode:
                suggestion = (
                    "Verifique:\n"
                    "1. O computador remoto está ligado e acessível na rede.\n"
                    "2. A pasta está compartilhada (Compartilhamento de Arquivos do Windows).\n"
                    "3. As credenciais de rede permitem acesso (conta/senha ou acesso público).\n"
                    "Teste no terminal: net use \\\\servidor\\pasta\n"
                    "Se usar UNC, confirme que o nome do computador está correto: "
                    "ping NomeDaOutraMaquina"
                )
            else:
                suggestion = (
                    "Crie a pasta manualmente (ex: mkdir C:\\ARKCluster) "
                    "ou clique no botão 📁 para escolher/criar um caminho existente.\n"
                    "Certifique-se de que todos os servidores do cluster apontam "
                    "para a mesma pasta."
                )
            results.append((sev, "Pasta do Cluster não encontrada / inacessível",
                            f"'{effective_cdir}' não existe ou está inacessível.",
                            suggestion))
    else:
        sev = "error" if net_mode else "warn"
        if using_profile:
            where = (f"Clusters (menu lateral) → selecione '{prof.name}' → "  # type: ignore[union-attr]
                     "campo 'Pasta de Dados de Viagem'")
        else:
            where = "aba Avançado → seção Cross-ARK → campo 'Pasta de Dados de Viagem'"
        results.append((sev, "Pasta de Dados de Viagem não definida",
                        "Sem esta pasta o ARK não sabe onde gravar os dados do personagem "
                        "ao viajar entre mapas — a transferência falhará.",
                        f"Configure o caminho em: {where}\n"
                        "Para clusters na mesma máquina: qualquer pasta local, "
                        "ex: C:\\ARKCluster\n"
                        "Para clusters em máquinas diferentes: caminho UNC "
                        "compartilhado em rede, ex: \\\\Servidor\\ARKCluster"))

    # ── Sync (modo rede) ──────────────────────────────────────────────
    if net_mode and prof is not None:
        if prof.sync_enabled:
            results.append(("ok", "Sincronização automática ativada",
                            f"Intervalo: {prof.sync_interval}s", ""))
            local = prof.local_cluster_dir.strip()
            if not local and srv.install_dir:
                from ..cluster_paths import default_local_cluster_dir
                local = default_local_cluster_dir(srv.install_dir)
            if local:
                if _P(local).exists():
                    results.append(("ok", "Pasta local de sync existe", local, ""))
                else:
                    results.append(("warn", "Pasta local de sync não encontrada",
                                    f"'{local}' não existe nesta máquina.",
                                    "Salve o perfil de cluster novamente (o Manager tenta criar) "
                                    "ou reinicie o servidor — o ARK também cria ao iniciar com cluster."))
            else:
                results.append(("warn", "Pasta local de sync não definida",
                                "Vincule este servidor ao perfil e salve, ou informe install_dir.",
                                "Com servidor vinculado e pasta de instalação configurada, o caminho "
                                "padrão é:\n"
                                "{pasta_instalação}\\ShooterGame\\Saved\\clusters"))
        else:
            results.append(("warn", "Sincronização automática desativada (modo Rede)",
                            "O app não está copiando os arquivos de viagem entre "
                            "a pasta local do ARK e a pasta de rede compartilhada.",
                            "Vá em Clusters → selecione o perfil → ative "
                            "'Sincronizar automaticamente com a pasta de rede' → "
                            "defina a pasta local e o intervalo → clique em Salvar.\n"
                            "Sem sync ativo em modo Rede, jogadores não conseguirão "
                            "transferir personagens entre servidores em máquinas diferentes."))

    # ── Nome de pasta de saves ────────────────────────────────────────
    if srv.alt_save_directory_name.strip():
        results.append(("ok", "AltSaveDirectoryName configurado",
                        srv.alt_save_directory_name.strip(), ""))
    else:
        # Verificar se há outros servidores na mesma máquina (sem dir de saves → conflito real)
        same_machine_peers = [
            s for s in app.config_manager.servers
            if s.id != srv.id and not s.alt_save_directory_name.strip()
        ]
        sev = "warn" if not same_machine_peers else "error"
        results.append((sev, "AltSaveDirectoryName vazio",
                        "Múltiplos servidores na mesma máquina sem este campo usarão "
                        "a mesma pasta de saves, corrompendo os mundos.",
                        "Abra a aba Avançado → seção Cross-ARK → campo "
                        "'Nome da Pasta de Saves': insira um nome único para este "
                        "servidor, ex: TheIsland, Ragnarok, Aberration.\n"
                        "Cada servidor na mesma máquina deve ter um nome diferente."))

    # ── Consistência — outros servidores no mesmo cluster ─────────────
    if effective_cid:
        same_cluster = [
            s for s in app.config_manager.servers
            if s.id != srv.id and (
                (s.cluster_profile_id and s.cluster_profile_id == srv.cluster_profile_id)
                or s.cluster.cluster_id.strip() == effective_cid
            )
        ]
        if same_cluster:
            results.append(("ok",
                            f"{len(same_cluster)} outro(s) servidor(es) no mesmo cluster neste app",
                            ", ".join(s.name for s in same_cluster), ""))
        else:
            # Para cluster multi-máquina isso é esperado — não é erro
            results.append(("warn",
                            "Nenhum outro servidor com este Cluster ID neste app",
                            "Pode ser esperado se os outros servidores estão em "
                            "máquinas gerenciadas por instâncias separadas do ARKLAND.",
                            "Se os outros servidores estão NESTA máquina: adicione-os "
                            "ao app e vincule ao mesmo Perfil de Cluster.\n"
                            "Se estão em OUTRAS máquinas: este aviso é normal — "
                            "confirme apenas que todos usam o mesmo Cluster ID "
                            "e apontam para a mesma pasta de rede compartilhada."))

    # ── Consistência de pasta entre servidores no mesmo app ───────────
    if effective_cdir and effective_cid:
        dir_mismatch = [
            s for s in app.config_manager.servers
            if s.id != srv.id
            and s.cluster.cluster_id.strip() == effective_cid
            and not s.cluster_profile_id  # só verifica config manual (perfil já centraliza)
            and s.cluster.cluster_dir_override.strip()
            and s.cluster.cluster_dir_override.strip() != effective_cdir
        ]
        if dir_mismatch:
            names = ", ".join(s.name for s in dir_mismatch)
            results.append(("error",
                            "Pasta do Cluster divergente entre servidores",
                            f"Servidores com pasta diferente: {names}",
                            "Todos os servidores do mesmo cluster devem apontar para "
                            "a mesma pasta. Corrija os caminhos na aba Avançado de cada "
                            "servidor, ou use um Perfil de Cluster para centralizar "
                            "esta configuração automaticamente."))

    # ── Downloads ────────────────────────────────────────────────────
    dl_checks = [
        (adv.prevent_download_survivors, "Download de Sobreviventes",
         "Jogadores não podem importar personagens de outros mapas.",
         "Para liberar: aba Avançado → seção Cross-ARK → desmarque "
         "'Bloquear Download de Sobreviventes'."),
        (adv.prevent_download_items, "Download de Itens",
         "Jogadores não podem trazer itens de outros mapas.",
         "Para liberar: aba Avançado → seção Cross-ARK → desmarque "
         "'Bloquear Download de Itens'."),
        (adv.prevent_download_dinos, "Download de Dinos",
         "Jogadores não podem trazer dinos domesticados de outros mapas.",
         "Para liberar: aba Avançado → seção Cross-ARK → desmarque "
         "'Bloquear Download de Dinos'."),
    ]
    for blocked, label, detail, fix in dl_checks:
        if blocked:
            results.append(("warn", f"{label} BLOQUEADO", detail, fix))
        else:
            results.append(("ok", f"{label} permitido", "", ""))

    # ── Uploads ──────────────────────────────────────────────────────
    ul_checks = [
        (adv.prevent_upload_survivors, "Upload de Sobreviventes",
         "Jogadores não podem enviar personagens para o cluster.",
         "Para liberar: aba Avançado → seção Cross-ARK → desmarque "
         "'Bloquear Upload de Sobreviventes'."),
        (adv.prevent_upload_items, "Upload de Itens",
         "Jogadores não podem enviar itens para o cluster.",
         "Para liberar: aba Avançado → seção Cross-ARK → desmarque "
         "'Bloquear Upload de Itens'."),
        (adv.prevent_upload_dinos, "Upload de Dinos",
         "Jogadores não podem enviar dinos para o cluster.",
         "Para liberar: aba Avançado → seção Cross-ARK → desmarque "
         "'Bloquear Upload de Dinos'."),
    ]
    for blocked, label, detail, fix in ul_checks:
        if blocked:
            results.append(("warn", f"{label} BLOQUEADO", detail, fix))
        else:
            results.append(("ok", f"{label} permitido", "", ""))

    return results

