# SPDX-License-Identifier: GPL-2.0+

import logging
import sys


def log_to_stdout(level=logging.INFO):
    fmt = '%(asctime)s [pid %(process)5d] %(name)s %(levelname)s %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    logging.getLogger().addHandler(stream_handler)


def init_logging(app):
    log_level = logging.DEBUG if app.debug else logging.INFO
    log_to_stdout(level=log_level)
    # In general we want to see everything from our own code,
    # but not detailed debug messages from third-party libraries.
    # Note that the log level on the handler above controls what
    # will actually appear on stdout.
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger('greenwave').setLevel(logging.DEBUG)
