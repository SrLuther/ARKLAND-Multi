from tools.update_ark_ase_config_catalog import build_catalogs


def test_catalog_generator_keeps_only_ase_supported_entries_and_descriptions():
    source = """
<!--start of command line-->
{{Server config variable
| name = -maxplayers=<count>
| default = 70
| cli = skip
| inASE = Yes
| info = Limits the maximum player count.
}}
{{Server config variable
| name = -asa-only
| inASE = No
| info = Not an ASE argument.
}}
<!--end of command line-->
<!--start of GameUserSettings.ini-->
<!--start of [ServerSettings]-->
{{Server config variable
| name = AllowCaveBuildingPvE
| type = boolean
| default = False
| inASE = Yes
| Allows building in caves in PvE.
}}
<!--end of GameUserSettings.ini-->
<!--start of Game.ini-->
====[ModInstaller]====
{{Server config variable
| name = ModIDS
| type = ModID
| default =
| inASE = Yes
| Specifies one mod ID per repeated line.
}}
<!--end of Game.ini-->
"""
    ini, cli = build_catalogs(source, {"entries": []})

    assert [(entry["file"], entry["section"], entry["key"]) for entry in ini] == [
        ("Game.ini", "ModInstaller", "ModIDS"),
        ("GameUserSettings.ini", "ServerSettings", "AllowCaveBuildingPvE"),
    ]
    mod_ids = next(entry for entry in ini if entry["key"] == "ModIDS")
    assert mod_ids["repeatable"] is True
    assert "repeated line" in mod_ids["description"]
    assert [entry["argument"] for entry in cli] == ["-maxplayers=<count>"]
