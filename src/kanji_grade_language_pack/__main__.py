"""The command line of the build: python -m kanji_grade_language_pack <command> ... (the Makefile runs them in Docker)."""
import argparse
import json
import os
import sys
import zipfile

from . import annotate as annotate_module
from . import minecraft_versions
from .download import download
from .grade_kanji_pdf import fetch_and_build
from .ja_jp_changes import changes_markdown
from .kanji import load_grade_kanji
from .kanji_reading_alignment import ReadingAligner
from .language_pack import LANGUAGES, build_pack, language_file, language_strings, write_zip
from .minecraft_versions_update import readme_with_versions, update
from .pack_diff import pack_diff_markdown
from .mojang_assets import fetch_ja_jp, java_version, resource_pack_format, served_ja_jp_sha1
from .pack_icon import icon_png
from .reading_fixes import load_reading_fixes


def _write(path: str, data: bytes) -> None:
    """Write through a temporary file, so a failed command leaves no half-written file that make takes as done."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temporary = path + ".part"
    with open(temporary, "wb") as f:
        f.write(data)
    os.replace(temporary, path)


def _json_lines(rows: list[dict]) -> bytes:
    return ("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n]\n").encode("utf-8")


def _load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def command_served_ja_jp_sha1(a) -> None:
    print(served_ja_jp_sha1(a.minecraft_version))


def command_resource_pack_format(a) -> None:
    print(resource_pack_format(a.minecraft_version))


def command_java_version(a) -> None:
    print(java_version(a.minecraft_version))


def command_fetch_ja_jp(a) -> None:
    _write(a.out, fetch_ja_jp(a.sha1))


def command_fetch_file(a) -> None:
    _write(a.out, download(a.url, "sha256", a.sha256))


def command_fetch_kanji_data(a) -> None:
    grade_kanji, appendix = fetch_and_build()
    _write(a.grade_kanji_out, _json_lines(grade_kanji))
    _write(a.appendix_out, _json_lines(appendix))
    print(f"{a.grade_kanji_out}: {len(grade_kanji)} kanji; {a.appendix_out}: {len(appendix)} words")


def command_make_variables(a) -> None:
    versions = minecraft_versions.load(a.minecraft_versions)
    _write(a.out, minecraft_versions.make_variables(versions, a.pack_version).encode("utf-8"))


def command_pack_groups(a) -> None:
    versions = minecraft_versions.load(a.minecraft_versions)
    print(json.dumps(minecraft_versions.groups_json(versions, a.pack_version)))


def command_update_minecraft_versions(a) -> None:
    """In the out directory: what changed, what a person has to do and what is good to know, as Markdown
    (minecraft_versions_update.md) and, when the table changed, the new table and READMEs (minecraft_versions.toml.new,
    README.md.new, README.ja.md.new; make puts them in place). person_needed=true|false to stdout."""
    versions = minecraft_versions.load(a.minecraft_versions)
    result = update(versions, a.fabric_loader_version, a.fabric_loom_version)
    _write(f"{a.out_dir}/minecraft_versions_update.md", result.markdown().encode("utf-8"))
    if result.changed:
        _write(f"{a.out_dir}/minecraft_versions.toml.new", minecraft_versions.dump(result.versions).encode("utf-8"))
        for path in a.readme:
            name = os.path.basename(path)
            with open(path, encoding="utf-8") as f:
                readme = f.read()
            _write(f"{a.out_dir}/{name}.new", readme_with_versions(name, readme, result.versions).encode("utf-8"))
    print(f"person_needed={'true' if result.person_needed else 'false'}")


def command_minecraft_versions_json(a) -> None:
    print(json.dumps([v.version for v in minecraft_versions.load(a.minecraft_versions)]))


def command_pack_diff(a) -> None:
    _write(a.out, pack_diff_markdown(a.previous, a.new).encode("utf-8"))


def command_annotate(a) -> None:
    """All the ja_jp.json files at once: a fix is in use when one of them uses it."""
    from sudachipy import Dictionary, SplitMode

    fixes = load_reading_fixes(a.reading_fixes)
    appendix = {row["word"]: row["reading"] for row in _load_json(a.joyo_appendix)}
    aligner = ReadingAligner(load_grade_kanji(a.grade_kanji), fixes.extra_kanji_readings, fixes.unsplit_words, appendix)
    tokenizer = Dictionary(dict="full").tokenizer(SplitMode.C)
    results = {}
    for sha1 in a.ja_jp_sha1:
        results[sha1] = annotate_module.annotate(_load_json(f"{a.build_dir}/ja_jp.{sha1}.json"), tokenizer, aligner, fixes)
    unused = fixes.unused()
    if unused:
        sys.exit(f"{a.reading_fixes}: fixes that match nothing (look at the string again):\n  " + "\n  ".join(unused))
    # A word Sudachi took for a person's name is often a misreading: each must be looked at and given a fix (or be in
    # unsplit_words when it is a name)
    names = sorted({f"{surface} ({reading}): {w.examples[0]}" for result in results.values()
                    for (surface, reading), w in result.words.items()
                    if w.name and not w.fixed and surface not in fixes.unsplit_words})
    if names:
        sys.exit(f"words Sudachi reads as names, with no fix in {a.reading_fixes}:\n  " + "\n  ".join(names))
    for sha1, result in results.items():
        markup_path = f"{a.build_dir}/ja_jp_reading_markup.{sha1}.json"
        _write(markup_path, json.dumps(result.markup, ensure_ascii=False, indent=1).encode("utf-8"))
        _write(f"{a.build_dir}/word_readings_for_review.{sha1}.tsv",
               annotate_module.word_readings_tsv(result.words).encode("utf-8"))
        status = {s: sum(1 for w in result.words.values() if w.status == s) for s in ("ok", "kana only", "unsplit")}
        print(f"{markup_path}: {len(result.markup)} strings; {len(result.words)} distinct words {status}")


def command_pack(a) -> None:
    texts = _load_json(a.ja_jp)
    markup = _load_json(a.markup)
    grade_kanji = load_grade_kanji(a.grade_kanji)
    with open(a.icon, "rb") as f:
        icon = f.read()
    entries, problems = build_pack(texts, markup, grade_kanji, icon, a.min_format, a.max_format)
    if problems:
        shown = "\n  ".join(problems[:30])
        sys.exit(f"{len(problems)} problems, the pack is not written:\n  {shown}")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    write_zip(a.out + ".part", entries)
    os.replace(a.out + ".part", a.out)
    for language in LANGUAGES:
        strings = json.loads(entries[language_file(language.code)])
        kept = sum(1 for k in texts if strings[k] == texts[k])
        print(f"{language.code}: {kept}/{len(texts)} strings as in ja_jp")
    print(a.out)


def command_pack_icon(a) -> None:
    _write(a.out, icon_png(a.font))


def command_show_string(a) -> None:
    texts = _load_json(a.ja_jp)
    markup = _load_json(a.markup)
    grade_kanji = load_grade_kanji(a.grade_kanji)
    if a.key not in texts:
        sys.exit(f"no string {a.key}")
    print(f"ja_jp    {texts[a.key]}")
    print(f"markup   {markup[a.key]}")
    for language in LANGUAGES:
        print(f"{language.code:8} {language_strings({a.key: texts[a.key]}, markup, language.grade, grade_kanji)[a.key]}")


def command_ja_jp_changes(a) -> None:
    languages = None
    if a.pack and os.path.exists(a.pack):
        with zipfile.ZipFile(a.pack) as z:
            languages = {l.code: json.loads(z.read(language_file(l.code))) for l in LANGUAGES}
    _write(a.out, changes_markdown(_load_json(a.previous), _load_json(a.new), languages).encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(prog="kanji_grade_language_pack")
    commands = parser.add_subparsers(required=True)

    def command(name, function, help_text, *arguments):
        p = commands.add_parser(name, help=help_text)
        for flag, *kind in arguments:
            if kind and kind[0] == "list":
                p.add_argument(flag, required=True, action="append")
            else:
                p.add_argument(flag, required=True, type=kind[0] if kind else str)
        p.set_defaults(function=function)
        return p

    command("served-ja-jp-sha1", command_served_ja_jp_sha1,
            "print the SHA-1 of the ja_jp.json a Minecraft version serves now", ("--minecraft-version",))
    command("resource-pack-format", command_resource_pack_format,
            "print the resource pack format of a Minecraft version (from its client jar)", ("--minecraft-version",))
    command("java-version", command_java_version,
            "print the major version of Java a Minecraft version runs on", ("--minecraft-version",))
    command("fetch-ja-jp", command_fetch_ja_jp, "download ja_jp.json by its SHA-1", ("--sha1",), ("--out",))
    command("fetch-file", command_fetch_file, "download a file and check its SHA-256",
            ("--url",), ("--sha256",), ("--out",))
    command("fetch-kanji-data", command_fetch_kanji_data,
            "build the grade kanji and the 付表 words from the government PDFs",
            ("--grade-kanji-out",), ("--appendix-out",))
    command("make-variables", command_make_variables, "write the Make variables of minecraft_versions.toml",
            ("--minecraft-versions",), ("--pack-version",), ("--out",))
    command("pack-groups", command_pack_groups, "print the packs as JSON (zip, Minecraft versions, version number)",
            ("--minecraft-versions",), ("--pack-version",))
    command("update-minecraft-versions", command_update_minecraft_versions,
            "bring the table up to Minecraft and Fabric, and list what a person has to do",
            ("--minecraft-versions",), ("--fabric-loader-version",), ("--fabric-loom-version",), ("--readme", "list"),
            ("--out-dir",))
    command("minecraft-versions-json", command_minecraft_versions_json,
            "print the Minecraft versions of the table as a JSON list", ("--minecraft-versions",))
    command("pack-diff", command_pack_diff, "list the strings that differ between two packs, per language",
            ("--previous",), ("--new",), ("--out",))
    command("annotate", command_annotate, "write the reading markup and the word list of every ja_jp.json",
            ("--build-dir",), ("--ja-jp-sha1", "list"), ("--grade-kanji",), ("--joyo-appendix",), ("--reading-fixes",))
    command("pack", command_pack, "check the seven languages and write the resource pack zip",
            ("--ja-jp",), ("--markup",), ("--grade-kanji",), ("--icon",), ("--min-format", int), ("--max-format", int),
            ("--out",))
    command("pack-icon", command_pack_icon, "draw pack.png", ("--font",), ("--out",))
    command("show-string", command_show_string, "print one string in the seven languages",
            ("--ja-jp",), ("--markup",), ("--grade-kanji",), ("--key",))
    changes = command("ja-jp-changes", command_ja_jp_changes, "list the strings a new ja_jp.json adds or changes",
                      ("--previous",), ("--new",), ("--out",))
    changes.add_argument("--pack", help="the pack built from the new ja_jp.json, when the build worked")
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
