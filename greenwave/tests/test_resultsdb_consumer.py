# SPDX-License-Identifier: GPL-2.0+

import mock

import greenwave.app_factory
import greenwave.consumers.resultsdb


def test_announcement_keys_decode_with_list():
    cls = greenwave.consumers.resultsdb.ResultsDBHandler
    app = greenwave.app_factory.create_app()
    message = {'msg': {'data': {
        'original_spec_nvr': ['glibc-1.0-1.fc27'],
    }}}

    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_update_for_build') as f:
            f.return_value = None
            subjects = list(cls.announcement_subjects(message))

    assert subjects == [('koji_build', 'glibc-1.0-1.fc27')]


def test_announcement_subjects_include_bodhi_update():
    cls = greenwave.consumers.resultsdb.ResultsDBHandler
    app = greenwave.app_factory.create_app()
    message = {'msg': {'data': {
        'original_spec_nvr': ['glibc-1.0-2.fc27'],
    }}}

    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_update_for_build') as f:
            f.return_value = 'FEDORA-27-12345678'
            subjects = list(cls.announcement_subjects(message))

    # Result was about a Koji build, but the build is in a Bodhi update.
    # So we should announce decisions about both subjects.
    assert subjects == [
        ('koji_build', 'glibc-1.0-2.fc27'),
        ('bodhi_update', 'FEDORA-27-12345678'),
    ]


def test_announcement_subjects_for_brew_build():
    # The 'brew-build' type appears internally within Red Hat. We treat it as an
    # alias of 'koji_build'.
    cls = greenwave.consumers.resultsdb.ResultsDBHandler
    app = greenwave.app_factory.create_app()
    message = {'msg': {'data': {
        'type': 'brew-build',
        'item': ['glibc-1.0-3.fc27'],
    }}}

    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_update_for_build') as f:
            f.return_value = None
            subjects = list(cls.announcement_subjects(message))

    assert subjects == [('koji_build', 'glibc-1.0-3.fc27')]
