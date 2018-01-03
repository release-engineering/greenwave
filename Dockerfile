FROM fedora:26
LABEL \
    name="Greenwave application" \
    vendor="Greenwave developers" \
    license="GPLv2+" \
    build-date=""
# The caller should build a greenwave RPM package using ./rpmbuild.sh and then pass it in this arg.
ARG greenwave_rpm
COPY $greenwave_rpm /tmp
RUN dnf -y install \
    python-gunicorn \
    /tmp/$(basename $greenwave_rpm) \
    && dnf -y clean all
USER 1001
EXPOSE 8080
ENTRYPOINT gunicorn --bind 0.0.0.0:8080 --access-logfile=- greenwave.wsgi:app
