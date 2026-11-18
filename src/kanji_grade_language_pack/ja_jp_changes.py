"""The strings a new ja_jp.json adds or changes, with what each language of the pack makes of them, as a Markdown table
for a person reviewing the readings (make ja-jp-changes)."""
from .language_pack import LANGUAGES


def _cell(text: str) -> str:
    # Mojang's strings go into a GitHub page: no table breaks, no mentions (@name notifies a user), no HTML
    return (text.replace("|", "\\|").replace("\n", "<br>").replace("@", "@\u200b")
            .replace("<", "&lt;").replace("&lt;br>", "<br>"))


def changes_markdown(previous: dict[str, str], new: dict[str, str], languages: dict[str, dict[str, str]] | None) -> str:
    """languages: {code: strings} of the pack built from the new ja_jp.json, or None when the build failed."""
    added = [k for k in new if k not in previous]
    changed = [k for k in new if k in previous and previous[k] != new[k]]
    removed = [k for k in previous if k not in new]
    codes = [language.code for language in LANGUAGES]
    lines = [f"Added {len(added)}, changed {len(changed)}, removed {len(removed)} strings.", ""]
    if languages:
        lines += ["| key | ja_jp | " + " | ".join(codes) + " |", "|---" * (len(codes) + 2) + "|"]
    else:
        lines += ["The pack was not built, so only the strings are listed.", "", "| key | ja_jp |", "|---|---|"]
    for key in added + changed:
        row = f"| `{key}` | {_cell(new[key])} |"
        if languages:
            row += " " + " | ".join(_cell(languages[code][key]) for code in codes) + " |"
        lines.append(row)
    if removed:
        lines += ["", "Removed: " + ", ".join(f"`{k}`" for k in removed)]
    return "\n".join(lines) + "\n"
