# SPDX-License-Identifier: GPL-2.0+

import json

from flask import current_app


def cache_key_generator(fn, arg):
    """ Given a function and arguments, return a "cache key" for the value.

    The returned cache key should uniquely identify the function and arguments
    passed to it.
    """
    return "|".join([
        fn.__module__,
        fn.__name__,
        json.dumps(arg)
    ]).encode('utf-8')


def cached(fn):
    """ Cache the given function.

    This is a decorator.

    The return value of the given function is cached in the ``cache`` object
    associated with the flask ``current_app``.
    """

    def wrapper(arg):
        key = cache_key_generator(fn, arg)
        creator = lambda: fn(arg)
        return current_app.cache.get_or_create(key, creator)
    wrapper.__module__ = fn.__module__
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper
