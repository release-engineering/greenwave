
import re
import json
import hashlib
from urlparse import parse_qs


updates = {}  #: {id -> update info}


def application(environ, start_response):
    path_info = environ['PATH_INFO']

    m = re.match(r'/updates/(.+)$', path_info)
    if m:
        updateid = m.group(1)
        if environ['REQUEST_METHOD'] == 'GET':
            if updateid in updates:
                start_response('200 OK', [('Content-Type', 'application/json')])
                return [json.dumps({'update': updates[updateid]})]
            else:
                start_response('404 Not Found', [])
                return []
        else:
            start_response('405 Method Not Allowed', [])
            return []

    m = re.match(r'/updates/$', path_info)
    if m:
        if environ['REQUEST_METHOD'] == 'GET':
            params = parse_qs(environ['QUERY_STRING'])
            if 'builds' in params:
                response_updates = [u for u in updates.values()
                                    if set(params['builds']).issubset(build['nvr']
                                                                      for build in u['builds'])]
            else:
                response_updates = updates.values()
            response_data = {
                'page': 1,
                'pages': 1,
                'rows_per_page': len(updates.values()),
                'total': len(updates.values()),
                'updates': response_updates,
            }
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [json.dumps(response_data)]
        if environ['REQUEST_METHOD'] == 'POST':
            body = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))
            updateid = 'FEDORA-2000-{}'.format(hashlib.sha1(body).hexdigest()[-8:])
            assert updateid not in updates
            update = json.loads(body)
            update['updateid'] = updateid
            updates[updateid] = update
            print('Fake Bodhi created new update %r' % update)
            start_response('201 Created', [('Content-Type', 'application/json')])
            return [json.dumps(update)]  # XXX check what Bodhi really returns
        else:
            start_response('405 Method Not Allowed', [])
            return []

    start_response('404 Not Found', [])
    return []
