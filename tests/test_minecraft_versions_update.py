from datetime import UTC, datetime, timedelta

import pytest

from kanji_grade_language_pack.minecraft_versions import MinecraftVersion
from kanji_grade_language_pack.minecraft_versions_update import FABRIC_API as FABRIC_API_ARTIFACT
from kanji_grade_language_pack.minecraft_versions_update import (Release, Sources, newest_stable, readme_with_versions,
                                                                 update)

A, B = "a" * 40, "b" * 40
TABLE = [MinecraftVersion("26.3", 97, A, 25, "0.166.2+26.3"), MinecraftVersion("26.2", 88, A, 25, "0.161.0+26.2")]
NOW = datetime(2026, 11, 16, tzinfo=UTC)
RELEASED = {"26.1": NOW - timedelta(days=300), "26.2": NOW - timedelta(days=200), "26.3": NOW - timedelta(days=100)}
FABRIC_API = ["0.161.0+26.2", "0.166.2+26.3"]


def sources(new_releases=(), fabric_api=(), served=None, formats=None, java=None, images=(25,), loader=("0.20.1",),
            loom=("1.19.4",)):
    """26.1 to 26.3 released long ago, and new_releases: (version, days ago)."""
    releases = [Release(v, t) for v, t in RELEASED.items()]
    releases += [Release(v, NOW - timedelta(days=days)) for v, days in new_releases]
    maven = {FABRIC_API_ARTIFACT: FABRIC_API + list(fabric_api), "fabric-loader": list(loader),
             "fabric-loom": list(loom)}
    served = {"26.2": A, "26.3": A, **(served or {})}
    return Sources(lambda: releases, lambda artifact: maven[artifact], lambda v: served[v],
                   lambda v: (formats or {})[v], lambda v: (java or {}).get(v, 25), lambda j: j in images)


def run(s):
    return update(TABLE, "0.20.1", "1.19.4", s)


def test_nothing_new():
    result = run(sources())
    assert not result.person_needed and result.versions == TABLE and result.notes == []


def test_a_release_without_fabric_api_is_for_a_person():
    result = run(sources([("26.4", 3)]))
    assert not result.changed and result.versions == TABLE and result.person_needed
    assert result.to_do[0].startswith("- 26.4: a new release, not added: no Fabric API")


def test_a_new_release_is_added_and_its_java_needs_an_image():
    result = run(sources([("26.4", 3)], ["0.170.0+26.4"], {"26.4": B}, formats={"26.4": 105}, java={"26.4": 27}))
    assert result.changed
    assert result.versions[-1] == MinecraftVersion("26.4", 105, B, 27, "0.170.0+26.4")
    assert result.new_ja_jp_sha1s == [B]
    assert any("docker/java27/Dockerfile" in line for line in result.to_do)
    assert any(f"PREVIOUS_SHA1={A} NEW_SHA1={B}" in line for line in result.to_do)


def test_a_new_ja_jp_for_one_version():
    result = run(sources(served={"26.2": B}))
    assert result.changed and result.versions[1].ja_jp_sha1 == B and result.new_ja_jp_sha1s == [B]


def test_a_newer_fabric_api_build_is_only_a_note():
    result = run(sources(fabric_api=["0.167.0+26.3", "0.150.0+26.4"]))
    assert not result.person_needed and result.versions == TABLE
    assert result.notes == ["- 26.3: a newer Fabric API build, 0.167.0+26.3 (the table keeps 0.166.2+26.3; take it by "
                            "hand when the client test needs it)"]


def test_a_later_patch_of_an_older_line_is_for_a_person():
    result = run(sources([("26.2.1", 3)], ["0.162.0+26.2.1"]))
    assert not result.changed and result.versions == TABLE
    assert result.to_do == ["- 26.2.1: a later patch of a line the table has, not added: add it by hand"]


def test_a_patch_of_an_unsupported_line_is_left_out():
    result = run(sources([("1.21.12", 3)]))
    assert not result.person_needed


def test_a_release_name_the_program_does_not_read():
    result = run(sources([("27", 3)]))
    assert not result.changed and len(result.to_do) == 1 and result.to_do[0].startswith("- 27: a release whose name")


def test_new_fabric_loader_and_loom_are_notes():
    result = run(sources(loader=["0.20.1", "0.21.0"], loom=["1.19.4", "1.20.0-alpha.31", "1.20.0"]))
    assert not result.person_needed
    assert [line.split(" is out")[0] for line in result.notes] == ["- Fabric Loader 0.21.0", "- Loom 1.20.0"]


def test_only_numbers_are_stable():
    assert newest_stable(["1.19.4", "1.20.0-alpha.31"]) == "1.19.4"


def test_the_newest_of_the_table_must_be_a_release():
    s = sources()
    s.releases = lambda: [Release("26.2", NOW)]
    with pytest.raises(ValueError):
        run(s)


def test_readme_with_versions():
    readme = "# Pack\n\n対応する版：Minecraft Java 版 26.1〜26.3\n\nmore\n"
    assert (readme_with_versions("README.ja.md", readme, TABLE)
            == "# Pack\n\n対応する版：Minecraft Java 版 26.2〜26.3\n\nmore\n")
    readme = "# Pack\n\nSupported versions: Minecraft: Java Edition 26.1–26.3\n"
    assert (readme_with_versions("README.md", readme, TABLE)
            == "# Pack\n\nSupported versions: Minecraft: Java Edition 26.2–26.3\n")
    with pytest.raises(ValueError):
        readme_with_versions("README.md", "no line\n", TABLE)
