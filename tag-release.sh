#!/bin/bash

# SPDX-License-Identifier: GPL-2.0+

set -e

version="$1"
prerelease="$2"

if [ -z "$version" ] ; then
    echo "Usage: $0 <version> [<prerelease>]" >&2
    echo "Example: $0 0.1 rc1" >&2
    exit 1
fi

if git status --porcelain | grep -q '^.M' ; then
    echo "Work tree has modifications, stash or add before tagging" >&2
    exit 1
fi

sed -i -e "/%global upstream_version /c\%global upstream_version ${version}${prerelease}" greenwave.spec
sed -i -e "/^Version:/c\Version:        $version" greenwave.spec
if [ -n "$prerelease" ] ; then
    sed -i -e "/^Release:/c\Release:        0.$prerelease%{?dist}" greenwave.spec
else
    sed -i -e "/^Release:/c\Release:        1%{?dist}" greenwave.spec
fi
sed -i -e "/^__version__ = /c\\__version__ = '$version$prerelease'" greenwave/__init__.py
git add greenwave.spec greenwave/__init__.py
git commit -m "Automatic commit of release $version$prerelease"
git tag -s "greenwave-$version$prerelease" -m "Tagging release $version$prerelease"
