#!/bin/bash

# SPDX-License-Identifier: GPL-2.0+

# Prints the current version based on the current git revision.

set -e

name=greenwave
if [ "$(git tag | wc -l)" -eq 0 ] ; then
    # never been tagged since the project is just starting out
    lastversion="0.0"
    revbase=""
else
    lasttag="$(git describe --abbrev=0 HEAD)"
    lastversion="${lasttag##${name}-}"
    revbase="^$lasttag"
fi
if [ "$(git rev-list $revbase HEAD | wc -l)" -eq 0 ] ; then
    # building a tag
    version="$lastversion"
else
    # git builds count as a pre-release of the next version
    version="$lastversion"
    version="${version%%[a-z]*}" # strip non-numeric suffixes like "rc1"
    # increment the last portion of the version
    version="${version%.*}.$((${version##*.} + 1))"
    commitcount=$(git rev-list $revbase HEAD | wc -l)
    commitsha=$(git rev-parse --short HEAD)
    version="${version}.dev${commitcount}+git.${commitsha}"
fi

echo $version
