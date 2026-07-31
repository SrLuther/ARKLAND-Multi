"""Backends de temperatura/uso de hardware para o painel Desempenho.

Ordem típica (Windows): LibreHardwareMonitor → OpenHardwareMonitor →
contador PDH de zona térmica → MSAcpi (CIM) → MSAcpi (wmic legado).

Sem driver/sensor exposto (placa Xeon sem ACPI térmico, GPU pré-nvidia-smi
como G210), devolve None — a UI mostra N/D, sem inventar valores.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import time
from typing import Optional

_CREATE_NO_WINDOW = 0x08000000

# Backend CPU escolhido na 1ª sonda bem-sucedida ("none" = sem sensor)
_CPU_BACKEND: Optional[str] = None
_CPU_RETRY_AT: float = 0.0
_SOFT_RETRY_SEC = 90.0

_LHM_OK: Optional[bool] = None
_OHM_OK: Optional[bool] = None
_NVIDIA_SMI_PRESENT: Optional[bool] = None
_NVIDIA_SMI_WORKS: Optional[bool] = None

_SOFT_RETRY_AT: float = 0.0


def _plausible_c(v: float) -> bool:
    return 5.0 < v < 120.0


def _run(cmd: list[str], timeout: float = 4.0) -> str:
    return subprocess.check_output(
        cmd,
        creationflags=_CREATE_NO_WINDOW,
        stderr=subprocess.DEVNULL,
        timeout=timeout,
    ).decode(errors="replace")


def _ps(command: str, timeout: float = 8.0) -> str:
    return _run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        timeout=timeout,
    )


def _maybe_reset_soft() -> None:
    global _LHM_OK, _OHM_OK, _SOFT_RETRY_AT, _CPU_BACKEND, _CPU_RETRY_AT
    now = time.monotonic()
    if _CPU_BACKEND == "none" and now >= _CPU_RETRY_AT:
        _CPU_BACKEND = None
        _LHM_OK = None
        _OHM_OK = None
    if now >= _SOFT_RETRY_AT:
        if _LHM_OK is False:
            _LHM_OK = None
        if _OHM_OK is False:
            _OHM_OK = None
        _SOFT_RETRY_AT = now + _SOFT_RETRY_SEC


def _parse_name_value_lines(text: str) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or "=" not in ln:
            continue
        name, _, raw = ln.partition("=")
        try:
            val = float(raw.strip().replace(",", "."))
        except ValueError:
            continue
        out.append((name.strip(), val))
    return out


_CPU_NAME_RE = re.compile(
    r"cpu\s*package|package|core\s*max|tctl|tdie|cpu\s*core|ccd|\bcpu\b",
    re.I,
)
_GPU_NAME_RE = re.compile(r"\bgpu\b|graphics|geforce|radeon|nvidia", re.I)


def _pick_temp(entries: list[tuple[str, float]], kind: str) -> Optional[float]:
    if not entries:
        return None
    pred = _CPU_NAME_RE if kind == "cpu" else _GPU_NAME_RE
    matched = [v for n, v in entries if pred.search(n) and _plausible_c(v)]
    if matched:
        return max(matched)
    if kind == "cpu":
        any_ok = [v for _, v in entries if _plausible_c(v)]
        if any_ok:
            return max(any_ok)
    return None


def _pick_load(entries: list[tuple[str, float]], kind: str) -> Optional[float]:
    if not entries:
        return None
    pred = _GPU_NAME_RE if kind == "gpu" else _CPU_NAME_RE
    preferred: list[float] = []
    fallback: list[float] = []
    for name, val in entries:
        if not (0.0 <= val <= 100.0) or not pred.search(name):
            continue
        if re.search(r"core|total|\bgpu\b", name, re.I):
            preferred.append(val)
        else:
            fallback.append(val)
    if preferred:
        return preferred[0]
    if fallback:
        return fallback[0]
    return None


_HW_SENSOR_PS = (
    "$ErrorActionPreference='SilentlyContinue'; "
    "$ns='{ns}'; $st='{st}'; "
    "Get-CimInstance -Namespace $ns -ClassName Sensor -EA Stop | "
    "Where-Object {{ $_.SensorType -eq $st }} | "
    "ForEach-Object {{ $_.Name + '=' + $_.Value }}"
)


def _query_hwmonitor(namespace: str, sensor_type: str) -> list[tuple[str, float]]:
    cmd = _HW_SENSOR_PS.format(ns=namespace, st=sensor_type)
    return _parse_name_value_lines(_ps(cmd, timeout=6.0))


def read_lhm(kind: str, sensor_type: str = "Temperature") -> Optional[float]:
    global _LHM_OK
    _maybe_reset_soft()
    if _LHM_OK is False:
        return None
    try:
        entries = _query_hwmonitor("root/LibreHardwareMonitor", sensor_type)
        _LHM_OK = bool(entries)
        if sensor_type == "Temperature":
            return _pick_temp(entries, kind)
        return _pick_load(entries, kind)
    except Exception:
        _LHM_OK = False
        return None


def read_ohm(kind: str, sensor_type: str = "Temperature") -> Optional[float]:
    global _OHM_OK
    _maybe_reset_soft()
    if _OHM_OK is False:
        return None
    try:
        entries = _query_hwmonitor("root/OpenHardwareMonitor", sensor_type)
        _OHM_OK = bool(entries)
        if sensor_type == "Temperature":
            return _pick_temp(entries, kind)
        return _pick_load(entries, kind)
    except Exception:
        _OHM_OK = False
        return None


# Uma única sessão PowerShell para descobrir o 1º backend CPU disponível
_DISCOVER_CPU_PS = r"""
$ErrorActionPreference = 'SilentlyContinue'
function Emit-Temps($tag, $entries) {
  if (-not $entries) { return $false }
  $vals = @()
  foreach ($e in $entries) {
    $n = [string]$e.Name
    $v = [double]$e.Value
    if ($v -gt 5 -and $v -lt 120 -and ($n -match 'CPU|Package|Core|Tctl|Tdie|CCD')) {
      $vals += $v
    }
  }
  if (-not $vals) {
    foreach ($e in $entries) {
      $v = [double]$e.Value
      if ($v -gt 5 -and $v -lt 120) { $vals += $v }
    }
  }
  if ($vals.Count -gt 0) {
    $max = ($vals | Measure-Object -Maximum).Maximum
    Write-Output ("{0}|{1}" -f $tag, $max)
    return $true
  }
  return $false
}
try {
  $s = @(Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor -EA Stop |
    Where-Object { $_.SensorType -eq 'Temperature' })
  if (Emit-Temps 'lhm' $s) { exit 0 }
} catch {}
try {
  $s = @(Get-CimInstance -Namespace root/OpenHardwareMonitor -ClassName Sensor -EA Stop |
    Where-Object { $_.SensorType -eq 'Temperature' })
  if (Emit-Temps 'ohm' $s) { exit 0 }
} catch {}
try {
  $samples = @(Get-Counter '\Thermal Zone Information(*)\Temperature' -EA Stop).CounterSamples
  $vals = @()
  foreach ($c in $samples) {
    $k = [double]$c.CookedValue
    if ($k -gt 500) { $k = $k / 10.0 }
    $t = $k - 273.15
    if ($t -gt 5 -and $t -lt 120) { $vals += $t }
  }
  if ($vals.Count -gt 0) {
    $max = ($vals | Measure-Object -Maximum).Maximum
    Write-Output ("pdh|{0}" -f $max)
    exit 0
  }
} catch {}
try {
  $zones = @(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -EA Stop)
  $vals = @()
  foreach ($z in $zones) {
    $t = ([double]$z.CurrentTemperature / 10.0) - 273.15
    if ($t -gt 5 -and $t -lt 120) { $vals += $t }
  }
  if ($vals.Count -gt 0) {
    $max = ($vals | Measure-Object -Maximum).Maximum
    Write-Output ("acpi_cim|{0}" -f $max)
    exit 0
  }
} catch {}
Write-Output 'none|'
"""


def _discover_cpu_via_ps() -> tuple[Optional[str], Optional[float]]:
    try:
        out = _ps(_DISCOVER_CPU_PS, timeout=12.0).strip()
    except Exception:
        return None, None
    for ln in out.splitlines():
        ln = ln.strip()
        if "|" not in ln:
            continue
        tag, _, raw = ln.partition("|")
        tag = tag.strip().lower()
        if tag == "none" or not raw.strip():
            return "none", None
        try:
            val = float(raw.strip().replace(",", "."))
        except ValueError:
            continue
        if _plausible_c(val):
            return tag, val
    return "none", None


def _read_acpi_wmic() -> Optional[float]:
    if shutil.which("wmic") is None:
        return None
    try:
        out = _run(
            [
                "wmic",
                "/namespace:\\\\root\\wmi",
                "path",
                "MSAcpi_ThermalZoneTemperature",
                "get",
                "CurrentTemperature",
                "/value",
            ],
            timeout=3.0,
        )
        vals: list[float] = []
        for ln in out.splitlines():
            ln = ln.strip()
            if ln.lower().startswith("currenttemperature="):
                try:
                    raw = int(ln.partition("=")[2].strip())
                    celsius = raw / 10.0 - 273.15
                    if _plausible_c(celsius):
                        vals.append(celsius)
                except ValueError:
                    pass
        if vals:
            return max(vals)
    except Exception:
        pass
    return None


def _read_pdh() -> Optional[float]:
    try:
        out = _ps(
            "$ErrorActionPreference='Stop'; "
            "$vals=@(); "
            "foreach ($c in (Get-Counter '\\Thermal Zone Information(*)\\Temperature')"
            ".CounterSamples) { "
            "$k=[double]$c.CookedValue; if ($k -gt 500) { $k = $k/10.0 }; "
            "$t=$k-273.15; if ($t -gt 5 -and $t -lt 120) { $vals += $t } }; "
            "if ($vals.Count -gt 0) { ($vals | Measure-Object -Maximum).Maximum }",
            timeout=6.0,
        ).strip()
        if not out:
            return None
        val = float(out.splitlines()[-1].strip().replace(",", "."))
        return val if _plausible_c(val) else None
    except Exception:
        return None


def _read_acpi_cim() -> Optional[float]:
    try:
        out = _ps(
            "$ErrorActionPreference='Stop'; "
            "$vals=@(); "
            "foreach ($z in (Get-CimInstance -Namespace root/wmi "
            "-ClassName MSAcpi_ThermalZoneTemperature)) { "
            "$t=([double]$z.CurrentTemperature/10.0)-273.15; "
            "if ($t -gt 5 -and $t -lt 120) { $vals += $t } }; "
            "if ($vals.Count -gt 0) { ($vals | Measure-Object -Maximum).Maximum }",
            timeout=6.0,
        ).strip()
        if not out:
            return None
        val = float(out.splitlines()[-1].strip().replace(",", "."))
        return val if _plausible_c(val) else None
    except Exception:
        return None


def _read_cached_cpu_backend(backend: str) -> Optional[float]:
    if backend == "lhm":
        return read_lhm("cpu")
    if backend == "ohm":
        return read_ohm("cpu")
    if backend == "pdh":
        return _read_pdh()
    if backend == "acpi_cim":
        return _read_acpi_cim()
    if backend == "acpi_wmic":
        return _read_acpi_wmic()
    return None


def read_cpu_temp_windows() -> Optional[float]:
    """Lê temperatura CPU no Windows; cacheia o backend que funcionou."""
    global _CPU_BACKEND, _CPU_RETRY_AT, _LHM_OK, _OHM_OK
    _maybe_reset_soft()

    if _CPU_BACKEND == "none":
        return None

    if _CPU_BACKEND:
        try:
            val = _read_cached_cpu_backend(_CPU_BACKEND)
        except Exception:
            val = None
        if val is not None:
            return val
        # Backend caiu (ex. LHM fechou) — redescobrir
        _CPU_BACKEND = None

    tag, val = _discover_cpu_via_ps()
    if tag and tag != "none" and val is not None:
        _CPU_BACKEND = tag
        if tag == "lhm":
            _LHM_OK = True
        elif tag == "ohm":
            _OHM_OK = True
        return val

    # Último recurso: wmic (fora do PS; em alguns hosts ainda responde)
    wmic_val = _read_acpi_wmic()
    if wmic_val is not None:
        _CPU_BACKEND = "acpi_wmic"
        return wmic_val

    _CPU_BACKEND = "none"
    _CPU_RETRY_AT = time.monotonic() + _SOFT_RETRY_SEC
    _LHM_OK = False
    _OHM_OK = False
    return None


def nvidia_smi_available() -> bool:
    global _NVIDIA_SMI_PRESENT
    if _NVIDIA_SMI_PRESENT is not None:
        return _NVIDIA_SMI_PRESENT
    _NVIDIA_SMI_PRESENT = shutil.which("nvidia-smi") is not None
    return _NVIDIA_SMI_PRESENT


def read_nvidia_smi(query: str) -> Optional[float]:
    """query ex.: temperature.gpu | utilization.gpu"""
    global _NVIDIA_SMI_WORKS
    if _NVIDIA_SMI_WORKS is False:
        return None
    if not nvidia_smi_available():
        _NVIDIA_SMI_WORKS = False
        return None
    try:
        out = _run(
            [
                "nvidia-smi",
                f"--query-gpu={query}",
                "--format=csv,noheader,nounits",
            ],
            timeout=3.0,
        ).strip()
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if not lines:
            _NVIDIA_SMI_WORKS = False
            return None
        raw = lines[0].replace(",", ".")
        if not re.match(r"^-?\d+(\.\d+)?$", raw):
            _NVIDIA_SMI_WORKS = False
            return None
        _NVIDIA_SMI_WORKS = True
        return float(raw)
    except Exception:
        _NVIDIA_SMI_WORKS = False
        return None


def read_gpu_temp() -> Optional[float]:
    t = read_nvidia_smi("temperature.gpu")
    if t is not None and _plausible_c(t):
        return t
    for reader in (
        lambda: read_lhm("gpu"),
        lambda: read_ohm("gpu"),
    ):
        try:
            val = reader()
        except Exception:
            val = None
        if val is not None:
            return val
    return None


def read_gpu_util() -> Optional[float]:
    u = read_nvidia_smi("utilization.gpu")
    if u is not None and 0.0 <= u <= 100.0:
        return u
    for reader in (
        lambda: read_lhm("gpu", "Load"),
        lambda: read_ohm("gpu", "Load"),
    ):
        try:
            val = reader()
        except Exception:
            val = None
        if val is not None:
            return val
    return None
