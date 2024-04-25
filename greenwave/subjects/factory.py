# SPDX-License-Identifier: GPL-2.0+
"""
Factory functions and helper functions to create subject object.
"""

from flask import current_app

from .subject import Subject
from .subject_type import create_subject_type


class UnknownSubjectDataError(RuntimeError):
    pass


def subject_types():
    return current_app.config["subject_types"]


def create_subject_from_data(data):
    """
    Returns instance of greenwave.subject.Subject created from data dict.

    :raises: UnknownSubjectDataError: if subject instance cannot be created
            from data (in case data are invalid or subject configuration is
            missing)
    """
    type_id = data.get("type")

    for type_ in subject_types():
        if type_id and type_.id != type_id:
            continue

        if not type_.item_key:
            continue

        item = data.get(type_.item_key)
        if not item:
            continue

        return Subject(type_, item)

    item = data.get("item")
    if type_id and item:
        return create_subject(type_id, item)

    raise UnknownSubjectDataError()


def create_subject(type_id, item):
    type_ = create_subject_type(type_id, subject_types())
    return Subject(type_, item)
