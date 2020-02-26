# SPDX-License-Identifier: GPL-2.0+
"""
Subject type helper functions.
"""

import glob
import os

from greenwave.safe_yaml import (
    SafeYAMLBool,
    SafeYAMLDict,
    SafeYAMLList,
    SafeYAMLObject,
    SafeYAMLString,
)


class SubjectType(SafeYAMLObject):
    root_yaml_tag = '!SubjectType'

    safe_yaml_attributes = {
        'id': SafeYAMLString(),

        'aliases': SafeYAMLList(item_type=str, optional=True),

        # Key name to load from decision 'subject' list or ResultsDB result
        # data ("item" will be used if the key is empty or not found).
        'item_key': SafeYAMLString(optional=True),

        # A build for subject identifier can be found on Koji/Brew.
        'is_koji_build': SafeYAMLBool(optional=True, default=False),

        # Is identifier in NVR format? If true, package name and short product
        # version can be parsed for identifier.
        'is_nvr': SafeYAMLBool(optional=True),

        # Subject type can be used with RemoteRule only if value is True.
        'supports_remote_rule': SafeYAMLBool(optional=True, default=False),

        # Omit responding with HTTP 404 if there is no applicable policy.
        'ignore_missing_policy': SafeYAMLBool(optional=True, default=False),

        'product_version': SafeYAMLString(optional=True),

        # Serialization dict for decision.
        'item_dict': SafeYAMLDict(optional=True),

        # List of serialization dicts for ResultsDB requests.
        # If not defined, defaults to single request with item_dict value.
        'result_queries': SafeYAMLList(item_type=dict, optional=True),
    }

    def matches(self, id_):
        return id_ == self.id or id_ in self.aliases

    @property
    def safe_yaml_label(self):
        return 'SubjectType {!r}'.format(self.id)

    def __repr__(self):
        return '<SubjectType {!r}>'.format(self.id)


class GenericSubjectType:
    def __init__(self, id_):
        self._set_default_attributes()
        self.id = id_
        self.is_koji_build = True
        self.is_nvr = False

    def _set_default_attributes(self):
        for name, attr in SubjectType.safe_yaml_attributes.items():
            self.__setattr__(name, attr.default_value)

    def __repr__(self):
        return '<GenericSubjectType {!r}>'.format(self.id)


def load_subject_types(subject_types_dir):
    """
    Load Greenwave subject types from the given directory.

    :param str subject_types_dir: A path points to the policies directory.
    :return: A list of subject_types.
    """
    paths = glob.glob(os.path.join(subject_types_dir, '*.yaml'))
    subject_types = []
    for path in paths:
        with open(path, 'r') as f:
            subject_types.extend(SubjectType.safe_load_all(f))

    return subject_types


def create_subject_type(id_, subject_types):
    for type_ in subject_types:
        if type_.matches(id_):
            return type_

    return GenericSubjectType(id_)
