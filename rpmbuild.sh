#!/bin/bash

# SPDX-License-Identifier: GPL-2.0+

# Builds a development (S)RPM from the current git revision.

set -e

if [ $# -eq 0 ] ; then
    echo "Usage: $1 -bs|-bb <rpmbuild-options...>" >&2
    echo "Hint: -bs builds SRPM, -bb builds RPM, refer to rpmbuild(8)" >&2
    exit 1
fi

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
    rpmver=""
    rpmrel=""
    version="$lastversion"
else
    # git builds count as a pre-release of the next version
    version="$lastversion"
    version="${version%%[a-z]*}" # strip non-numeric suffixes like "rc1"
    # increment the last portion of the version
    version="${version%.*}.$((${version##*.} + 1))"
    commitcount=$(git rev-list $revbase HEAD | wc -l)
    commitsha=$(git rev-parse --short HEAD)
    rpmver="${version}"
    rpmrel="0.git.${commitcount}.${commitsha}"
    version="${version}.dev${commitcount}+git.${commitsha}"
fi

workdir="$(mktemp -d)"
trap "rm -rf $workdir" EXIT
outdir="$(readlink -f ./rpmbuild-output)"
mkdir -p "$outdir"

git archive --format=tar HEAD | tar -C "$workdir" -xf -
if [ -n "$rpmrel" ] ; then
    # need to hack the version in the spec
    sed --regexp-extended --in-place \
        -e "/%global upstream_version /c\%global upstream_version ${version}" \
        -e "/^Version:/cVersion: ${rpmver}" \
        -e "/^Release:/cRelease: ${rpmrel}%{?dist}" \
        "$workdir/${name}.spec"
    # also hack the Python module version
    sed --regexp-extended --in-place \
        -e "/^__version__ = /c\\__version__ = '$version'" \
        "$workdir/greenwave/__init__.py"
fi
( cd "$workdir" && python setup.py sdist )
mv "$workdir"/dist/*.tar.gz "$workdir"

rpmbuild \
    --define "_topdir $workdir" \
    --define "_sourcedir $workdir" \
    --define "_specdir $workdir" \
    --define "_rpmdir $outdir" \
    --define "_srcrpmdir $outdir" \
    "$@" "$workdir/${name}.spec"
