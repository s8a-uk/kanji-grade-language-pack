# The versions the build depends on that are neither in pyproject.toml / uv.lock nor in minecraft_versions.toml (the
# Minecraft versions, their resource pack formats, ja_jp.json files and Fabric API builds). The Makefile reads this
# file and passes the values on (to the Python CLI, to Gradle with -P).

# The pack's own version (the name of the zip, GitHub Releases, Modrinth)
PACK_VERSION := 0.2.0

# The client test (game_client_test/): the latest stable releases, for every Minecraft version
# (https://fabricmc.net/develop); the Fabric API of each version is in minecraft_versions.toml
FABRIC_LOADER_VERSION := 0.20.1
FABRIC_LOOM_VERSION := 1.19.4

# The font of the icon: Yuji Syuku (SIL OFL 1.1) at a fixed commit of github.com/google/fonts
ICON_FONT_URL := https://raw.githubusercontent.com/google/fonts/807bf6c8eb6a18198f7944895bb8ec114ba5f381/ofl/yujisyuku/YujiSyuku-Regular.ttf
ICON_FONT_SHA256 := 82728ebafc8c97391e2dab633414a806f344b8e4e2227d307179f07b548fca61
