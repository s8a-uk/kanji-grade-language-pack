import json
import zipfile

from kanji_grade_language_pack.language_pack import LANGUAGES, language_file
from kanji_grade_language_pack.pack_diff import pack_diff_markdown


def write_pack(path, strings):
    with zipfile.ZipFile(path, "w") as z:
        for language in LANGUAGES:
            z.writestr(language_file(language.code), json.dumps(strings))


def test_added_changed_and_removed_strings(tmp_path):
    write_pack(tmp_path / "previous.zip", {"a.same": "おなじ", "a.changed": "まえ", "a.removed": "きえる"})
    write_pack(tmp_path / "new.zip", {"a.same": "おなじ", "a.changed": "あと", "a.added": "ふえる"})
    markdown = pack_diff_markdown(str(tmp_path / "previous.zip"), str(tmp_path / "new.zip"))
    assert "| ja_kana | 2 | 1 |" in markdown
    assert "| `a.added` |  | ふえる |" in markdown
    assert "| `a.changed` | まえ | あと |" in markdown
    assert "| `a.removed` | きえる | (removed) |" in markdown
    assert "a.same" not in markdown


def test_no_difference(tmp_path):
    write_pack(tmp_path / "previous.zip", {"a": "おなじ"})
    write_pack(tmp_path / "new.zip", {"a": "おなじ"})
    markdown = pack_diff_markdown(str(tmp_path / "previous.zip"), str(tmp_path / "new.zip"))
    assert "###" not in markdown and "| ja_g6 | 0 | 0 |" in markdown
