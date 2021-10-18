FROM registry.access.redhat.com/ubi8/ubi-minimal:8.5 as base

RUN microdnf install -y --nodocs --setopt install_weak_deps=0 python39-pip

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    WEB_CONCURRENCY=8

# --- Build stage
FROM base as builder

RUN microdnf install -y --nodocs --setopt install_weak_deps=0 git-core

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY . .
# hadolint ignore=SC1091
RUN set -ex \
    && version=$(./get-version.sh) \
    && test -n "$version" \
    && pip3 install --no-cache-dir -r requirements-builder.txt \
    && python3 -m venv /venv \
    && . /venv/bin/activate \
    && pip install --no-cache-dir -r requirements-builder2.txt \
    && poetry version "$version" \
    && poetry install --no-dev --no-root \
    && poetry build \
    && mkdir -p /src/docker \
    && cp -v docker/docker-entrypoint.sh /src/docker \
    && cp -vr conf /src \
    && cp -vr dist /src

# --- Final image
FROM base as greenwave
LABEL \
    name="Greenwave application" \
    vendor="Greenwave developers" \
    license="GPLv2+" \
    build-date=""

WORKDIR /src
COPY --from=builder /src .
COPY --from=builder /venv /venv
RUN set -ex \
    && /venv/bin/pip install --no-cache-dir dist/*.whl \
    && rm -r dist \
    # This will allow a non-root user to install a custom root CA at run-time
    && chmod 777 /etc/pki/tls/certs/ca-bundle.crt

USER 1001
EXPOSE 8080
ENTRYPOINT ["/src/docker/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "--enable-stdio-inheritance", "greenwave.wsgi:app"]
