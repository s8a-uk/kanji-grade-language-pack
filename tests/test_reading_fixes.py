import pytest

from kanji_grade_language_pack.reading_fixes import load_reading_fixes

FIXES = '''
unsplit_words = ["松明"]

[extra_kanji_readings]
"来" = ["き", "こ"]

[[word_reading]]
word = "何"
sudachi = "なん"
reading = "なに"
next_word_in = ["か"]

[[word_reading]]
word = "他"
sudachi = "た"
reading = "ほか"
next_word_in = ["の"]

[[word_reading]]
word = "他"
sudachi = "た"
reading = "た"
previous_word_in = ["その"]
next_word_in = ["の"]

[[word_reading]]
key = "only.here"
word = "日"
sudachi = "ひ"
reading = "にち"

[[word_reading]]
word = "日"
sudachi = "ひ"
reading = "にち"
after = "placeholder"

[string_markup]
"a.key" = "⟦字|じ⟧"
'''


@pytest.fixture
def fixes(tmp_path):
    path = tmp_path / "fixes.toml"
    path.write_text(FIXES, encoding="utf-8")
    return load_reading_fixes(str(path))


def test_conditions(fixes):
    assert fixes.reading("k", "何", "なん", "", "か", None) == "なに"
    assert fixes.reading("k", "何", "なん", "", "ら", None) is None  # 何ら stays なんら
    assert fixes.reading("k", "他", "た", "て", "の", None) == "ほか"
    assert fixes.reading("k", "他", "た", "その", "の", None) == "た"  # the rule with more conditions wins
    assert fixes.reading("k", "日", "ひ", "", "", "placeholder") == "にち"
    assert fixes.reading("k", "日", "ひ", "", "", None) is None


def test_a_key_wins_between_rules_with_as_many_conditions(fixes):
    assert fixes.reading("only.here", "日", "ひ", "", "", None) == "にち"


def test_unused_fixes_are_listed(fixes):
    fixes.reading("k", "何", "なん", "", "か", None)
    unused = fixes.unused()
    assert "何/なん → なに, next_word_in ['か']" not in unused
    assert any(u.startswith("他/た → ほか") for u in unused)
    assert "string_markup a.key" in unused
    assert "unsplit_words 松明" in unused
    assert "extra_kanji_readings 来" in unused


def test_unknown_fields_are_errors(tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text('[[word_reading]]\nword = "何"\nsudachi = "なん"\nreading = "なに"\nnext = ["か"]\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_reading_fixes(str(path))


def test_the_fixes_of_the_build_load():
    load_reading_fixes("data/reading_fixes.toml")
