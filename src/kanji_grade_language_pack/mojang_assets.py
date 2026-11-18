"""The vanilla ja_jp.json, an asset of Minecraft fetched by its SHA-1.

Mojang updates the translations of a version after its release (the version's asset index changes), so the build
pins the file by its SHA-1 (ja_jp_sha1 in minecraft_versions.toml) and served_ja_jp_sha1 says which one a version serves now.
"""
import functools
import io
import json
import re
import zipfile

from .download import download, download_unchecked

MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
ASSET = "https://resources.download.minecraft.net/{}/{}"
SHA1 = re.compile(r"[0-9a-f]{40}")


def _sha1(value: object) -> str:
    if not isinstance(value, str) or not SHA1.fullmatch(value):
        raise ValueError(f"not a SHA-1: {value!r}")
    return value


# The hosts the manifest may send to: Mojang's
MOJANG_URL = re.compile(r"https://(piston-meta|piston-data|launchermeta|launcher)\.mojang\.com/[^\s]+")


def _mojang_url(value: object) -> str:
    if not isinstance(value, str) or not MOJANG_URL.fullmatch(value):
        raise ValueError(f"not a URL of Mojang: {value!r}")
    return value


def field_of(document: object, name: str, *keys: str) -> object:
    """document[keys[0]][keys[1]]...: when Mojang changes the form of its JSON, a message naming what is missing (fix
    this module) instead of a bare KeyError."""
    value = document
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"{name} has no {'.'.join(keys)}: Mojang changed the form of its JSON; "
                             f"fix src/kanji_grade_language_pack/mojang_assets.py")
        value = value[key]
    return value


@functools.cache
def manifest() -> dict:
    """The version manifest, once per run: the values taken from it in one run agree with each other."""
    return json.loads(download_unchecked(MANIFEST))


@functools.cache
def _version(minecraft_version: str) -> dict:
    """The version JSON of a Minecraft version, checked against the SHA-1 the version manifest gives."""
    versions = field_of(manifest(), "the version manifest", "versions")
    entry = next((v for v in versions if field_of(v, "a version of the manifest", "id") == minecraft_version), None)
    if entry is None:
        raise ValueError(f"unknown Minecraft version: {minecraft_version}")
    url = field_of(entry, f"the manifest's {minecraft_version}", "url")
    sha1 = field_of(entry, f"the manifest's {minecraft_version}", "sha1")
    return json.loads(download(_mojang_url(url), "sha1", _sha1(sha1)))


def java_version(minecraft_version: str) -> int:
    """The major version of Java a Minecraft version runs on (javaVersion.majorVersion of its version JSON)."""
    return int(field_of(_version(minecraft_version), f"the version JSON of {minecraft_version}",
                        "javaVersion", "majorVersion"))


def resource_pack_format(minecraft_version: str) -> int:
    """The resource pack format of a version (pack_version.resource_major of version.json in the client jar)."""
    name = f"the version JSON of {minecraft_version}"
    url = field_of(_version(minecraft_version), name, "downloads", "client", "url")
    sha1 = field_of(_version(minecraft_version), name, "downloads", "client", "sha1")
    with zipfile.ZipFile(io.BytesIO(download(_mojang_url(url), "sha1", _sha1(sha1)))) as jar:
        version_json = json.loads(jar.read("version.json"))
    return int(field_of(version_json, f"version.json of the {minecraft_version} client", "pack_version",
                        "resource_major"))


def served_ja_jp_sha1(minecraft_version: str) -> str:
    """The SHA-1 of the ja_jp.json in the asset index of the version now: manifest → version → asset index, each
    checked against the SHA-1 the step before gives."""
    name = f"the version JSON of {minecraft_version}"
    url = field_of(_version(minecraft_version), name, "assetIndex", "url")
    sha1 = field_of(_version(minecraft_version), name, "assetIndex", "sha1")
    index = json.loads(download(_mojang_url(url), "sha1", _sha1(sha1)))
    return _sha1(field_of(index, f"the asset index of {minecraft_version}", "objects", "minecraft/lang/ja_jp.json",
                          "hash"))


def fetch_ja_jp(sha1: str) -> bytes:
    _sha1(sha1)
    return download(ASSET.format(sha1[:2], sha1), "sha1", sha1)
