# SPDX-License-Identifier: GPL-2.0+

import requests
from flask import Blueprint, request, current_app, jsonify
from werkzeug.exceptions import BadRequest, NotFound, UnsupportedMediaType
from greenwave.policies import policies, summarize_answers

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
    applicable_policies = [policy for policy in policies
                           if policy.product_version == product_version and
                           policy.decision_context == decision_context]
    if not applicable_policies:
        raise NotFound('Cannot find any applicable policies for %s' % product_version)
    subjects = [item.strip() for item in request.get_json()['subject'] if item]
    policies_satisified = True
    summary_lines = []
    unsatisfied_requirements = []
    timeout = current_app.config['REQUESTS_TIMEOUT']
    for policy in applicable_policies:
        for item in subjects:
            # XXX make this more efficient than just fetching everything
            response = requests_session.get(
                current_app.config['RESULTSDB_API_URL'] + '/results',
                params={'item': item}, timeout=timeout)
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

            answers = policy.check(item, results, waivers)
            if not all(answer.is_satisfied for answer in answers):
                policies_satisified = False
            summary_lines.append('{}: {}'.format(item, summarize_answers(answers, policy.id)))
            unsatisfied_requirements.extend(answer for answer in answers
                                            if not answer.is_satisfied)

    res = {
        'policies_satisified': policies_satisified,
        'summary': '\n'.join(summary_lines),
        'applicable_policies': [policy.id for policy in applicable_policies],
        'unsatisfied_requirements': [a.to_json() for a in unsatisfied_requirements],
    }
    return jsonify(res), 200
