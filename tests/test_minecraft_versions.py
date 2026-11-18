import os

import pytest

from kanji_grade_language_pack.minecraft_versions import MinecraftVersion, dump, groups, groups_json, load, make_variables

A, B = "a" * 40, "b" * 40


def version(name, pack_format, sha1, api="0.1.0+x", java=25):
    return MinecraftVersion(name, pack_format, sha1, java, api)


def test_versions_served_the_same_ja_jp_share_a_pack():
    packs = groups([version("26.3", 97, A), version("26.1", 84, A), version("26.2", 88, A)])
    assert len(packs) == 1
    assert [v.version for v in packs[0].versions] == ["26.1", "26.2", "26.3"]
    assert (packs[0].min_format, packs[0].max_format) == (84, 97)
    assert packs[0].label == "26.1-26.3"
    assert packs[0].zip_name("1.0.0") == "kanji-grade-ja-1.0.0+mc26.1-26.3.zip"


def test_a_new_ja_jp_starts_a_new_pack():
    packs = groups([version("26.1", 84, A), version("26.2", 88, A), version("26.3", 97, B)])
    assert [(p.label, p.ja_jp_sha1) for p in packs] == [("26.1-26.2", A), ("26.3", B)]


def test_a_pack_must_be_a_run_of_versions():
    # 26.1 and 26.3 served the same file, 26.2 another: one zip for 26.1 and 26.3 would cover 26.2's format too
    with pytest.raises(ValueError):
        groups([version("26.1", 84, A), version("26.2", 88, B), version("26.3", 97, A)])


def test_versions_sort_as_numbers():
    packs = groups([version("26.10", 120, A), version("26.9", 110, A)])
    assert packs[0].label == "26.9-26.10"


def test_dump_and_load(tmp_path):
    versions = [version("26.2", 88, A, "0.161.0+26.2"), version("26.3", 97, A, "0.166.2+26.3", java=27)]
    path = tmp_path / "minecraft_versions.toml"
    path.write_text(dump(versions), encoding="utf-8")
    assert load(str(path)) == versions


def test_make_variables_and_json():
    versions = [version("26.2", 88, A, "0.161.0+26.2"), version("26.3", 97, A, "0.166.2+26.3", java=27)]
    variables = make_variables(versions, "1.0.0")
    assert "MINECRAFT_VERSIONS := 26.2 26.3\n" in variables
    assert f"PACK_ZIP.{A} := dist/kanji-grade-ja-1.0.0+mc26.2-26.3.zip\n" in variables
    assert "FABRIC_API_VERSION.26.3 := 0.166.2+26.3\n" in variables
    # Versions on different Java versions share a pack; each is tested on its own Java
    assert "JAVA_VERSION.26.2 := 25\n" in variables and "JAVA_VERSION.26.3 := 27\n" in variables
    (pack,) = groups_json(versions, "1.0.0")
    assert pack["version_number"] == "1.0.0+mc26.2-26.3"
    assert pack["game_versions_lines"] == "26.2\n26.3"


def test_the_table_of_the_build_loads():
    assert groups(load("minecraft_versions.toml"))


def test_every_java_of_the_table_has_a_client_test_image():
    for v in load("minecraft_versions.toml"):
        assert os.path.isfile(f"game_client_test/docker/java{v.java_version}/Dockerfile"), v
