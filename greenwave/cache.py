# SPDX-License-Identifier: GPL-2.0+

import dogpile.cache

# Our globally available cache region.  Gets initialized in app_factory.
cache = dogpile.cache.make_region()

# Provide a convenient alias for the key generator we want to use
key_generator = dogpile.cache.util.function_key_generator
