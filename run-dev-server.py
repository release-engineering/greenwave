#!/usr/bin/python

# SPDX-License-Identifier: GPL-2.0+

from greenwave.app_factory import create_app

if __name__ == '__main__':
    app = create_app('greenwave.config.DevelopmentConfig')
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG'],
    )
