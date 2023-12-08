#!/usr/bin/env python3

import stomp
import time
from argparse import ArgumentParser

HEADERS = {"CI_NAME": "job-name", "CI_TYPE": "custom"}


def build_arg_parser(description):
    """
    Constructs an argument parser
    """
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--topic",
        "-t",
        required=True,
        help="Single topic name to publish message to. "
             "Example VirtualTopic.eng.ci.mkovarik-namespace.container-image.test.running"
    )
    parser.add_argument(
        "-p",
        "--path-to-message",
        required=True,
        help="Path to JSON file containing the message contents.",
    )
    parser.add_argument(
        "--headers",
        default="",
        help="Comma-separated list of key=value pairs to set as message headers",
    )
    parser.add_argument(
        "--port",
        default=61612,
        help="UMB port",
    )
    parser.add_argument(
        "--host",
        default="umb.api.redhat.com",
        help="UMB server",
    )
    parser.add_argument(
        "--ssl-key",
        default="jenkins.key",
        help="SSL key for UMB connection",
    )
    parser.add_argument(
        "--ssl-cert",
        default="jenkins.crt",
        help="SSL cert for UMB connection",
    )
    return parser


if __name__ == "__main__":
    parser = build_arg_parser(
        "Send custom UMB message to selected UMB topic. "
        "Sends demo message when arguments are not specified"
    )
    args = parser.parse_args()
    with open(args.path_to_message) as fp:
        msg = fp.read()
    if args.headers:
        headers = dict(h.split("=", 1) for h in args.headers.split(","))
    else:
        headers = HEADERS
    conn = stomp.Connection12([(args.host, args.port)])
    conn.set_listener("", stomp.PrintingListener())
    #conn.set_ssl(
    #    for_hosts=[(args.host, args.port)],
    #    key_file=args.ssl_key,
    #    cert_file=args.ssl_cert,
    #)
    conn.connect(wait=True)
    conn.send(body=msg, destination=f"/topic/{args.topic}", headers=headers)
    # Give some time to listener to catch error message
    time.sleep(2)
    conn.disconnect()
