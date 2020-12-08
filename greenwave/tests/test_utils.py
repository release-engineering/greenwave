# SPDX-License-Identifier: GPL-2.0+

import json
import os

import pytest
import requests
from werkzeug.exceptions import InternalServerError

import greenwave.app_factory
from greenwave.utils import json_error, load_config


SETTINGS_DIR = os.path.abspath(os.path.dirname(__file__))
SETTINGS_BASE_NAME = os.path.join(SETTINGS_DIR, 'settings')


@pytest.mark.parametrize(('error, expected_status_code,'
                          'expected_error_message_part'), [
    (ConnectionError('ERROR'), 502, 'ERROR'),
    (requests.ConnectionError('ERROR'), 502, 'ERROR'),
    (requests.ConnectTimeout('TIMEOUT'), 502, 'TIMEOUT'),
    (requests.Timeout('TIMEOUT'), 504, 'TIMEOUT'),
    (InternalServerError(), 500, 'The server encountered an internal error')
])
def test_json_connection_error(error, expected_status_code,
                               expected_error_message_part):
    app = greenwave.app_factory.create_app()
    with app.app_context():
        with app.test_request_context():
            r = json_error(error)
            data = json.loads(r.get_data())
            assert r.status_code == expected_status_code
            assert expected_error_message_part in data['message']


def test_load_config_defaults(monkeypatch):
    monkeypatch.setenv('GREENWAVE_CONFIG', SETTINGS_BASE_NAME + '_empty.py')
    monkeypatch.delenv('GREENWAVE_POLICIES_DIR', raising=False)
    monkeypatch.delenv('GREENWAVE_SUBJECT_TYPES_DIR', raising=False)
    config = load_config('greenwave.config.ProductionConfig')
    assert config['POLICIES_DIR'] == '/etc/greenwave/policies'
    assert config['SUBJECT_TYPES_DIR'] == '/etc/greenwave/subject_types'


def test_load_config_override_with_env(monkeypatch):
    monkeypatch.setenv('GREENWAVE_CONFIG', SETTINGS_BASE_NAME + '_empty.py')
    monkeypatch.setenv('GREENWAVE_POLICIES_DIR', '/policies')
    monkeypatch.setenv('GREENWAVE_SUBJECT_TYPES_DIR', '/subject_types')
    config = load_config('greenwave.config.ProductionConfig')
    assert config['POLICIES_DIR'] == '/policies'
    assert config['SUBJECT_TYPES_DIR'] == '/subject_types'


def test_load_config_override_with_custom_config(monkeypatch):
    monkeypatch.setenv('GREENWAVE_CONFIG', SETTINGS_BASE_NAME + '_override.py')
    monkeypatch.setenv('GREENWAVE_POLICIES_DIR', '/policies')
    monkeypatch.setenv('GREENWAVE_SUBJECT_TYPES_DIR', '/subject_types')
    config = load_config('greenwave.config.ProductionConfig')
    assert config['POLICIES_DIR'] == '/src/conf/policies'
    assert config['SUBJECT_TYPES_DIR'] == '/src/conf/subject_types'
