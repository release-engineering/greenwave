# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+

import socket

hostname = socket.gethostname()

config = dict(
    active=True,
    # Set this to dev if you're hacking on fedmsg or an app.
    # Set to stg or prod if running in the Fedora Infrastructure
    environment="dev",

    # Default is 0
    high_water_mark=0,
    io_threads=1,

    # For the fedmsg-hub and fedmsg-relay. ##

    # This is a status dir to keep a record of the last processed message
    #status_directory=os.getcwd() + "/status",
    #status_directory='/var/run/fedmsg/status',

    # This is the URL of a datagrepper instance that we can query for backlog.
    #datagrepper_url="https://apps.fedoraproject.org/datagrepper/raw",

    # We almost always want the fedmsg-hub to be sending messages with zmq as
    # opposed to amqp or stomp.  You can send with only *one* of the messaging
    # backends: zeromq or amqp or stomp.  You cannot send with two or more at
    # the same time.  Here, zmq is either enabled, or it is not.  If it is not,
    # see the options below for how to configure stomp or amqp.
    zmq_enabled=True,

    # On the other hand, if you wanted to use STOMP *instead* of zeromq, you
    # could do the following...
    #zmq_enabled=False,
    #stomp_uri='localhost:59597,localhost:59598',
    #stomp_user='username',
    #stomp_pass='password',
    #stomp_ssl_crt='/path/to/an/optional.crt',
    #stomp_ssl_key='/path/to/an/optional.key',

    # When subscribing to messages, we want to allow splats ('*') so we tell
    # the hub to not be strict when comparing messages topics to subscription
    # topics.
    zmq_strict=False,

    # Number of seconds to sleep after initializing waiting for sockets to sync
    post_init_sleep=0.5,

    # Wait a whole second to kill all the last io threads for messages to
    # exit our outgoing queue (if we have any).  This is in milliseconds.
    zmq_linger=1000,

    # See the following
    #   - http://tldp.org/HOWTO/TCP-Keepalive-HOWTO/overview.html
    #   - http://api.zeromq.org/3-2:zmq-setsockopt
    zmq_tcp_keepalive=1,
    zmq_tcp_keepalive_cnt=3,
    zmq_tcp_keepalive_idle=60,
    zmq_tcp_keepalive_intvl=5,

    # Number of miliseconds that zeromq will wait to reconnect until it gets
    # a connection if an endpoint is unavailable.
    zmq_reconnect_ivl=100,
    # Max delay that you can reconfigure to reduce reconnect storm spam. This
    # is in miliseconds.
    zmq_reconnect_ivl_max=1000,

    # This is a dict of possible addresses from which fedmsg can send
    # messages.  fedmsg.init(...) requires that a 'name' argument be passed
    # to it which corresponds with one of the keys in this dict.
    endpoints={
        "greenwave.%s" % hostname: [
            "tcp://127.0.0.1:5011",
        ],
        "relay_outbound": [
            "tcp://127.0.0.1:4001",
        ],
    },
    # This is the address of an active->passive relay.  It is used for the
    # fedmsg-logger command which requires another service with a stable
    # listening address for it to send messages to.
    # It is also used by the git-hook, for the same reason.
    # It is also used by the mediawiki php plugin which, due to the oddities of
    # php, can't maintain a single passive-bind endpoint of it's own.
    relay_inbound=[
        "tcp://127.0.0.1:2003",
    ],
    sign_messages=False,
    validate_signatures=False,

    # Use these implementations to sign and validate messages
    crypto_backend='x509',
    crypto_validate_backends=['x509'],

    ssldir="/etc/pki/fedmsg",
    crl_location="https://fedoraproject.org/fedmsg/crl.pem",
    crl_cache="/var/run/fedmsg/crl.pem",
    crl_cache_expiry=10,

    ca_cert_location="https://fedoraproject.org/fedmsg/ca.crt",
    ca_cert_cache="/var/run/fedmsg/ca.crt",
    ca_cert_cache_expiry=0,  # Never expires

    certnames={
        # In prod/stg, map hostname to the name of the cert in ssldir.
        # Unfortunately, we can't use socket.getfqdn()
        #"app01.stg": "app01.stg.phx2.fedoraproject.org",
    },

    # A mapping of fully qualified topics to a list of cert names for which
    # a valid signature is to be considered authorized.  Messages on topics not
    # listed here are considered automatically authorized.
    routing_policy={
        # Only allow announcements from production if they're signed by a
        # certain certificate.
        "org.fedoraproject.prod.announce.announcement": [
            "announce-lockbox.phx2.fedoraproject.org",
        ],
    },

    # Set this to True if you want messages to be dropped that aren't
    # explicitly whitelisted in the routing_policy.
    # When this is False, only messages that have a topic in the routing_policy
    # but whose cert names aren't in the associated list are dropped; messages
    # whose topics do not appear in the routing_policy are not dropped.
    routing_nitpicky=False,

    # Greenwave API url
    greenwave_api_url='https://greenwave.domain.local/api/v1.0',

    # In production, these details should match the details of the frontend's
    # CACHE configuration, so that the backend and frontend can manipulate the
    # same shared store.
    greenwave_cache={'backend': 'dogpile.cache.null'},
)
