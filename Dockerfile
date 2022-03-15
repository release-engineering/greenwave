FROM registry.fedoraproject.org/fedora:35
LABEL \
    name="Greenwave application" \
    vendor="Greenwave developers" \
    license="GPLv2+" \
    build-date=""

RUN dnf -y install \
    git-core \
    python3-dateutil \
    python3-dogpile-cache \
    python3-fedmsg \
    python3-flask \
    python3-gunicorn \
    python3-memcached \
    python3-pip \
    python3-prometheus_client \
    python3-PyYAML \
    python3-requests \
    && dnf -y clean all \
    && rm -rf /tmp/*

# This will allow a non-root user to install a custom root CA at run-time
RUN chmod 777 /etc/pki/tls/certs/ca-bundle.crt

COPY . /tmp/code
WORKDIR /tmp/code
RUN set -ex \
    && version=$(./get-version.sh) \
    && test -n "$version" \
    && sed --regexp-extended -i -e \
        "/^__version__ = /c\\__version__ = '$version'" greenwave/__init__.py \
    && pip3 install . --no-cache-dir --no-deps \
    && mkdir -p /src/docker \
    && cp -v docker/docker-entrypoint.sh /src/docker \
    && cp -vr conf /src \
    && rm -rf /tmp/* \
    # Quick test for the installed package and version
    && python3 -c "import greenwave; assert(greenwave.__version__ == '$version')"

WORKDIR /src

USER 1001
EXPOSE 8080
ENTRYPOINT ["/src/docker/docker-entrypoint.sh"]
CMD ["/usr/bin/gunicorn-3", "--workers", "8", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "--enable-stdio-inheritance", "greenwave.wsgi:app"]
