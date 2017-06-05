
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import logging
import sys


def init_logging(app):
    log_level = logging.DEBUG if app.debug else logging.INFO
    fmt = '[%(filename)s:%(lineno)d] ' if app.debug else '%(module)-12s '
    fmt += '%(asctime)s %(levelname)-7s %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    app.logger.addHandler(stream_handler)
