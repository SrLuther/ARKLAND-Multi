"""Compare a read-only ASE save copy with the live census. Never enables enforcement."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import ntpath
from pathlib import Path
import subprocess
import sys
import uuid

PARSER_COMMIT = "1d9a3e2b1a8052fdfc187174edfc920ca53216f3"


def class_key(value):
    return str(value).rsplit("/", 1)[-1].rsplit(".", 1)[-1].casefold().removesuffix("_c")


def u32(value):
    return int(value or 0) & 0xFFFFFFFF


def coordinates(value):
    result = tuple(float(part) for part in value)
    if len(result) != 3 or not all(math.isfinite(part) for part in result):
        raise ValueError("Invalid actor coordinates")
    return result


def compare(saved, live, *, parse_errors=(), tolerance=0.05):
    """Pure comparison, retaining ambiguous identities instead of guessing a winner."""
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Invalid position tolerance")
    catalog = defaultdict(list)
    for row in live.get("class_catalog", ()):
        catalog[class_key(row["class_name"])].append(row)
    issues = {key: [] for key in ("class_collisions", "unknown_classes", "save_identity_conflicts",
        "live_identity_conflicts", "missing_live", "missing_save", "metadata_mismatches", "health",
        "excluded_actor_mismatches", "unresolved_actor_classification")}
    for key, rows in catalog.items():
        decisions = {(r["is_structure"], r["is_supply_crate"]) for r in rows}
        countable = any(structure and not crate for structure, crate in decisions)
        if len(decisions) != 1 or (countable and len({r["blueprint"] for r in rows}) != 1):
            issues["class_collisions"].append(key)
    excluded_index = defaultdict(list)
    for row in live.get("excluded_structure_actors", ()):
        excluded_index[(class_key(row["class_name"]), row["actor_name"])].append(row)
    unknown = defaultdict(int)
    candidates = defaultdict(list)
    excluded = 0
    for row in saved:
        key = class_key(row["class_name"])
        evidence = catalog.get(key)
        if not evidence:
            unknown[key] += 1
            continue
        if key in issues["class_collisions"]:
            continue
        if not evidence[0]["is_structure"] or evidence[0]["is_supply_crate"]:
            excluded += 1
            continue
        # Scope is retained: actors in different data files are not silently merged.
        identity = (key, tuple(row["names"]), bool(row["from_data_file"]), row["data_file_index"])
        candidates[identity].append(row)
    issues["unknown_classes"] = [{"class": key, "actors": count} for key, count in sorted(unknown.items())]
    unique = []
    duplicate_records = 0
    confirmed_map_actors = 0
    excluded_identity_actors = 0
    confirmed_death_caches = 0
    for identity, rows in candidates.items():
        signatures = {(u32(r["targeting_team"]), u32(r["player_data_id"]), coordinates(r["xyz"])) for r in rows}
        if len(signatures) != 1:
            issues["save_identity_conflicts"].append(list(identity))
            continue
        duplicate_records += len(rows) - 1
        row = rows[0]
        native = excluded_index.get((identity[0], row["names"][0]), ())
        if native:
            if len(native) != 1:
                issues["excluded_actor_mismatches"].append({"actor": row["names"][0], "reason": "ambiguous_native_identity"})
                continue
            evidence = native[0]
            owner = (u32(row["targeting_team"]), u32(row["player_data_id"]))
            native_owner = (u32(evidence["targeting_team"]), u32(evidence["player_data_id"]))
            if "xyz" not in evidence or owner != native_owner or max(abs(a-b) for a,b in zip(coordinates(row["xyz"]),coordinates(evidence["xyz"]))) > tolerance:
                issues["excluded_actor_mismatches"].append({"actor": row["names"][0], "reason": "owner_or_position"})
                continue
            excluded_identity_actors += 1
            # The save header identifies a map-file instance, while the native census
            # confirms no player ownership on this exact actor. StructureID and
            # NetStartup are not origin proofs: map actors can have a nonzero ID
            # and NetStartup is false on most map-origin ASE actors in this checkpoint.
            if (evidence.get("reason") == "generated_death_cache" and evidence.get("death_cache_character_id_marker") is True
                    and math.isfinite(float(evidence.get("death_cache_creation_time", 0))) and float(evidence.get("death_cache_creation_time", 0)) > 0):
                confirmed_death_caches += 1
            elif row["from_data_file"] and owner == (0, 0):
                confirmed_map_actors += 1
            else:
                issues["unresolved_actor_classification"].append({"class": identity[0], "actor": row["names"][0],
                    "reason": evidence["reason"], "structure_id": evidence["structure_id"],
                    "saved_from_data_file": row["from_data_file"],
                    "saved_owner": {"targeting_team": owner[0], "player_data_id": owner[1]},
                    "native_evidence": {key: evidence[key] for key in (
                        "blueprint", "environment_structure", "is_placing_player_structure", "consumed_item_blueprint",
                        "loaded_from_save", "net_startup", "owner_name", "owner_actor_blueprint",
                        "instigator_blueprint", "original_creation_time", "item_structure_blueprint",
                        "matches_item_structure") if key in evidence}})
            continue
        unique.append(row)
    saved_index, live_index = defaultdict(list), defaultdict(list)
    for row in unique:
        saved_index[(class_key(row["class_name"]), row["names"][0])].append(row)
    for row in live["structures"]:
        live_index[(class_key(row["blueprint"]), row.get("actor_name", ""))].append(row)
    matched, maximum_delta = 0, 0.0
    for identity in saved_index.keys() | live_index.keys():
        left, right = saved_index.get(identity, ()), live_index.get(identity, ())
        if len(left) > 1 or len(right) > 1 or not identity[1]:
            issues["live_identity_conflicts"].append(list(identity))
        elif not right:
            issues["missing_live"].append(list(identity))
        elif not left:
            issues["missing_save"].append(right[0]["structure_id"])
        else:
            a, b = left[0], right[0]
            if not b.get("coordinates_available"):
                issues["metadata_mismatches"].append({"actor": identity[1], "reason": "live_position_unavailable"})
                continue
            xyz = coordinates(a["xyz"])
            position = coordinates(b["position"][key] for key in ("x", "y", "z"))
            delta = max(abs(a - b) for a, b in zip(xyz, position))
            maximum_delta = max(maximum_delta, delta)
            if (u32(a["targeting_team"]), u32(a["player_data_id"])) != (u32(b["targeting_team"]), u32(b["player_data_id"])) or delta > tolerance:
                issues["metadata_mismatches"].append({"actor": identity[1], "reason": "owner_or_position", "max_xyz_delta": delta})
            else:
                matched += 1
    health = issues["health"]
    for key in ("runtime_healthy", "journal_healthy"):
        if live.get(key) is not True:
            health.append(key)
    if live.get("class_catalog_overflow") or live.get("excluded_identity_overflow") or live.get("identity_conflicts"):
        health.append("catalog_or_identity_conflict")
    last_scan = live.get("last_completed_scan") or {}
    if not last_scan or last_scan.get("duplicate_ids") or last_scan.get("collection_mutations"):
        health.append("completed_scan_not_stable")
    if last_scan.get("unique_structures") != len(live["structures"]):
        health.append("scan_and_ledger_disagree")
    if live.get("observed_structures") != len(live["structures"]):
        health.append("journal_and_status_disagree")
    reconciliation = live.get("reconciliation")
    run_id = live.get("run_id")
    scoped_checkpoint = False
    if run_id is not None or reconciliation is not None:
        try:
            if not isinstance(run_id, str) or str(uuid.UUID(run_id)).casefold() != run_id.casefold():
                raise ValueError("Invalid run identity")
            revision = live["inventory_revision"]
            if type(revision) is not int or revision < 0:
                raise ValueError("Invalid inventory revision")
            if live.get("journal_state_revision_match") is not True or type(live.get("journal_applied_revision")) is not int or live["journal_applied_revision"] != revision:
                raise ValueError("Journal contains records from a different revision")
            if not isinstance(reconciliation, dict) or reconciliation.get("live_checkpoint_consistent") is not True:
                raise ValueError("Census not reconciled")
            if reconciliation.get("scan_matches_ledger") is not True or any(
                    type(reconciliation.get(key)) is not int or reconciliation[key] != 0 for key in (
                        "ledger_absent_from_scan", "changed_since_scan", "scan_absent_from_ledger", "unresolved_owners")):
                raise ValueError("Census identity/ownership mismatch")
            scan_revision = last_scan["inventory_revision"]
            if type(scan_revision) is not int or scan_revision < 0 or scan_revision > revision:
                raise ValueError("Invalid scan revision")
            scoped_checkpoint = True
        except (KeyError, TypeError, ValueError, AttributeError):
            health.append("run_scoped_reconciliation_unavailable")
    tracked_matches = not parse_errors and matched == len(live["structures"]) and not any(issues[key] for key in (
        "class_collisions", "unknown_classes", "save_identity_conflicts", "live_identity_conflicts", "missing_live", "missing_save", "metadata_mismatches"))
    blockers = [{"reason": key, "count": len(value)} for key, value in issues.items() if value]
    if parse_errors:
        blockers.append({"reason": "parser_errors", "count": len(parse_errors)})
    if not scoped_checkpoint:
        blockers.append({"reason": "current_run_identity_and_reconciliation_required", "count": 1})
    unresolved_groups = defaultdict(int)
    for row in issues["unresolved_actor_classification"]:
        unresolved_groups[row["class"]] += 1
    return {"format": "arkland-structure-save-audit-v1", "checkpoint_matches": not parse_errors and not any(issues.values()),
        "tracked_structures_match": tracked_matches,
        "run_id": run_id, "inventory_revision": live.get("inventory_revision"),
        "run_scoped_checkpoint": scoped_checkpoint, "activation_blockers": blockers,
        "unresolved_actor_groups": dict(sorted(unresolved_groups.items())),
        "complete_inventory": False, "enforcement": False, "saved_actor_records": len(saved),
        "save_structure_records": sum(len(rows) for rows in candidates.values()), "save_unique_structures": len(unique),
        "duplicate_save_records_collapsed": duplicate_records, "live_structures": len(live["structures"]),
        "matched": matched, "classified_non_countable_actor_records": excluded,
        "confirmed_static_map_actors": confirmed_map_actors, "excluded_identity_actors_compared": excluded_identity_actors,
        "confirmed_generated_death_caches": confirmed_death_caches,
        "maximum_xyz_delta": maximum_delta, "parser_error_count": len(parse_errors),
        "issues": issues, "limitation": "One checkpoint comparison; not proof of every lifecycle, mod or pre-consumption veto."}


def read_saved_actors(save):
    actors = []
    for obj in save.objects:
        # Header metadata distinguishes actors from inventory items and components.
        # Classification as structure comes exclusively from the SDK census below.
        if obj.is_item or obj.location is None or len(obj.names) != 1:
            continue
        actors.append({"class_name": obj.class_name, "names": list(obj.names),
            "from_data_file": obj.from_data_file, "data_file_index": obj.data_file_index,
            "targeting_team": obj.get_property_value("TargetingTeam"),
            "player_data_id": obj.get_property_value("OwningPlayerID"),
            "xyz": [obj.location.x, obj.location.y, obj.location.z]})
        if getattr(obj, "_lazy_source", None) is not None:
            obj.evict_properties()
    return actors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", type=Path, required=True, help="Stable copied save, never the live server file")
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-instance", required=True)
    parser.add_argument("--parser-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.resolve() in {args.save.resolve(), args.live.resolve(), args.manifest.resolve()}:
        raise ValueError("Output must not replace an input")
    commit = subprocess.run(["git", "-C", str(args.parser_root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    if commit != PARSER_COMMIT:
        raise ValueError("Parser revision does not match the reviewed pinned revision")
    if subprocess.run(["git", "-C", str(args.parser_root), "diff", "--quiet", "HEAD", "--", "arkparser"], check=False).returncode:
        raise ValueError("Parser source has local changes")
    sys.path.insert(0, str(args.parser_root.resolve()))
    from arkparser import WorldSave
    live = json.loads(args.live.read_text(encoding="utf-8-sig"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    if live.get("instance") != args.expected_instance or manifest.get("instance") != args.expected_instance:
        raise ValueError("Checkpoint belongs to another instance")
    if live.get("run_id") is not None and (manifest.get("run_id") != live["run_id"] or
            manifest.get("inventory_revision") != live.get("inventory_revision")):
        raise ValueError("Save checkpoint is not bound to the native run/revision")
    source = ntpath.normcase(ntpath.normpath(manifest["source"]))
    if ntpath.normcase(ntpath.normpath(str(args.save.resolve()))) == source:
        raise ValueError("Refusing to parse the live server save; use a stable copied checkpoint")
    expected_root = ntpath.normcase(ntpath.normpath(live["canonical_instance_path"])) + "\\shootergame\\saved\\"
    if not source.startswith(expected_root):
        raise ValueError("Save source does not belong to the observed instance path")
    with args.save.open("rb") as handle:
        if int.from_bytes(handle.read(2), "little") not in range(5, 13):
            raise ValueError("Audit supports ASE v5-v12 binary saves only")
        handle.seek(0)
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest.casefold() != manifest["sha256"].casefold() or args.save.stat().st_size != manifest["save_bytes"]:
        raise ValueError("Copied save hash/size mismatch")
    save = WorldSave.load(args.save, lazy_properties=True)
    if save.is_asa or save.version not in range(5, 13):
        raise ValueError("Audit supports ASE only")
    result = compare(read_saved_actors(save), live, parse_errors=save.parse_errors)
    with args.save.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != digest:
            raise ValueError("Save copy changed while parsing")
    result.update({"instance": args.expected_instance, "save_sha256": digest, "save_version": save.version,
        "save_object_count": save.object_count, "parser_commit": commit,
        "save_modified_utc": manifest["save_modified_utc"], "runtime_updated_at_unix": live["updated_at_unix"]})
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "issues"}, ensure_ascii=False))
    print(json.dumps({key: len(value) for key, value in result["issues"].items()}))
    return 0 if result["checkpoint_matches"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
