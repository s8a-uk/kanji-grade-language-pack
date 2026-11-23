"""The strings that differ between two packs, per language, as Markdown (for the summary of a pull request's build:
how a change of the readings, the rules or SudachiDict changes what the children read)."""
import json
import zipfile

from .ja_jp_changes import _cell
from .language_pack import LANGUAGES, language_file

EXAMPLES = 40  # per language shown
SHOWN = ("ja_kana", "ja_g1", "ja_g6")  # the kana-only language, the one with the fewest kanji, the one with the most


def _languages(path: str) -> dict[str, dict[str, str]]:
    with zipfile.ZipFile(path) as z:
        return {l.code: json.loads(z.read(language_file(l.code))) for l in LANGUAGES}


def pack_diff_markdown(previous_path: str, new_path: str) -> str:
    """Per language: the strings that differ (added or changed) and the strings removed, with examples for SHOWN."""
    previous, new = _languages(previous_path), _languages(new_path)
    lines = ["| language | strings added or changed | strings removed |", "|---|---|---|"]
    differing, removed = {}, {}
    for code in previous:
        differing[code] = sorted(k for k in new[code] if previous[code].get(k) != new[code][k])
        removed[code] = sorted(k for k in previous[code] if k not in new[code])
        lines.append(f"| {code} | {len(differing[code])} | {len(removed[code])} |")
    for code in SHOWN:
        if differing[code] or removed[code]:
            lines += ["", f"### {code}", "", "| key | before | after |", "|---|---|---|"]
            shown = differing[code][:EXAMPLES] + removed[code][:max(0, EXAMPLES - len(differing[code]))]
            for key in shown:
                after = _cell(new[code][key]) if key in new[code] else "(removed)"
                lines.append(f"| `{key}` | {_cell(previous[code].get(key, ''))} | {after} |")
            if len(differing[code]) + len(removed[code]) > len(shown):
                lines.append(f"\n{len(differing[code]) + len(removed[code]) - len(shown)} more not shown.")
    return "\n".join(lines) + "\n"
