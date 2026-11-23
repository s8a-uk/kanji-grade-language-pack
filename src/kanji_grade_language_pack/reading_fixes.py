"""Hand-written fixes of the readings and the splitting that Sudachi gives (data/reading_fixes.toml).

  extra_kanji_readings  {kanji: [reading, ...]}  readings a kanji takes inside words that the 常用漢字表 does not list
                        (来る → き・こ), used to split a word's reading over its kanji
  unsplit_words         [word, ...]  words read in a way the 常用漢字表 and its 付表 do not list (ateji, names): never
                        split over their kanji, always written in kana
  [[word_reading]]      the reading of a word wherever a rule matches it:
                          word, sudachi   the word as Sudachi splits it, and Sudachi's reading in hiragana
                          reading         the right reading
                          key             only in this string of ja_jp.json
                          previous_word_in  only when the word before is one of these ("" for the start of the line)
                          next_word_in    only when the next word is one of these ("" for the end of the line)
                          after           only right after a "number" (0-9) or a "placeholder" (%s, %1$s)
                        The rule with the most conditions wins; between as many, the one with a key.
  [string_markup]       {key: markup}  the whole reading markup of one string, when no rule can express it

Every rule and every string markup must be used; a fix that no longer matches anything (Sudachi or ja_jp.json changed)
stops the build, so it is looked at again.
"""
import tomllib
from dataclasses import dataclass, field

AFTER = ("number", "placeholder")


@dataclass(frozen=True)
class WordReadingRule:
    word: str
    sudachi: str
    reading: str
    key: str | None = None
    previous_word_in: tuple[str, ...] | None = None
    next_word_in: tuple[str, ...] | None = None
    after: str | None = None

    @property
    def specificity(self) -> tuple[int, bool]:
        conditions = (self.key, self.previous_word_in, self.next_word_in, self.after)
        return sum(x is not None for x in conditions), self.key is not None

    def matches(self, key: str, previous_word: str, next_word: str, after: str | None) -> bool:
        return ((self.key is None or self.key == key)
                and (self.previous_word_in is None or previous_word in self.previous_word_in)
                and (self.next_word_in is None or next_word in self.next_word_in)
                and (self.after is None or self.after == after))

    def describe(self) -> str:
        parts = [f"{self.word}/{self.sudachi} → {self.reading}"]
        if self.key:
            parts.append(f"key {self.key}")
        if self.previous_word_in is not None:
            parts.append(f"previous_word_in {list(self.previous_word_in)}")
        if self.next_word_in is not None:
            parts.append(f"next_word_in {list(self.next_word_in)}")
        if self.after:
            parts.append(f"after {self.after}")
        return ", ".join(parts)


@dataclass
class ReadingFixes:
    extra_kanji_readings: dict[str, tuple[str, ...]]
    unsplit_words: frozenset[str]
    word_rules: dict[tuple[str, str], list[WordReadingRule]]
    string_markup: dict[str, str]
    used: set[object] = field(default_factory=set)

    def reading(self, key: str, word: str, sudachi: str, previous_word: str, next_word: str,
                after: str | None) -> str | None:
        """The fixed reading of a word, or None to keep Sudachi's."""
        matching = [r for r in self.word_rules.get((word, sudachi), [])
                    if r.matches(key, previous_word, next_word, after)]
        if not matching:
            return None
        best = max(matching, key=lambda r: r.specificity)
        if sum(r.specificity == best.specificity for r in matching) > 1:
            raise ValueError(f"{key}: two word_reading rules as specific match {word}/{sudachi}")
        self.used.add(best)
        return best.reading

    def markup_of_string(self, key: str) -> str | None:
        if key in self.string_markup:
            self.used.add(("string", key))
            return self.string_markup[key]
        return None

    def mark_unsplit_word_used(self, word: str) -> None:
        self.used.add(("unsplit", word))

    def mark_kanji_reading_used(self, kanji: str) -> None:
        self.used.add(("kanji", kanji))

    def unused(self) -> list[str]:
        out = [r.describe() for rules in self.word_rules.values() for r in rules if r not in self.used]
        out += [f"string_markup {k}" for k in self.string_markup if ("string", k) not in self.used]
        out += [f"unsplit_words {w}" for w in sorted(self.unsplit_words) if ("unsplit", w) not in self.used]
        out += [f"extra_kanji_readings {k}" for k in self.extra_kanji_readings if ("kanji", k) not in self.used]
        return out


def _strings(value) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x for x in value)


def _check_types(path: str, data: dict) -> None:
    """Every value of the right type: a list of words written as one string ("その") would else be taken as letters."""
    problems = []
    if not _strings(data.get("unsplit_words", [])):
        problems.append("unsplit_words must be a list of words")
    for kanji, readings in data.get("extra_kanji_readings", {}).items():
        if not _strings(readings):
            problems.append(f"extra_kanji_readings {kanji}: must be a list of readings")
    for row in data.get("word_reading", []):
        for name in ("word", "sudachi", "reading", "key", "after"):
            if name in row and not (isinstance(row[name], str) and row[name]):
                problems.append(f"word_reading {row}: {name} must be a string")
        for name in ("previous_word_in", "next_word_in"):
            # "" is allowed in these lists: the start or the end of the line
            if name in row and not (isinstance(row[name], list) and all(isinstance(x, str) for x in row[name])):
                problems.append(f"word_reading {row}: {name} must be a list of words")
    for key, markup in data.get("string_markup", {}).items():
        if not isinstance(markup, str):
            problems.append(f"string_markup {key}: must be a string")
    if problems:
        raise ValueError(f"{path}: " + "; ".join(problems))


def load_reading_fixes(path: str) -> ReadingFixes:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    unknown = set(data) - {"extra_kanji_readings", "unsplit_words", "word_reading", "string_markup"}
    if unknown:
        raise ValueError(f"{path}: unknown tables {sorted(unknown)}")
    _check_types(path, data)
    rules: dict[tuple[str, str], list[WordReadingRule]] = {}
    for row in data.get("word_reading", []):
        extra = set(row) - {"word", "sudachi", "reading", "key", "previous_word_in", "next_word_in", "after"}
        if extra:
            raise ValueError(f"{path}: word_reading {row}: unknown fields {sorted(extra)}")
        if row.get("after") not in (None, *AFTER):
            raise ValueError(f"{path}: word_reading {row}: after must be one of {AFTER}")
        rule = WordReadingRule(
            row["word"], row["sudachi"], row["reading"], row.get("key"),
            tuple(row["previous_word_in"]) if "previous_word_in" in row else None,
            tuple(row["next_word_in"]) if "next_word_in" in row else None, row.get("after"))
        same = rules.setdefault((rule.word, rule.sudachi), [])
        conditions = (rule.key, rule.previous_word_in, rule.next_word_in, rule.after)
        if any((r.key, r.previous_word_in, r.next_word_in, r.after) == conditions for r in same):
            raise ValueError(f"{path}: two word_reading rules with the same conditions: {rule.describe()}")
        same.append(rule)
    return ReadingFixes(
        extra_kanji_readings={k: tuple(v) for k, v in data.get("extra_kanji_readings", {}).items()},
        unsplit_words=frozenset(data.get("unsplit_words", [])),
        word_rules=rules,
        string_markup=dict(data.get("string_markup", {})),
    )
