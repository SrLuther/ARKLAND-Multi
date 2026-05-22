from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def get_cluster_health(app: "ARKServerManagerApp", srv: "ServerConfig") -> list:
    """Retorna lista de (status, título, detalhe) para o diagnóstico de cluster.

    status: "ok" | "warn" | "error"
    """
    from pathlib import Path as _P
    from .server_config import ClusterProfile

    results: list[tuple[str, str, str]] = []
    cl  = srv.cluster
    adv = srv.advanced_settings

    # ── Resolve perfil ativo vs. configuração manual ──────────────────
    prof: "ClusterProfile | None" = None
    if srv.cluster_profile_id:
        prof = app.config_manager.get_cluster(srv.cluster_profile_id)

    using_profile = prof is not None
    effective_cid  = (prof.cluster_id   if prof else cl.cluster_id).strip()
    effective_cdir = (prof.cluster_dir   if prof else cl.cluster_dir_override).strip()
    net_mode       = (prof.mode == "network") if prof else False

    # ── Cluster habilitado ────────────────────────────────────────────
    if cl.enabled:
        results.append(("ok",   "Cluster habilitado", ""))
    else:
        results.append(("error", "Cluster não habilitado",
                         "Marque 'Habilitar Cluster (Cross-ARK)' na aba Avançado."))

    # ── Perfil vinculado ──────────────────────────────────────────────
    if using_profile:
        results.append(("ok",  f"Perfil de cluster ativo: {prof.name}",  # type: ignore[union-attr]
                         f"Modo: {'Rede' if net_mode else 'Local'}"))
    else:
        results.append(("warn", "Sem perfil de cluster vinculado",
                         "Configuração manual não é sincronizada entre instâncias do app. "
                         "Use um Perfil de Cluster para multi-máquina."))

    # ── Cluster ID ───────────────────────────────────────────────────
    if effective_cid:
        results.append(("ok",  "Cluster ID configurado", effective_cid))
    else:
        results.append(("error", "Cluster ID vazio",
                         "Defina um ID único igual em todos os servidores do cluster."))

    # ── Pasta do cluster ─────────────────────────────────────────────
    if effective_cdir:
        is_unc    = effective_cdir.startswith("\\\\")
        is_mapped = (len(effective_cdir) >= 2 and effective_cdir[1] == ":"
                     and effective_cdir[0].isalpha()
                     and _P(effective_cdir).is_absolute() is not False
                     and effective_cdir[0].upper() not in ("C", "D", "E"))
        is_network_path = is_unc or is_mapped

        if net_mode and not is_network_path:
            results.append(("warn", "Pasta do Cluster não parece ser caminho de rede",
                             f"Modo Rede ativo, mas '{effective_cdir}' parece ser caminho local. "
                             "Use caminho UNC (\\\\servidor\\pasta) ou unidade mapeada."))
        elif net_mode and is_unc:
            results.append(("ok",  "Caminho UNC configurado (modo rede)", effective_cdir))
        elif net_mode and is_mapped:
            results.append(("ok",  "Unidade de rede mapeada configurada", effective_cdir))

        if _P(effective_cdir).exists():
            results.append(("ok",  "Pasta do Cluster acessível", effective_cdir))
        else:
            sev = "error" if net_mode else "warn"
            results.append((sev, "Pasta do Cluster não encontrada / inacessível",
                             f"'{effective_cdir}' não existe ou sem permissão. "
                             + ("Verifique se o compartilhamento de rede está ativo e mapeado."
                                if net_mode else
                                "Crie a pasta ou corrija o caminho.")))
    else:
        sev = "error" if net_mode else "warn"
        results.append((sev, "Pasta do Cluster não definida",
                         "Sem ClusterDirOverride os servidores em máquinas diferentes "
                         "não compartilharão dados de viagem."))

    # ── Sync (modo rede) ──────────────────────────────────────────────
    if net_mode and prof is not None:
        if prof.sync_enabled:
            results.append(("ok",  "Sincronização automática ativada",
                             f"Intervalo: {prof.sync_interval}s"))
            local = prof.local_cluster_dir.strip()
            if local:
                if _P(local).exists():
                    results.append(("ok",  "Pasta local de sync existe", local))
                else:
                    results.append(("warn", "Pasta local de sync não encontrada",
                                     f"'{local}' não existe. O ARK precisa ter acesso a ela."))
            else:
                results.append(("error", "Pasta local de sync não definida",
                                 "Com sync ativo é necessário definir a pasta local onde "
                                 "o ARK grava os dados de viagem."))
        else:
            results.append(("warn", "Sincronização automática desativada (modo rede)",
                             "Sem sync o app não copia os dados de viagem entre a pasta "
                             "local do ARK e o compartilhamento de rede. Ative na aba Clusters."))

    # ── Nome de pasta de saves ────────────────────────────────────────
    if srv.alt_save_directory_name.strip():
        results.append(("ok",  "AltSaveDirectoryName configurado",
                         srv.alt_save_directory_name.strip()))
    else:
        results.append(("warn", "AltSaveDirectoryName vazio",
                         "Necessário quando múltiplos servidores rodam na mesma máquina "
                         "para evitar conflito de saves."))

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
            results.append(("ok",  f"{len(same_cluster)} outro(s) servidor(es) no mesmo cluster",
                             ", ".join(s.name for s in same_cluster)))
        else:
            results.append(("warn", "Nenhum outro servidor com o mesmo Cluster ID no app",
                             "Este servidor está sozinho no cluster. "
                             "Servidores em outras máquinas não aparecem aqui."))

    # ── Downloads ────────────────────────────────────────────────────
    dl_checks = [
        (adv.prevent_download_survivors, "Download de Sobreviventes",
         "Jogadores não podem importar personagens de outros mapas."),
        (adv.prevent_download_items,     "Download de Itens",
         "Jogadores não podem trazer itens de outros mapas."),
        (adv.prevent_download_dinos,     "Download de Dinos",
         "Jogadores não podem trazer dinos domesticados de outros mapas."),
    ]
    for blocked, label, detail in dl_checks:
        if blocked:
            results.append(("warn", f"{label} BLOQUEADO", detail))
        else:
            results.append(("ok",  f"{label} permitido", ""))

    # ── Uploads ──────────────────────────────────────────────────────
    ul_checks = [
        (adv.prevent_upload_survivors, "Upload de Sobreviventes",
         "Jogadores não podem enviar personagens para o cluster."),
        (adv.prevent_upload_items,     "Upload de Itens",
         "Jogadores não podem enviar itens para o cluster."),
        (adv.prevent_upload_dinos,     "Upload de Dinos",
         "Jogadores não podem enviar dinos para o cluster."),
    ]
    for blocked, label, detail in ul_checks:
        if blocked:
            results.append(("warn", f"{label} BLOQUEADO", detail))
        else:
            results.append(("ok",  f"{label} permitido", ""))

    return results

