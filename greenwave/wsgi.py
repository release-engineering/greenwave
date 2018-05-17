# SPDX-License-Identifier: GPL-2.0+

import logging
from greenwave.logger import init_logging, log_to_stdout
from greenwave.app_factory import create_app

app = create_app()
init_logging()
log_to_stdout(level=logging.DEBUG if app.debug else logging.INFO)
