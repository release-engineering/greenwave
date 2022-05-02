import os

config = {
    # fedmsg boilerplate
    'endpoints': {},
    'sign_messages': False,
    'validate_signatures': False,

    # STOMP settings
    'zmq_enabled': False,
    'stomp_uri': 'umb:61612',
    'stomp_heartbeat': 900000,
    'stomp_ack_mode': 'client-individual',

    # Hacks to make us publish to
    # /topic/VirtualTopic.eng.greenwave.decision.update
    'topic_prefix': '/topic/VirtualTopic',
    'environment': 'eng',
    'resultsdb_topic_suffix': 'resultsdb.result.new',
    'waiverdb_topic_suffix': 'waiverdb.waiver.new',

    # Workaround for moksha memory leak and mitigate message loss.
    # Memory leak is fixed in python-moksha-hub-1.5.7 (https://github.com/mokshaproject/moksha/pull/57).
    'moksha.blocking_mode': True,

    # moksha-monitor-exporter's point of contact
    'moksha.monitoring.socket': 'tcp://0.0.0.0:10030',
}

# Enable one consumer or the other in different deployments.
if os.environ.get("RESULTSDB_HANDLER") and os.environ.get("WAIVERDB_HANDLER"):
    raise ValueError("Both RESULTSDB_HANDLER and WAIVERDB_HANDLER may not"
                     "be specified.  Only one.")

if os.environ.get("RESULTSDB_HANDLER"):
    config.update({
        'resultsdb_handler': True,
        'waiverdb_handler': False,
        'stomp_queue': '/queue/Consumer.client-greenwave.resultsdb.VirtualTopic.eng.resultsdb.result.new',
    })
elif os.environ.get("WAIVERDB_HANDLER"):
    config.update({
        'resultsdb_handler': False,
        'waiverdb_handler': True,
        'stomp_queue': '/queue/Consumer.client-greenwave.waiverdb.VirtualTopic.eng.waiverdb.waiver.new',
    })


