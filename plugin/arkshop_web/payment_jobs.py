"""Jobs de confirmação de pagamento Mercado Pago (Fase 2).

Fluxo: request HTTP só lê/escreve DB curto → responde → fetch MP + crédito
correm aqui, sem segurar worker Waitress.

Também concentra a reconciliação (webhook perdido): ``reconcile_payment`` consulta
o MP (GET, somente leitura) e aplica o MESMO fluxo idempotente do webhook.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

log = logging.getLogger("arkshop_web.payment_jobs")

# O webhook responde 200 de imediato — o MP NÃO reenvia depois. Por isso o fetch
# em background tenta mais de uma vez (MP pode devolver 404/5xx logo após criar).
_FETCH_RETRY_DELAYS = (1.0, 3.0)
_FETCH_ATTEMPTS_BACKGROUND = 3


def enqueue_mp_payment_confirm(
    *,
    mp_payment_id: str,
    payment_id: str | None = None,
    source: str = "poll",
    submit: Callable[..., bool] | None = None,
) -> bool:
    """Agenda fetch MP + finalize. dedupe por mp_id (ou payment_id)."""
    mp_id = str(mp_payment_id or "").strip()
    pid = str(payment_id or "").strip() or None
    if not mp_id and not pid:
        return False

    if submit is None:
        from background_tasks import submit as _submit

        submit = _submit

    key = f"mp-confirm:{mp_id or pid}"

    def _job() -> None:
        _confirm_mp_payment(mp_id, payment_id=pid, source=source)

    return bool(submit(_job, dedupe_key=key, name="mp-payment-confirm"))


def _fetch_mp_payment(
    app_mod: Any, token: str, mp_id: str, *, attempts: int,
) -> tuple[dict[str, Any] | None, Exception | None]:
    """GET /v1/payments/{id} com retry curto. Devolve (resposta, último erro)."""
    last_exc: Exception | None = None
    total = max(1, int(attempts))
    for i in range(total):
        try:
            resp = app_mod.fetch_payment(
                token, mp_id, timeout=app_mod._MP_WEBHOOK_FETCH_TIMEOUT,
            )
            return (resp if isinstance(resp, dict) else None), None
        except Exception as exc:  # noqa: BLE001 — registrado abaixo
            last_exc = exc
            if i + 1 < total:
                time.sleep(_FETCH_RETRY_DELAYS[min(i, len(_FETCH_RETRY_DELAYS) - 1)])
    return None, last_exc


def _confirm_mp_payment(
    mp_payment_id: str,
    *,
    payment_id: str | None = None,
    source: str = "poll",
    attempts: int = _FETCH_ATTEMPTS_BACKGROUND,
) -> dict[str, Any]:
    """Corre fora do request: HTTP MP → sessão DB curta → crédito."""
    # Import lazy evita ciclo app ↔ jobs.
    import app as app_mod

    token = app_mod._get_mp_access_token()
    if not token:
        log.warning("mp confirm skip: token ausente source=%s", source)
        return {"result": "no_token", "message": "Access Token do Mercado Pago não configurado"}

    mp_id = str(mp_payment_id or "").strip()
    mp_resp: dict[str, Any] | None = None
    if mp_id:
        mp_resp, fetch_exc = _fetch_mp_payment(app_mod, token, mp_id, attempts=attempts)
        if mp_resp is None:
            err = str(fetch_exc)[:300] if fetch_exc else "resposta vazia"
            log.warning(
                "mp confirm fetch failed mp_id=%s source=%s: %s", mp_id, source, err,
            )
            _safe_audit(
                app_mod, "mp_payment_fetch_failed", severity="warn", source=source,
                order_id=payment_id, message=f"Falha ao consultar pagamento no Mercado Pago: {err}",
                mp_payment_id=mp_id,
            )
            return {"result": "fetch_failed", "message": f"Falha ao consultar o Mercado Pago: {err}"}

    if mp_resp is None:
        return {"result": "fetch_failed", "message": "Sem id de pagamento do Mercado Pago"}

    return apply_mp_payment_response(
        app_mod, mp_resp, mp_id=mp_id, payment_id_hint=payment_id, source=source,
    )


def _safe_audit(app_mod: Any, event_type: str, **kw: Any) -> None:
    """Auditoria persistente que nunca derruba o job."""
    try:
        app_mod._audit_event(event_type, **kw)
    except Exception:  # noqa: BLE001
        log.debug("audit %s falhou", event_type, exc_info=True)


def apply_mp_payment_response(
    app_mod: Any,
    mp_resp: dict[str, Any],
    *,
    mp_id: str = "",
    payment_id_hint: str | None = None,
    source: str = "poll",
    actor_steam_id: str | None = None,
) -> dict[str, Any]:
    """Casa a resposta do MP com a doação local e aplica o fluxo idempotente.

    Segurança: crédito só com status approved (mapeado) e valor pago >= preço do
    pacote; ``credited`` + SELECT ... FOR UPDATE impedem crédito em dobro.
    """
    from pix_payments import map_mp_status, mp_amount_covers_package

    external_ref = str(mp_resp.get("external_reference") or "").strip() or (payment_id_hint or "")
    resolved_mp_id = str(mp_resp.get("id") or mp_id or "").strip()
    mp_status = str(mp_resp.get("status", "") or "")
    mapped = map_mp_status(mp_status)
    audit: dict[str, Any] = {}
    out: dict[str, Any] = {"result": "unchanged", "mp_status": mp_status}

    db = app_mod._SessionLocal()
    try:
        payment = None
        if external_ref:
            payment = (
                db.query(app_mod.PointPayment)
                .filter(app_mod.PointPayment.payment_id == external_ref)
                .first()
            )
        if not payment and resolved_mp_id:
            payment = (
                db.query(app_mod.PointPayment)
                .filter(app_mod.PointPayment.mp_payment_id == resolved_mp_id)
                .first()
            )
        if not payment:
            log.info(
                "mp confirm ignored (no row) mp_id=%s ref=%s source=%s",
                resolved_mp_id, external_ref, source,
            )
            audit = dict(
                event_type="mp_payment_no_row", severity="warn", source=source,
                order_id=external_ref or None,
                message="Pagamento do Mercado Pago sem doação local correspondente",
                mp_payment_id=resolved_mp_id, mp_status_raw=mp_status,
            )
            out.update(result="no_row", message="Nenhuma doação local corresponde a este pagamento")
            return out

        payment_id = payment.payment_id
        was_credited = bool(payment.credited)
        old_status = payment.status
        old_mp_id = payment.mp_payment_id
        base_audit = dict(
            order_id=payment_id, actor_steam_id=payment.steam_id,
            mp_payment_id=resolved_mp_id, mp_status_raw=mp_status,
            mapped_status=mapped, amount_brl=payment.amount_brl,
            paid_amount=mp_resp.get("transaction_amount"),
            status_detail=mp_resp.get("status_detail"),
        )

        if resolved_mp_id and (
            not old_mp_id or (mapped == "APROVADO" and not was_credited and old_mp_id != resolved_mp_id)
        ):
            payment.mp_payment_id = resolved_mp_id
            payment.updated_at = app_mod._now()

        if mapped == "APROVADO" and not was_credited and not mp_amount_covers_package(
            mp_resp, payment.amount_brl,
        ):
            db.commit()
            log.error(
                "mp confirm amount mismatch payment_id=%s paid=%s expected=%s",
                payment_id, mp_resp.get("transaction_amount"), payment.amount_brl,
            )
            audit = dict(
                event_type="mp_amount_mismatch", severity="error", source=source,
                message="Pagamento aprovado com valor MENOR que o pacote — NÃO creditado (revisar manualmente)",
                **base_audit,
            )
            out.update(
                result="amount_mismatch", status=old_status, credited=False,
                message="Valor pago menor que o do pacote — não creditado",
            )
            return out

        if (
            was_credited and mapped == "APROVADO" and old_mp_id and resolved_mp_id
            and old_mp_id != resolved_mp_id
        ):
            audit_dup = dict(
                event_type="mp_duplicate_approved", severity="warn", source=source,
                message="Segundo pagamento aprovado para a mesma doação (já creditada) — avaliar estorno",
                **base_audit,
            )
        else:
            audit_dup = None

        app_mod._finalize_pix_payment(db, payment, mp_status, source=source)
        db.commit()
        log.info(
            "mp confirm done payment_id=%s status=%s credited=%s source=%s",
            payment.payment_id, payment.status, payment.credited, source,
        )
        newly_credited = bool(payment.credited) and not was_credited
        result = "credited" if newly_credited else (
            "already_credited" if was_credited else ("updated" if payment.status != old_status else "unchanged")
        )
        out.update(
            result=result, payment_id=payment_id, status=payment.status,
            credited=bool(payment.credited), points=int(payment.points or 0),
        )
        audit = dict(
            event_type="mp_payment_checked",
            severity="info", source=source,
            message=f"MP status={mp_status or '?'} → {payment.status} ({result})",
            status_before=old_status, status_after=payment.status,
            result=result, **base_audit,
        )
        if audit_dup:
            _safe_audit(app_mod, **audit_dup)
        return out
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        log.exception("mp confirm DB failed mp_id=%s source=%s", mp_id, source)
        audit = dict(
            event_type="mp_payment_apply_failed", severity="error", source=source,
            order_id=external_ref or None,
            message=f"Falha ao aplicar pagamento do Mercado Pago: {str(exc)[:300]}",
            mp_payment_id=resolved_mp_id, mp_status_raw=mp_status,
        )
        out.update(result="error", message=f"Falha ao aplicar: {str(exc)[:200]}")
        return out
    finally:
        app_mod._release_db_session(db, force=True)
        if audit:
            if actor_steam_id:
                audit["actor_type"] = "admin"
                if audit.get("actor_steam_id"):
                    audit["target_steam_id"] = audit["actor_steam_id"]
                audit["actor_steam_id"] = actor_steam_id
            _safe_audit(app_mod, **audit)


def reconcile_payment(
    payment_id: str,
    *,
    source: str = "admin_reconcile",
    actor_steam_id: str | None = None,
    attempts: int = 1,
) -> dict[str, Any]:
    """Reconsulta o MP (GET, somente leitura) para UMA doação e aplica o fluxo idempotente."""
    import app as app_mod
    from pix_payments import pick_best_payment, search_payments_by_external_reference

    pid = str(payment_id or "").strip()
    token = app_mod._get_mp_access_token()
    if not token:
        return {"result": "no_token", "message": "Access Token do Mercado Pago não configurado"}

    db = app_mod._SessionLocal()
    try:
        row = (
            db.query(app_mod.PointPayment)
            .filter(app_mod.PointPayment.payment_id == pid)
            .first()
        )
        if not row:
            return {"result": "not_found", "message": "Doação não encontrada"}
        snap = {
            "credited": bool(row.credited),
            "status": row.status,
            "mp_id": str(row.mp_payment_id or "").strip(),
            "method": app_mod._resolve_payment_method(row),
        }
    finally:
        app_mod._release_db_session(db, force=True)

    if snap["credited"]:
        return {
            "result": "already_credited", "payment_id": pid, "status": snap["status"],
            "credited": True, "message": "Doação já creditada — nada a fazer",
        }

    mp_resp: dict[str, Any] | None = None
    last_err: Exception | None = None
    # Cartão/boleto (Checkout Pro): pode haver várias tentativas por preferência —
    # a busca por external_reference acha a aprovada. PIX: id direto.
    if snap["method"] != "pix" or not snap["mp_id"]:
        try:
            mp_resp = pick_best_payment(
                search_payments_by_external_reference(token, pid, timeout=app_mod._MP_WEBHOOK_FETCH_TIMEOUT * 2)
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    if mp_resp is None and snap["mp_id"]:
        mp_resp, last_err = _fetch_mp_payment(app_mod, token, snap["mp_id"], attempts=attempts)
    if mp_resp is None:
        err = f": {str(last_err)[:200]}" if last_err else ""
        _safe_audit(
            app_mod, "mp_payment_fetch_failed", severity="warn", source=source,
            order_id=pid, message=f"Reconsulta MP sem resultado{err}",
            mp_payment_id=snap["mp_id"] or None,
        )
        return {
            "result": "not_found_in_mp", "payment_id": pid, "status": snap["status"],
            "credited": False,
            "message": f"Mercado Pago não retornou pagamento para esta doação{err}",
        }

    res = apply_mp_payment_response(
        app_mod, mp_resp, mp_id=snap["mp_id"], payment_id_hint=pid,
        source=source, actor_steam_id=actor_steam_id,
    )
    res.setdefault("payment_id", pid)
    return res


def reconcile_pending_payments(
    *,
    max_age_hours: float = 72.0,
    limit: int = 30,
    source: str = "auto_reconcile",
) -> dict[str, Any]:
    """Varre doações não creditadas (PENDENTE/ABANDONADO) recentes e reconsulta o MP."""
    import app as app_mod
    from datetime import timedelta

    if not app_mod._get_mp_access_token() or app_mod._SessionLocal is None:
        return {"checked": 0, "credited": 0}
    cutoff = app_mod._now() - timedelta(hours=max(1.0, float(max_age_hours)))
    db = app_mod._SessionLocal()
    try:
        ids = [
            r[0]
            for r in db.query(app_mod.PointPayment.payment_id)
            .filter(
                app_mod.PointPayment.credited.is_(False),
                app_mod.PointPayment.status.in_(("PENDENTE", "ABANDONADO")),
                app_mod.PointPayment.created_at >= cutoff,
            )
            .order_by(app_mod.PointPayment.created_at.desc())
            .limit(max(1, int(limit)))
            .all()
        ]
    finally:
        app_mod._release_db_session(db, force=True)

    checked = credited = 0
    for pid in ids:
        try:
            res = reconcile_payment(pid, source=source)
        except Exception:  # noqa: BLE001
            log.exception("auto reconcile falhou payment_id=%s", pid)
            continue
        checked += 1
        if res.get("result") == "credited":
            credited += 1
        time.sleep(0.3)
    if checked:
        log.info("auto reconcile: verificadas=%s creditadas=%s", checked, credited)
    return {"checked": checked, "credited": credited}
