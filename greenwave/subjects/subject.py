# SPDX-License-Identifier: GPL-2.0+

import re


def _to_dict(format_dict, item):
    result = {}

    item_key = format_dict.get('item_key')
    if item_key:
        result[item_key] = item

    keys = format_dict.get('keys', {})
    for key, value in keys.items():
        result[key] = value

    return result


class Subject:
    """
    Decision subject.

    Main properties are type and item/identifier.

    Item or identifier should uniquely identify the artefact (test subject).
    """

    def __init__(self, type_, item):
        self.item = item
        self._type = type_

    @property
    def type(self):
        """Subject type string."""
        return self._type.id

    @property
    def identifier(self):
        """Alias for item property."""
        return self.item

    @property
    def package_name(self):
        """Package name of the subject or None."""
        if self._type.is_nvr:
            return self.item.rsplit("-", 2)[0]

        return None

    @property
    def short_product_version(self):
        """Get short product version of the subject (guess from identifier) or None."""
        if self._type.is_nvr:
            try:
                _, _, release = self.identifier.rsplit("-", 2)
                _, short_prod_version = release.rsplit(".", 1)
                return short_prod_version
            except (KeyError, ValueError):
                pass

        return None

    @property
    def product_version(self):
        for pv_match in self._type.product_version_match:
            pv = re.sub(pv_match['match'], pv_match['product_version'], self.item)
            if pv and pv != self.item:
                return pv.lower()

        return self._type.product_version

    @property
    def is_koji_build(self):
        return self._type.is_koji_build

    @property
    def supports_remote_rule(self):
        return self._type.supports_remote_rule

    @property
    def ignore_missing_policy(self):
        return self._type.ignore_missing_policy

    def to_dict(self):
        if self._type.item_dict:
            return _to_dict(self._type.item_dict, self.item)

        return {"type": self.type, "item": self.item}

    def result_queries(self):
        """
        Yields parameters for RestulsDB queries.

        For example, one set of parameters could have "type=koji_build" for one
        query and "type=brew-build" for another.
        """
        if self._type.result_queries:
            for query_dict in self._type.result_queries:
                yield _to_dict(query_dict, self.item)
        else:
            yield self.to_dict()

    def __str__(self):
        return "subject_type {!r}, subject_identifier {!r}".format(
            self.type, self.item
        )

    def __repr__(self):
        return "Subject({!r}, {!r})".format(
            self._type, self.item
        )
