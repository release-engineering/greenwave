import uuid

from dogpile.cache import make_region

from greenwave.utils import mangle_key


def test_cache():
    cache = make_region(key_mangler=mangle_key)
    cache.configure(
        backend='dogpile.cache.pymemcache',
        expiration_time=5,
        arguments={
            'url': 'localhost:11211',
            'distributed_lock': True,
        },
    )
    key = uuid.uuid1().hex
    assert cache.get(key) is not True
    cache.set(key, True)
    assert cache.get(key) is True
