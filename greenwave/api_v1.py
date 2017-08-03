# SPDX-License-Identifier: GPL-2.0+

import requests
from flask import Blueprint, request, current_app, jsonify
from werkzeug.exceptions import BadRequest, NotFound, UnsupportedMediaType
from greenwave.policies import summarize_answers

api = (Blueprint('api_v1', __name__))

requests_session = requests.Session()


@api.route('/decision', methods=['POST'])
def make_decision():
    """
    Make a decision after evaluating all applicable policies based on test
    results. The request must be
    :mimetype:`application/json`.

    **Sample request**:

    .. sourcecode:: http

       POST /api/v1.0/decision HTTP/1.1
       Host: localhost:5005
       Accept-Encoding: gzip, deflate
       Accept: application/json
       Connection: keep-alive
       User-Agent: HTTPie/0.9.4
       Content-Type: application/json
       Content-Length: 91

       {
           "decision_context": "bodhi_update_push_stable",
           "product_version": "fedora-26",
           "subject": [{"item": "glibc-1.0-1.f26", "type": "koji_build"}]
       }


    **Sample response**:

    .. sourcecode:: http

       HTTP/1.0 200
       Content-Length: 228
       Content-Type: application/json
       Date: Thu, 16 Mar 2017 17:42:04 GMT
       Server: Werkzeug/0.12.1 Python/2.7.13

       {
           "policies_satisified": false,
           "summary": "2 of 15 required tests failed",
           "applicable_policies": ["1"],
           "unsatisfied_requirements": [
               {
                   'item': {"item": "glibc-1.0-1.f26", "type": "koji_build"},
                   'result_id': "123",
                   'testcase': 'dist.depcheck',
                   'type': 'test-result-failed'
               },
               {
                   'item': {"item": "glibc-1.0-1.f26", "type": "koji_build"},
                   'result_id': "124",
                   'testcase': 'dist.rpmlint',
                   'type': 'test-result-missing'
               }
           ]
       }

    :jsonparam string product_version: The product version string used for querying WaiverDB.
    :jsonparam string decision_context: The decision context string, identified by a
        free-form string label. It is to be named through coordination between policy
        author and calling application, for example ``bodhi_update_push_stable``.
    :jsonparam list subject: A list of items about which the caller is requesting a decision
        used for querying ResultsDB. Each item contains one or more key-value pairs of 'data' key
        in ResultsDB API. For example, [{"type": "koji_build", "item": "xscreensaver-5.37-3.fc27"}].
    :statuscode 200: A decision was made.
    :statuscode 400: Invalid data was given.
    """
    if request.get_json():
        if ('product_version' not in request.get_json() or
                not request.get_json()['product_version']):
            raise BadRequest('Missing required product version')
        if ('decision_context' not in request.get_json() or
                not request.get_json()['decision_context']):
            raise BadRequest('Missing required decision context')
        if ('subject' not in request.get_json() or
                not request.get_json()['subject']):
            raise BadRequest('Missing required subject')
    else:
        raise UnsupportedMediaType('No JSON payload in request')
    if not isinstance(request.get_json()['subject'], list):
        raise BadRequest('Invalid subject, must be a list of items')
    product_version = request.get_json()['product_version']
    decision_context = request.get_json()['decision_context']
    applicable_policies = [policy for policy in current_app.config['policies']
                           if policy.applies_to(decision_context, product_version)]
    if not applicable_policies:
        raise NotFound('Cannot find any applicable policies for %s' % product_version)
    subjects = [item for item in request.get_json()['subject'] if isinstance(item, dict)]
    if not subjects:
        raise BadRequest('Invalid subject, must be a list of dicts')
    answers = []
    timeout = current_app.config['REQUESTS_TIMEOUT']
    for item in subjects:
        # XXX make this more efficient than just fetching everything
        params = item.copy()
        params.update({'limit': '1000'})
        response = requests_session.get(
            current_app.config['RESULTSDB_API_URL'] + '/results',
            params=params, timeout=timeout)
        response.raise_for_status()
        results = response.json()['data']
        if results:
            response = requests_session.get(
                current_app.config['WAIVERDB_API_URL'] + '/waivers/',
                params={'product_version': product_version,
                        'result_id': ','.join(str(result['id']) for result in results)},
                timeout=timeout)
            response.raise_for_status()
            waivers = response.json()['data']
        else:
            waivers = []
        for policy in applicable_policies:
            answers.extend(policy.check(item, results, waivers))
    res = {
        'policies_satisified': all(answer.is_satisfied for answer in answers),
        'summary': summarize_answers(answers),
        'applicable_policies': [policy.id for policy in applicable_policies],
        'unsatisfied_requirements': [answer.to_json() for answer in answers
                                     if not answer.is_satisfied],
    }
    return jsonify(res), 200
