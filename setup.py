# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+

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
    with open(version_file, 'r') as f:
        version_pattern = "^__version__ = '(.+)'$"
        match = re.search(version_pattern, f.read(), re.MULTILINE)
    if match is None:
        err_msg = 'No line matching %r found in %r'
        raise ValueError(err_msg % (version_pattern, version_file))
    return match.group(1)


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
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=get_requirements(),
    tests_require=get_requirements(requirements_file='dev-requirements.txt'),
    test_suite='greenwave.tests',
    entry_points="""\
    [moksha.consumer]
    resultsdb = greenwave.consumers.resultsdb:ResultsDBHandler
    waiverdb = greenwave.consumers.waiverdb:WaiverDBHandler
    """,
    data_files=[('/etc/fedmsg.d/', ['fedmsg.d/resultsdb.py',
                                    'fedmsg.d/waiverdb.py'])]
)
