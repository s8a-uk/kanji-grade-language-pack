# The image of the client test for the Minecraft versions on Java 25 (java_version = 25 in minecraft_versions.toml):
# Java for Gradle and the client, Xvfb and Mesa (software OpenGL) for a client without a display or a GPU. For a
# Minecraft version on another Java, copy this directory to docker/java<N>/ and change the base image to that Java.
# The FROM line stays literal, so Dependabot updates each Java's image (within its major version)
FROM eclipse-temurin:25.0.5_8-jdk-noble@sha256:80f67fb3d6f76e2d817d98a4cc2a9cf05f054d4e6adc5e2144bde671d722e63f
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb xauth libgl1 libgl1-mesa-dri libglx-mesa0 libegl1 \
       mesa-vulkan-drivers libxrandr2 libxcursor1 libxi6 libxxf86vm1 libxinerama1 libxtst6 libxkbcommon0 \
       libpulse0 libopenal1 \
    && rm -rf /var/lib/apt/lists/*
# The user of the host (make passes its UID), so the container can write the mounted project; the image has a user
# with UID 1000 already (ubuntu)
ARG UID=1000
RUN { id -u "${UID}" >/dev/null 2>&1 || useradd --create-home --uid "${UID}" tester; } \
    && mkdir /gradle && chown "${UID}" /gradle
ENV GRADLE_USER_HOME=/gradle
USER ${UID}
