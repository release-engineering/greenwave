# SPDX-License-Identifier: GPL-2.0+
from greenwave.listeners.base import BaseListener
from greenwave.subjects.factory import create_subject


class WaiverDBListener(BaseListener):
    monitor_labels = {"handler": "waiverdb"}

    def __init__(self, config_obj=None):
        super().__init__(uid_suffix="waiverdb", config_obj=config_obj)
        self.topic = self.app.config["LISTENER_WAIVERDB_QUEUE"]
        self.koji_base_url = self.app.config["KOJI_BASE_URL"]

    def _consume_message(self, msg):
        super()._consume_message(message=msg)
        product_version = msg["product_version"]
        testcase = msg["testcase"]
        subject = create_subject(msg["subject_type"], msg["subject_identifier"])
        submit_time = msg["timestamp"]

        self._publish_decision_change(
            submit_time=submit_time,
            subject=subject,
            testcase=testcase,
            product_version=product_version,
            publish_testcase=True,
        )
        return True
