"""The Minecraft versions the pack is made for (minecraft_versions.toml), and the packs they need.

Every version has its resource pack format, the SHA-1 of the ja_jp.json Mojang serves it, the Java it runs on, and the
Fabric API the client test runs with. The client test of a version runs on its Java (game_client_test/docker/java<N>/),
so versions on different Java versions can be tested side by side. Versions served the same ja_jp.json share one pack (a PackGroup): its pack.mcmeta covers the formats of
all of them (min_format to max_format), and it is published for all of them. Mojang changes the ja_jp.json of a version
after its release, often to the same file for several versions, so the groups follow the SHA-1s.
"""
import re
import tomllib
from dataclasses import dataclass

from .mojang_assets import SHA1

VERSION = re.compile(r"\d+(\.\d+)+")
FIELDS = {"version", "resource_pack_format", "ja_jp_sha1", "java_version", "fabric_api_version"}
FABRIC_API_VERSION = re.compile(r"\d+(\.\d+)+\+\d+(\.\d+)+")
HEADER = """# The Minecraft versions the pack is made for (src/kanji_grade_language_pack/minecraft_versions.py).
#   version               a release of Minecraft: Java Edition
#   resource_pack_format  its resource pack format (make resource-pack-format MINECRAFT_VERSION=<version>)
#   ja_jp_sha1            the SHA-1 of the ja_jp.json Mojang serves it (make served-ja-jp-sha1 MINECRAFT_VERSION=<version>)
#   java_version          the major version of Java it runs on (make java-version MINECRAFT_VERSION=<version>); its
#                         client test runs in the image of game_client_test/docker/java<java_version>/
#   fabric_api_version    the Fabric API the client test runs with (https://fabricmc.net/develop)
# Versions with the same ja_jp_sha1 share one pack. make update-minecraft-versions brings the table up to Minecraft and
# Fabric (.github/workflows/check-minecraft-versions.yml runs it every day and tells when there is something to do).
"""


@dataclass(frozen=True)
class MinecraftVersion:
    version: str
    resource_pack_format: int
    ja_jp_sha1: str
    java_version: int
    fabric_api_version: str

    @property
    def order(self) -> tuple[int, ...]:
        return tuple(int(x) for x in self.version.split("."))


@dataclass(frozen=True)
class PackGroup:
    ja_jp_sha1: str
    versions: tuple[MinecraftVersion, ...]  # oldest first

    @property
    def min_format(self) -> int:
        return min(v.resource_pack_format for v in self.versions)

    @property
    def max_format(self) -> int:
        return max(v.resource_pack_format for v in self.versions)

    @property
    def label(self) -> str:
        """The versions as they go into names: 26.3, or 26.1-26.3 for several."""
        first, last = self.versions[0].version, self.versions[-1].version
        return first if first == last else f"{first}-{last}"

    def zip_name(self, pack_version: str) -> str:
        return f"kanji-grade-ja-{pack_version}+mc{self.label}.zip"


def load(path: str) -> list[MinecraftVersion]:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    if set(data) != {"minecraft"}:
        raise ValueError(f"{path}: only [[minecraft]] tables are allowed")
    versions = []
    for row in data["minecraft"]:
        if set(row) != FIELDS:
            raise ValueError(f"{path}: {row}: needs {', '.join(sorted(FIELDS))}")
        # Every value has one form: they become Make variables and arguments of Gradle
        if not (isinstance(row["version"], str) and VERSION.fullmatch(row["version"])
                and isinstance(row["ja_jp_sha1"], str) and SHA1.fullmatch(row["ja_jp_sha1"])
                and isinstance(row["fabric_api_version"], str) and FABRIC_API_VERSION.fullmatch(row["fabric_api_version"])
                and all(type(row[name]) is int and row[name] > 0 for name in ("resource_pack_format", "java_version"))):
            raise ValueError(f"{path}: {row}: a value of the wrong form")
        versions.append(MinecraftVersion(row["version"], row["resource_pack_format"], row["ja_jp_sha1"],
                                         row["java_version"], row["fabric_api_version"]))
    if len({v.version for v in versions}) != len(versions):
        raise ValueError(f"{path}: a version twice")
    return sorted(versions, key=lambda v: v.order)


def dump(versions: list[MinecraftVersion]) -> str:
    rows = []
    for v in sorted(versions, key=lambda v: v.order, reverse=True):
        rows.append(f'[[minecraft]]\nversion = "{v.version}"\nresource_pack_format = {v.resource_pack_format}\n'
                    f'ja_jp_sha1 = "{v.ja_jp_sha1}"\njava_version = {v.java_version}\n'
                    f'fabric_api_version = "{v.fabric_api_version}"\n')
    return HEADER + "\n" + "\n".join(rows)


def groups(versions: list[MinecraftVersion]) -> list[PackGroup]:
    """The packs: one per ja_jp.json, newest versions last. A group must be a run of consecutive versions, so its
    format range covers no version of another group."""
    ordered = sorted(versions, key=lambda v: v.order)
    out: list[PackGroup] = []
    for v in ordered:
        if out and out[-1].ja_jp_sha1 == v.ja_jp_sha1:
            out[-1] = PackGroup(v.ja_jp_sha1, out[-1].versions + (v,))
        elif any(g.ja_jp_sha1 == v.ja_jp_sha1 for g in out):
            raise ValueError(f"{v.version}: served the ja_jp.json of an older group, with other versions between")
        else:
            out.append(PackGroup(v.ja_jp_sha1, (v,)))
    return out


def make_variables(versions: list[MinecraftVersion], pack_version: str) -> str:
    """Make variables for the Makefile (build/minecraft_versions.mk)."""
    lines = ["# Made by make from minecraft_versions.toml and versions.mk; do not edit"]
    pack_groups = groups(versions)
    lines.append(f"MINECRAFT_VERSIONS := {' '.join(v.version for v in versions)}")
    lines.append(f"LATEST_MINECRAFT_VERSION := {versions[-1].version}")
    lines.append(f"JA_JP_SHA1S := {' '.join(g.ja_jp_sha1 for g in pack_groups)}")
    lines.append(f"PACK_ZIPS := {' '.join('dist/' + g.zip_name(pack_version) for g in pack_groups)}")
    for g in pack_groups:
        lines.append(f"PACK_ZIP.{g.ja_jp_sha1} := dist/{g.zip_name(pack_version)}")
        lines.append(f"MIN_FORMAT.{g.ja_jp_sha1} := {g.min_format}")
        lines.append(f"MAX_FORMAT.{g.ja_jp_sha1} := {g.max_format}")
    for v in versions:
        lines.append(f"JA_JP_SHA1.{v.version} := {v.ja_jp_sha1}")
        lines.append(f"JAVA_VERSION.{v.version} := {v.java_version}")
        lines.append(f"FABRIC_API_VERSION.{v.version} := {v.fabric_api_version}")
    return "\n".join(lines) + "\n"


def groups_json(versions: list[MinecraftVersion], pack_version: str) -> list[dict]:
    """The packs for the workflows: the zip, the Minecraft versions to publish it for (also one per line, as
    mc-publish takes them), its version number."""
    return [{"zip": g.zip_name(pack_version), "label": g.label, "ja_jp_sha1": g.ja_jp_sha1,
             "game_versions": [v.version for v in g.versions],
             "game_versions_lines": "\n".join(v.version for v in g.versions),
             "version_number": f"{pack_version}+mc{g.label}"}
            for g in groups(versions)]
