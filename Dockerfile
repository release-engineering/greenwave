FROM fedora:31
LABEL \
    name="Greenwave application" \
    vendor="Greenwave developers" \
    license="GPLv2+" \
    build-date=""

# The caller can optionally provide a cacert url
ARG cacert_url=undefined

WORKDIR /src
RUN dnf -y install \
    git-core \
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

RUN if [ "$cacert_url" != "undefined" ]; then \
        cd /etc/pki/ca-trust/source/anchors \
        && curl -O --insecure $cacert_url \
        && update-ca-trust extract; \
    fi
# This will allow a non-root user to install a custom root CA at run-time
RUN chmod 777 /etc/pki/tls/certs/ca-bundle.crt
COPY . .
RUN pip3 install . --no-deps
# Remove the default fedmsg config files included in the repo
RUN rm -rf ./fedmsg.d
USER 1001
EXPOSE 8080
ENTRYPOINT ["/src/docker/docker-entrypoint.sh"]
CMD ["/usr/bin/gunicorn-3", "--workers", "8", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "--enable-stdio-inheritance", "greenwave.wsgi:app"]
