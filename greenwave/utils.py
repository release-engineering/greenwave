# SPDX-License-Identifier: GPL-2.0+

from flask import jsonify, current_app
from werkzeug.exceptions import HTTPException


def json_error(error):
    """
    Return error responses in JSON.

    :param error: One of Exceptions. It could be HTTPException, ConnectionError, or
    Timeout.
    :return: JSON error response.

    """
    if isinstance(error, HTTPException):
        response = jsonify(message=error.description)
        response.status_code = error.code
    else:
        # Could be ConnectionError or Timeout
        current_app.logger.exception('Returning 500 to user.')
        response = jsonify(message=str(error.message))
        response.status_code = 500
    return response
