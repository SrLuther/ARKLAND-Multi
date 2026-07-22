"""Jobs de confirmação de pagamento Mercado Pago (Fase 2).

Fluxo: request HTTP só lê/escreve DB curto → responde → fetch MP + crédito
correm aqui, sem segurar worker Waitress.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

log = logging.getLogger("arkshop_web.payment_jobs")


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


def _confirm_mp_payment(
    mp_payment_id: str,
    *,
    payment_id: str | None = None,
    source: str = "poll",
) -> None:
    """Corre fora do request: HTTP MP → sessão DB curta → crédito."""
    # Import lazy evita ciclo app ↔ jobs.
    import app as app_mod

    token = app_mod._get_mp_access_token()
    if not token:
        log.warning("mp confirm skip: token ausente source=%s", source)
        return

    mp_id = str(mp_payment_id or "").strip()
    mp_resp: dict[str, Any] | None = None
    if mp_id:
        try:
            mp_resp = app_mod.fetch_payment(
                token, mp_id, timeout=app_mod._MP_WEBHOOK_FETCH_TIMEOUT,
            )
        except Exception as exc:
            log.warning(
                "mp confirm fetch failed mp_id=%s source=%s: %s",
                mp_id, source, exc,
            )
            return

    if mp_resp is None:
        return

    external_ref = str(mp_resp.get("external_reference") or "").strip() or payment_id
    resolved_mp_id = str(mp_resp.get("id") or mp_id or "").strip()
    mp_status = str(mp_resp.get("status", "") or "")

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
            return

        if resolved_mp_id and not payment.mp_payment_id:
            payment.mp_payment_id = resolved_mp_id
            payment.updated_at = app_mod._now()

        app_mod._finalize_pix_payment(db, payment, mp_status, source=source)
        db.commit()
        log.info(
            "mp confirm done payment_id=%s status=%s credited=%s source=%s",
            payment.payment_id, payment.status, payment.credited, source,
        )
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        log.exception("mp confirm DB failed mp_id=%s source=%s", mp_id, source)
    finally:
        app_mod._release_db_session(db, force=True)
