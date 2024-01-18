# SPDX-License-Identifier: GPL-2.0+
from greenwave.listeners.base import BaseListener
from greenwave.product_versions import subject_product_versions
from greenwave.subjects.factory import (
    create_subject_from_data,
    UnknownSubjectDataError,
)


def _unpack_value(value):
    """
    If value is list with single element, returns the element, otherwise
    returns the value.
    """
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value


def _get_brew_task_id(msg):
    data = msg.get("data")
    if not data:
        return None

    task_id = _unpack_value(data.get("brew_task_id"))
    try:
        return int(task_id)
    except (ValueError, TypeError):
        return None


class ResultsDBListener(BaseListener):
    monitor_labels = {"handler": "resultsdb"}

    def __init__(self, config_obj=None):
        super().__init__(uid_suffix="resultsdb", config_obj=config_obj)
        self.topic = self.app.config["LISTENER_RESULTSDB_QUEUE"]
        self.koji_base_url = self.app.config["KOJI_BASE_URL"]

    @staticmethod
    def announcement_subject(msg):
        """
        Returns pairs of (subject type, subject identifier) for announcement
        consideration from the message.
        """

        try:
            data = msg["data"]  # New format
        except KeyError:
            data = msg["task"]  # Old format

        unpacked = {k: _unpack_value(v) for k, v in data.items()}

        try:
            subject = create_subject_from_data(unpacked)
        except UnknownSubjectDataError:
            return None

        # note: it is *intentional* that we do not handle old format
        # compose-type messages, because it is impossible to reliably
        # produce a decision from these. compose decisions can only be
        # reliably made from new format messages, where we can rely on
        # productmd.compose.id being available. See:
        # https://pagure.io/greenwave/issue/122
        # https://pagure.io/taskotron/resultsdb/issue/92
        # https://pagure.io/taskotron/resultsdb/pull-request/101
        # https://pagure.io/greenwave/pull-request/262#comment-70350
        if subject.type == "compose" and "productmd.compose.id" not in data:
            return None

        return subject

    def _consume_message(self, msg):
        super()._consume_message(message=msg)
        try:
            testcase = msg["testcase"]["name"]
        except KeyError:
            testcase = msg["task"]["name"]

        try:
            submit_time = msg["submit_time"]
        except KeyError:
            submit_time = msg["result"]["submit_time"]

        outcome = msg.get("outcome")
        if outcome in self.app.config["OUTCOMES_INCOMPLETE"]:
            self.app.logger.debug("Assuming no decision change on outcome %r", outcome)
            return False

        brew_task_id = _get_brew_task_id(msg)

        subject = self.announcement_subject(msg)
        if subject is None:
            return False

        self.app.logger.debug("Considering subject: %r", subject)

        product_versions = subject_product_versions(
            subject,
            self.koji_base_url,
            brew_task_id,
        )

        self.app.logger.debug("Guessed product versions: %r", product_versions)

        if not product_versions:
            product_versions = [None]

        for product_version in product_versions:
            self._publish_decision_change(
                submit_time=submit_time,
                subject=subject,
                testcase=testcase,
                product_version=product_version,
                publish_testcase=False,
            )

        return True
