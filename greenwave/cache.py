# SPDX-License-Identifier: GPL-2.0+

import functools
import dogpile.cache
import flask

# Provide a convenient alias for the key generator we want to use
key_generator = dogpile.cache.util.function_key_generator


def cached(fn):
    """ Cache arguments with a region hung on the flask app. """
    @functools.wraps(fn)
    def wrapper(*args):
        decoration = flask.current_app.cache.cache_on_arguments
        decorator = decoration(function_key_generator=key_generator)
        return decorator(fn)(*args)
    return wrapper
