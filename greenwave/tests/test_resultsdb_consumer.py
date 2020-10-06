# SPDX-License-Identifier: GPL-2.0+

import mock
import pytest

from textwrap import dedent

import greenwave.consumers.resultsdb
from greenwave.app_factory import create_app
from greenwave.product_versions import subject_product_version
from greenwave.policies import Policy
from greenwave.subjects.factory import create_subject


@pytest.fixture(autouse=True)
def mock_retrieve_decision():
    with mock.patch('greenwave.decision.make_decision') as mocked:
        def retrieve_decision(data, config):
            #pylint: disable=unused-argument
            if 'when' in data:
                return None
            return {}
        mocked.side_effect = retrieve_decision
        yield mocked


@pytest.fixture
def mock_retrieve_results():
    with mock.patch('greenwave.resources.ResultsRetriever.retrieve') as mocked:
        yield mocked


@pytest.fixture
def mock_retrieve_scm_from_koji():
    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as mocked:
        yield mocked


@pytest.fixture
def mock_retrieve_yaml_remote_rule():
    with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as mocked:
        yield mocked


def announcement_subject(message):
    cls = greenwave.consumers.resultsdb.ResultsDBHandler

    app = create_app()
    with app.app_context():
        subject = cls.announcement_subject(message)
        if subject:
            return subject.to_dict()


def test_announcement_keys_decode_with_list():
    message = {'msg': {'data': {
        'original_spec_nvr': ['glibc-1.0-1.fc27'],
    }}}
    assert announcement_subject(message) == {'type': 'koji_build', 'item': 'glibc-1.0-1.fc27'}


def test_no_announcement_subjects_for_empty_nvr():
    """The CI pipeline submits a lot of results for the test
    'org.centos.prod.ci.pipeline.allpackages-build.package.ignored'
    with the 'original_spec_nvr' key present, but the value just an
    empty string. To avoid unpredictable consequences, we should not
    return any announcement subjects for such a message.
    """
    message = {'msg': {'data': {
        'original_spec_nvr': [""],
    }}}

    assert announcement_subject(message) is None


def test_announcement_subjects_for_brew_build():
    # The 'brew-build' type appears internally within Red Hat. We treat it as an
    # alias of 'koji_build'.
    message = {'msg': {'data': {
        'type': 'brew-build',
        'item': ['glibc-1.0-3.fc27'],
    }}}

    assert announcement_subject(message) == {'type': 'koji_build', 'item': 'glibc-1.0-3.fc27'}


def test_announcement_subjects_for_new_compose_message():
    """Ensure we are producing the right subjects for compose decisions
    as this has caused a lot of confusion in the past. The only
    reliable way to make a compose decision is by looking for the key
    productmd.compose.id with value of the compose ID. This is only
    possible with new-style 'resultsdb' fedmsgs, like this one.
    """
    message = {
        'msg': {
            'data': {
                "scenario": ["fedora.universal.x86_64.64bit"],
                "source": ["openqa"],
                "productmd.compose.name": ["Fedora"],
                "firmware": ["bios"],
                "meta.conventions": ["result productmd.compose fedora.compose"],
                "productmd.compose.respin": ["0"],
                "item": ["Fedora-Rawhide-20181205.n.0"],
                "productmd.compose.id": ["Fedora-Rawhide-20181205.n.0"],
                "type": ["compose"],
                "productmd.compose.date": ["20181205"],
                "productmd.compose.version": ["Rawhide"],
                "arch": ["x86_64"],
                "productmd.compose.type": ["nightly"],
                "productmd.compose.short": ["Fedora"],
            }
        }
    }

    assert announcement_subject(message) == \
        {'productmd.compose.id': 'Fedora-Rawhide-20181205.n.0'}


def test_no_announcement_subjects_for_old_compose_message():
    """With an old-style 'taskotron' fedmsg like this one, it is not
    possible to reliably make a compose decision - see
    https://pagure.io/greenwave/issue/122 etc. So we should NOT
    produce any subjects for this kind of message.
    """
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

    assert announcement_subject(message) is None


parameters = [
    ('fedmsg', 'greenwave.consumers.consumer.fedmsg.publish'),
    ('fedora-messaging', 'greenwave.consumers.consumer.fedora_messaging.api.publish'),
]


