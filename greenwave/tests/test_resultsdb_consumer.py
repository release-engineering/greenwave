# SPDX-License-Identifier: GPL-2.0+

import mock

import greenwave.app_factory
import greenwave.consumers.resultsdb


def test_announcement_keys_decode_with_list():
    cls = greenwave.consumers.resultsdb.ResultsDBHandler
    app = greenwave.app_factory.create_app()
    message = {'msg': {'data': {
        u'original_spec_nvr'.encode('utf-8'): [u'glibc-1.0-1.fc27'.encode('utf-8')],
    }}}

    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_update_for_build') as f:
            f.return_value = None
            subjects = list(cls.announcement_subjects(message))

    assert subjects == [(u'koji_build', u'glibc-1.0-1.fc27')]
