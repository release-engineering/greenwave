# SPDX-License-Identifier: GPL-2.0+

import greenwave.consumers.resultsdb


def test_announcement_keys_decode_with_list():
    cls = greenwave.consumers.resultsdb.ResultsDBHandler
    config = {'ANNOUNCEMENT_SUBJECT_KEYS': [('foo',)]}
    message = {'msg': {'data': {
        u'foo'.encode('utf-8'): [u'bar'.encode('utf-8')],
    }}}

    subjects = cls.announcement_subjects(config, message)

    assert list(subjects) == [{u'foo': u'bar'}]