@pytest.mark.parametrize("config,publish", parameters)
def test_remote_rule_decision_change(
        mock_retrieve_yaml_remote_rule,
        mock_retrieve_scm_from_koji,
        mock_retrieve_results,
        config,
        publish):
    """
    Test publishing decision change message for test cases mentioned in
    gating.yaml.
    """
    with mock.patch('greenwave.config.Config.MESSAGING', config):
        with mock.patch(publish) as mock_fedmsg:
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

            nvr = 'nethack-1.2.3-1.rawhide'
            result = {
                'id': 1,
                'testcase': {'name': 'dist.rpmdeplint'},
                'outcome': 'PASSED',
                'data': {'item': nvr, 'type': 'koji_build'},
                'submit_time': '2019-03-25T16:34:41.882620'
            }
            mock_retrieve_results.return_value = [result]

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
                        },
                        'submit_time': '2019-03-25T16:34:41.882620'
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

            if config == "fedmsg":
                mock_call = mock_fedmsg.mock_calls[0][2]
                assert mock_call['topic'] == 'decision.update'
                actual_msgs_sent = mock_call['msg']
            else:
                mock_call = mock_fedmsg.mock_calls[0][1][0]
                assert mock_call.topic == 'greenwave.decision.update'
                actual_msgs_sent = mock_call.body

            assert actual_msgs_sent == {
                'decision_context': 'test_context',
                'product_version': 'fedora-rawhide',
                'subject': [
                    {'item': nvr, 'type': 'koji_build'},
                ],
                'subject_type': 'koji_build',
                'subject_identifier': nvr,
                'previous': None,
            }


@pytest.mark.parametrize("config,publish", parameters)
def test_remote_rule_decision_change_not_matching(
        mock_retrieve_yaml_remote_rule,
        mock_retrieve_scm_from_koji,
        mock_retrieve_results,
        config,
        publish):
    """
    Test publishing decision change message for test cases mentioned in
    gating.yaml.
    """
    with mock.patch('greenwave.config.Config.MESSAGING', config):
        with mock.patch(publish) as mock_fedmsg:
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

            nvr = 'nethack-1.2.3-1.rawhide'
            result = {
                'id': 1,
                'testcase': {'name': 'dist.rpmdeplint'},
                'outcome': 'PASSED',
                'data': {'item': nvr, 'type': 'koji_build'},
                'submit_time': '2019-03-25T16:34:41.882620'
            }
            mock_retrieve_results.return_value = [result]

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
                        },
                        'submit_time': '2019-03-25T16:34:41.882620'
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


def test_guess_product_version():
    hub = mock.MagicMock()
    hub.config = {
        'environment': 'environment',
        'topic_prefix': 'topic_prefix',
    }
    handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)
    with handler.flask_app.app_context():
        subject = create_subject('koji_build', 'release-e2e-test-1.0.1685-1.el5')
        product_version = subject_product_version(subject)
        assert product_version == 'rhel-5'

        subject = create_subject('redhat-module', 'rust-toolset-rhel8-20181010170614.b09eea91')
        product_version = subject_product_version(subject)
        assert product_version == 'rhel-8'


def test_guess_product_version_with_koji():
    koji_proxy = mock.MagicMock()
    koji_proxy.getBuild.return_value = {'task_id': 666}
    koji_proxy.getTaskRequest.return_value = ['git://example.com/project', 'rawhide', {}]

    app = create_app()
    with app.app_context():
        subject = create_subject('container-build', 'fake_koji_build')
    product_version = subject_product_version(subject, koji_proxy)
    koji_proxy.getBuild.assert_called_once_with('fake_koji_build')
    koji_proxy.getTaskRequest.assert_called_once_with(666)
    assert product_version == 'fedora-rawhide'


def test_guess_product_version_with_koji_without_task_id():
    koji_proxy = mock.MagicMock()
    koji_proxy.getBuild.return_value = {'task_id': None}

    app = create_app()
    with app.app_context():
        subject = create_subject('container-build', 'fake_koji_build')
    product_version = subject_product_version(subject, koji_proxy)

    koji_proxy.getBuild.assert_called_once_with('fake_koji_build')
    koji_proxy.getTaskRequest.assert_not_called()
    assert product_version is None


@pytest.mark.parametrize('nvr', (
    'badnvr.elastic-1-228',
    'badnvr-1.2-1.elastic8',
    'el99',
    'badnvr-1.2.f30',
))
def test_guess_product_version_failure(nvr):
    app = create_app()
    with app.app_context():
        subject = create_subject('koji_build', nvr)
    product_version = subject_product_version(subject)
    assert product_version is None


