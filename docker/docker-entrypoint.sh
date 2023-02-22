#!/bin/bash
set -e

if [ -z "$GREENWAVE_CONFIG" ]; then
    if [ -f /etc/greenwave/settings.py ]; then
        export GREENWAVE_CONFIG=/etc/greenwave/settings.py
    elif [ -f /src/conf/settings.py ]; then
        export GREENWAVE_CONFIG=/src/conf/settings.py
    else
        export GREENWAVE_CONFIG=/src/conf/settings.py.example
    fi
fi

if [ -z "$GREENWAVE_SUBJECT_TYPES_DIR" ]; then
    if [ -d /etc/greenwave/subject_types ]; then
        export GREENWAVE_SUBJECT_TYPES_DIR=/etc/greenwave/subject_types
    else
        export GREENWAVE_SUBJECT_TYPES_DIR=/src/conf/subject_types
    fi
fi

if [ -z "$GREENWAVE_POLICIES_DIR" ]; then
    if [ -d /etc/greenwave/policies ]; then
        export GREENWAVE_POLICIES_DIR=/etc/greenwave/policies
    else
        export GREENWAVE_POLICIES_DIR=/src/conf/policies
    fi
fi

. /venv/bin/activate
exec "$@"
