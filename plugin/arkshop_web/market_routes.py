"""Rotas HTTP do Mercado de Dinos."""
from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify, request

from market_economy import (
    calculate_suggested_value,
    load_economy_global_config,
    load_tier_legend,
    list_species_economy_meta,
    normalize_stat_points,
    patch_economy_global_config,
    patch_species_economy_meta,
    shop_catalog_display_name,
    simulate_economy,
    species_economy_meta_from_defaults,
)
from market_service import (
    get_species_table_payload,
    list_species_public,
    pre_register_catalog_item,
    sync_catalog_to_db,
    sync_registry_overlay_to_db,
    update_species_display_name,
    _list_species_aliases,
    _species_row_is_commerce_dino,
)

from market_listings import (
    admin_bulk_classify_listings,
    admin_classify_listing,
    admin_flag_listing,
    admin_remove_listing,
    admin_set_listing_price,
    claim_deliveries,
    commerce_ready,
    get_listing_detail,
    get_pending_claims,
    get_profile,
    list_active_listings,
    list_market_audit_events,
    list_pending_classification,
    list_seller_listings,
    list_seller_vitrine_audit_events,
    mark_claim_delivered,
    pause_listing,
    player_market_history,
    preview_plugin_economy,
    process_plugin_admin_action,
    process_plugin_upload,
    promote_listings_on_species_activate,
    reconcile_pending_listings,
    recompute_draft_listings,
    purchase_listing,
    release_claims,
    set_listing_price,
    upsert_display_name,
    withdraw_listing,
    expire_stale_claims,
)