@pytest.mark.parametrize("config,publish", parameters)
def test_decision_change_for_modules(
        mock_retrieve_yaml_remote_rule,
        mock_retrieve_scm_from_koji,
        mock_retrieve_results,
        config,
        publish):
    """
    Test publishing decision change message for a module.
    """
    with mock.patch('greenwave.config.Config.MESSAGING', config):
        with mock.patch(publish) as mock_fedmsg:

            # gating.yaml
            gating_yaml = dedent("""
                --- !Policy
                product_versions:
                  - rhel-8
                decision_context: osci_compose_gate_modules
                subject_type: redhat-module
                rules:
                  - !PassingTestCaseRule {test_case_name: baseos-ci.redhat-module.tier1.functional}
            """)
            mock_retrieve_yaml_remote_rule.return_value = gating_yaml

            policies = dedent("""
            --- !Policy
                id: "osci_compose_modules"
                product_versions:
                  - rhel-8
                decision_context: osci_compose_gate_modules
                subject_type: redhat-module
                blacklist: []
                rules:
                  - !RemoteRule {}
            """)

            nsvc = 'python36-3.6-820181204160430.17efdbc7'
            result = {
                'id': 1,
                'testcase': {'name': 'baseos-ci.redhat-module.tier1.functional'},
                'outcome': 'PASSED',
                'data': {'item': nsvc, 'type': 'redhat-module'},
                'submit_time': '2019-03-25T16:34:41.882620'
            }
            mock_retrieve_results.return_value = [result]

            mock_retrieve_scm_from_koji.return_value = ('modules', nsvc,
                                                        '97273b80dd568bd15f9636b695f6001ecadb65e0')

            message = {
                'body': {
                    'topic': 'resultsdb.result.new',
                    'msg': {
                        'id': result['id'],
                        'outcome': 'PASSED',
                        'testcase': {
                            'name': 'baseos-ci.redhat-module.tier1.functional',
                        },
                        'data': {
                            'item': [nsvc],
                            'type': ['redhat-module'],
                        },
                        'submit_time': '2019-03-25T16:34:41.882620'
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

            if config == "fedmsg":
                mock_call = mock_fedmsg.mock_calls[0][2]
                assert mock_call['topic'] == 'decision.update'
                actual_msgs_sent = mock_call['msg']
            else:
                mock_call = mock_fedmsg.mock_calls[0][1][0]
                assert mock_call.topic == 'greenwave.decision.update'
                actual_msgs_sent = mock_call.body

            assert actual_msgs_sent == {
                'decision_context': 'osci_compose_gate_modules',
                'product_version': 'rhel-8',
                'subject': [
                    {'item': nsvc, 'type': 'redhat-module'},
                ],
                'subject_type': 'redhat-module',
                'subject_identifier': nsvc,
                'previous': None,
            }


def test_real_fedora_messaging_msg(mock_retrieve_results):
    message = {
        'msg': {
            'task': {
                'type': 'bodhi_update',
                'item': 'FEDORA-2019-9244c8b209',
                'name': 'update.advisory_boot'
            },
            'result': {
                'id': 23523568,
                'submit_time': '2019-04-24 13:06:12 UTC',
                'prev_outcome': None,
                'outcome': 'PASSED',
                'log_url': 'https://openqa.stg.fedoraproject.org/tests/528801'
            }
        }
    }

    result = {
        "data": {
            "arch": [
                "x86_64"
            ],
            "firmware": [
                "bios"
            ],
            "item": [
                "FEDORA-2019-9244c8b209"
            ],
            "meta.conventions": [
                "result fedora.bodhi"
            ],
            "scenario": [
                "fedora.updates-server.x86_64.64bit"
            ],
            "source": [
                "openqa"
            ],
            "type": [
                "bodhi_update"
            ]
        },
        "groups": [
            "61d11797-79cd-579f-b150-349cc77e0941",
            "222c442c-5d94-528f-9b9e-3fb379edf657",
            "0f3309ea-6d4c-59b2-b422-d73e9b8511f3"
        ],
        "href": "https://taskotron.stg.fedoraproject.org/resultsdb_api/api/v2.0/results/23523568",
        "id": 23523568,
        "note": "",
        "outcome": "PASSED",
        "ref_url": "https://openqa.stg.fedoraproject.org/tests/528801",
        "submit_time": "2019-04-24T13:06:12.135146",
        "testcase": {
            "href": "https://taskotron.stg.fedoraproject.org/resultsdb_api/api/v2.0/testcases/update.advisory_boot", # noqa
            "name": "update.advisory_boot",
            "ref_url": "https://openqa.stg.fedoraproject.org/tests/546627"
        }
    }

    policies = dedent("""
        --- !Policy
        id: test_policy
        product_versions: [fedora-rawhide]
        decision_context: test_context
        subject_type: bodhi_update
        rules:
          - !PassingTestCaseRule {test_case_name: update.advisory_boot}
    """)

    config = 'fedora-messaging'
    publish = 'greenwave.consumers.consumer.fedora_messaging.api.publish'

    with mock.patch('greenwave.config.Config.MESSAGING', config):
        with mock.patch(publish) as mock_fedmsg:
            result = {
                'id': 1,
                'testcase': {'name': 'dist.rpmdeplint'},
                'outcome': 'PASSED',
                'data': {'item': 'FEDORA-2019-9244c8b209', 'type': 'bodhi_update'},
                'submit_time': '2019-04-24 13:06:12.135146'
            }
            mock_retrieve_results.return_value = [result]

            hub = mock.MagicMock()
            hub.config = {
                'environment': 'environment',
                'topic_prefix': 'topic_prefix',
            }
            handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

            handler.koji_proxy = None
            handler.flask_app.config['policies'] = Policy.safe_load_all(policies)
            with handler.flask_app.app_context():
                handler.consume(message)

            assert len(mock_fedmsg.mock_calls) == 1

            mock_call = mock_fedmsg.mock_calls[0][1][0]
            assert mock_call.topic == 'greenwave.decision.update'
            actual_msgs_sent = mock_call.body

            assert actual_msgs_sent == {
                'decision_context': 'test_context',
                'product_version': 'fedora-rawhide',
                'subject': [
                    {'item': 'FEDORA-2019-9244c8b209', 'type': 'bodhi_update'},
                ],
                'subject_type': 'bodhi_update',
                'subject_identifier': 'FEDORA-2019-9244c8b209',
                'previous': None,
            }


def test_container_brew_build(mock_retrieve_results):
    message = {
        'msg': {
            'submit_time': '2019-08-27T13:57:53.490376',
            'testcase': {
                'name': 'example_test',
            },
            'data': {
                'brew_task_id': ['666'],
                'type': ['brew-build'],
                'item': ['example-container'],
            }
        }
    }

    policies = dedent("""
        --- !Policy
        id: test_policy
        product_versions: [example_product_version]
        decision_context: test_context
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: example_test}
    """)

    config = 'fedora-messaging'
    publish = 'greenwave.consumers.consumer.fedora_messaging.api.publish'

    with mock.patch('greenwave.config.Config.MESSAGING', config):
        with mock.patch(publish) as mock_fedmsg:
            result = {
                'id': 1,
                'testcase': {'name': 'example_test'},
                'outcome': 'PASSED',
                'data': {'item': 'example-container', 'type': 'koji_build'},
                'submit_time': '2019-04-24 13:06:12.135146'
            }
            mock_retrieve_results.return_value = [result]

            hub = mock.MagicMock()
            hub.config = {
                'environment': 'environment',
                'topic_prefix': 'topic_prefix',
            }
            handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

            koji_proxy = mock.MagicMock()
            koji_proxy.getBuild.return_value = None
            koji_proxy.getTaskRequest.return_value = [
                'git://example.com/project', 'example_product_version', {}]
            handler.koji_proxy = koji_proxy

            handler.flask_app.config['policies'] = Policy.safe_load_all(policies)
            with handler.flask_app.app_context():
                handler.consume(message)

            koji_proxy.getBuild.assert_not_called()
            koji_proxy.getTaskRequest.assert_called_once_with(666)

            assert len(mock_fedmsg.mock_calls) == 1

            mock_call = mock_fedmsg.mock_calls[0][1][0]
            assert mock_call.topic == 'greenwave.decision.update'
            actual_msgs_sent = mock_call.body

            assert actual_msgs_sent == {
                'decision_context': 'test_context',
                'product_version': 'example_product_version',
                'subject': [
                    {'item': 'example-container', 'type': 'koji_build'},
                ],
                'subject_type': 'koji_build',
                'subject_identifier': 'example-container',
                'previous': None,
            }
