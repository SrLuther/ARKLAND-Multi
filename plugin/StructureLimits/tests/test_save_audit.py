import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("structure_save_audit", Path(__file__).parents[1] / "tools/save_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class SaveAuditTests(unittest.TestCase):
    def setUp(self):
        self.saved = [{"class_name": "ModFloor_C", "names": ["ModFloor_C_7"],
            "from_data_file": False, "data_file_index": 0, "targeting_team": 90000,
            "player_data_id": 123, "xyz": [1., 2., 3.]}]
        self.live = {"runtime_healthy": True, "journal_healthy": True, "observed_structures": 1,
            "identity_conflicts": 0, "last_completed_scan": {"unique_structures": 1, "duplicate_ids": 0, "collection_mutations": 0},
            "class_catalog": [{"class_name": "ModFloor_C", "blueprint": "/game/mod/modfloor.modfloor",
                "is_structure": True, "is_supply_crate": False}],
            "structures": [{"structure_id": "77", "actor_name": "ModFloor_C_7", "blueprint": "/game/mod/modfloor.modfloor",
                "targeting_team": 90000, "player_data_id": 123, "coordinates_available": True,
                "position": {"x": 1., "y": 2., "z": 3.}}]}

    def test_match_is_not_permission_to_enforce(self):
        result = audit.compare(self.saved, self.live)
        self.assertTrue(result["checkpoint_matches"])
        self.assertFalse(result["complete_inventory"])
        self.assertFalse(result["enforcement"])
        self.assertEqual(result["matched"], 1)

    def test_identical_duplicate_records_collapse(self):
        result = audit.compare(self.saved * 2, self.live)
        self.assertTrue(result["checkpoint_matches"])
        self.assertEqual(result["save_unique_structures"], 1)
        self.assertEqual(result["duplicate_save_records_collapsed"], 1)

    def test_disagreeing_duplicate_is_not_arbitrarily_selected(self):
        other = copy.deepcopy(self.saved[0])
        other["targeting_team"] = 99999
        result = audit.compare(self.saved + [other], self.live)
        self.assertFalse(result["checkpoint_matches"])
        self.assertEqual(len(result["issues"]["save_identity_conflicts"]), 1)

    def test_unknown_class_is_reported(self):
        other = copy.deepcopy(self.saved[0])
        other["class_name"] = "NewMod_C"
        result = audit.compare(self.saved + [other], self.live)
        self.assertFalse(result["checkpoint_matches"])
        self.assertEqual(result["issues"]["unknown_classes"][0]["class"], "newmod")

    def test_same_short_name_from_two_paths_is_ambiguous(self):
        self.live["class_catalog"].append({**self.live["class_catalog"][0], "blueprint": "/another/modfloor.modfloor"})
        result = audit.compare(self.saved, self.live)
        self.assertFalse(result["checkpoint_matches"])
        self.assertEqual(result["issues"]["class_collisions"], ["modfloor"])

    def test_source_scope_is_preserved(self):
        other = {**self.saved[0], "from_data_file": True, "data_file_index": 1}
        result = audit.compare(self.saved + [other], self.live)
        self.assertFalse(result["checkpoint_matches"])
        self.assertEqual(result["duplicate_save_records_collapsed"], 0)

    def test_changed_position_or_owner_is_reported(self):
        for field in ("xyz", "targeting_team", "player_data_id"):
            with self.subTest(field=field):
                saved = copy.deepcopy(self.saved)
                saved[0][field] = [100., 2., 3.] if field == "xyz" else 999
                self.assertFalse(audit.compare(saved, self.live)["checkpoint_matches"])

    def test_scan_mutation_and_parser_error_prevent_pass(self):
        self.live["last_completed_scan"]["collection_mutations"] = 1
        self.assertFalse(audit.compare(self.saved, self.live)["checkpoint_matches"])
        self.live["last_completed_scan"]["collection_mutations"] = 0
        self.assertFalse(audit.compare(self.saved, self.live, parse_errors=["unsupported property"])["checkpoint_matches"])

    def test_sdk_classification_excludes_non_structures(self):
        other = {**self.saved[0], "class_name": "Dino_C"}
        self.live["class_catalog"].append({"class_name": "Dino_C", "blueprint": "/game/dino.dino",
            "is_structure": False, "is_supply_crate": False})
        result = audit.compare(self.saved + [other], self.live)
        self.assertTrue(result["checkpoint_matches"])
        self.assertEqual(result["classified_non_countable_actor_records"], 1)

    def test_non_finite_coordinates_are_rejected(self):
        self.saved[0]["xyz"][0] = float("nan")
        with self.assertRaises(ValueError):
            audit.compare(self.saved, self.live)

    def test_map_actor_is_excluded_only_with_matching_native_evidence(self):
        actor = {**self.saved[0], "names": ["MapActor_1"], "from_data_file": True, "targeting_team": 0, "player_data_id": 0}
        self.live["excluded_structure_actors"] = [{"class_name": "ModFloor_C", "actor_name": "MapActor_1",
            "structure_id": "0", "targeting_team": 0, "player_data_id": 0, "xyz": [1., 2., 3.],
            "reason": "missing_structure_id", "net_startup": False}]
        result = audit.compare(self.saved + [actor], self.live)
        self.assertTrue(result["checkpoint_matches"])
        self.assertEqual(result["confirmed_static_map_actors"], 1)

    def test_map_source_alone_does_not_exclude_actor_with_player_ownership(self):
        actor = {**self.saved[0], "names": ["MapActor_1"], "from_data_file": True, "targeting_team": 90000, "player_data_id": 0}
        self.live["excluded_structure_actors"] = [{"class_name": "ModFloor_C", "actor_name": "MapActor_1",
            "structure_id": "900", "targeting_team": 90000, "player_data_id": 0, "xyz": [1., 2., 3.],
            "reason": "missing_player_ownership", "net_startup": True}]
        result = audit.compare(self.saved + [actor], self.live)
        self.assertFalse(result["checkpoint_matches"])
        self.assertEqual(result["confirmed_static_map_actors"], 0)

    def test_dynamic_unowned_actor_is_unresolved(self):
        actor = {**self.saved[0], "names": ["MapActor_1"], "targeting_team": 0, "player_data_id": 0}
        self.live["excluded_structure_actors"] = [{"class_name": "ModFloor_C", "actor_name": "MapActor_1",
            "structure_id": "0", "targeting_team": 0, "player_data_id": 0, "xyz": [1., 2., 3.],
            "reason": "missing_structure_id", "net_startup": False}]
        result = audit.compare(self.saved + [actor], self.live)
        self.assertFalse(result["checkpoint_matches"])
        self.assertTrue(result["tracked_structures_match"])
        self.assertEqual(len(result["issues"]["unresolved_actor_classification"]), 1)

    def test_non_structure_aliases_can_share_short_name(self):
        other = {**self.saved[0], "class_name": "Tree_C"}
        self.live["class_catalog"].extend([{"class_name": "Tree_C", "blueprint": value,
            "is_structure": False, "is_supply_crate": False} for value in ("/game/tree.tree", "/mod/tree.tree")])
        self.assertTrue(audit.compare(self.saved + [other], self.live)["checkpoint_matches"])

    def test_death_cache_requires_native_marker_and_creation_time(self):
        actor = {**self.saved[0], "names": ["Bag_1"]}
        evidence = {"class_name": "ModFloor_C", "actor_name": "Bag_1", "structure_id": "900",
            "targeting_team": 90000, "player_data_id": 123, "xyz": [1., 2., 3.],
            "reason": "generated_death_cache", "death_cache_character_id_marker": True, "death_cache_creation_time": 100}
        self.live["excluded_structure_actors"] = [evidence]
        self.assertTrue(audit.compare(self.saved + [actor], self.live)["checkpoint_matches"])
        evidence["death_cache_character_id_marker"] = False
        self.assertFalse(audit.compare(self.saved + [actor], self.live)["checkpoint_matches"])


if __name__ == "__main__":
    unittest.main()
