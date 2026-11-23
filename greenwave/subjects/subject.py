# SPDX-License-Identifier: GPL-2.0+

import re

from greenwave.subjects.subject_type import GenericSubjectType, SubjectType


def _to_dict(format_dict, item):
    result = {}

    item_key = format_dict.get("item_key")
    if item_key:
        result[item_key] = item

    keys = format_dict.get("keys", {})
    for key, value in keys.items():
        result[key] = value

    return result


class Subject:
    """
    Decision subject.

    Main properties are type and item/identifier.

    Item or identifier should uniquely identify the artefact (test subject).
    """

    subject_type: GenericSubjectType | SubjectType
    item: str

    def __init__(self, type_: GenericSubjectType | SubjectType, item: str):
        self.subject_type = type_
        self.item = item

    def product_versions_from_koji_build_target(self, target):
        return sorted(
            self._matching_product_versions(
                target, self.subject_type.product_version_from_koji_build_target
            )
        )

    @property
    def type(self):
        """Subject type string."""
        return self.subject_type.id

    @property
    def identifier(self):
        """Alias for item property."""
        return self.item

    @property
    def package_name(self):
        """Package name of the subject or None."""
        if self.subject_type.is_nvr:
            return self.item.rsplit("-", 2)[0]

        return None

    @property
    def short_product_version(self):
        """Get short product version of the subject (guess from identifier) or None."""
        if self.subject_type.is_nvr:
            try:
                _, _, release = self.identifier.rsplit("-", 2)
            except ValueError:
                return None

            # Koji draft builds use "<release>,draft_<build_id>".
            release = release.partition(",")[0]

            # The product version is the last release component, but trailing
            # numeric build revisions can follow it, for example
            # "6.el10_1.2".
            parts = release.split(".")
            while len(parts) > 1 and parts[-1].isdigit():
                parts.pop()
            return parts[-1]

        return None

    @property
    def product_versions(self):
        pvs = sorted(
            {
                pv.lower()
                for pv in self._matching_product_versions(
                    self.item, self.subject_type.product_version_match
                )
            }
        )
        if pvs:
            return pvs

        if self.subject_type.product_version:
            return [self.subject_type.product_version]

        return []

    @property
    def is_koji_build(self):
        return self.subject_type.is_koji_build

    @property
    def ignore_missing_policy(self):
        return self.subject_type.ignore_missing_policy

    def to_dict(self):
        if self.subject_type.item_dict:
            return _to_dict(self.subject_type.item_dict, self.item)

        return {"type": self.type, "item": self.item}

    def result_queries(self):
        """
        Yields parameters for RestulsDB queries.

        For example, one set of parameters could have "type=koji_build" for one
        query and "type=brew-build" for another.
        """
        if self.subject_type.result_queries:
            for query_dict in self.subject_type.result_queries:
                yield _to_dict(query_dict, self.item)
        else:
            yield self.to_dict()

    def _matching_product_versions(self, text, match_dict):
        return {
            re.sub(pv_match["match"], pv_match["product_version"], text)
            for pv_match in match_dict
            if re.match(pv_match["match"], text)
        }

    def __str__(self):
        return f"subject_type {self.type!r}, subject_identifier {self.item!r}"

    def __repr__(self):
        return f"Subject({self.subject_type!r}, {self.item!r})"
