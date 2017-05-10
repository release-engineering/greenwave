# -*- coding: utf-8 -*-
#
# This file is part of the Greenwave project.
# Copyright (C) 2017 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
import re

from setuptools import setup, find_packages


here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as fd:
    README = fd.read()


def get_project_version(version_file='greenwave/__init__.py'):
    """
    Read the declared version of the project from the source code.

    Args:
        version_file: The file with the version string in it. The version must
            be in the format ``__version__ = '<version>'`` and the file must be
            UTF-8 encoded.
    """
    with open(version_file, "rb") as f:
        version_pattern = b"^__version__ = '(.+)'$"
        match = re.search(version_pattern, f.read(), re.MULTILINE)
    if match is None:
        err_msg = "No line matching  %r found in %r"
        raise ValueError(err_msg % (version_pattern, version_file))
    return match.groups()[0].decode("utf-8")


def get_requirements(requirements_file='requirements.txt'):
    """Get the contents of a file listing the requirements.

    Args:
        requirements_file (str): The path to the requirements file, relative
                                 to this file.

    Returns:
        list: the list of requirements, or an empty list if
              ``requirements_file`` could not be opened or read.
    """
    with open(requirements_file) as fd:
        lines = fd.readlines()
    dependencies = []
    for line in lines:
        maybe_dep = line.strip()
        if maybe_dep.startswith('#'):
            # Skip pure comment lines
            continue
        if maybe_dep.startswith('git+'):
            # VCS reference for dev purposes, expect a trailing comment
            # with the normal requirement
            __, __, maybe_dep = maybe_dep.rpartition('#')
        else:
            # Ignore any trailing comment
            maybe_dep, __, __ = maybe_dep.partition('#')
        # Remove any whitespace and assume non-empty results are dependencies
        maybe_dep = maybe_dep.strip()
        if maybe_dep:
            dependencies.append(maybe_dep)
    return dependencies


setup(
    name='greenwave',
    version=get_project_version(),
    description=(
        'Greenwave is a service to decide whether a software artifact can pass'
        ' certain gating points in a software delivery pipeline'
    ),
    long_description=README,
    # Possible options are at https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 1 - Planning',
        'Framework :: Flask',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    license='GPLv2+',
    maintainer='Fedora Infrastructure Team',
    maintainer_email='infrastructure@lists.fedoraproject.org',
    platforms=['Fedora', 'GNU/Linux'],
    url='https://pagure.io/greenwave/',
    packages=find_packages(exclude=('greenwave.tests', 'greenwave.tests.*')),
    include_package_data=True,
    zip_safe=False,
    install_requires=get_requirements(),
    tests_require=get_requirements(requirements_file='dev-requirements.txt'),
    test_suite='greenwave.tests',
)
