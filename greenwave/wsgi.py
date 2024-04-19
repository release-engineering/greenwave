# SPDX-License-Identifier: GPL-2.0+

import logging

from greenwave.app_factory import create_app
from greenwave.logger import init_logging, log_to_stdout

init_logging()
log_to_stdout(logging.DEBUG)
app = create_app()
