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

    :jsonparam string product_version: The product version string used for querying WaiverDB.
    :jsonparam string decision_context: The decision context string.
    :jsonparam array subject: A list of items about which the caller is requesting a decision
        used for querying ResultsDB. For example, a list of build NVRs.
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
    subjects = [item.strip() for item in request.get_json()['subject'] if item]
    answers = []
    timeout = current_app.config['REQUESTS_TIMEOUT']
    for item in subjects:
        # XXX make this more efficient than just fetching everything
        response = requests_session.get(
            current_app.config['RESULTSDB_API_URL'] + '/results',
            params={'item': item, 'limit': '1000'}, timeout=timeout)
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
