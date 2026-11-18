include versions.mk

.DEFAULT_GOAL := all

IMAGE := kanji-grade-language-pack-build
GRADLE_CACHE_VOLUME := kanji-grade-language-pack-gradle

GRADE_KANJI := data/grade_kanji_readings.json
JOYO_APPENDIX := data/joyo_appendix_words.json
READING_FIXES := data/reading_fixes.toml
PACK_ICON := data/pack_icon.png
ICON_FONT := build/fonts/YujiSyuku-Regular.ttf
SOURCES := $(wildcard src/kanji_grade_language_pack/*.py)
IMAGE_STAMP := build/image.stamp
# The tag of a release (release.yml): one release holds the packs of all the Minecraft versions
RELEASE_TAG := v$(PACK_VERSION)

# Containers get no capabilities. Those without network get the repository read-write (with .git read-only, so nothing
# run inside can change hooks or history); those with network (downloads, Gradle, the Minecraft client) get it
# read-only, with only the directories they write mounted read-write
GIT_READ_ONLY := $(if $(wildcard .git),-v $(CURDIR)/.git:/workspace/.git:ro)
DOCKER := docker run --rm --cap-drop=ALL --security-opt no-new-privileges
DOCKER_RUN := $(DOCKER) -v $(CURDIR):/workspace $(GIT_READ_ONLY)
# $(call DOCKER_RUN_ONLINE,<directories it may write>)
DOCKER_RUN_ONLINE = $(DOCKER) -v $(CURDIR):/workspace:ro $(foreach d,$(1),-v $(CURDIR)/$(d):/workspace/$(d))
CLI := python -P -m kanji_grade_language_pack
OFFLINE := $(DOCKER_RUN) --network none $(IMAGE) $(CLI)
# $(call ONLINE,<directories it may write>)
ONLINE = $(call DOCKER_RUN_ONLINE,$(1)) $(IMAGE) $(CLI)

# The Minecraft versions and their packs, from minecraft_versions.toml: MINECRAFT_VERSIONS, LATEST_MINECRAFT_VERSION,
# JA_JP_SHA1S (one per pack), PACK_ZIPS, PACK_ZIP.<sha1>, MIN_FORMAT.<sha1>, MAX_FORMAT.<sha1>, JA_JP_SHA1.<version>,
# JAVA_VERSION.<version>, FABRIC_API_VERSION.<version>. A pack's zip is named after its Minecraft versions:
# kanji-grade-ja-0.1.1+mc26.1-26.3.zip. Not read when the only goals need none of it (so they need no Docker)
MINECRAFT_VERSIONS_MK := build/minecraft_versions.mk
GOALS_WITHOUT_VERSIONS := clean image github-settings print-RELEASE_TAG print-PACK_VERSION
ifneq ($(MAKECMDGOALS),)
ifeq ($(filter-out $(GOALS_WITHOUT_VERSIONS),$(MAKECMDGOALS)),)
WITHOUT_VERSIONS := yes
endif
endif
ifndef WITHOUT_VERSIONS
include $(MINECRAFT_VERSIONS_MK)
endif
$(MINECRAFT_VERSIONS_MK): minecraft_versions.toml versions.mk $(SOURCES) $(IMAGE_STAMP)
	$(OFFLINE) make-variables --minecraft-versions minecraft_versions.toml --pack-version $(PACK_VERSION) --out $@

# One Minecraft version for the commands that take one (MINECRAFT_VERSION=<version>; the newest when unset or empty)
ifeq ($(strip $(MINECRAFT_VERSION)),)
override MINECRAFT_VERSION := $(LATEST_MINECRAFT_VERSION)
endif
# Stops a command that needs a version of the table on any other
CHECK_MINECRAFT_VERSION = $(if $(JA_JP_SHA1.$(MINECRAFT_VERSION)),,$(error MINECRAFT_VERSION=$(MINECRAFT_VERSION) is not \
	in minecraft_versions.toml: $(MINECRAFT_VERSIONS)))
VERSION_JA_JP_SHA1 = $(JA_JP_SHA1.$(MINECRAFT_VERSION))
VERSION_PACK_ZIP = $(PACK_ZIP.$(VERSION_JA_JP_SHA1))
# The client test of a Minecraft version runs on the Java it runs on: one image per major version of Java, built from
# game_client_test/docker/java<N>/
VERSION_JAVA = $(JAVA_VERSION.$(MINECRAFT_VERSION))
GAME_CLIENT_TEST_IMAGE = kanji-grade-language-pack-game-client-test-java$(VERSION_JAVA)
GAME_CLIENT_TEST_DOCKERFILE_DIRECTORY = game_client_test/docker/java$(VERSION_JAVA)
READING_MARKUPS := $(foreach s,$(JA_JP_SHA1S),build/ja_jp_reading_markup.$(s).json)
# The pack of the newest Minecraft version (make -s print-LATEST_PACK_ZIP, for the workflows)
LATEST_PACK_ZIP = $(PACK_ZIP.$(JA_JP_SHA1.$(LATEST_MINECRAFT_VERSION)))

.PHONY: all image test annotate-readings show-string served-ja-jp-sha1 resource-pack-format java-version \
	update-minecraft-versions ja-jp-changes pack-diff fetch-kanji-data pack-icon game-client-test-image game-client-test \
	game-client-tests gradle-verification-metadata gradle-verification-metadata-of pack-groups minecraft-versions-json \
	github-settings lock clean
.DELETE_ON_ERROR:

# The packs: one zip in dist/ per ja_jp.json of minecraft_versions.toml
all: $(PACK_ZIPS)

image: $(IMAGE_STAMP)

$(IMAGE_STAMP): Dockerfile pyproject.toml uv.lock
	docker build --build-arg UID=$$(id -u) -t $(IMAGE) .
	mkdir -p build && touch $@

build/ja_jp.%.json: | $(IMAGE_STAMP)
	$(call ONLINE,build) fetch-ja-jp --sha1 $* --out $@

# The reading markup of every string of every ja_jp.json, and its words with their readings for review
# (build/word_readings_for_review.<sha1>.tsv); all at once, so a fix is in use when one ja_jp.json uses it
$(READING_MARKUPS) &: $(foreach s,$(JA_JP_SHA1S),build/ja_jp.$(s).json) $(GRADE_KANJI) $(JOYO_APPENDIX) \
		$(READING_FIXES) $(SOURCES) $(IMAGE_STAMP)
	$(OFFLINE) annotate --build-dir build $(foreach s,$(JA_JP_SHA1S),--ja-jp-sha1 $(s)) --grade-kanji $(GRADE_KANJI) \
		--joyo-appendix $(JOYO_APPENDIX) --reading-fixes $(READING_FIXES)

annotate-readings: $(READING_MARKUPS)

define PACK_RULE
$(PACK_ZIP.$(1)): build/ja_jp_reading_markup.$(1).json $(PACK_ICON) $(MINECRAFT_VERSIONS_MK)
	$$(OFFLINE) pack --ja-jp build/ja_jp.$(1).json --markup build/ja_jp_reading_markup.$(1).json \
		--grade-kanji $(GRADE_KANJI) --icon $(PACK_ICON) --min-format $(MIN_FORMAT.$(1)) --max-format $(MAX_FORMAT.$(1)) \
		--out $$@
endef
$(foreach s,$(JA_JP_SHA1S),$(eval $(call PACK_RULE,$(s))))

# make -s print-<variable>: its value (make -s print-RELEASE_TAG, for the workflows)
print-%:
	@echo '$($*)'

# The packs as JSON: zip, label, Minecraft versions, version number (for the workflows)
pack-groups: $(IMAGE_STAMP)
	@$(OFFLINE) pack-groups --minecraft-versions minecraft_versions.toml --pack-version $(PACK_VERSION)

# The Minecraft versions as a JSON list (for the matrix of the workflows)
minecraft-versions-json: $(IMAGE_STAMP)
	@$(OFFLINE) minecraft-versions-json --minecraft-versions minecraft_versions.toml

test: $(IMAGE_STAMP)
	$(DOCKER_RUN) --network none $(IMAGE) python -P -m pytest

# make show-string KEY=<key of ja_jp.json> [MINECRAFT_VERSION=<version>]: the string, its markup, the seven languages
show-string: $(READING_MARKUPS)
	$(CHECK_MINECRAFT_VERSION)
	@$(OFFLINE) show-string --ja-jp build/ja_jp.$(VERSION_JA_JP_SHA1).json \
		--markup build/ja_jp_reading_markup.$(VERSION_JA_JP_SHA1).json --grade-kanji $(GRADE_KANJI) --key '$(KEY)'

# The SHA-1 of the ja_jp.json, the resource pack format and the Java of any Minecraft version
# (MINECRAFT_VERSION=<version>; the format downloads the client jar)
served-ja-jp-sha1: $(IMAGE_STAMP)
	@$(call ONLINE,) served-ja-jp-sha1 --minecraft-version $(MINECRAFT_VERSION)

resource-pack-format: $(IMAGE_STAMP)
	@$(call ONLINE,) resource-pack-format --minecraft-version $(MINECRAFT_VERSION)

java-version: $(IMAGE_STAMP)
	@$(call ONLINE,) java-version --minecraft-version $(MINECRAFT_VERSION)

# Brings minecraft_versions.toml (and the line of README.md and README.ja.md that names the versions) up to Minecraft
# and Fabric where that is mechanical: a version now served a new ja_jp.json, a new release that has a Fabric API. What
# changed, what a person has to do by hand and what is good to know: build/minecraft_versions_update.md (printed), and
# person_needed=true|false (for check-minecraft-versions.yml)
update-minecraft-versions: $(IMAGE_STAMP)
	@$(call ONLINE,build) update-minecraft-versions --minecraft-versions minecraft_versions.toml \
		--fabric-loader-version $(FABRIC_LOADER_VERSION) --fabric-loom-version $(FABRIC_LOOM_VERSION) \
		--readme README.md --readme README.ja.md --out-dir build
	@if [ -f build/minecraft_versions.toml.new ]; then \
		for f in minecraft_versions.toml README.md README.ja.md; do cp build/$$f.new $$f; rm build/$$f.new; done; fi
	@cat build/minecraft_versions_update.md

# make ja-jp-changes PREVIOUS_SHA1=<sha1> NEW_SHA1=<sha1>: build/ja_jp_changes.md, the strings the new ja_jp.json adds
# or changes, with the languages of its pack (make update-minecraft-versions gives the SHA-1s)
ja-jp-changes: build/ja_jp.$(PREVIOUS_SHA1).json build/ja_jp.$(NEW_SHA1).json $(IMAGE_STAMP)
	$(OFFLINE) ja-jp-changes --previous build/ja_jp.$(PREVIOUS_SHA1).json --new build/ja_jp.$(NEW_SHA1).json \
		--pack '$(PACK_ZIP.$(NEW_SHA1))' --out build/ja_jp_changes.md

# make pack-diff PREVIOUS=<zip> NEW=<zip> (both inside the repository, as the container sees only it):
# build/pack_diff.md, the strings that differ in each of the seven languages
# (for pull requests: how a change of the readings, the rules or SudachiDict changes the packs)
pack-diff: $(IMAGE_STAMP)
	$(OFFLINE) pack-diff --previous '$(PREVIOUS)' --new '$(NEW)' --out build/pack_diff.md

# data/grade_kanji_readings.json and data/joyo_appendix_words.json, from the PDFs of MEXT and the Agency for Cultural
# Affairs (kept in git; make the files again and look at git diff)
fetch-kanji-data: $(IMAGE_STAMP)
	$(call ONLINE,data) fetch-kanji-data --grade-kanji-out $(GRADE_KANJI) --appendix-out $(JOYO_APPENDIX)

$(ICON_FONT): | $(IMAGE_STAMP)
	mkdir -p build/fonts
	$(call ONLINE,build/fonts) fetch-file --url $(ICON_FONT_URL) --sha256 $(ICON_FONT_SHA256) --out $@

# data/pack_icon.png, the pack's pack.png (kept in git, so a build needs no font)
pack-icon: $(ICON_FONT)
	$(OFFLINE) pack-icon --font $(ICON_FONT) --out $(PACK_ICON)

# The image of the client test for the Java of MINECRAFT_VERSION
game-client-test-image:
	$(CHECK_MINECRAFT_VERSION)
	@test -f $(GAME_CLIENT_TEST_DOCKERFILE_DIRECTORY)/Dockerfile || { echo "Minecraft $(MINECRAFT_VERSION) runs on \
	Java $(VERSION_JAVA): add $(GAME_CLIENT_TEST_DOCKERFILE_DIRECTORY)/Dockerfile (copy another Java's)"; exit 1; }
	docker build --build-arg UID=$$(id -u) -t $(GAME_CLIENT_TEST_IMAGE) $(GAME_CLIENT_TEST_DOCKERFILE_DIRECTORY)

GRADLE_PROPERTIES = -Pminecraft_version=$(MINECRAFT_VERSION) -Pjava_version=$(VERSION_JAVA) \
	-Pfabric_loader_version=$(FABRIC_LOADER_VERSION) \
	-Pfabric_api_version=$(FABRIC_API_VERSION.$(MINECRAFT_VERSION)) -Pfabric_loom_version=$(FABRIC_LOOM_VERSION) \
	-Ppack=/workspace/$(VERSION_PACK_ZIP)
# Gradle needs its project directory writable (its caches, its build, the client's run directory, the verification
# metadata): game_client_test/ is, the rest of the repository is not. Nothing in game_client_test/ runs on the host
GRADLE_WRITABLE := game_client_test
# $(call GRADLE,<more directories it may write>)
GRADLE = timeout 1800 $(call DOCKER_RUN_ONLINE,$(GRADLE_WRITABLE) $(1)) --init \
	-e SDL_VIDEO_FORCE_EGL=1 -v $(GRADLE_CACHE_VOLUME):/gradle -w /workspace/game_client_test $(GAME_CLIENT_TEST_IMAGE) \
	./gradlew --no-daemon $(GRADLE_PROPERTIES)

# The pack of one Minecraft version (MINECRAFT_VERSION=<version>; the newest by default) in that version's client on
# Xvfb (game_client_test/): the game takes the pack, the seven languages are in the list, every string of each is in
# the game. Screenshots: game_client_test/run/<version>/screenshots/
game-client-test: $(PACK_ZIPS) game-client-test-image
	$(CHECK_MINECRAFT_VERSION)
	$(call GRADLE,) prodClientGameTest

# The client test of every Minecraft version, one after another
game-client-tests:
	$(foreach v,$(MINECRAFT_VERSIONS),$(MAKE) game-client-test MINECRAFT_VERSION=$(v) &&) true

# game_client_test/gradle/verification-metadata.xml: the SHA-256 of the Gradle dependencies of every Minecraft version,
# written again after a change of the Fabric or Gradle versions (each run adds what its version needs). Write it from an
# empty Gradle cache (GRADLE_CACHE_VOLUME=<a new name>), or what the cache holds is not recorded
gradle-verification-metadata: $(PACK_ZIPS)
	$(foreach v,$(MINECRAFT_VERSIONS),$(MAKE) gradle-verification-metadata-of MINECRAFT_VERSION=$(v) &&) true

gradle-verification-metadata-of: game-client-test-image
	$(CHECK_MINECRAFT_VERSION)
	$(call GRADLE,) --write-verification-metadata sha256 prodClientGameTest

# The settings of the GitHub repository (Actions, security, the release environment, rulesets), applied again with gh
# on the host: after making the repository again, and after making it public
github-settings:
	bash .github/apply-repository-settings.sh

# uv.lock again from pyproject.toml (after a change of a version there)
lock: $(IMAGE_STAMP)
	$(DOCKER_RUN) -e UV_PROJECT_ENVIRONMENT=/tmp/venv $(IMAGE) uv lock

clean:
	rm -rf build
	rm -f dist/kanji-grade-ja-*.zip
