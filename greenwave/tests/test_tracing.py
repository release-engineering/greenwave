# SPDX-License-Identifier: GPL-2.0+

from unittest.mock import MagicMock, patch

import stomp

from greenwave.listeners.resultsdb import ResultsDBListener
from greenwave.subjects.subject import SubjectType
from greenwave.tracing import init_tracing

JSON_MESSAGE = {
    "data": {
        "brew_task_id": [
            "57212843"
        ],
        "ci_docs": [
            "https://docs.example.com/ci"
        ],
        "ci_email": [
            "example@email.com"
        ],
        "ci_name": [
            "Container Test"
        ],
        "ci_team": [
            "Test"
        ],
        "ci_url": [
            "https://docs.example.com/ci"
        ],
        "full_names": [
            "https://docs.example.com/ci"
        ],
        "id": [
            "sha256:a7fc01280c6b8173611c75a2cbd5a19f5d2ce42d9578d4efcc944e4bc80b09a0"
        ],
        "issuer": [
            "Test"
        ],
        "item": [
            "avahi"
        ],
        "log": [
            "https://docs.example.com/ci"
        ],
        "msg_id": [
            "ID:jenkins-2-8dcwr-46389-1700226798425-136563:1:1:1:1"
        ],
        "scratch": [
            "false"
        ],
        "system_architecture": [
            "x86_64"
        ],
        "system_provider": [
            "Test"
        ],
        "type": [
            "redhat-module"
        ]
    },
    "groups": [],
    "href": "https://docs.example.com/ci",
    "id": 23659469,
    "note": "Result status PASSED",
    "outcome": "PASSED",
    "ref_url": "https://docs.example.com/ci",
    "submit_time": "2023-11-27T11:42:24.538119",
    "testcase": {
        "href": "https://docs.example.com/ci",
        "name": "baseos-ci.redhat-module.tier0.functional",
        "ref_url": None
    },
    "traceparent": "00-a9c3b99a95cc045e573e163c3ac80a77-d99d251a8caecd06-01"
}
patch_subject = SubjectType()
patch_subject.id = "redhat-module"  # type: ignore

patch_decision = {
    'policies_satisfied': True,
    'summary': "TestSucced",
    'satisfied_requirements': [None],
    'unsatisfied_requirements': [None]
}
patch_old_decision = {
    'policies_satisfied': True,
    'summary': "TestSucced",
    'satisfied_requirements': [None],
    'unsatisfied_requirements': [None]
}

real_connection = stomp.connect.StompConnection11()
mock_connection = MagicMock(real_connection)
mock_connection.send = MagicMock(side_effect=[])


@patch('greenwave.listeners.base._is_decision_unchanged', return_value=False)
@patch.object(ResultsDBListener, '_old_and_new_decisions',
              return_value=(patch_old_decision, patch_decision))
@patch('greenwave.subjects.factory.subject_types', return_value=[patch_subject])
def test_tracing(mocked_factory, mocked_decision, mocked_decision_unchanged):
    resultdb_class = ResultsDBListener()
    with patch.object(resultdb_class, 'connection', side_effect=mock_connection):
        mock_publish = MagicMock(side_effect=resultdb_class._publish_decision_update)
        resultdb_class._publish_decision_update = mock_publish
        resultdb_class._consume_message(JSON_MESSAGE)
        mock_publish.assert_called_once()
        assert mock_publish.call_args.args[0]["traceparent"] == JSON_MESSAGE[
            "traceparent"]


@patch("greenwave.tracing.TracerProvider")
@patch("greenwave.tracing.OTLPSpanExporter")
@patch("greenwave.tracing.FlaskInstrumentor")
@patch("greenwave.tracing.BatchSpanProcessor")
@patch("greenwave.tracing.Resource")
def test_init_tracing_with_valid_config(mock_resource, mock_batch, mock_instrumentor,
                                        mock_span_exporter,
                                        mock_provider):
    app = MagicMock()
    app.config.get.side_effect = lambda key: {
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://example.com",
        "OTEL_EXPORTER_SERVICE_NAME": "example_service"
    }.get(key)

    init_tracing(app)

    mock_provider.assert_called_once_with(
        resource=mock_resource.create.return_value)
    mock_span_exporter.assert_called_once_with(endpoint="http://example.com")
    mock_provider.return_value.add_span_processor.assert_called_once_with(
        mock_batch.return_value)
    (mock_instrumentor().instrument_app.
     assert_called_once_with(app,
                             tracer_provider=mock_provider.return_value))


@patch("greenwave.tracing.TracerProvider")
def test_init_tracing_with_invalid_config_name(mock_provider):
    app = MagicMock()
    app.config.get.side_effect = lambda key: {
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://example.com",
    }.get(key)

    init_tracing(app)
    mock_provider.assert_not_called()


@patch("greenwave.tracing.TracerProvider")
def test_init_tracing_with_invalid_config_endpoint(mock_provider):
    app = MagicMock()
    app.config.get.side_effect = lambda key: {
        "OTEL_EXPORTER_SERVICE_NAME": "example_service",
    }.get(key)

    init_tracing(app)
    mock_provider.assert_not_called()
