# SPDX-License-Identifier: GPL-2.0+


def _get_latest_results(results, unique_keys):
    """
    Yields only the latest results for unique architecture and variant pairs.

    The input results are sorted from latest to oldest.
    """
    visited_arch_variants = set()
    for result in results:
        result_data = result["data"]

        # Items under test result "data" are lists which are unhashable
        # types in Python. This converts anything that is stored there
        # to a string so we don't have to care about the stored value.
        arch_variant = tuple(
            str(result_data.get(key))
            for key in unique_keys
        )

        if arch_variant not in visited_arch_variants:
            visited_arch_variants.add(arch_variant)
            yield result


def _to_dict(format_dict, type_, item):
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
            return _to_dict(self._type.item_dict, self.type, self.item)

        return {"type": self.type, "item": self.item}

    def result_queries(self):
        """
        Yields parameters for RestulsDB queries.

        For example, one set of parameters could have "type=koji_build" for one
        query and "type=brew-build" for another.
        """
        if self._type.result_queries:
            for query_dict in self._type.result_queries:
                yield _to_dict(query_dict, self.type, self.item)
        else:
            yield self.to_dict()

    def get_latest_results(self, results):
        """
        Filters out results to get only the latest relevant ones.

        The input results are sorted from latest to oldest.
        """
        if self._type.latest_result_unique_keys:
            return list(_get_latest_results(results, self._type.latest_result_unique_keys))
        return results

    def __str__(self):
        return "subject_type {!r}, subject_identifier {!r}".format(
            self.type_, self.item
        )
