from pytest import fixture

from greenwave.config import TestingConfig
from greenwave.subjects.subject_type import (
    create_subject_type,
    load_subject_types,
)


@fixture(scope="session")
def subject_types():
    yield load_subject_types(TestingConfig.SUBJECT_TYPES_DIR)


def test_subject_type_create(subject_types):
    subject_type = create_subject_type("koji_build", subject_types)
    assert subject_type.id == "koji_build"
    assert subject_type.aliases == ["brew-build"]
    assert subject_type.is_koji_build
    assert subject_type.is_nvr
    assert subject_type.item_key == "original_spec_nvr"


def test_subject_type_matches_type_id(subject_types):
    subject_type = create_subject_type("koji_build", subject_types)
    assert subject_type.id == "koji_build"
    assert subject_type.matches("koji_build")


def test_subject_type_matches_alias(subject_types):
    subject_type = create_subject_type("koji_build", subject_types)
    assert subject_type.aliases == ["brew-build"]
    assert subject_type.matches("brew-build")


def test_subject_type_safe_yaml_label(subject_types):
    subject_type = create_subject_type("koji_build", subject_types)
    assert subject_type.safe_yaml_label == "SubjectType 'koji_build'"
