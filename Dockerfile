# The build: Python with the packages of uv.lock (hashes checked). The project's own code is not copied in; the
# Makefile mounts the repository at /workspace and runs python -P -m kanji_grade_language_pack.
# uv, from its image (a stage of its own, so Dependabot follows it)
FROM ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d AS uv

FROM python:3.15.2-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_NO_CACHE=1
COPY pyproject.toml uv.lock /opt/project/
RUN cd /opt/project && uv sync --frozen --no-install-project
ENV PATH=/opt/venv/bin:$PATH PYTHONPATH=/workspace/src PYTHONDONTWRITEBYTECODE=1
# The user of the host (make passes its UID), so the build writes files the host user owns
ARG UID=1000
RUN useradd --create-home --uid "${UID}" builder
USER builder
WORKDIR /workspace
