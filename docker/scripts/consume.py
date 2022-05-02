#!/usr/bin/env python3

import json
import os
import itertools

from pprint import pprint

from rhmsg.activemq.consumer import AMQConsumer

ADDRESS = "Consumer.mister.queue.VirtualTopic.eng.>"
SUBSCRIPTION_NAME = "Greenwave"
URLS = ["amqp://localhost:5671"]

counter = itertools.count(1)


class InsecureAMQConsumer(AMQConsumer):
    ssl_domain = None

    def __init__(self, urls):
        self.urls = urls


def message_handler(message, data):
    num = next(counter)

    body = message.body
    if isinstance(body, str):
        body = body.encode("utf-8", "backslashreplace")
    if data["dump"]:
        print("------------- ({0}) {1} --------------".format(num, message.id))
        print("address:", message.address)
        print("subject:", message.subject)
        print("properties:", message.properties)
        print("durable:", message.durable)
        print("content_type:", message.content_type)
        print("content_encoding:", message.content_encoding)
        print("delivery_count:", message.delivery_count)
        print("reply_to:", message.reply_to)
        print("priority:", message.priority)
        if data["pp"]:
            print("body:")
            pprint(json.loads(body))
        else:
            print("body:", body)
    else:
        if data["pp"]:
            print("Got [%02d]:" % num)
            pprint(json.loads(body))
        else:
            print("Got [%02d]:" % num, body)

    return data["one_message_only"], not data["manual_ack"]


def main():
    os.environ['PN_TRACE_FRM'] = '1'
    consumer = InsecureAMQConsumer(urls=URLS)
    consumer.consume(
        ADDRESS,
        selector=None,
        callback=message_handler,
        auto_accept=False,
        subscription_name=SUBSCRIPTION_NAME,
        data={
            "dump": False,
            "pp": False,
            "one_message_only": False,
            "manual_ack": False,
        },
    )


if __name__ == '__main__':
    main()
