#!/usr/bin/env bash
# make game-client-test MINECRAFT_VERSION=<version> for the workflows: Gradle downloads Loom, Minecraft and Fabric from
# Maven repositories, which now and then fail for a while (Maven Central answers "429 Too Many Requests" to GitHub's
# runners). A failed download, and only that ("Could not resolve all" in the log), is tried again up to 3 times, after
# 1, 3 and 9 minutes, with --refresh-dependencies so Gradle asks the repositories again instead of trusting what the
# failed run cached. A failing test is not tried again.
# Usage: run-game-client-test-with-download-retries.sh <Minecraft version> [more make variables...]
set -uo pipefail

version=$1
shift
log=build/game-client-test.$version.log
mkdir -p build
arguments=""
for wait in 0 60 180 540; do
	if [ "$wait" -gt 0 ]; then
		echo "::warning::Gradle could not download its dependencies ($version): trying again in $wait seconds"
		sleep "$wait"
		arguments=--refresh-dependencies
	fi
	if make game-client-test MINECRAFT_VERSION="$version" GRADLE_ARGUMENTS="$arguments" "$@" 2>&1 | tee "$log"; then
		exit 0
	fi
	grep -q "Could not resolve all" "$log" || exit 1
done
exit 1
