from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import paramiko

from .credential_vault import WindowsCredentialVault
from .models import SSHProfile
from .service import ChangedHostKeyError, SSHService, UnknownHostKeyError


APPROVED = "Aprovado"
ATTENTION = "Atenção"
FAILED = "Falhou"
NOT_CHECKED = "Não verificado"


@dataclass
class DiagnosticResult:
    name: str
    status: str
    detail: str
    owner: str = "Local"


def _result(name: str, status: str, detail: str, owner: str = "Local") -> DiagnosticResult:
    return DiagnosticResult(name, status, detail, owner)


def _credential_store_available() -> bool:
    if os.name != "nt":
        return False
    try:
        api = WindowsCredentialVault()._api()
        return bool(api.CredReadW and api.CredWriteW and api.CredDeleteW)
    except (OSError, AttributeError):
        return False


def run_local_diagnostics(
    *,
    ssh_executable: str | None = None,
    home: Path | None = None,
    credential_store_check: Callable[[], bool] = _credential_store_available,
    run: Callable = subprocess.run,
) -> list[DiagnosticResult]:
    home = Path(home or Path.home())
    results: list[DiagnosticResult] = []
    results.append(_result("Sistema operacional", APPROVED, f"{platform.system()} {platform.release()}"))

    executable = ssh_executable or shutil.which("ssh")
    if not executable:
        results.append(_result("Cliente OpenSSH", FAILED, "ssh.exe não foi encontrado no PATH do ARKLAND. Instale ou habilite o cliente OpenSSH do Windows."))
        results.append(_result("Versão OpenSSH", NOT_CHECKED, "Não há cliente SSH para consultar."))
    else:
        try:
            proc = run([executable, "-V"], capture_output=True, text=True, timeout=5, check=False)
            version = (proc.stderr or proc.stdout).strip()
            if proc.returncode == 0 and version:
                results.append(_result("Cliente OpenSSH", APPROVED, f"Encontrado: {executable}"))
                results.append(_result("Versão OpenSSH", APPROVED, version))
            else:
                results.append(_result("Cliente OpenSSH", ATTENTION, f"Executável encontrado, mas não respondeu normalmente: {version or proc.returncode}"))
                results.append(_result("Versão OpenSSH", FAILED, "Não foi possível consultar a versão."))
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append(_result("Cliente OpenSSH", FAILED, f"O executável não pôde ser iniciado: {exc}"))
            results.append(_result("Versão OpenSSH", FAILED, "A execução do cliente falhou."))

    for module in ("paramiko", "pyte"):
        try:
            available = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            available = False
        results.append(_result(
            f"Biblioteca {module}", APPROVED if available else FAILED,
            "Disponível no ambiente do ARKLAND." if available else f"A biblioteca {module} não está instalada/incluída no aplicativo.",
        ))

    key_names = ("id_ed25519", "id_ecdsa", "id_rsa", "id_dsa")
    found = [name for name in key_names if (home / ".ssh" / name).is_file()]
    results.append(_result(
        "Chaves SSH locais", APPROVED if found else ATTENTION,
        f"Foram encontrados {len(found)} arquivo(s) de chave privada por nomes convencionais; nenhum conteúdo foi lido ou exibido."
        if found else "Nenhuma chave com nome convencional foi encontrada. Isso não impede autenticação por senha nem por chave em outro caminho.",
    ))

    ssh_add = shutil.which("ssh-add") if executable else None
    if not ssh_add:
        results.append(_result("Agente SSH", ATTENTION, "ssh-add não está disponível; uma chave selecionada no perfil ainda pode funcionar."))
    else:
        try:
            proc = run([ssh_add, "-l"], capture_output=True, text=True, timeout=5, check=False)
            if proc.returncode == 0:
                count = sum(1 for line in proc.stdout.splitlines() if line.strip())
                results.append(_result("Agente SSH", APPROVED, f"Agente acessível; {count} identidade(s) carregada(s). Fingerprints não foram exibidos."))
            elif "no identities" in (proc.stderr + proc.stdout).casefold() or "nenhuma identidade" in (proc.stderr + proc.stdout).casefold():
                results.append(_result("Agente SSH", ATTENTION, "Agente acessível, mas sem identidades carregadas."))
            else:
                results.append(_result("Agente SSH", ATTENTION, "Não foi possível consultar o agente; verifique se o serviço ssh-agent está ativo."))
        except (OSError, subprocess.TimeoutExpired):
            results.append(_result("Agente SSH", ATTENTION, "O agente não respondeu ao teste."))

    vault_ok = credential_store_check()
    results.append(_result(
        "Armazenamento seguro", APPROVED if vault_ok else ATTENTION,
        "A API do Gerenciador de Credenciais do Windows está disponível; o diagnóstico não gravou nem leu segredos."
        if vault_ok else "O cofre nativo do Windows não está disponível neste sistema. Não salve senhas SSH em arquivos de configuração.",
    ))

    config = home / ".ssh" / "config"
    if not config.exists():
        results.append(_result("Configuração OpenSSH", ATTENTION, "Ainda não existe ~/.ssh/config. Ela só será criada se você solicitar a integração de alias para Codex."))
    elif not executable:
        results.append(_result("Configuração OpenSSH", NOT_CHECKED, "Sem cliente OpenSSH, a sintaxe não pode ser validada."))
    else:
        try:
            proc = run([executable, "-F", str(config), "-G", "arkland-diagnostic.invalid"], capture_output=True, text=True, timeout=8, check=False)
            results.append(_result(
                "Configuração OpenSSH", APPROVED if proc.returncode == 0 else FAILED,
                "A configuração foi interpretada sem erro." if proc.returncode == 0 else (proc.stderr or "Sintaxe OpenSSH inválida.").strip(),
            ))
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append(_result("Configuração OpenSSH", ATTENTION, f"Não foi possível validar a configuração: {exc}"))

    results.append(_result(
        "Ambiente do Codex no VS Code", NOT_CHECKED,
        "O ARKLAND pode testar seu próprio processo, mas não inspeciona o PATH, sandbox ou credenciais do agente Codex. Depois de configurar o alias, o comando deve ser testado no terminal do agente.",
        "Codex / VS Code",
    ))
    return results