def register_market_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    read_shop_config: Callable[[], dict[str, Any]],
    admin_required: Callable,
    login_required: Callable,
    api_key_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    audit_event: Callable[..., None],
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    def _ensure_market_player_profile_table() -> tuple[bool, str | None]:
        """Garante market_player_profile antes de ler/gravar nome (migrate pode ser assíncrono)."""
        from app import _ENGINE
        from market_migrate import ensure_market_schema, schema_status

        if _ENGINE is None:
            return False, "Engine indisponível"
        try:
            st = schema_status(_ENGINE)
            if not st.get("tables", {}).get("market_player_profile"):
                ensure_market_schema(_ENGINE, bootstrap=False)
                st = schema_status(_ENGINE)
            if not st.get("tables", {}).get("market_player_profile"):
                return False, "Tabela de perfil do mercado indisponível — aguarde a migração do banco."
            return True, None
        except Exception as exc:
            return False, str(exc)

    @app.route("/api/market/species-table", methods=["GET"])
    def market_species_table_public():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            payload = get_species_table_payload(db)
            payload["ok"] = True
            return jsonify(payload)
        finally:
            db.close()

    @app.route("/api/market/calculate-preview", methods=["POST"])
    def market_calculate_preview():
        """Preview de valor sugerido + breakdown (sem persistir)."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        species_key = str(body.get("species_key") or "").strip()
        if not species_key:
            return jsonify({"ok": False, "error": "species_key obrigatório"}), 400
        db = session_factory()
        try:
            from app import MarketSpecies, MarketSpeciesStatMultiplier
            from market_service import species_row_to_economy

            row = db.query(MarketSpecies).filter(MarketSpecies.species_key == species_key).first()
            if not row:
                return jsonify({"ok": False, "error": "Espécie não cadastrada"}), 404
            mult_rows = (
                db.query(MarketSpeciesStatMultiplier)
                .filter(MarketSpeciesStatMultiplier.species_id == row.id)
                .all()
            )
            economy = species_row_to_economy(row, mult_rows)
            points = normalize_stat_points(body.get("stats_max") or body.get("stat_points") or {})
            total, breakdown = calculate_suggested_value(economy, points)
            return jsonify(
                {
                    "ok": True,
                    "species_key": species_key,
                    "computed_base_value": total,
                    "calculation_breakdown": breakdown,
                    "species": economy.to_dict(),
                }
            )
        finally:
            db.close()

    @app.route("/api/market/admin/species", methods=["GET"])
    @admin_required
    def market_admin_list_species():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        status = (request.args.get("status") or "").strip()
        db = session_factory()
        try:
            from app import MarketSpecies

            q = db.query(MarketSpecies).order_by(MarketSpecies.root_value.desc())
            if status:
                q = q.filter(MarketSpecies.status == status)
            else:
                q = q.filter(MarketSpecies.status != "INACTIVE")
            rows = [r for r in q.all() if _species_row_is_commerce_dino(db, r)]
            items = list_species_public(db, active_only=False)
            by_key = {i["species_key"]: i for i in items}
            catalog = read_shop_config()
            out = []
            for row in rows:
                data = by_key.get(row.species_key) or {
                    "species_key": row.species_key,
                    "display_name": row.display_name,
                    "root_value": row.root_value,
                    "status": row.status,
                }
                data["status"] = row.status
                data["catalog_item_id"] = row.catalog_item_id
                data["shop_catalog_name"] = shop_catalog_display_name(catalog, row.catalog_item_id)
                data["linked_variants"] = _list_species_aliases(db, row.id)
                out.append(data)
            return jsonify({"ok": True, "species": out, "tier_legend": load_tier_legend()})
        finally:
            db.close()

    @app.route("/api/market/admin/species/sync-catalog", methods=["POST"])
    @admin_required
    def market_admin_sync_catalog():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        activate = bool(body.get("activate", False))
        reset_display_names = bool(body.get("reset_display_names", False))
        raw_overrides = body.get("display_names") or body.get("display_name_overrides") or {}
        overrides = (
            {str(k): str(v) for k, v in raw_overrides.items() if str(v).strip()}
            if isinstance(raw_overrides, dict)
            else None
        )
        db = session_factory()
        try:
            result = sync_catalog_to_db(
                db,
                read_shop_config(),
                activate=activate,
                display_name_overrides=overrides,
                reset_display_names=reset_display_names,
            )
            audit_event(
                "MARKET_CATALOG_SYNC",
                source="admin",
                actor_type="admin",
                **result,
            )
            return jsonify({"ok": True, **result})
        finally:
            db.close()

    @app.route("/api/market/admin/species/sync-registry", methods=["POST"])
    @admin_required
    def market_admin_sync_registry():
        """Importa overlay ark_species_registry.json (mods Abyss, etc.) para market_species."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        activate = bool(body.get("activate", False))
        only_missing = bool(body.get("only_missing", False))
        reset_display_names = bool(body.get("reset_display_names", False))
        raw_overrides = body.get("display_names") or body.get("display_name_overrides") or {}
        overrides = (
            {str(k): str(v) for k, v in raw_overrides.items() if str(v).strip()}
            if isinstance(raw_overrides, dict)
            else None
        )
        db = session_factory()
        try:
            result = sync_registry_overlay_to_db(
                db,
                activate=activate,
                only_missing=only_missing,
                display_name_overrides=overrides,
                reset_display_names=reset_display_names,
            )
            audit_event(
                "MARKET_REGISTRY_SYNC",
                source="admin",
                actor_type="admin",
                **result,
            )
            return jsonify({"ok": True, **result})
        finally:
            db.close()

    @app.route("/api/market/admin/species/<species_key>", methods=["PATCH"])
    @admin_required
    def market_admin_patch_species(species_key: str):
        """Renomeia espécie só no Comércio (tabela/vitrine) — não altera a loja."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        name = str(body.get("display_name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "display_name obrigatório"}), 400
        db = session_factory()
        try:
            result = update_species_display_name(
                db,
                species_key,
                name,
                catalog=read_shop_config(),
            )
            audit_event(
                "MARKET_SPECIES_DISPLAY_NAME_UPDATED",
                species_key=species_key,
                metadata={"display_name": name},
            )
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/admin/species/<species_key>/activate", methods=["POST"])
    @admin_required
    def market_admin_activate_species(species_key: str):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        from datetime import datetime, timezone

        from app import MarketSpecies

        db = session_factory()
        try:
            row = db.query(MarketSpecies).filter(MarketSpecies.species_key == species_key).first()
            if not row:
                return jsonify({"ok": False, "error": "Espécie não encontrada"}), 404
            row.status = "ACTIVE"
            row.activated_at = datetime.now(timezone.utc)
            db.commit()
            promoted = promote_listings_on_species_activate(db, species_key)
            promoted += reconcile_pending_listings(db)
            audit_event(
                "MARKET_SPECIES_ACTIVATED",
                species_key=species_key,
                promoted_listings=promoted,
            )
            return jsonify(
                {
                    "ok": True,
                    "species_key": species_key,
                    "status": "ACTIVE",
                    "promoted_listings": promoted,
                }
            )
        finally:
            db.close()

    @app.route("/api/market/admin/listings/reconcile-pending", methods=["POST"])
    @admin_required
    def market_admin_reconcile_pending():
        """Promove listings PENDING cuja espécie já está ACTIVE (correção manual)."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            promoted = reconcile_pending_listings(db)
            audit_event("MARKET_LISTINGS_RECONCILED", promoted_listings=promoted)
            return jsonify({"ok": True, "promoted_listings": promoted})
        finally:
            db.close()

    @app.route("/api/market/admin/economy/config", methods=["GET"])
    @admin_required
    def market_admin_economy_config_get():
        cfg = load_economy_global_config()
        species = list_species_economy_meta()
        if db_ready():
            db = session_factory()
            try:
                from app import MarketSpecies

                db_rows = {
                    r.species_key: r for r in db.query(MarketSpecies).all()
                }
                for sp in species:
                    row = db_rows.get(sp["species_key"])
                    if row and row.root_value:
                        sp["root_value"] = row.root_value
                        sp["bonus_space"] = max(
                            0, sp["size_cap"] - row.root_value
                        )
                        sp["db_status"] = row.status
            finally:
                db.close()
        cfg["species"] = species
        return jsonify({"ok": True, **cfg})

    @app.route("/api/market/admin/economy/config", methods=["PATCH"])
    @admin_required
    def market_admin_economy_config_patch():
        body = request.get_json(silent=True) or {}
        try:
            cfg = patch_economy_global_config(body)
            audit_event("MARKET_ECONOMY_CONFIG_UPDATED")
            return jsonify({"ok": True, **cfg})
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/market/admin/economy/species/<species_key>", methods=["PATCH"])
    @admin_required
    def market_admin_economy_species_patch(species_key: str):
        body = request.get_json(silent=True) or {}
        updated = patch_species_economy_meta(species_key.strip(), body)
        if updated is None:
            return jsonify({"ok": False, "error": "Espécie não encontrada no JSON"}), 404
        audit_event("MARKET_ECONOMY_SPECIES_UPDATED", species_key=species_key)
        meta = species_economy_meta_from_defaults(species_key)
        return jsonify({"ok": True, "species_key": species_key, **meta})

    @app.route("/api/market/admin/economy/simulate", methods=["POST"])
    @admin_required
    def market_admin_economy_simulate():
        body = request.get_json(silent=True) or {}
        species_key = str(body.get("species_key") or "").strip()
        if not species_key:
            return jsonify({"ok": False, "error": "species_key obrigatório"}), 400
        root = body.get("root_value")
        root_value = int(root) if root is not None else None
        result = simulate_economy(
            species_key,
            body.get("stats_max") or body.get("stat_points") or {},
            root_value=root_value,
        )
        if result is None:
            return jsonify({"ok": False, "error": "Espécie não encontrada"}), 404
        return jsonify({"ok": True, **result})

    @app.route("/api/market/admin/economy/recompute-listings", methods=["POST"])
    @admin_required
    def market_admin_economy_recompute_listings():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            count = recompute_draft_listings(db)
            audit_event("MARKET_LISTINGS_RECOMPUTED", count=count)
            return jsonify({"ok": True, "recomputed": count})
        finally:
            db.close()

    @app.route("/api/market/admin/species/<species_key>/multipliers/defaults", methods=["GET"])
    @admin_required
    def market_admin_mult_defaults(species_key: str):
        """Multiplicadores sugeridos de market_species_defaults.json (para o editor admin)."""
        from market_economy import build_multipliers_from_defaults

        mults = build_multipliers_from_defaults(species_key.strip())
        return jsonify(
            {
                "ok": True,
                "species_key": species_key,
                "multipliers": {k: v.to_dict() for k, v in sorted(mults.items())},
            }
        )

    @app.route("/api/market/admin/species/<species_key>/multipliers", methods=["PATCH"])
    @admin_required
    def market_admin_patch_multipliers(species_key: str):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        mults = body.get("multipliers")
        if not isinstance(mults, dict):
            return jsonify({"ok": False, "error": "multipliers obrigatório"}), 400
        db = session_factory()
        try:
            from app import MarketSpecies, MarketSpeciesStatMultiplier

            row = db.query(MarketSpecies).filter(MarketSpecies.species_key == species_key).first()
            if not row:
                return jsonify({"ok": False, "error": "Espécie não encontrada"}), 404
            for stat_key, val in mults.items():
                if isinstance(val, dict):
                    multiplier = int(val.get("multiplier", 0))
                    enabled = bool(val.get("enabled", multiplier > 0))
                else:
                    multiplier = int(val)
                    enabled = multiplier > 0
                mrow = (
                    db.query(MarketSpeciesStatMultiplier)
                    .filter(
                        MarketSpeciesStatMultiplier.species_id == row.id,
                        MarketSpeciesStatMultiplier.stat_key == stat_key,
                    )
                    .first()
                )
                if mrow is None:
                    mrow = MarketSpeciesStatMultiplier(
                        species_id=row.id, stat_key=stat_key
                    )
                    db.add(mrow)
                mrow.multiplier = multiplier
                mrow.enabled = enabled
            db.commit()
            audit_event("MARKET_SPECIES_MULTIPLIERS_UPDATED", species_key=species_key)
            return jsonify({"ok": True, "species_key": species_key})
        finally:
            db.close()

    @app.route("/api/market/admin/listings/classify", methods=["POST"])
    @admin_required
    def market_admin_classify_listing():
        """Confirma classificação admin: ativa espécie e promove listing para DRAFT."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        listing_id = int(body.get("listing_id") or 0)
        if not listing_id:
            return jsonify({"ok": False, "error": "listing_id obrigatório"}), 400
        db = session_factory()
        try:
            result = admin_classify_listing(
                db,
                listing_id,
                species_key=str(body.get("species_key") or "").strip() or None,
                display_name=str(body.get("display_name") or "").strip() or None,
                tier=str(body.get("tier") or "").strip() or None,
                root_value=int(body["root_value"]) if body.get("root_value") is not None else None,
                approve=bool(body.get("approve", True)),
            )
            audit_event("MARKET_LISTING_CLASSIFIED", listing_id=listing_id, **result)
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/admin/listings/classify/bulk", methods=["POST"])
    @admin_required
    def market_admin_classify_bulk():
        """Aprova em lote listings com sugestão de alta confiança."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        raw_ids = body.get("listing_ids") or []
        listing_ids = (
            [int(x) for x in raw_ids if str(x).isdigit()] if isinstance(raw_ids, list) else None
        )
        db = session_factory()
        try:
            result = admin_bulk_classify_listings(
                db,
                listing_ids=listing_ids,
                min_confidence=str(body.get("min_confidence") or "high"),
                limit=min(100, int(body.get("limit") or 50)),
            )
            audit_event("MARKET_LISTINGS_BULK_CLASSIFIED", **result)
            return jsonify({"ok": True, **result})
        finally:
            db.close()

    @app.route("/api/market/admin/listings/<int:listing_id>/remove", methods=["POST"])
    @admin_required
    def market_admin_listing_remove(listing_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        admin_steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            result = admin_remove_listing(
                db,
                listing_id,
                admin_steam_id,
                reason=str(body.get("reason") or ""),
            )
            audit_event("MARKET_LISTING_ADMIN_REMOVED", listing_id=listing_id)
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/admin/listings/<int:listing_id>/price", methods=["PATCH"])
    @admin_required
    def market_admin_listing_price(listing_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        price = body.get("price_absolute") or body.get("price")
        if price is None:
            return jsonify({"ok": False, "error": "price obrigatório"}), 400
        admin_steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            listing = admin_set_listing_price(
                db,
                listing_id,
                admin_steam_id,
                int(price),
                pause=bool(body.get("pause", False)),
            )
            return jsonify({"ok": True, "listing": listing})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/admin/listings/<int:listing_id>/flag", methods=["POST"])
    @admin_required
    def market_admin_listing_flag(listing_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        admin_steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            listing = admin_flag_listing(
                db,
                listing_id,
                admin_steam_id,
                reason=str(body.get("reason") or ""),
                pause=bool(body.get("pause", True)),
            )
            return jsonify({"ok": True, "listing": listing})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/admin/species/registry-stats", methods=["GET"])
    @admin_required
    def market_admin_registry_stats():
        from ark_species_registry import registry_stats

        return jsonify({"ok": True, **registry_stats()})

    @app.route("/api/market/admin/species/pending-classification", methods=["GET"])
    @admin_required
    def market_admin_pending_classification():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            items = list_pending_classification(db)
            return jsonify({"ok": True, "listings": items})
        finally:
            db.close()

    @app.route("/api/market/catalog/dinos", methods=["GET"])
    @admin_required
    def market_catalog_dinos_status():
        """Lista dinos do config.json com status no Comércio (admin)."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        from market_service import list_catalog_dinos_market_status

        db = session_factory()
        try:
            catalog = read_shop_config()
            dinos = list_catalog_dinos_market_status(db, catalog)
            missing = [d for d in dinos if not d.get("market_registered")]
            return jsonify(
                {
                    "ok": True,
                    "dinos": dinos,
                    "total": len(dinos),
                    "registered": len(dinos) - len(missing),
                    "missing": len(missing),
                }
            )
        finally:
            db.close()

    @app.route("/api/market/catalog/pre-register", methods=["POST"])
    @admin_required
    def market_pre_register():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        catalog_item_id = str(body.get("catalog_item_id") or body.get("item_id") or "").strip()
        db = session_factory()
        try:
            result = pre_register_catalog_item(db, read_shop_config(), catalog_item_id)
            audit_event(
                "MARKET_SPECIES_PRE_REGISTERED",
                source="admin",
                actor_type="admin",
                **result,
            )
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/catalog/pre-register/bulk", methods=["POST"])
    @admin_required
    def market_pre_register_bulk():
        """Pré-cadastra vários dinos do catálogo (ou todos os ausentes)."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        from market_service import bulk_pre_register_catalog_items

        body = request.get_json(silent=True) or {}
        raw_ids = body.get("catalog_item_ids") or body.get("item_ids")
        item_ids = None
        if isinstance(raw_ids, list):
            item_ids = [str(i) for i in raw_ids]
        only_missing = bool(body.get("only_missing", True))
        activate = bool(body.get("activate", False))
        db = session_factory()
        try:
            result = bulk_pre_register_catalog_items(
                db,
                read_shop_config(),
                item_ids=item_ids,
                only_missing=only_missing,
                activate=activate,
            )
            audit_event(
                "MARKET_SPECIES_PRE_REGISTERED_BULK",
                source="admin",
                actor_type="admin",
                created=result.get("created"),
                updated=result.get("updated"),
                skipped=result.get("skipped"),
            )
            return jsonify({"ok": True, **result})
        finally:
            db.close()

    @app.route("/api/market/admin/schema-status", methods=["GET"])
    @admin_required
    def market_admin_schema_status():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        from app import _ENGINE
        from market_migrate import schema_status

        if _ENGINE is None:
            return jsonify({"ok": False, "error": "Engine indisponível"}), 503
        try:
            status = schema_status(_ENGINE)
            return jsonify({"ok": True, **status})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    # ── Perfil Comércio ───────────────────────────────────────────────────────

    @app.route("/api/market/profile", methods=["GET"])
    @login_required
    def market_get_profile():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        schema_ok, schema_err = _ensure_market_player_profile_table()
        if not schema_ok:
            return jsonify({"ok": False, "error": schema_err or "Schema do mercado indisponível"}), 503
        steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            row = get_profile(db, steam_id)
            if not row:
                return jsonify({"ok": True, "profile": None, "commerce_enabled": False})
            return jsonify(
                {
                    "ok": True,
                    "profile": {
                        "steam_id": row.steam_id,
                        "market_display_name": row.market_display_name,
                        "commerce_enabled": row.commerce_enabled,
                    },
                }
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/market/profile/display-name", methods=["PATCH"])
    @login_required
    @_limit("10 per minute")
    def market_set_display_name():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        schema_ok, schema_err = _ensure_market_player_profile_table()
        if not schema_ok:
            return jsonify({"ok": False, "error": schema_err or "Schema do mercado indisponível"}), 503
        body = request.get_json(silent=True) or {}
        name = str(body.get("market_display_name") or body.get("display_name") or "").strip()
        steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            result = upsert_display_name(db, steam_id, name)
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    # ── Listings (web) ────────────────────────────────────────────────────────

    @app.route("/api/market/listings", methods=["GET"])
    def market_list_listings():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        species_key = (request.args.get("species_key") or "").strip() or None
        seller = (request.args.get("seller_steam_id") or "").strip() or None
        limit = min(100, max(1, int(request.args.get("limit") or 50)))
        offset = max(0, int(request.args.get("offset") or 0))
        db = session_factory()
        try:
            items = list_active_listings(
                db, species_key=species_key, seller_steam_id=seller, limit=limit, offset=offset
            )
            return jsonify({"ok": True, "listings": items})
        finally:
            db.close()

    @app.route("/api/market/vitrine/<steam_id>", methods=["GET"])
    def market_vitrine(steam_id: str):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            items = list_active_listings(db, seller_steam_id=steam_id.strip())
            prof = get_profile(db, steam_id.strip())
            return jsonify(
                {
                    "ok": True,
                    "seller_steam_id": steam_id,
                    "seller_display_name": prof.market_display_name if prof else None,
                    "listings": items,
                }
            )
        finally:
            db.close()

    @app.route("/api/market/listings/<int:listing_id>/price", methods=["PATCH"])
    @login_required
    def market_set_price(listing_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            price = body.get("price_absolute")
            activate = bool(body.get("activate", False))
            kwargs: dict[str, Any] = {
                "price_absolute": int(price) if price is not None else None,
                "activate": activate,
            }
            if "custom_name" in body:
                kwargs["custom_name"] = body.get("custom_name")
            if "category" in body:
                kwargs["category"] = body.get("category")
            if "custom_description" in body:
                kwargs["custom_description"] = body.get("custom_description")
            result = set_listing_price(db, listing_id, steam_id, **kwargs)
            return jsonify({"ok": True, "listing": result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/listings/<int:listing_id>/purchase", methods=["POST"])
    @login_required
    @_limit("10 per minute; 30 per hour")
    def market_purchase(listing_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            result = purchase_listing(db, listing_id, steam_id)
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/listings/<int:listing_id>", methods=["GET"])
    def market_get_listing(listing_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        viewer = steam_id_from_session()
        db = session_factory()
        try:
            item = get_listing_detail(db, listing_id, viewer_steam_id=viewer)
            return jsonify({"ok": True, "listing": item})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        finally:
            db.close()

    @app.route("/api/market/my/listings", methods=["GET"])
    @login_required
    def market_my_listings():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            items = list_seller_listings(db, steam_id)
            return jsonify({"ok": True, "listings": items})
        finally:
            db.close()

    @app.route("/api/market/listings/<int:listing_id>/pause", methods=["POST"])
    @login_required
    def market_pause_listing(listing_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            result = pause_listing(db, listing_id, steam_id)
            return jsonify({"ok": True, "listing": result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/listings/<int:listing_id>/withdraw", methods=["POST"])
    @login_required
    def market_withdraw_listing(listing_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            result = withdraw_listing(db, listing_id, steam_id)
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/my/history", methods=["GET"])
    @login_required
    def market_my_history():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            history = player_market_history(db, steam_id)
            return jsonify({"ok": True, **history})
        finally:
            db.close()

    @app.route("/api/market/my/audit", methods=["GET"])
    @login_required
    def market_my_audit():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session() or "")
        limit = min(100, max(1, int(request.args.get("limit") or 50)))
        offset = max(0, int(request.args.get("offset") or 0))
        db = session_factory()
        try:
            events = list_seller_vitrine_audit_events(
                db, steam_id, limit=limit, offset=offset
            )
            return jsonify({"ok": True, "events": events})
        finally:
            db.close()

    @app.route("/api/market/admin/audit/export", methods=["GET"])
    @admin_required
    def market_admin_audit_export():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        import csv
        import io

        event_type = (request.args.get("event_type") or "").strip() or None
        steam_id = (request.args.get("steam_id") or "").strip() or None
        db = session_factory()
        try:
            events = list_market_audit_events(
                db, event_type=event_type, steam_id=steam_id, limit=500
            )
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(
                [
                    "created_at",
                    "event_type",
                    "severity",
                    "steam_id",
                    "listing_id",
                    "claim_id",
                    "effective_price",
                    "market_trace_id",
                ]
            )
            for ev in events:
                writer.writerow(
                    [
                        ev.get("created_at"),
                        ev.get("event_type"),
                        ev.get("severity"),
                        ev.get("steam_id"),
                        ev.get("listing_id"),
                        ev.get("claim_id"),
                        ev.get("effective_price"),
                        ev.get("market_trace_id"),
                    ]
                )
            from flask import Response

            return Response(
                buf.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=market_audit.csv"},
            )
        finally:
            db.close()

    @app.route("/api/market/admin/audit", methods=["GET"])
    @admin_required
    def market_admin_audit():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        event_type = (request.args.get("event_type") or "").strip() or None
        steam_id = (request.args.get("steam_id") or "").strip() or None
        trace = (request.args.get("market_trace_id") or "").strip() or None
        limit = min(500, max(1, int(request.args.get("limit") or 100)))
        offset = max(0, int(request.args.get("offset") or 0))
        db = session_factory()
        try:
            events = list_market_audit_events(
                db,
                event_type=event_type,
                steam_id=steam_id,
                market_trace_id=trace,
                limit=limit,
                offset=offset,
            )
            return jsonify({"ok": True, "events": events})
        finally:
            db.close()

    # ── Plugin (X-API-Key) ────────────────────────────────────────────────────

    @app.route("/api/market/plugin/profile/<steam_id>", methods=["GET"])
    @api_key_required(allow_admin_session=False)
    @_limit("120 per minute")
    def market_plugin_profile(steam_id: str):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            ready, err = commerce_ready(db, steam_id.strip())
            prof = get_profile(db, steam_id.strip())
            return jsonify(
                {
                    "ok": True,
                    "commerce_ready": ready,
                    "error": err,
                    "market_display_name": prof.market_display_name if prof else None,
                }
            )
        finally:
            db.close()

    @app.route("/api/market/plugin/preview", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("60 per minute")
    def market_plugin_preview():
        """Preview de economia para /enviar in-game (sem persistir)."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        metadata = body.get("metadata") or body
        db = session_factory()
        try:
            result = preview_plugin_economy(db, metadata if isinstance(metadata, dict) else {})
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/market/upload", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("30 per minute")
    def market_plugin_upload():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        db = session_factory()
        try:
            result = process_plugin_upload(db, body)
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            audit_event(
                "MARKET_UPLOAD_REJECTED",
                severity="warn",
                source="plugin",
                target_steam_id=str(body.get("steam_id") or ""),
                message=str(exc),
            )
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/plugin/admin", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("30 per minute")
    def market_plugin_admin():
        """Moderação in-game (/mercado_admin) — requer admin_steam_id na lista de admins."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        db = session_factory()
        try:
            result = process_plugin_admin_action(db, body)
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/pending/<steam_id>", methods=["GET"])
    @api_key_required(allow_admin_session=False)
    @_limit("60 per minute")
    def market_pending_claims(steam_id: str):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            items = get_pending_claims(db, steam_id.strip())
            return jsonify({"ok": True, "claims": items})
        finally:
            db.close()

    @app.route("/api/market/claims/claim", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("60 per minute")
    def market_claims_claim():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        steam_id = str(body.get("steam_id") or "").strip()
        raw_ids = body.get("claim_ids") or []
        claim_ids = [int(x) for x in raw_ids if str(x).isdigit()] if isinstance(raw_ids, list) else []
        db = session_factory()
        try:
            claimed = claim_deliveries(db, steam_id, claim_ids)
            return jsonify({"ok": True, "claimed": claimed})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/market/admin/claims/expire-stale", methods=["POST"])
    @admin_required
    def market_admin_expire_stale_claims():
        """Dispara processamento manual de claims expirados (auditoria / suporte)."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        batch = min(200, max(1, int(body.get("batch_size") or 50)))
        db = session_factory()
        try:
            result = expire_stale_claims(db, batch_size=batch)
            audit_event("MARKET_CLAIMS_EXPIRE_MANUAL", **result)
            return jsonify({"ok": True, **result})
        finally:
            db.close()

    @app.route("/api/market/claims/release", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("60 per minute")
    def market_claims_release():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        steam_id = str(body.get("steam_id") or "").strip()
        raw_ids = body.get("claim_ids") or []
        claim_ids = [int(x) for x in raw_ids if str(x).isdigit()] if isinstance(raw_ids, list) else []
        db = session_factory()
        try:
            released = release_claims(db, steam_id, claim_ids)
            return jsonify({"ok": True, "released": released})
        finally:
            db.close()

    @app.route("/api/market/claims/delivered", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("60 per minute")
    def market_claims_delivered():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        steam_id = str(body.get("steam_id") or "").strip()
        claim_id = int(body.get("claim_id") or 0)
        db = session_factory()
        try:
            result = mark_claim_delivered(db, claim_id, steam_id)
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()
