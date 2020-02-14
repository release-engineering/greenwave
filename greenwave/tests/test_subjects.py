# pylint: disable=unused-argument

import pytest

from greenwave.subjects.factory import (
    create_subject,
    create_subject_from_data,
    UnknownSubjectDataError,
)


def test_subject_create_from_data(app):
    data = {
        'item': 'some_item',
        'type': 'some_type',
    }
    subject = create_subject_from_data(data)

    assert subject.item == 'some_item'
    assert subject.type == 'some_type'
    assert subject.to_dict() == data
    assert list(subject.result_queries()) == [data]


def test_subject_create_from_data_bad(app):
    with pytest.raises(UnknownSubjectDataError):
        create_subject_from_data({})


def test_subject_create_generic(app):
    subject = create_subject('some_type', 'some_item')
    assert subject.item == 'some_item'
    assert subject.type == 'some_type'
    assert subject.identifier == subject.item
    assert subject.package_name is None
    assert subject.short_product_version is None
    assert subject.product_version is None
    assert subject.is_koji_build
    assert not subject.supports_remote_rule


def test_subject_koji_build_result_queries(app):
    subject = create_subject('koji_build', 'some_nvr')
    assert list(subject.result_queries()) == [
        {'type': 'koji_build,brew-build', 'item': 'some_nvr'},
        {'original_spec_nvr': 'some_nvr'},
    ]


def test_subject_ignore_missing_policy(app):
    subject = create_subject('bodhi_update', 'some_item')
    assert subject.ignore_missing_policy


def test_subject_to_str(app):
    subject = create_subject('koji_build', 'some_nvr')
    assert str(subject) == "subject_type 'koji_build', subject_identifier 'some_nvr'"


def test_subject_to_repr(app):
    subject = create_subject('koji_build', 'some_nvr')
    assert repr(subject) == "Subject(<SubjectType 'koji_build'>, 'some_nvr')"