def run_remote_diagnostics(
    profile: SSHProfile,
    service: SSHService,
    *,
    password: str | None = None,
    key_passphrase: str | None = None,
    resolver: Callable = socket.getaddrinfo,
    tcp_probe: Callable = socket.create_connection,
) -> list[DiagnosticResult]:
    """Read-only checks: DNS, TCP, SSH identity, auth, and an echo command."""
    profile.validate()
    results: list[DiagnosticResult] = []
    try:
        addresses = resolver(profile.host, int(profile.port), type=socket.SOCK_STREAM)
        resolved = sorted({entry[4][0] for entry in addresses})
        if not resolved:
            raise socket.gaierror("Nenhum endereço foi retornado.")
        results.append(_result("Resolução de endereço", APPROVED, ", ".join(resolved), "Remoto / rede"))
    except (socket.gaierror, OSError) as exc:
        return [
            _result("Resolução de endereço", FAILED, f"Não foi possível resolver o host: {exc}", "Remoto / DNS"),
            _result("Porta SSH", NOT_CHECKED, "A verificação parou antes de tentar a porta.", "Remoto / rede"),
            _result("Serviço SSH", NOT_CHECKED, "A verificação parou antes do handshake.", "Máquina remota"),
            _result("Identidade do host", NOT_CHECKED, "Não verificada.", "Máquina remota"),
            _result("Autenticação", NOT_CHECKED, "Não tentada.", "Máquina remota"),
            _result("Comando de leitura", NOT_CHECKED, "Não executado.", "Máquina remota"),
        ]

    try:
        with tcp_probe((profile.host, int(profile.port)), timeout=5):
            pass
        results.append(_result("Porta SSH", APPROVED, f"TCP {profile.port} aceitou conexão; isso ainda não prova que seja SSH.", "Remoto / rede"))
    except (OSError, TimeoutError) as exc:
        results.append(_result("Porta SSH", FAILED, f"Porta inacessível ou recusada: {exc}", "Remoto / firewall ou serviço remoto"))
        results.extend([
            _result("Serviço SSH", NOT_CHECKED, "A conexão TCP não foi estabelecida.", "Máquina remota"),
            _result("Identidade do host", NOT_CHECKED, "Não verificada.", "Máquina remota"),
            _result("Autenticação", NOT_CHECKED, "Não tentada.", "Máquina remota"),
            _result("Comando de leitura", NOT_CHECKED, "Não executado.", "Máquina remota"),
        ])
        return results

    try:
        inspection = service.inspect_host(profile)
        results.append(_result("Serviço SSH", APPROVED, "Handshake SSH concluído.", "Máquina remota"))
        results.append(_result("Identidade do host", APPROVED if inspection.trusted else ATTENTION,
                               f"Fingerprint {inspection.fingerprint}. " + ("Já confiável." if inspection.trusted else "Ainda não foi confiado; compare por um canal independente antes de aprovar."),
                               "Máquina remota / identidade"))
        if not inspection.trusted:
            results.extend([
                _result("Autenticação", NOT_CHECKED, "Bloqueada até a confiança explícita na identidade do servidor.", "Máquina remota"),
                _result("Comando de leitura", NOT_CHECKED, "Não executado porque o host ainda não é confiável.", "Máquina remota"),
            ])
            return results
    except ChangedHostKeyError as exc:
        return results + [
            _result("Serviço SSH", APPROVED, "O servidor respondeu ao handshake SSH.", "Máquina remota"),
            _result("Identidade do host", FAILED, f"Fingerprint conhecido {exc.known_fingerprint}; recebido {exc.received_fingerprint}. Conexão bloqueada.", "Máquina remota / segurança"),
            _result("Autenticação", NOT_CHECKED, "Não tentada devido à alteração de identidade.", "Máquina remota"),
            _result("Comando de leitura", NOT_CHECKED, "Não executado.", "Máquina remota"),
        ]
    except TimeoutError as exc:
        return results + [
            _result("Serviço SSH", FAILED, str(exc), "Máquina remota / rede"),
            _result("Identidade do host", NOT_CHECKED, "Handshake incompleto.", "Máquina remota"),
            _result("Autenticação", NOT_CHECKED, "Não tentada.", "Máquina remota"),
            _result("Comando de leitura", NOT_CHECKED, "Não executado.", "Máquina remota"),
        ]
    except (ConnectionError, paramiko.SSHException, OSError) as exc:
        return results + [
            _result("Serviço SSH", FAILED, f"Porta TCP aberta, mas o serviço SSH não respondeu corretamente: {exc}", "Máquina remota / serviço"),
            _result("Identidade do host", NOT_CHECKED, "Handshake SSH inválido.", "Máquina remota"),
            _result("Autenticação", NOT_CHECKED, "Não tentada.", "Máquina remota"),
            _result("Comando de leitura", NOT_CHECKED, "Não executado.", "Máquina remota"),
        ]

    client = None
    try:
        client = service.authenticate(profile, password, key_passphrase)
        results.append(_result("Autenticação", APPROVED, "Autenticação SSH aceita.", "Máquina remota / credenciais"))
    except paramiko.AuthenticationException:
        results.extend([
            _result("Autenticação", FAILED, "Credenciais recusadas. Confira usuário, chave, senha ou permissões da conta.", "Máquina remota / autenticação"),
            _result("Comando de leitura", NOT_CHECKED, "Não executado sem autenticação.", "Máquina remota"),
        ])
        return results
    except PermissionError as exc:
        results.extend([
            _result("Autenticação", ATTENTION, str(exc), "Local / credenciais"),
            _result("Comando de leitura", NOT_CHECKED, "Não tentado sem credenciais.", "Máquina remota"),
        ])
        return results
    except (TimeoutError, socket.timeout) as exc:
        results.extend([
            _result("Autenticação", FAILED, f"Tempo esgotado durante autenticação: {exc}", "Remoto / rede"),
            _result("Comando de leitura", NOT_CHECKED, "Não executado.", "Máquina remota"),
        ])
        return results
    except (paramiko.SSHException, OSError) as exc:
        results.extend([
            _result("Autenticação", FAILED, f"Falha SSH durante autenticação: {exc}", "Máquina remota / autenticação"),
            _result("Comando de leitura", NOT_CHECKED, "Não executado.", "Máquina remota"),
        ])
        return results

    try:
        exit_code, output = service.run_read_probe(client)
        success = exit_code == 0 and "ARKLAND_SSH_READ_PROBE" in output
        results.append(_result(
            "Comando de leitura", APPROVED if success else FAILED,
            "Sessão autenticada executou um comando echo inofensivo." if success else f"O servidor aceitou a sessão, mas o comando não confirmou execução (código {exit_code}). Saída: {output[:240]}",
            "Máquina remota / permissões",
        ))
        remote_os = service.identify_remote_os(client)
        results.append(_result(
            "Sistema operacional remoto",
            APPROVED if remote_os else ATTENTION,
            remote_os or "A autenticação funcionou, mas não foi possível identificar o shell/OS com comandos de leitura compatíveis.",
            "Máquina remota / shell",
        ))
    except (TimeoutError, paramiko.SSHException, OSError) as exc:
        results.append(_result("Comando de leitura", FAILED, f"A sessão foi autenticada, mas o comando de leitura falhou: {exc}", "Máquina remota / shell ou permissões"))
        results.append(_result("Sistema operacional remoto", NOT_CHECKED, "A identificação depende de uma sessão autenticada.", "Máquina remota"))
    finally:
        if client is not None:
            client.close()
    return results
