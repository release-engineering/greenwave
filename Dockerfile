FROM quay.io/fedora/python-313:20260204@sha256:598f8ed357664b1a28977269f9c1d61bc605b6fa4dbc447a4c30c3aab8e032ba AS builder

# builder should use root to install/create all files
USER root

# hadolint ignore=DL3033,DL3041,DL4006,SC2039,SC3040
RUN set -exo pipefail \
    && mkdir -p /mnt/rootfs \
    # install runtime dependencies
    && dnf install -y \
        --installroot=/mnt/rootfs \
        --use-host-config \
        --setopt install_weak_deps=false \
        --nodocs \
        --disablerepo=* \
        --enablerepo=fedora,updates \
        python3 \
    && dnf --installroot=/mnt/rootfs clean all \
    # Install uv
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && python3 -m venv /venv

ENV \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Copy only specific files to avoid accidentally including any generated files
# or secrets.
COPY greenwave ./greenwave
COPY conf ./conf
COPY docker ./docker
COPY \
    pyproject.toml \
    uv.lock \
    README.md \
    ./

ARG SHORT_COMMIT
ARG COMMIT_TIMESTAMP

# hadolint ignore=SC1091
RUN set -ex \
    && export PATH=/root/.cargo/bin:"$PATH" \
    && . /venv/bin/activate \
    && uv version "2.3.0.dev$COMMIT_TIMESTAMP+git.$SHORT_COMMIT" \
    && uv build --wheel \
    && version=$(uv version --short) \
    && pip install --no-cache-dir dist/greenwave-"$version"-py3*.whl \
    && deactivate \
    && mv /venv /mnt/rootfs \
    && mkdir -p /mnt/rootfs/src/docker \
    && cp -v docker/docker-entrypoint.sh /mnt/rootfs/src/docker \
    && cp -vr conf /mnt/rootfs/src

# This is just to satisfy linters
USER 1001

# --- Final image
FROM scratch
LABEL \
    summary="Greenwave application" \
    description="Decision-making service for gating in a software delivery pipeline." \
    maintainer="Red Hat, Inc." \
    license="GPLv2+" \
    url="https://github.com/release-engineering/greenwave" \
    io.k8s.display-name="Greenwave"

ENV \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    WEB_CONCURRENCY=8

COPY --from=builder /mnt/rootfs/ /
COPY --from=builder \
    /etc/yum.repos.d/fedora.repo \
    /etc/yum.repos.d/fedora-updates.repo \
    /etc/yum.repos.d/
WORKDIR /src

USER 1001
EXPOSE 8080
ENTRYPOINT ["/src/docker/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "--enable-stdio-inheritance", "greenwave.wsgi:app"]
