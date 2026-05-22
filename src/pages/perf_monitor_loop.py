from __future__ import annotations
from typing import TYPE_CHECKING
from ..ui_constants import _GREEN
import time
try:
    import psutil as _psutil  # type: ignore[reportMissingModuleSource]
except Exception:
    _psutil = None  # type: ignore[assignment]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def perf_monitor_loop(app: "ARKServerManagerApp") -> None:
    import time
    assert _psutil is not None
    while app._perf_running:
        try:
            cpu_pct = _psutil.cpu_percent(interval=2)
            if not app._perf_running:
                break
            mem = _psutil.virtual_memory()
            freq = _psutil.cpu_freq()
            cores_phys = _psutil.cpu_count(logical=False) or 1
            cores_log  = _psutil.cpu_count(logical=True) or 1

            freq_str = f"{freq.current / 1000:.2f} GHz" if freq else ""
            cpu_info = f"{cores_phys} núcleos  /  {cores_log} threads"
            if freq_str:
                cpu_info += f"  ·  {freq_str}"

            used_gb  = mem.used  / (1024 ** 3)
            total_gb = mem.total / (1024 ** 3)
            ram_info = f"{used_gb:.1f} GB  /  {total_gb:.1f} GB  ({mem.percent:.0f}%)"

            gpu_pct  = app._get_nvidia_gpu_pct()
            gpu_temp = app._get_nvidia_gpu_temp()
            cpu_temp = app._get_cpu_temp()
            srv_stats = app._collect_server_stats()

            def _update(cp=cpu_pct, rp=float(mem.percent), ci=cpu_info,
                         ri=ram_info, gp=gpu_pct,
                         ct=cpu_temp, gt=gpu_temp, ss=srv_stats):
                try:
                    if app._perf_cpu_pct_var:
                        app._perf_cpu_pct_var.set(f"{cp:.0f}%")
                    if app._perf_cpu_bar:
                        clr = _GREEN if cp < 70 else ("#ffaa44" if cp < 90 else "#ff4444")
                        app._perf_cpu_bar.configure(progress_color=clr)
                        app._perf_cpu_bar.set(cp / 100)
                    if app._perf_cpu_info_var:
                        app._perf_cpu_info_var.set(ci)
                    if app._perf_cpu_temp_var:
                        if ct is not None:
                            tc = "#ff4444" if ct > 90 else ("#ffaa44" if ct > 70 else "#ff9944")
                            app._perf_cpu_temp_var.set(f"🌡 Temperatura: {ct:.0f} °C")
                            try:
                                app._perf_cpu_temp_var._label_ref.configure(text_color=tc)  # type: ignore
                            except Exception:
                                pass
                        else:
                            app._perf_cpu_temp_var.set("🌡 Temperatura: N/D")

                    if app._perf_ram_pct_var:
                        app._perf_ram_pct_var.set(f"{rp:.0f}%")
                    if app._perf_ram_bar:
                        clr = _GREEN if rp < 70 else ("#ffaa44" if rp < 90 else "#ff4444")
                        app._perf_ram_bar.configure(progress_color=clr)
                        app._perf_ram_bar.set(rp / 100)
                    if app._perf_ram_info_var:
                        app._perf_ram_info_var.set(ri)

                    if gp is not None:
                        if app._perf_gpu_pct_var:
                            app._perf_gpu_pct_var.set(f"{gp:.0f}%")
                        if app._perf_gpu_bar:
                            clr = _GREEN if gp < 70 else ("#ffaa44" if gp < 90 else "#ff4444")
                            app._perf_gpu_bar.configure(progress_color=clr)
                            app._perf_gpu_bar.set(gp / 100)
                    if app._perf_gpu_temp_var:
                        if gt is not None:
                            app._perf_gpu_temp_var.set(f"🌡 Temperatura: {gt:.0f} °C")
                        else:
                            app._perf_gpu_temp_var.set("🌡 Temperatura: N/D")

                    app._update_perf_servers(ss)
                except Exception:
                    pass

            try:
                app.after(0, _update)
            except Exception:
                break

            # ── Verificação de limiares ────────────────────────────────
            try:
                _warn = float(app._perf_alert_warn_var.get()) if app._perf_alert_warn_var else 80.0
                _crit = float(app._perf_alert_crit_var.get()) if app._perf_alert_crit_var else 90.0
            except (ValueError, AttributeError):
                _warn, _crit = 80.0, 90.0

            def _classify(v: float) -> str:
                if v >= _crit:
                    return "crit"
                if v >= _warn:
                    return "warn"
                return "ok"

            _checks = [
                ("cpu", cpu_pct),
                ("ram", float(mem.percent)),
                ("gpu", gpu_pct if gpu_pct is not None else -1.0),
            ]
            for _metric, _val in _checks:
                if _val < 0:
                    continue
                _new_st = _classify(_val)
                _old_st = app._perf_last_state.get(_metric, "ok")
                if _new_st != _old_st:
                    app._perf_last_state[_metric] = _new_st
                    app._log_perf_critical(_metric, _val, _new_st)

        except Exception:
            time.sleep(2)

