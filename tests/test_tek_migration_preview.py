from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.diagnostics import tek_migration_preview as preview


ROOT = Path(__file__).resolve().parents[1]


def _profile(path: Path, *, profile_id: str = "classic-1", **overrides):
    path.mkdir(parents=True, exist_ok=True)
    data = {
        "id": profile_id,
        "name": "Test ARK Server",
        "install_dir": str(path),
        "server_exe": "ShooterGameServer.exe",
        "server_port": 7777,
        "query_port": 27015,
        "rcon_port": 27020,
        "rcon_enabled": True,
        "max_players": 70,
    }
    data.update(overrides)
    return data


def _repos(tmp_path: Path, classic_profiles, tek_profiles, clusters_profiles=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    classic = tmp_path / "servers.json"
    tek = tmp_path / "asm_servers.json"
    classic.write_text(json.dumps(classic_profiles), encoding="utf-8")
    tek.write_text(json.dumps(tek_profiles), encoding="utf-8")
    clusters = None
    if clusters_profiles is not None:
        clusters = tmp_path / "clusters.json"
        clusters.write_text(json.dumps(clusters_profiles), encoding="utf-8")
    return classic, tek, clusters


def _report(tmp_path: Path, classic_profiles, tek_profiles, clusters_profiles=None):
    classic, tek, clusters = _repos(tmp_path, classic_profiles, tek_profiles, clusters_profiles)
    return preview.build_preview(classic, tek, ROOT, clusters)


def test_matrix_includes_every_classic_top_level_and_nested_field():
    matrix = preview.build_field_matrix(ROOT)
    paths = {row["source"] for row in matrix}
    assert len(paths) >= 300
    assert {"id", "game_settings.xp_multiplier", "advanced_settings.prevent_download_items", "cluster.enabled"} <= paths
    required = {
        "source_type", "purpose", "source_default", "destination", "destination_type",
        "transformation", "compatibility", "data_loss_risk", "dependencies", "migration_decision",
    }
    assert all(required <= row.keys() for row in matrix)
    assert all(row["compatibility"] for row in matrix)


def test_classic_profile_without_tek_counterpart_is_previewed_without_migration(tmp_path):
    report = _report(tmp_path, [_profile(tmp_path / "ark")], [])
    item = report["classic_profile_previews"][0]
    assert item["tek_candidates"] == []
    assert item["eligibility"] == "READY_FOR_FUTURE_MIGRATION"
    assert report["migration_performed"] is False


def test_valid_tek_profile_is_listed_and_not_marked_as_unknown(tmp_path):
    ark = tmp_path / "tek-ark"
    ark.mkdir()
    tek_profile = {"id": "tek-1", "name": "TEK", "install_dir": str(ark), "session_name": "World"}
    report = _report(tmp_path, [], [tek_profile])
    assert report["profile_repositories"]["TEK"]["profiles"][0]["id"] == "tek-1"
    assert report["profile_repositories"]["TEK"]["profiles"][0]["unknown_field_names"] == []


def test_same_id_across_repositories_is_blocked(tmp_path):
    classic = _profile(tmp_path / "classic-ark", profile_id="shared")
    tek = {"id": "shared", "name": "TEK", "install_dir": str(tmp_path / "tek-ark")}
    report = _report(tmp_path, [classic], [tek])
    assert report["classic_profile_previews"][0]["eligibility"] == "BLOCKED"
    assert any(c["code"] == "duplicate_id_across_repositories" for c in report["global_conflicts"])


def test_different_profile_ids_for_same_installation_are_blocked(tmp_path):
    shared = tmp_path / "ark"
    classic = _profile(shared, profile_id="classic")
    tek = {"id": "tek", "name": "TEK", "install_dir": str(shared)}
    item = _report(tmp_path, [classic], [tek])["classic_profile_previews"][0]
    assert item["eligibility"] == "BLOCKED"
    assert any(x["code"] == "tek_profile_already_targets_same_installation" for x in item["conflicts_and_pending_items"])


@pytest.mark.parametrize(
    "first,second",
    [(r"C:\\ARK\\Server", r"c:/ark/server/"), (r"C:\\ARK\\Server\\..\\Server", r"c:/ARK/Server")],
)
def test_windows_paths_normalize_case_separators_and_dot_segments(tmp_path, first, second):
    classic = _profile(tmp_path / "dummy", install_dir=first)
    tek = {"id": "tek", "name": "TEK", "install_dir": second}
    report = _report(tmp_path, [classic], [tek])
    assert report["classic_profile_previews"][0]["eligibility"] == "BLOCKED"
    assert any(x["code"] == "duplicate_normalized_install_path" for x in report["global_conflicts"])


def test_two_tek_profiles_for_same_installation_are_reported_as_conflict(tmp_path):
    shared = tmp_path / "tek-ark"
    classic = _profile(tmp_path / "classic-ark")
    teks = [{"id": "t1", "name": "T1", "install_dir": str(shared)}, {"id": "t2", "name": "T2", "install_dir": str(shared)}]
    report = _report(tmp_path, [classic], teks)
    assert any(x["code"] == "duplicate_normalized_install_path" for x in report["global_conflicts"])


def test_two_classic_profiles_for_same_installation_are_reported_as_conflict(tmp_path):
    shared = tmp_path / "classic-ark"
    classics = [_profile(shared, profile_id="c1"), _profile(shared, profile_id="c2")]
    report = _report(tmp_path, classics, [])
    assert all(item["eligibility"] == "BLOCKED" for item in report["classic_profile_previews"])


def test_duplicate_ids_inside_one_repository_are_reported(tmp_path):
    classics = [_profile(tmp_path / "c1", profile_id="same"), _profile(tmp_path / "c2", profile_id="same")]
    report = _report(tmp_path, classics, [])
    assert all(item["eligibility"] == "BLOCKED" for item in report["classic_profile_previews"])
    assert any(x["code"] == "duplicate_profile_id" for item in report["classic_profile_previews"] for x in item["conflicts_and_pending_items"])


def test_missing_or_inaccessible_install_directory_requires_review(tmp_path):
    missing = tmp_path / "absent"
    profile = {"id": "classic-1", "name": "ARK", "install_dir": str(missing)}
    item = _report(tmp_path, [profile], [])["classic_profile_previews"][0]
    assert item["install_path"]["directory_state"] == "directory_missing_or_inaccessible"
    assert item["eligibility"] == "REVIEW_REQUIRED"


def test_relative_windows_path_is_not_assumed_to_be_physical_identity(tmp_path):
    item = _report(tmp_path, [_profile(tmp_path / "unused", install_dir=r"Server\\One")], [])["classic_profile_previews"][0]
    assert item["install_path"]["directory_state"] == "relative_unresolved"
    assert item["eligibility"] == "REVIEW_REQUIRED"


def test_nondefault_field_without_destination_blocks_preview_and_value_is_not_emitted(tmp_path):
    item = _report(tmp_path, [_profile(tmp_path / "ark", battlemetrics_id="987654")], [])["classic_profile_previews"][0]
    assert item["eligibility"] == "BLOCKED"
    assert any(x["code"].startswith("nondefault_field_without_destination:battlemetrics_id") for x in item["conflicts_and_pending_items"])
    assert "987654" not in json.dumps(item)


def test_field_with_transform_is_reported_for_review(tmp_path):
    item = _report(tmp_path, [_profile(tmp_path / "ark", map="Ragnarok")], [])["classic_profile_previews"][0]
    changed = next(x for x in item["changed_fields"] if x["field"] == "map")
    assert changed["compatibility"] == "equivalence_with_transform"
    assert item["eligibility"] == "REVIEW_REQUIRED"


def test_missing_required_field_is_blocked(tmp_path):
    classic = _profile(tmp_path / "ark")
    del classic["id"]
    item = _report(tmp_path, [classic], [])["classic_profile_previews"][0]
    assert item["eligibility"] == "BLOCKED"
    assert any(x["code"] == "invalid_required_id" for x in item["conflicts_and_pending_items"])


def test_invalid_field_type_is_blocked(tmp_path):
    item = _report(tmp_path, [_profile(tmp_path / "ark", server_port="7777")], [])["classic_profile_previews"][0]
    assert item["eligibility"] == "BLOCKED"
    assert "server_port" in item["invalid_fields"]


def test_invalid_list_member_type_is_blocked(tmp_path):
    item = _report(tmp_path, [_profile(tmp_path / "ark", admin_ids=[123])], [])["classic_profile_previews"][0]
    assert item["eligibility"] == "BLOCKED"
    assert "admin_ids" in item["invalid_fields"]


def test_mod_ini_custom_data_is_not_silently_discarded(tmp_path):
    item = _report(tmp_path, [_profile(tmp_path / "ark", mod_ini_configs={"123": {"game_ini": "[Mod]\nX=1"}})], [])["classic_profile_previews"][0]
    assert item["eligibility"] == "BLOCKED"
    assert any(x["field"] == "mod_ini_configs" and x["compatibility"] == "no_equivalent" for x in item["changed_fields"])


def test_backup_settings_are_identified_as_global_scope_transform(tmp_path):
    item = _report(tmp_path, [_profile(tmp_path / "ark", backup_enabled=True, backup_interval_hours=12)], [])["classic_profile_previews"][0]
    changed = {x["field"]: x for x in item["changed_fields"]}
    assert changed["backup_enabled"]["compatibility"] == "partial_equivalence"
    assert changed["backup_interval_hours"]["compatibility"] == "equivalence_with_transform"
    assert item["eligibility"] == "REVIEW_REQUIRED"


def test_schedule_and_cluster_data_are_not_lost_silently(tmp_path):
    item = _report(
        tmp_path,
        [_profile(tmp_path / "ark", scheduled_tasks=[{"action": "stop", "time": "04:00"}], cluster={"enabled": True})],
        [],
    )["classic_profile_previews"][0]
    assert item["eligibility"] == "BLOCKED"
    assert any(x["field"] == "scheduled_tasks" for x in item["changed_fields"])
    assert "cluster.enabled" in {x["field"] for x in item["changed_fields"]}


def test_shared_cluster_repository_is_optional_but_referenced_clusters_are_checked(tmp_path):
    profile = _profile(tmp_path / "ark", cluster_profile_id="cluster-1")
    without = _report(tmp_path / "without", [profile], [])
    assert any(x["code"] == "cluster_repository_not_supplied" for x in without["classic_profile_previews"][0]["conflicts_and_pending_items"])

    profile2 = _profile(tmp_path / "ark2", cluster_profile_id="cluster-1")
    valid = _report(tmp_path / "valid", [profile2], [], [{"id": "cluster-1", "name": "Cluster", "cluster_id": "ark-cluster"}])
    assert valid["profile_repositories"]["clusters"]["provided"] is True
    assert not any(x["code"] == "referenced_cluster_profile_missing" for x in valid["classic_profile_previews"][0]["conflicts_and_pending_items"])

    profile3 = _profile(tmp_path / "ark3", cluster_profile_id="missing")
    missing = _report(tmp_path / "missing", [profile3], [], [])
    assert missing["classic_profile_previews"][0]["eligibility"] == "BLOCKED"


def test_secret_values_never_appear_in_preview(tmp_path):
    secret = "DoNotPrint-Server-Password-91"
    item = _report(tmp_path, [_profile(tmp_path / "ark", rcon_password=secret, server_password=secret)], [])["classic_profile_previews"][0]
    rendered = json.dumps(item)
    assert secret not in rendered
    assert "rcon_password" in item["sensitive_fields_present"]
    assert all(x["value_included"] is False for x in item["changed_fields"])


def test_malformed_repository_entries_are_reported_without_migration(tmp_path):
    report = _report(tmp_path, [_profile(tmp_path / "ark"), "not-a-profile"], [])
    assert any(x["code"] == "malformed_profile_entry" for x in report["global_conflicts"])
    assert report["migration_performed"] is False


def test_unknown_fields_block_instead_of_being_dropped(tmp_path):
    item = _report(tmp_path, [_profile(tmp_path / "ark", future_setting={"x": 1})], [])["classic_profile_previews"][0]
    assert item["eligibility"] == "BLOCKED"
    assert item["unknown_field_names"] == ["future_setting"]


def test_preview_does_not_change_profile_or_ini_bytes_or_invoke_server_manager(tmp_path, monkeypatch):
    ark = tmp_path / "ark"
    classic = _profile(ark)
    gus = ark / "GameUserSettings.ini"
    gus.write_bytes(b"\xff\xfe[ServerSettings]\x00\n\x00X\x00=\x001\x00\n\x00")
    classic_path, tek_path, _clusters = _repos(tmp_path, [classic], [])
    protected = [classic_path, tek_path, gus]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    report = preview.build_preview(classic_path, tek_path, ROOT)
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    assert before == after
    assert report["ini_files_opened"] is False
    assert report["database_opened"] is False
    assert report["server_operations_performed"] is False
    assert "ServerManager" not in preview.__dict__
    assert "AsmServerManager" not in preview.__dict__
    assert report["migration_performed"] is False


def test_same_inputs_produce_deterministic_report(tmp_path):
    classic = _profile(tmp_path / "ark")
    classic_path, tek_path, _clusters = _repos(tmp_path, [classic], [])
    first = preview.build_preview(classic_path, tek_path, ROOT)
    second = preview.build_preview(classic_path, tek_path, ROOT)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_cli_output_is_explicit_and_never_overwrites(tmp_path):
    classic_path, tek_path, _clusters = _repos(tmp_path, [_profile(tmp_path / "ark")], [])
    output = tmp_path / "diagnostic.json"
    assert preview.main(["--classic", str(classic_path), "--tek", str(tek_path), "--out", str(output)]) == 0
    original = output.read_bytes()
    assert preview.main(["--classic", str(classic_path), "--tek", str(tek_path), "--out", str(output)]) == 2
    assert output.read_bytes() == original


def test_cli_refuses_to_use_an_input_as_output(tmp_path):
    classic_path, tek_path, _clusters = _repos(tmp_path, [_profile(tmp_path / "ark")], [])
    before = classic_path.read_bytes()
    assert preview.main(["--classic", str(classic_path), "--tek", str(tek_path), "--out", str(classic_path)]) == 2
    assert classic_path.read_bytes() == before


def test_cli_does_not_create_output_directory(tmp_path):
    classic_path, tek_path, _clusters = _repos(tmp_path, [_profile(tmp_path / "ark")], [])
    missing_dir = tmp_path / "not-created"
    assert preview.main(["--classic", str(classic_path), "--tek", str(tek_path), "--out", str(missing_dir / "report.json")]) == 2
    assert not missing_dir.exists()

