#!/usr/bin/env python3

import json
import os
import sys

import proton
from rhmsg.activemq.producer import AMQProducer

TOPIC = "VirtualTopic.eng.resultsdb.result.new"
URLS = ["amqp://localhost:5671"]
SUBJECT = f"test_message_{sys.argv[1]}"
MESSAGE = {
    "submit_time": "2019-08-27T13:57:53.490376",
    "testcase": {"name": "example_test"},
    "data": {"type": ["brew-build"], "item": ["example-container"]},
}
MESSAGE = {
    "data": {
        "category": ["validation"],
        "ci_email": ["exd-guild-gating@redhat.com"],
        "ci_irc": ["not available"],
        "ci_name": ["example-jenkins"],
        "ci_team": ["PnT DevOps"],
        "ci_url": ["https://jenkins.example.com"],
        "component": ["nethack-prod"],
        "item": ["nethack-prod-3.5.202110051331.w9756"],
        "log": ["https://jenkins.example.com/job/x/build/y/console"],
        "publisher_id": ["msg-greenwave-segment-test"],
        "type": ["koji_build"],
        "version": ["3.5.202110051331.w9756"],
    },
    "groups": ["52c6b84b-b617-4b79-af47-8975d11bb635"],
    "href": "http://resultsdb/api/v2.0/results/123",
    "id": "123",
    "note": "",
    "outcome": "PASSED",
    "ref_url": "https://jenkins.example.com/job/x/build/y",
    "submit_time": "2021-10-05T13:35:29.721850",
    "testcase": {
        "href": "http://resultsdb/api/v2.0/testcases/dist.abicheck",
        "name": "dist.abicheck",
        "ref_url": "https://jenkins.example.com/job/x/build/y",
    },
}


def main():
    os.environ["PN_TRACE_FRM"] = "1"

    with AMQProducer(urls=URLS) as producer:
        # Disable SSL
        del producer.conf["cert"]

        producer.through_topic(TOPIC)
        body = json.dumps(MESSAGE)
        message = proton.Message(subject=SUBJECT, body=body)
        producer.send(message)


if __name__ == "__main__":
    main()
