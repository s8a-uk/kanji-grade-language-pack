"""Following Minecraft and Fabric (make update-minecraft-versions): what is new since minecraft_versions.toml was
written. The table is brought up to it where that is mechanical (a version now served a new ja_jp.json, a new release
that has a Fabric API); everything else is listed for a person to do by hand. The daily workflow
.github/workflows/check-minecraft-versions.yml runs it and fails when a person has something to do."""
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime

from .download import download_unchecked
from .minecraft_versions import VERSION, MinecraftVersion
from .mojang_assets import field_of, java_version, manifest, resource_pack_format, served_ja_jp_sha1

FABRIC_MAVEN = "https://maven.fabricmc.net/net/fabricmc/{}/maven-metadata.xml"
FABRIC_API, FABRIC_LOADER, FABRIC_LOOM = "fabric-api/fabric-api", "fabric-loader", "fabric-loom"
# The images of the client test, one per major version of Java
JAVA_IMAGE_DIRECTORY = "game_client_test/docker/java{}"
# The line of each README that names the versions: its start and what goes between the first and the last version
# (tests/test_data.py keeps them equal to the table)
README_VERSION_LINES = {
    "README.md": ("Supported versions: Minecraft: Java Edition ", "–"),
    "README.ja.md": ("対応する版：Minecraft Java 版 ", "〜"),
}


@dataclass(frozen=True)
class Release:
    version: str  # the id in Mojang's version manifest
    released: datetime


@dataclass
class Update:
    versions: list[MinecraftVersion]
    changes: list[str] = field(default_factory=list)  # Markdown lines: what changed in the table
    to_do: list[str] = field(default_factory=list)  # Markdown lines: what a person has to do by hand
    notes: list[str] = field(default_factory=list)  # Markdown lines: worth knowing, nothing to do now
    new_ja_jp_sha1s: list[str] = field(default_factory=list)  # ja_jp.json files no version had: readings to review

    @property
    def changed(self) -> bool:
        return bool(self.changes)

    @property
    def person_needed(self) -> bool:
        return bool(self.changes or self.to_do)

    def markdown(self) -> str:
        lines = []
        for title, items in (("Changed in minecraft_versions.toml and the READMEs", self.changes),
                             ("To do by hand", self.to_do), ("Good to know", self.notes)):
            lines += [f"### {title}", "", *(items or ["Nothing."]), ""]
        return "\n".join(lines)


@dataclass
class Sources:
    """Where update() learns about Minecraft and Fabric (the network by default; tests give their own)."""
    releases: Callable[[], list[Release]]
    fabric_maven_versions: Callable[[str], list[str]]  # an artifact of Fabric's Maven → the versions it lists
    served_ja_jp_sha1: Callable[[str], str]
    resource_pack_format: Callable[[str], int]
    java_version: Callable[[str], int]
    java_image_exists: Callable[[int], bool]


def maven_versions(artifact: str) -> list[str]:
    return re.findall(r"<version>([^<]+)</version>", download_unchecked(FABRIC_MAVEN.format(artifact)).decode())


def releases() -> list[Release]:
    """The releases in Mojang's version manifest (every id, also one that does not look like a version)."""
    out = []
    for v in field_of(manifest(), "the version manifest", "versions"):
        if field_of(v, "a version of the manifest", "type") == "release":
            released = datetime.fromisoformat(field_of(v, "a version of the manifest", "releaseTime"))
            out.append(Release(field_of(v, "a version of the manifest", "id"), released))
    return out


NETWORK = Sources(releases, maven_versions, served_ja_jp_sha1, resource_pack_format, java_version,
                  lambda java: os.path.isdir(JAVA_IMAGE_DIRECTORY.format(java)))


def _order(version: str) -> tuple[int, ...]:
    return tuple(int(x) for x in version.split("."))


def fabric_api_builds(versions: list[str]) -> dict[str, str]:
    """{Minecraft version: the newest Fabric API build for it} (builds are named <API version>+<Minecraft version>)."""
    out: dict[str, str] = {}
    for version in versions:
        api, _, minecraft = version.partition("+")
        if VERSION.fullmatch(minecraft) and VERSION.fullmatch(api):
            if minecraft not in out or _order(api) > _order(out[minecraft].partition("+")[0]):
                out[minecraft] = version
    return out


def newest_stable(versions: list[str]) -> str | None:
    """The newest version made of numbers only (no alpha, beta or snapshot)."""
    return max((v for v in versions if VERSION.fullmatch(v)), key=_order, default=None)


