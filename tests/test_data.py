import collections
import json

from kanji_grade_language_pack.grade_kanji_pdf import APPENDIX_COUNT, GRADE_COUNTS


def test_grade_kanji(grade_kanji):
    counts = collections.Counter(k.grade for k in grade_kanji.values())
    assert tuple(counts[g] for g in range(1, 7)) == GRADE_COUNTS
    assert all(k.on or k.kun for k in grade_kanji.values())


def test_appendix():
    with open("data/joyo_appendix_words.json", encoding="utf-8") as f:
        rows = json.load(f)
    assert len({row["reading"] for row in rows}) == APPENDIX_COUNT


def test_the_readme_names_the_minecraft_versions_of_the_table():
    from kanji_grade_language_pack.minecraft_versions import load
    from kanji_grade_language_pack.minecraft_versions_update import README_VERSION_LINES, readme_version_line

    versions = load("minecraft_versions.toml")
    for name in README_VERSION_LINES:
        with open(name, encoding="utf-8") as f:
            readme = f.read()
        assert readme_version_line(name, versions) + "\n" in readme, name
