# SPDX-License-Identifier: GPL-2.0+

import mock

from textwrap import dedent

import greenwave.app_factory
import greenwave.consumers.resultsdb
from greenwave.policies import Policy


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


def test_announcement_subjects_for_autocloud_compose():
    cls = greenwave.consumers.resultsdb.ResultsDBHandler
    app = greenwave.app_factory.create_app()
    message = {
        'msg': {
            'task': {
                'item': 'Fedora-AtomicHost-28_Update-20180723.1839.x86_64.qcow2',
                'type': 'compose',
                'name': 'compose.install_no_user'
            },
            'result': {
                'prev_outcome': None,
                'outcome': 'PASSED',
                'id': 23004689,
                'submit_time': '2018-07-23 21:07:38 UTC',
                'log_url': 'https://apps.fedoraproject.org/autocloud/jobs/9238/output'
            }
        }
    }

    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_update_for_build') as f:
            f.return_value = None
            subjects = list(cls.announcement_subjects(message))

    assert subjects == [('compose', 'Fedora-AtomicHost-28_Update-20180723.1839.x86_64.qcow2')]


@mock.patch('greenwave.resources.retrieve_update_for_build', return_value=None)
@mock.patch('greenwave.resources.retrieve_decision')
@mock.patch('greenwave.resources.retrieve_scm_from_koji')
@mock.patch('greenwave.resources.retrieve_yaml_remote_rule')
@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_remote_rule_decision_change(
        mock_fedmsg,
        mock_retrieve_yaml_remote_rule,
        mock_retrieve_scm_from_koji,
        mock_retrieve_decision,
        testdatabuilder):
    """
    Test publishing decision change message for test cases mentioned in
    gating.yaml.
    """
    # gating.yaml
    gating_yaml = dedent("""
        --- !Policy
        product_versions: [fedora-rawhide, notexisting_prodversion]
        decision_context: test_context
        rules:
          - !PassingTestCaseRule {test_case_name: dist.rpmdeplint}
    """)
    mock_retrieve_yaml_remote_rule.return_value = gating_yaml

    policies = dedent("""
        --- !Policy
        id: test_policy
        product_versions: [fedora-rawhide]
        decision_context: test_context
        subject_type: koji_build
        rules:
          - !RemoteRule {}
    """)

    nvr = testdatabuilder.unique_nvr(product_version='rawhide')
    result = testdatabuilder.create_result(
        item=nvr, testcase_name='dist.rpmdeplint', outcome='PASSED')

    def retrieve_decision(url, data):
        if 'ignore_result' in data:
            return None
        return {}
    mock_retrieve_decision.side_effect = retrieve_decision
    mock_retrieve_scm_from_koji.return_value = ('rpms', nvr,
                                                'c3c47a08a66451cb9686c49f040776ed35a0d1bb')

    message = {
        'body': {
            'topic': 'resultsdb.result.new',
            'msg': {
                'id': result['id'],
                'outcome': 'PASSED',
                'testcase': {
                    'name': 'dist.rpmdeplint',
                },
                'data': {
                    'item': [nvr],
                    'type': ['koji_build'],
                }
            }
        }
    }
    hub = mock.MagicMock()
    hub.config = {
        'environment': 'environment',
        'topic_prefix': 'topic_prefix',
    }
    handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

    handler.flask_app.config['policies'] = Policy.safe_load_all(policies)
    with handler.flask_app.app_context():
        handler.consume(message)

    assert len(mock_fedmsg.mock_calls) == 1

    mock_call = mock_fedmsg.mock_calls[0][2]
    assert mock_call['topic'] == 'decision.update'

    actual_msgs_sent = [mock_call['msg'] for call in mock_fedmsg.mock_calls]
    assert actual_msgs_sent[0] == {
        'decision_context': 'test_context',
        'product_version': 'fedora-rawhide',
        'subject': [
            {'item': nvr, 'type': 'koji_build'},
        ],
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'previous': None,
    }


@mock.patch('greenwave.resources.retrieve_update_for_build', return_value=None)
@mock.patch('greenwave.resources.retrieve_decision')
@mock.patch('greenwave.resources.retrieve_scm_from_koji')
@mock.patch('greenwave.resources.retrieve_yaml_remote_rule')
@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_remote_rule_decision_change_not_matching(
        mock_fedmsg,
        mock_retrieve_yaml_remote_rule,
        mock_retrieve_scm_from_koji,
        mock_retrieve_decision,
        testdatabuilder):
    """
    Test publishing decision change message for test cases mentioned in
    gating.yaml.
    """
    # gating.yaml
    gating_yaml = dedent("""
        --- !Policy
        product_versions: [fedora-rawhide]
        decision_context: test_context
        rules:
          - !PassingTestCaseRule {test_case_name: dist.rpmdeplint}
    """)
    mock_retrieve_yaml_remote_rule.return_value = gating_yaml

    policies = dedent("""
        --- !Policy
        id: test_policy
        product_versions: [fedora-rawhide]
        decision_context: another_test_context
        subject_type: koji_build
        rules:
          - !RemoteRule {}
    """)

    nvr = testdatabuilder.unique_nvr(product_version='rawhide')
    result = testdatabuilder.create_result(
        item=nvr, testcase_name='dist.rpmdeplint', outcome='PASSED')

    def retrieve_decision(url, data):
        if 'ignore_result' in data:
            return None
        return {}
    mock_retrieve_decision.side_effect = retrieve_decision
    mock_retrieve_scm_from_koji.return_value = ('rpms', nvr,
                                                'c3c47a08a66451cb9686c49f040776ed35a0d1bb')

    message = {
        'body': {
            'topic': 'resultsdb.result.new',
            'msg': {
                'id': result['id'],
                'outcome': 'PASSED',
                'testcase': {
                    'name': 'dist.rpmdeplint',
                },
                'data': {
                    'item': [nvr],
                    'type': ['koji_build'],
                }
            }
        }
    }
    hub = mock.MagicMock()
    hub.config = {
        'environment': 'environment',
        'topic_prefix': 'topic_prefix',
    }
    handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

    handler.flask_app.config['policies'] = Policy.safe_load_all(policies)
    with handler.flask_app.app_context():
        handler.consume(message)

    assert len(mock_fedmsg.mock_calls) == 0
