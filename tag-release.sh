#!/bin/bash

# SPDX-License-Identifier: GPL-2.0+

set -e

version="$1"
prerelease="$2"
name=Greenwave

release_notes_file=docs/release-notes.rst

if [ -z "$version" ] ; then
    echo "Usage: $0 <version> [<prerelease>]" >&2
    echo "Example: $0 0.1 rc1" >&2
    exit 1
fi

if git status --porcelain | grep -q '^.M' ; then
    echo "Work tree has modifications, stash or add before tagging" >&2
    exit 1
fi

if ! grep -q --fixed-strings "$name ${version%.*}" "$release_notes_file"; then
    echo "Section \"$name $version\" not found in \"$release_notes_file\"."
    echo "Please update release notes."
    exit 1
fi

poetry version "$version$prerelease"

git add "pyproject.toml"
git commit -m "Automatic commit of release $version$prerelease"
git tag -s "greenwave-$version$prerelease" -m "Tagging release $version$prerelease"