def update(versions: list[MinecraftVersion], fabric_loader_version: str, fabric_loom_version: str,
           sources: Sources = NETWORK) -> Update:
    """The table brought up to Mojang and Fabric, and what a person has to do. The Fabric API of a version in the
    table is not raised by itself: a newer build is only a note (a version takes the newest one when it is added)."""
    all_releases = sources.releases()
    released = {r.version: r.released for r in all_releases}
    newest = max(versions, key=lambda v: v.order)
    oldest = min(versions, key=lambda v: v.order)
    if newest.version not in released:
        raise ValueError(f"the newest version of the table, {newest.version}, is not a release in Mojang's manifest")
    fabric_api = fabric_api_builds(sources.fabric_maven_versions(FABRIC_API))
    known_sha1s = {v.ja_jp_sha1 for v in versions}
    result = Update([])
    for v in versions:
        new = v
        served = sources.served_ja_jp_sha1(v.version)
        if served != v.ja_jp_sha1:
            result.changes.append(f"- {v.version}: ja_jp.json {v.ja_jp_sha1} → {served}")
            new = replace(new, ja_jp_sha1=served)
        api = fabric_api.get(v.version)
        if api and _order(api.partition("+")[0]) > _order(v.fabric_api_version.partition("+")[0]):
            result.notes.append(f"- {v.version}: a newer Fabric API build, {api} (the table keeps "
                                f"{v.fabric_api_version}; take it by hand when the client test needs it)")
        result.versions.append(new)

    # Releases since the oldest version of the table that it does not have, oldest first
    since = min(released[v.version] for v in versions if v.version in released)
    table = {v.version for v in versions}
    for r in sorted((r for r in all_releases if r.released >= since and r.version not in table),
                    key=lambda r: r.released):
        if not VERSION.fullmatch(r.version):
            result.to_do.append(f"- {r.version}: a release whose name the program does not read: make VERSION "
                                f"(minecraft_versions.py) read it and the order of versions (MinecraftVersion.order, "
                                f"_order in minecraft_versions_update.py) place it")
            continue
        if _order(r.version) < oldest.order:
            continue  # a patch of a line older than the table: not supported
        if _order(r.version) < newest.order:
            result.to_do.append(f"- {r.version}: a later patch of a line the table has, not added: add it by hand")
            continue
        api = fabric_api.get(r.version)
        if api is None:
            result.to_do.append(f"- {r.version}: a new release, not added: no Fabric API build the program reads. "
                                f"Wait for Fabric, or look at https://fabricmc.net/develop (when it has one, the names "
                                f"of the builds changed: fix fabric_api_builds)")
            continue
        added = MinecraftVersion(r.version, sources.resource_pack_format(r.version),
                                 sources.served_ja_jp_sha1(r.version), sources.java_version(r.version), api)
        result.changes.append(f"- {r.version}: added (resource pack format {added.resource_pack_format}, "
                              f"ja_jp.json {added.ja_jp_sha1}, Java {added.java_version}, Fabric API {api})")
        if not sources.java_image_exists(added.java_version):
            result.to_do.append(f"- {r.version} runs on Java {added.java_version}, which the client test has no image "
                                f"for: add {JAVA_IMAGE_DIRECTORY.format(added.java_version)}/Dockerfile")
        result.versions.append(added)

    result.new_ja_jp_sha1s = sorted({v.ja_jp_sha1 for v in result.versions} - known_sha1s)
    for sha1 in result.new_ja_jp_sha1s:
        result.to_do.append(f"- Review the strings of the new ja_jp.json {sha1}: make ja-jp-changes "
                            f"PREVIOUS_SHA1={newest.ja_jp_sha1} NEW_SHA1={sha1}")

    for name, artifact, current in (("Fabric Loader", FABRIC_LOADER, fabric_loader_version),
                                    ("Loom", FABRIC_LOOM, fabric_loom_version)):
        latest = newest_stable(sources.fabric_maven_versions(artifact))
        if latest and _order(latest) > _order(current):
            result.notes.append(f"- {name} {latest} is out (versions.mk has {current}): raise it by hand when a new "
                                f"Minecraft needs it")
    return result


def readme_version_line(readme_name: str, versions: list[MinecraftVersion]) -> str:
    """The line of the README that names the first and the last version of the table."""
    start, between = README_VERSION_LINES[readme_name]
    ordered = sorted(versions, key=lambda v: v.order)
    return f"{start}{ordered[0].version}{between}{ordered[-1].version}"


def readme_with_versions(readme_name: str, readme: str, versions: list[MinecraftVersion]) -> str:
    """The README (README_VERSION_LINES names it) with its line of supported versions naming the table's."""
    start, _ = README_VERSION_LINES[readme_name]
    line = readme_version_line(readme_name, versions)
    new, count = re.subn(f"(?m)^{re.escape(start)}.*$", lambda _: line, readme)
    if count != 1:
        raise ValueError(f"{readme_name} has no single line {start}…")
    return new
