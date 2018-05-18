#!/usr/bin/python

# SPDX-License-Identifier: GPL-2.0+

import logging

from greenwave.app_factory import create_app
from greenwave.logger import init_logging, log_to_stdout

if __name__ == '__main__':
    app = create_app('greenwave.config.DevelopmentConfig')
    init_logging()
    log_to_stdout(level=logging.DEBUG)
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG'],
    )
