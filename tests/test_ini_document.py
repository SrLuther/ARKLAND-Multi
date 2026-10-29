from src.asm_engine.ini_document import IniDocument


def test_unchanged_utf16_ini_round_trips_byte_for_byte():
    original = "[ServerSettings]\r\nKey=one\r\nKey=two\r\n".encode("utf-16")

    document = IniDocument.parse(original)

    assert document.to_bytes() == original


def test_preserves_comments_raw_lines_and_repeated_sections():
    original = (
        "; header\n"
        "[Game]\n"
        "Key=first\n"
        "raw structured entry\n"
        "[Game]\n"
        "Key=second\n"
    )
    document = IniDocument.parse(original)

    assert document.find_values("Game", "Key") == ["first", "second"]
    assert document.find_values("Game", "Key", section_occurrence=1) == ["second"]
    assert document.to_text() == original


def test_replaces_only_selected_duplicate_and_keeps_surrounding_text():
    original = "[Game]\r\n; keep\r\nKey = first  \r\nKey=second\r\n"
    document = IniDocument.parse(original)

    document.set_value("Game", "Key", "changed", occurrence=1)

    assert document.find_values("Game", "Key") == ["first  ", "changed"]
    assert document.to_text() == "[Game]\r\n; keep\r\nKey = first  \r\nKey=changed\r\n"


def test_can_target_duplicate_key_in_a_specific_repeated_section():
    document = IniDocument.parse("[Game]\nKey=one\n[Game]\nKey=two\n")

    document.set_value("Game", "Key", "updated", section_occurrence=1)

    assert document.find_values("Game", "Key") == ["one", "updated"]


def test_adds_missing_key_to_last_matching_section_without_reformatting_existing_lines():
    document = IniDocument.parse("; top\n[Game]\nKey=one\n\n[Game]\nOther=two\n")

    document.set_value("Game", "NewKey", "value")

    assert document.to_text() == "; top\n[Game]\nKey=one\n\n[Game]\nOther=two\nNewKey=value\n"


def test_adds_key_after_section_header_without_final_newline():
    document = IniDocument.parse(b"[Game]")

    document.set_value("Game", "Key", "value")

    assert document.to_text() == "[Game]\r\nKey=value\r\n"


def test_removes_one_duplicate_without_removing_the_others():
    document = IniDocument.parse("[Game]\nKey=one\nKey=two\nKey=three\n")

    removed = document.remove_values("Game", "Key", occurrence=1)

    assert removed == 1
    assert document.find_values("Game", "Key") == ["one", "three"]


def test_config_serializer_emits_only_sections_and_configuration_pairs():
    document = IniDocument.parse(
        "; header\r\n"
        "[Game]\r\n"
        "# note\r\n"
        "Key=one\r\n"
        "not an ini option\r\n"
        "\r\n"
        "[Game]\r\n"
        "Key=two\r\n"
    )

    assert document.to_config_text() == (
        "[Game]\r\nKey=one\r\nKey=two\r\n"
    )
