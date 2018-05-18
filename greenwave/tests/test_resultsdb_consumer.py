# SPDX-License-Identifier: GPL-2.0+

import greenwave.app_factory
import greenwave.consumers.resultsdb


def test_announcement_keys_decode_with_list():
    cls = greenwave.consumers.resultsdb.ResultsDBHandler
    app = greenwave.app_factory.create_app()
    app.config['ANNOUNCEMENT_SUBJECT_KEYS'] = [('foo',)]
    message = {'msg': {'data': {
        u'foo'.encode('utf-8'): [u'bar'.encode('utf-8')],
    }}}

    with app.app_context():
        subjects = list(cls.announcement_subjects(message))

    assert subjects == [{u'foo': u'bar'}]
